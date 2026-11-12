#!/usr/bin/env python3
"""Keep pr-risk-assessment eval runs on the frozen evidence.

Each case freezes a pull request in input.json. The live pull request carries
its risk-tier label and chai-bot's records, and the repository's later history
shows how a merged change turned out. A run may read input.json and the
repository's source at input.json's base_sha; never the pull request, its
head, other commits or branches, or this eval's answers.

One policy serves both sides of the eval:

- PreToolUse hook: copied into each case workspace next to input.json and run
  as a script. Exit code 2 denies the tool call and returns the reason to the
  model. A failure inside the guard also exits 2, because a hook that exits 1
  lets the call through.
- pull_request_not_read judge (judge_pull_request_not_read): re-applies the
  policy to every recorded call the hook let through and, however a command
  was spelled, fails a run whose tool output carries a risk-tier label or this
  eval's answers.

The policy reads commands as text. It stops the ordinary routes (gh flags
before the subcommand, fetches of other refs, a partial clone's on-demand
fetch of another commit, contents reads at other refs), not a script written
to a file and then run; the judge's output check is the backstop.
"""

import json
import os
import re
import shlex
import sys
import traceback
from pathlib import Path

BLOCKED = "Blocked by the eval harness"
GUIDANCE = (
    "The pull request is frozen in input.json. Read the repository only at "
    "base_sha {base}: fetch that commit into an empty repository, then "
    "`git show {base}:<path>`, or use the contents API with ref={base}."
)

HOOKED_TOOLS = ("Bash", "WebFetch", "Read", "Grep", "Glob")
NETWORK_TOOLS = ("Bash", "WebFetch")

# chai-bot's tier label prefix, or this eval's answer keys (annotations.yaml).
LEAK_MARKERS = re.compile(r"chai-risk-assessment/|\bexpected_tier\b|\bacceptable_tiers\b")

EVAL_ANSWERS = re.compile(r"/evals/")

# One owner, repository, or ref path segment, including gh's {owner}/{repo};
# shell punctuation ends it, as in B=https://.../<sha>; for f in ...
SEG = r"[^/\s'\"?#;&|()<>`]+"

# Pull requests, issues, and searches, on any repository.
PULL_REQUEST_READS = re.compile(
    rf"repos/{SEG}/{SEG}/(?:pulls|issues|events|timeline)\b"
    r"|commits/[0-9a-fA-F]+/pulls\b"
    r"|search/(?:issues|code|commits)\b"
    r"|\bgraphql\b"
    rf"|github\.com/{SEG}/{SEG}/(?:pull|pulls|issues)\b"
    r"|github\.com/search\b"
    r"|\bgh\s+(?:pr|issue|search|browse)\b",
    re.IGNORECASE,
)
GH_DENIED = {"pr", "issue", "search", "browse"}
GH_VALUE_FLAGS = {"-R", "--repo", "--hostname"}

FULL_SHA = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{40}(?![0-9a-fA-F])")

# REST paths: `repos/` starting a word (gh api) or after api.github.com/, so a
# local directory named repos/ does not count.
REST = re.compile(
    rf"(?:api\.github\.com/|(?<![\w./-])/?)repos/(?P<owner>{SEG})/(?P<name>{SEG})(?P<rest>/[^\s'\"]*)?",
    re.IGNORECASE,
)
RAW = re.compile(
    rf"raw\.githubusercontent\.com/(?P<owner>{SEG})/(?P<name>{SEG})/(?P<ref>{SEG})",
    re.IGNORECASE,
)
WEB = re.compile(
    rf"(?<![\w.-])github\.com/(?P<owner>{SEG})/(?P<name>{SEG})(?P<rest>/[^\s'\"]*)?",
    re.IGNORECASE,
)
REF_PARAM = re.compile(r"\bref=([^\s&'\"#]+)")

SHELL_OPERATORS = re.compile(r"&&|\|\||[;|&\n()`]|\$\(")
COMMAND_END = re.compile(r"&&|\|\||[;|\n]")
ASSIGNMENT = re.compile(
    r"(?:^|(?<=[\s;&|(]))(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|[^\s;&|)]*)"
)
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w.-]*)\1")

GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
FETCH_VALUE_FLAGS = {
    "--depth", "--deepen", "--shallow-since", "--shallow-exclude", "--filter",
    "--refmap", "-j", "--jobs", "-o", "--server-option", "--upload-pack",
    "--negotiation-tip", "--recurse-submodules-default", "--submodule-prefix",
}
FETCH_OTHER_REFS = {"--all", "--multiple", "--tags", "-t"}


def load_evidence(path):
    """The repository and base commit a case may read, from its input.json."""
    data = json.loads(Path(path).read_text())
    return {"repo": data["repo"].lower(), "base_sha": data["base_sha"].lower()}


def denial(tool, tool_input, evidence):
    """Why the policy denies a tool call, or None when it may run."""
    if tool not in HOOKED_TOOLS:
        return None
    text = _tool_text(tool, tool_input)
    if EVAL_ANSWERS.search(text):
        return "this repository's eval answers are not evidence"
    if tool not in NETWORK_TOOLS:
        return None
    if PULL_REQUEST_READS.search(text) or _gh_denial(text):
        return "the pull request, its labels, comments, and searches are not evidence"
    return _base_only_denial(text, evidence)


def _tool_text(tool, tool_input):
    if tool == "Bash":
        return _expand_variables(_strip_file_heredocs(str(tool_input.get("command", ""))))
    if tool == "WebFetch":
        return str(tool_input.get("url", ""))
    return json.dumps(tool_input)


def _strip_file_heredocs(command):
    """Drop the bodies of heredocs that cat or tee write to a file.

    A run writes its result JSON, which names the pull request URL, that way.
    Heredocs piped or fed to another program stay, since they run.
    """
    lines = command.split("\n")
    kept = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        match = HEREDOC.search(line)
        if not match:
            continue
        writes_file = "|" not in line and (
            re.search(r"\btee\b", line)
            or (re.search(r"\bcat\b", line) and ">" in line.replace("<<", ""))
        )
        if not writes_file:
            continue
        end = next((k for k in range(i, len(lines)) if lines[k].strip() == match.group(2)), None)
        if end is not None:
            i = end
    return "\n".join(kept)


def _expand_variables(command):
    """Substitute variables the same command assigns, as in B=<sha>; ... $B."""
    values = {name: value.strip("'\"") for name, value in ASSIGNMENT.findall(command)}
    return VARIABLE.sub(lambda m: values.get(m.group(1) or m.group(2), m.group(0)), command)


def _simple_commands(text):
    return [part for part in SHELL_OPERATORS.split(text) if part.strip()]


def _words(part):
    try:
        return shlex.split(part)
    except ValueError:
        return part.split()


def _gh_denial(text):
    """gh pr, issue, search, or browse, with or without flags before them."""
    for part in _simple_commands(text):
        words = _words(part)
        for i, word in enumerate(words):
            if os.path.basename(word) != "gh":
                continue
            rest = words[i + 1:]
            k = 0
            while k < len(rest) and rest[k].startswith("-"):
                k += 2 if rest[k] in GH_VALUE_FLAGS else 1
            if k < len(rest) and rest[k] in GH_DENIED:
                return f"gh {rest[k]}"
    return None


def _base_only_denial(text, evidence):
    base, repo = evidence["base_sha"], evidence["repo"]
    for sha in FULL_SHA.findall(text):
        if sha.lower() != base:
            return f"object {sha[:12]} is not the base commit"
    for part in _simple_commands(text):
        reason = _git_denial(_words(part), base)
        if reason:
            return reason
    for match in REST.finditer(text):
        if _is_target(match, repo):
            reason = _rest_denial(match.group("rest") or "", _command_around(text, match), base)
            if reason:
                return reason
    for match in RAW.finditer(text):
        if _is_target(match, repo) and match.group("ref").lower() != base:
            return f"raw file at {match.group('ref')!r}, not the base commit"
    for match in WEB.finditer(text):
        if _is_target(match, repo):
            reason = _web_denial(match.group("rest") or "", base)
            if reason:
                return reason
    return None


def _is_target(match, repo):
    owner, name = match.group("owner"), match.group("name")
    if owner.startswith("{"):
        return True  # gh api resolves {owner}/{repo} from the clone's remote
    name = name[:-4] if name.lower().endswith(".git") else name
    return f"{owner}/{name}".lower() == repo


def _git_denial(words, base):
    for i, word in enumerate(words):
        if os.path.basename(word) != "git":
            continue
        j = i + 1
        while j < len(words) and words[j].startswith("-"):
            j += 2 if words[j] in GIT_GLOBAL_VALUE_FLAGS else 1
        if j >= len(words):
            continue
        sub, args = words[j], words[j + 1:]
        if sub in ("clone", "pull"):
            return f"git {sub} brings a branch's current history"
        if sub == "remote" and args[:1] == ["update"]:
            return "git remote update fetches every branch"
        if sub == "fetch":
            reason = _fetch_denial(args, base)
            if reason:
                return reason
    return None


def _fetch_denial(args, base):
    positional = []
    k = 0
    while k < len(args):
        arg = args[k]
        if arg in FETCH_OTHER_REFS:
            return f"git fetch {arg} fetches other refs"
        if arg.startswith("-"):
            k += 2 if arg in FETCH_VALUE_FLAGS else 1
            continue
        positional.append(arg)
        k += 1
    refspecs = positional[1:]
    if not refspecs:
        return "git fetch without the base commit fetches the remote's branches"
    for spec in refspecs:
        if spec.lstrip("+").split(":", 1)[0].lower() != base:
            return f"git fetch of {spec!r} is not the base commit (name base_sha literally)"
    return None


def _command_around(text, match):
    """The single command a match sits in, for its -f ref= arguments."""
    start = max((m.end() for m in COMMAND_END.finditer(text, 0, match.start())), default=0)
    end_match = COMMAND_END.search(text, match.end())
    return text[start:end_match.start() if end_match else len(text)]


def _rest_denial(rest, command, base):
    parts = [p for p in rest.split("?", 1)[0].split("/") if p]
    if not parts:
        return None
    head = parts[0].lower()
    if head in ("contents", "readme"):
        refs = REF_PARAM.findall(command)
        if not refs:
            return f"{head} without ref=base_sha reads the default branch"
        if any(ref.lower() != base for ref in refs):
            return f"{head} at a ref other than the base commit"
        return None
    if head in ("commits", "tarball", "zipball") and len(parts) == 2 and parts[1].lower() == base:
        return None
    if head == "git" and len(parts) == 3 and parts[1] in ("trees", "commits") and parts[2].lower() == base:
        return None
    return f"repos/<repo>/{head} reaches beyond the base commit's source"


def _web_denial(rest, base):
    parts = [p for p in rest.split("?", 1)[0].split("/") if p]
    if not parts:
        return None
    kind = parts[0].lower()
    ref = parts[1].lower() if len(parts) > 1 else ""
    if kind in ("blob", "tree", "raw") and ref == base:
        return None
    if kind == "archive" and ref.startswith(base):
        return None
    return f"github.com/<repo>/{kind} reaches beyond the base commit's source"


# ── Judge ──

CASES = Path(__file__).resolve().parents[1] / "cases" / "pr-risk-assessment"


def judge_pull_request_not_read(outputs):
    """Fail a run where a denied call got through or a tool output leaked the tier."""
    evidence = load_evidence(CASES / Path(outputs["case_dir"]).name / "input.json")
    events = outputs.get("events") or []
    results = {e.get("tool_use_id"): _content(e) for e in events if e.get("type") == "tool_result"}
    findings = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for call in event.get("tools") or []:
            result = results.get(call.get("id"))
            if result is None or BLOCKED in result:
                continue
            reason = denial(call.get("name", ""), call.get("input") or {}, evidence)
            if reason:
                findings.append(f"{call.get('name')} not blocked ({reason}): "
                                f"{json.dumps(call.get('input'))[:160]}")
    for result in results.values():
        match = LEAK_MARKERS.search(result)
        if match and BLOCKED not in result:
            findings.append(f"a tool output carries {match.group(0)!r}")
    if findings:
        return (False, f"{len(findings)} finding(s): " + "; ".join(findings[:3]))
    return (True, "No call reached the pull request or beyond base_sha, "
                  "and no tool output carried a tier label")


def _content(event):
    content = event.get("content")
    return content if isinstance(content, str) else json.dumps(content)


# ── Hook ──

def main():
    event = json.load(sys.stdin)
    evidence = load_evidence(Path(__file__).resolve().parent / "input.json")
    reason = denial(event.get("tool_name", ""), event.get("tool_input") or {}, evidence)
    if reason is None:
        return 0
    print(f"{BLOCKED}: {reason}. {GUIDANCE.format(base=evidence['base_sha'])}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # exit 1 would let the call through: deny instead
        traceback.print_exc()
        print(f"{BLOCKED}: the evidence guard failed, so the call is denied.", file=sys.stderr)
        sys.exit(2)
