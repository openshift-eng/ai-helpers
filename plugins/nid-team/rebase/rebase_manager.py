#!/usr/bin/env python3
"""Track a manually operated rebase; never execute its Git or GitHub mutations."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CORE_GATES = {"carry-accounting", "tree-accounting", "review"}
SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
GIT_TIMEOUT_SECONDS = 300


class InvalidState(ValueError):
    """The requested transition lacks matching inputs or evidence."""


def require(condition, message):
    """Reject an invalid input or transition through the CLI's error path."""
    if not condition:
        raise InvalidState(message)


def read_json(path):
    """Read a retained JSON artifact without modifying it."""
    return json.loads(Path(path).read_text())


def digest(value):
    """Hash canonical JSON so formatting changes do not invalidate evidence."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def file_digest(path):
    """Hash retained log bytes without loading a large log into memory."""
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path, value):
    """Replace one artifact atomically after serializing its complete value."""
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


def git(repo, *args):
    """Run a bounded Git query without optional index-refresh writes."""
    result = subprocess.run(["git", "-C", str(repo), *args], check=True,
                            capture_output=True, text=True,
                            timeout=GIT_TIMEOUT_SECONDS,
                            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    return result.stdout.strip()


def commit(repo, ref):
    """Resolve a ref to a full commit ID, treating the ref as an operand."""
    return git(repo, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")


def ancestor(repo, older, newer):
    """Distinguish absent ancestry from a failed or timed-out Git query."""
    result = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor",
                             older, newer], capture_output=True, text=True,
                            timeout=GIT_TIMEOUT_SECONDS,
                            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    require(result.returncode in (0, 1), "Cannot inspect commit ancestry")
    return result.returncode == 0


def nonempty(value):
    """Require textual content rather than a missing or whitespace-only field."""
    return isinstance(value, str) and bool(value.strip())


def downstream_branch(repo, ref):
    """Resolve the selected local or remote-tracking ref to its branch name."""
    full_ref = git(repo, "rev-parse", "--symbolic-full-name", "--verify",
                   "--end-of-options", ref)
    if full_ref.startswith("refs/heads/"):
        return full_ref.removeprefix("refs/heads/")
    require(full_ref.startswith("refs/remotes/"),
            "downstream_ref must identify a local or remote-tracking branch")
    # Match discovered remote names, including names containing a slash.
    for remote in sorted(git(repo, "remote").splitlines(), key=len, reverse=True):
        prefix = f"refs/remotes/{remote}/"
        if full_ref.startswith(prefix):
            return full_ref.removeprefix(prefix)
    raise InvalidState("downstream_ref has no configured remote mapping")


def validate_plan(plan):
    """Check pinned inputs, candidate destination, and complete artifact shape."""
    require(isinstance(plan, dict) and plan.get("schema_version") == 1,
            "Expected plan schema_version 1")
    for key in ("repo", "downstream_ref", "upstream_tag", "branch"):
        require(nonempty(plan.get(key)), f"Missing plan field: {key}")
    repo = Path(plan["repo"])
    require(repo.is_absolute() and str(repo.resolve()) == plan["repo"],
            "repo must be an absolute, resolved checkout path")
    require(Path(git(repo, "rev-parse", "--show-toplevel")).resolve() == repo,
            "repo must be the checkout root")
    for key in ("downstream_sha", "upstream_sha", "previous_upstream_sha"):
        require(isinstance(plan.get(key), str) and SHA.fullmatch(plan[key]),
                f"Expected full commit SHA: {key}")
        require(commit(repo, plan[key]) == plan[key], f"Unknown commit: {key}")
    branch = plan["branch"]
    require(not branch.startswith("refs/"), "Candidate branch must be a short branch name")
    require(git(repo, "check-ref-format", "--branch", branch) == branch,
            "Candidate branch must be a literal branch name, not a checkout alias")
    require(branch not in {"main", "master"},
            "Candidate branch must not be main or master")
    for key in ("carries", "tree_deltas", "validations"):
        require(isinstance(plan.get(key), list), f"Expected list: {key}")
    ids, sources = set(), set()
    for carry in plan["carries"]:
        require(isinstance(carry, dict) and nonempty(carry.get("id")), "Carry needs an id")
        require(carry["id"] not in ids, "Duplicate carry id")
        ids.add(carry["id"])
        source = carry.get("source_sha")
        require(isinstance(source, str) and SHA.fullmatch(source), "Carry needs full source_sha")
        require(source not in sources, "Duplicate source_sha")
        sources.add(source)
        require(commit(repo, source) == source, "Unknown carry commit")
        require(carry.get("action") in {"cherry-pick", "squash", "drop", "undecided"},
                "Unknown carry action")
        require(nonempty(carry.get("rationale")), "Carry needs a rationale")
    for carry in plan["carries"]:
        if carry["action"] == "squash":
            require(carry.get("squash_into") in ids and carry["squash_into"] != carry["id"],
                    "Squash needs another carry id as squash_into")
    for delta in plan["tree_deltas"]:
        require(isinstance(delta, dict) and all(nonempty(delta.get(key)) for key in
                ("path", "status", "disposition", "rationale")), "Incomplete tree delta")
        require(delta["disposition"] in {"retain", "adapt", "upstream", "drop", "regenerate", "undecided"},
                "Unknown tree disposition")
    gates = set(CORE_GATES)
    for check in plan["validations"]:
        require(isinstance(check, dict) and isinstance(check.get("id"), str)
                and NAME.fullmatch(check["id"]), "Invalid validation id")
        require(check["id"] not in gates, "Duplicate or reserved validation id")
        gates.add(check["id"])
        require(nonempty(check.get("command")) and isinstance(check.get("required"), bool),
                "Validation needs command and required boolean")
    return plan


class Manager:
    """Bind a single rebase plan to application, evidence, and review records."""

    def __init__(self, directory):
        """Locate the external run artifacts without reading or creating them."""
        self.directory = Path(directory).resolve()
        self.state_path = self.directory / "state.json"
        self.plan_path = self.directory / "plan.json"
        self.state = None
        self.plan = None

    def load(self):
        """Load state only when the retained plan still matches its accepted digest."""
        self.state = read_json(self.state_path)
        self.plan = validate_plan(read_json(self.plan_path))
        require(digest(self.plan) == self.state.get("plan_sha256"),
                "Plan changed; preserve this run and initialize a new state directory")

    def save(self):
        """Persist the current state after the caller's checks have succeeded."""
        write_json(self.state_path, self.state)

    def init(self, source):
        """Accept a pinned plan once, preserving artifacts on repeat invocation."""
        plan = validate_plan(read_json(source))
        require(not self.directory.is_relative_to(Path(plan["repo"])),
                "State directory must be outside the target checkout")
        if self.state_path.exists():
            self.load()
            require(digest(plan) == self.state["plan_sha256"],
                    "Existing run uses another plan; use a new state directory")
            return
        require(not (self.directory / "result.json").exists(),
                "Application artifacts without state; preserve them and recover explicitly")
        if self.plan_path.exists():
            require(digest(read_json(self.plan_path)) == digest(plan), "Existing plan differs")
        self.plan = plan
        self.check_refs()
        self.state = {"schema_version": 1, "plan_sha256": digest(plan), "phase": "planned",
                      "head_sha": None, "gates": {}, "feedback": {}, "pr": None}
        write_json(self.plan_path, plan)
        self.save()

    def check_refs(self):
        """Require unchanged inputs and a distinct candidate before active work."""
        for ref, sha in ((self.plan["downstream_ref"], self.plan["downstream_sha"]),
                         (self.plan["upstream_tag"], self.plan["upstream_sha"])):
            require(commit(self.plan["repo"], ref) == sha,
                    f"Selected ref moved: {ref}; review a new plan instead of retargeting this run")
        require(self.plan["branch"] != downstream_branch(
            self.plan["repo"], self.plan["downstream_ref"]),
            "Candidate branch must not be the downstream branch")

    def current_head(self):
        """Return HEAD only for the clean planned branch with no Git operation pending."""
        repo = self.plan["repo"]
        git_dir = Path(git(repo, "rev-parse", "--absolute-git-dir"))
        require(not any((git_dir / marker).exists() for marker in
                        ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD",
                         "rebase-apply", "rebase-merge", "sequencer")),
                "Git operation is in progress; finish or recover it before recording results")
        require(not git(repo, "status", "--porcelain"), "Checkout has uncommitted changes")
        require(git(repo, "branch", "--show-current") == self.plan["branch"],
                "Checkout is not on the planned branch")
        return commit(repo, "HEAD")

    def gate_ids(self):
        """List allowed semantic and repository-specific evidence gate IDs."""
        return CORE_GATES | {v["id"] for v in self.plan["validations"]}

    def required_gates(self):
        """List checks whose current PASS evidence is needed for readiness."""
        return CORE_GATES | {v["id"] for v in self.plan["validations"] if v["required"]}

    def gate_problems(self, head):
        """Report absent, failing, stale, or altered required evidence."""
        problems = []
        for name in sorted(self.required_gates()):
            evidence = self.state["gates"].get(name)
            if not evidence:
                problems.append(f"{name}: missing")
                continue
            if (evidence["head_sha"] != head or
                    evidence["plan_sha256"] != self.state["plan_sha256"]):
                problems.append(f"{name}: stale")
                continue
            if evidence["verdict"] != "PASS":
                problems.append(f"{name}: {evidence['verdict']}")
            try:
                if file_digest(evidence["log"]) != evidence["log_sha256"]:
                    problems.append(f"{name}: log changed")
            except OSError:
                problems.append(f"{name}: log unavailable")
        return problems

    def require_validated(self):
        """Require current inputs, application record, and passing retained evidence."""
        self.check_refs()
        head = self.current_head()
        require(head == self.state["head_sha"], "Result is stale; record the revised application")
        require(digest(read_json(self.directory / "result.json")) == self.state["result_sha256"],
                "Application result changed; record the revised application")
        problems = self.gate_problems(head)
        require(not problems, "Validation blocked: " + "; ".join(problems))
        return head

    def apply(self, source):
        """Accept a complete proposed result before replacing the prior record."""
        require(self.state["phase"] not in {"complete", "closed"}, "Run is terminal")
        self.check_refs()
        head = self.current_head()
        result = read_json(source)
        require(isinstance(result, dict) and result.get("plan_sha256") == self.state["plan_sha256"]
                and result.get("head_sha") == head, "Result does not match plan and current HEAD")
        require(ancestor(self.plan["repo"], self.plan["upstream_sha"], head)
                and ancestor(self.plan["repo"], self.plan["downstream_sha"], head),
                "Result must retain both pinned upstream and downstream ancestry")
        require(all(c["action"] != "undecided" for c in self.plan["carries"]),
                "Unresolved carry decision")
        require(all(d["disposition"] != "undecided" for d in self.plan["tree_deltas"]),
                "Unresolved tree delta")
        rows = result.get("carries")
        require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows),
                "Result needs carries")
        by_id = {row.get("id"): row for row in rows}
        require(len(by_id) == len(rows) and set(by_id) == {c["id"] for c in self.plan["carries"]},
                "Result must account for every carry exactly once")
        for carry in self.plan["carries"]:
            row = by_id[carry["id"]]
            outcome = row.get("outcome")
            allowed = {"cherry-pick": {"picked", "upstream", "regenerated"},
                       "squash": {"squashed", "upstream", "regenerated"},
                       "drop": {"dropped", "upstream", "regenerated"}}
            require(outcome in allowed[carry["action"]], "Outcome contradicts carry decision")
            require(nonempty(row.get("rationale")), "Carry result needs a rationale")
            if outcome in {"dropped", "upstream"}:
                require(row.get("result_sha") is None, "Dropped/upstream carry must have null result_sha")
            else:
                self.check_result_commit(row.get("result_sha"), head)
            if outcome == "squashed":
                require(row["result_sha"] == by_id[carry["squash_into"]].get("result_sha"),
                        "Squashed carry must map to its target's result commit")
        repairs = result.get("repairs", [])
        require(isinstance(repairs, list), "Expected repairs list")
        for repair in repairs:
            require(isinstance(repair, dict) and nonempty(repair.get("rationale")),
                    "Repair needs rationale")
            self.check_result_commit(repair.get("result_sha"), head)
        result_sha256 = digest(result)
        if self.state["head_sha"] != head or self.state.get("result_sha256") != result_sha256:
            self.state["gates"] = {}
        self.state.update(phase="applied", head_sha=head, result_sha256=result_sha256)
        write_json(self.directory / "result.json", result)
        self.save()

    def check_result_commit(self, sha, head):
        """Require a new candidate commit, excluding ancestry retained by an ours merge."""
        require(isinstance(sha, str) and SHA.fullmatch(sha), "Expected full result SHA")
        require(ancestor(self.plan["repo"], sha, head), "Result commit is not in candidate history")
        require(not any(ancestor(self.plan["repo"], sha, self.plan[key])
                        for key in ("upstream_sha", "downstream_sha")),
                "Result commit belongs to pre-rebase history, not candidate application")

    def record(self, name, source):
        """Bind gate evidence and its log digest to the accepted candidate head."""
        require(self.state["phase"] not in {"planned", "complete", "closed"},
                "Record application before evidence")
        require(name in self.gate_ids(), "Unknown gate")
        evidence = read_json(source)
        head = self.current_head()
        require(head == self.state["head_sha"], "Result is stale; record the revised application")
        require(isinstance(evidence, dict) and evidence.get("head_sha") == head
                and evidence.get("plan_sha256") == self.state["plan_sha256"],
                "Evidence does not match plan and current HEAD")
        require(evidence.get("verdict") in {"PASS", "FAIL", "SKIP", "INCONCLUSIVE"},
                "Invalid evidence verdict")
        require(nonempty(evidence.get("rationale")), "Evidence needs rationale, including SKIP justification")
        require(nonempty(evidence.get("log")) and Path(evidence["log"]).is_absolute(),
                "Evidence log must be an absolute path")
        logfile = Path(evidence["log"]).resolve()
        require(logfile.is_file() and logfile.stat().st_size > 0, "Evidence log must exist and be nonempty")
        evidence["log"] = str(logfile)
        evidence["log_sha256"] = file_digest(logfile)
        self.state["gates"][name] = evidence
        self.save()

    def validate(self):
        """Advance only when every required gate passes at the current revision."""
        require(self.state["phase"] in {"applied", "validated", "draft", "review"}, "Validate an applied candidate")
        self.require_validated()
        self.state["phase"] = "validated"
        self.save()

    def feedback(self, source):
        """Import comments idempotently and reopen edited feedback with its history."""
        require(self.state["phase"] not in {"planned", "complete", "closed"}, "No active candidate")
        comments = read_json(source)
        require(isinstance(comments, list), "Feedback input must be an array")
        for comment in comments:
            require(isinstance(comment, dict) and all(nonempty(comment.get(k)) for k in
                    ("id", "body", "url", "updated_at")), "Incomplete feedback snapshot")
            body_sha = digest(comment["body"])
            existing = self.state["feedback"].get(comment["id"])
            if existing and existing["body_sha256"] == body_sha:
                continue
            versions = [] if not existing else existing.get("versions", []) + [
                {k: v for k, v in existing.items() if k != "versions"}]
            self.state["feedback"][comment["id"]] = {
                **comment, "body_sha256": body_sha, "received_head": self.state["head_sha"],
                "resolution": None, "versions": versions}
        self.save()

    def resolve_feedback(self, identity, outcome, rationale):
        """Record a reasoned resolution backed by current validation evidence."""
        require(identity in self.state["feedback"], "Unknown feedback id")
        require(nonempty(rationale), "Feedback resolution needs a rationale")
        head = self.require_validated()
        item = self.state["feedback"][identity]
        if outcome == "addressed":
            require(head != item["received_head"], "Acknowledgement is not a code change; use no-change or declined with reasoning")
        item["resolution"] = {"outcome": outcome, "rationale": rationale, "head_sha": head}
        self.save()

    def pending_feedback(self):
        """Find feedback lacking a resolution for the accepted candidate revision."""
        return sorted(key for key, item in self.state["feedback"].items()
                      if not item["resolution"] or
                      item["resolution"]["head_sha"] != self.state["head_sha"])

    def sync_pr(self, source):
        """Reconcile one PR's identity and remote state without inventing readiness."""
        pr = read_json(source)
        require(isinstance(pr, dict) and type(pr.get("number")) is int and pr["number"] > 0,
                "PR needs a positive number")
        require(nonempty(pr.get("target_repository")) and
                re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", pr["target_repository"]),
                "PR needs target_repository owner/name")
        require(pr.get("url") == f"https://github.com/{pr['target_repository']}/pull/{pr['number']}",
                "PR URL does not match identity")
        require(pr.get("head_ref") == self.plan["branch"], "PR branch does not match candidate")
        require(isinstance(pr.get("head_sha"), str) and SHA.fullmatch(pr["head_sha"]),
                "PR needs a full head SHA")
        previous = self.state["pr"]
        if previous:
            base = previous["base_ref"]
        else:
            base = downstream_branch(self.plan["repo"], self.plan["downstream_ref"])
        require(pr.get("base_ref") == base, "PR base does not match planned downstream branch")
        require(pr.get("state") in {"OPEN", "CLOSED", "MERGED"} and isinstance(pr.get("draft"), bool),
                "Invalid PR state")
        if previous:
            require(all(pr[k] == previous[k] for k in ("number", "url", "target_repository")),
                    "This run already tracks a different PR")
        if pr["state"] in {"MERGED", "CLOSED"}:
            require(previous is not None, "Track a PR before marking the run closed or complete")
            self.state["phase"] = "complete" if pr["state"] == "MERGED" else "closed"
        else:
            require(self.state["phase"] in {"applied", "validated", "draft", "review"},
                    "Record application before tracking an open PR")
            require(pr["head_sha"] == self.state["head_sha"], "PR head does not match candidate")
            require(self.current_head() == self.state["head_sha"], "PR candidate is stale")
            if not pr["draft"]:
                self.require_validated()
                require(not self.pending_feedback(), "Unresolved feedback blocks review readiness")
            self.state["phase"] = "draft" if pr["draft"] else "review"
        self.state["pr"] = pr
        self.save()

    def status(self):
        """Report saved progress alongside current checkout and evidence problems."""
        head = commit(self.plan["repo"], "HEAD")
        checkout_problem = None
        try:
            self.current_head()
        except InvalidState as exc:
            checkout_problem = str(exc)
        result_problem = None
        if self.state["head_sha"]:
            try:
                if digest(read_json(self.directory / "result.json")) != self.state["result_sha256"]:
                    result_problem = "Application result changed; record the revised application"
            except (OSError, ValueError):
                result_problem = "Application result is unavailable"
        return {"checkout_problem": checkout_problem, "result_problem": result_problem,
                "phase": self.state["phase"], "plan_sha256": self.state["plan_sha256"],
                "candidate_head": self.state["head_sha"], "checkout_head": head,
                "gate_problems": self.gate_problems(head),
                "pending_feedback": self.pending_feedback(), "pr": self.state["pr"],
                "pr_head_differs": bool(self.state["pr"] and
                                        self.state["pr"]["head_sha"] != self.state["head_sha"])}


@contextlib.contextmanager
def locked(directory):
    """Serialize state updates and release the advisory lock on every exit path."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise InvalidState("Another process is updating this run") from exc
        yield


def main(argv=None):
    """Dispatch one state operation and report expected failures without a traceback."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("--plan", required=True)
    sub.add_parser("status")
    advance = sub.add_parser("advance")
    advance.add_argument("--to", choices=("applied", "validated"), required=True)
    advance.add_argument("--result")
    record = sub.add_parser("record")
    record.add_argument("--gate", required=True)
    record.add_argument("--evidence", required=True)
    sub.add_parser("feedback").add_argument("--input", required=True)
    resolve = sub.add_parser("resolve-feedback")
    resolve.add_argument("--id", required=True)
    resolve.add_argument("--outcome", choices=("addressed", "declined", "no-change"), required=True)
    resolve.add_argument("--rationale", required=True)
    sub.add_parser("sync-pr").add_argument("--input", required=True)
    args = parser.parse_args(argv)
    manager = Manager(args.state_dir)
    try:
        if args.command == "status":
            manager.load()
        else:
            if args.command == "init":
                candidate = validate_plan(read_json(args.plan))
                require(not manager.directory.is_relative_to(Path(candidate["repo"])),
                        "State directory must be outside the target checkout")
            else:
                require(manager.state_path.exists(), "No initialized state directory")
            with locked(manager.directory):
                if args.command == "init":
                    manager.init(args.plan)
                else:
                    manager.load()
                    if args.command == "advance":
                        if args.to == "applied":
                            require(args.result, "--result is required for applied")
                            manager.apply(args.result)
                        else:
                            manager.validate()
                    elif args.command == "record":
                        manager.record(args.gate, args.evidence)
                    elif args.command == "feedback":
                        manager.feedback(args.input)
                    elif args.command == "resolve-feedback":
                        manager.resolve_feedback(args.id, args.outcome, args.rationale)
                    elif args.command == "sync-pr":
                        manager.sync_pr(args.input)
        print(json.dumps(manager.status(), indent=2, sort_keys=True))
        return 0
    except (InvalidState, OSError, ValueError, KeyError, TypeError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
