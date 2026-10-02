#!/usr/bin/env python3
"""Collect a read-only PR snapshot for has-review-work's semantic decision.

This helper returns JSON evidence, not COMMENT_WORK. The skill decides whether
the remaining comments contain requests rather than pure acknowledgments.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from filter_optional_checks import filter_checks
from is_slash_command_only import is_slash_command_only

# Reuse the worker's authorization policy and historical reply signatures.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "address-review-pr" / "scripts"))
import check_authorized
from check_replied import is_bot_reply

GH_TIMEOUT = 30
THREAD_QUERY = """
query($owner:String!,$repo:String!,$number:Int!,$endCursor:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$endCursor) {
        nodes { id isResolved comments(first:1) { nodes { databaseId } } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


def run_gh(args: list[str], *, allow_failure_json: bool = False) -> Any:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=GH_TIMEOUT,
    )
    if result.returncode and not allow_failure_json:
        raise RuntimeError(f"gh request failed (exit {result.returncode})")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as err:
        raise RuntimeError("gh request did not return valid JSON") from err
    return value


def paginated_items(endpoint: str) -> list[dict]:
    # --slurp makes pagination explicit instead of depending on concatenated JSON.
    pages = run_gh(["api", endpoint, "--paginate", "--slurp"])
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("REST response must contain arrays of items")
    items = [item for page in pages for item in page]
    if any(not isinstance(item, dict) for item in items):
        raise ValueError("REST response contains an invalid item")
    return items


def fetch_threads(owner: str, repo: str, number: int) -> dict[int, dict]:
    pages = run_gh([
        "api", "graphql", "--paginate", "--slurp",
        "-f", f"owner={owner}", "-f", f"repo={repo}",
        "-F", f"number={number}", "-f", f"query={THREAD_QUERY}",
    ])
    roots = {}
    for page in pages:
        if page.get("errors"):
            raise RuntimeError("GraphQL review-thread lookup failed")
        connection = page["data"]["repository"]["pullRequest"]["reviewThreads"]
        for thread in connection["nodes"]:
            # All REST replies point to the thread's root. Only its id is needed,
            # so nested comment pagination is unnecessary, even in long threads.
            for comment in thread["comments"]["nodes"]:
                roots[comment["databaseId"]] = thread
    return roots


def normalized_login(login: str) -> str:
    return login.lower().removesuffix("[bot]")


class Authorizer:
    """Cache OWNERS once and organization membership once per login."""

    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.owners: set[str] | None = None
        self.cache: dict[str, bool] = {}

    def __call__(self, login: str) -> bool:
        key = login.lower()
        if key not in self.cache:
            if key in {bot.lower() for bot in check_authorized.APPROVED_BOTS}:
                self.cache[key] = True
            elif not login or normalized_login(login) in check_authorized.IGNORED_ACCOUNTS or key.endswith("[bot]"):
                self.cache[key] = False
            else:
                if self.owners is None:
                    self.owners = {
                        user.lower() for user in check_authorized.get_authorized_users(self.owner, self.repo)
                    }
                self.cache[key] = key in self.owners or check_authorized.is_org_member(self.owner, login)
        return self.cache[key]


def collect_candidates(
    inline: list[dict], reviews: list[dict], conversation: list[dict],
    threads: dict[int, dict], agent_login: str, authorize,
) -> tuple[list[dict], dict[str, int]]:
    """Filter a single snapshot; never mutate shell state or refetch per item."""
    agent = normalized_login(agent_login)

    def bot_reply(comment: dict) -> bool:
        login = (comment.get("user") or {}).get("login", "")
        return bool(login) and (
            normalized_login(login) == agent or is_bot_reply(login, comment.get("body", ""))
        )

    latest_inline_reply: dict[int, str] = {}
    for comment in inline:
        if bot_reply(comment):
            root = comment.get("in_reply_to_id") or comment["id"]
            latest_inline_reply[root] = max(
                latest_inline_reply.get(root, ""), comment["created_at"],
            )
    latest_conversation_reply = max(
        (c["created_at"] for c in conversation if bot_reply(c)), default="",
    )

    candidates = []
    skipped = Counter()
    for kind, items in (
        ("review_comment", inline), ("review", reviews), ("issue_comment", conversation),
    ):
        for comment in items:
            login = (comment.get("user") or {}).get("login", "")
            body = comment.get("body") or ""
            if bot_reply(comment) or normalized_login(login) in check_authorized.IGNORED_ACCOUNTS:
                skipped["bot"] += 1
                continue
            if kind == "review" and comment.get("state") in ("APPROVED", "PENDING"):
                skipped["review_state"] += 1
                continue
            if is_slash_command_only(body):
                skipped["empty_or_commands"] += 1
                continue

            thread = None
            if kind == "review_comment":
                root = comment.get("in_reply_to_id") or comment["id"]
                thread = threads.get(root)
                if thread is None:
                    raise RuntimeError("Inline comment missing from review-thread snapshot; retry")
                if thread["isResolved"]:
                    skipped["resolved"] += 1
                    continue
                replied_at = latest_inline_reply.get(root, "")
                created_at = comment["created_at"]
            else:
                replied_at = latest_conversation_reply
                created_at = comment["submitted_at"] if kind == "review" else comment["created_at"]

            if replied_at and replied_at >= created_at:
                skipped["replied"] += 1
                continue
            if not authorize(login):
                skipped["unauthorized"] += 1
                continue
            candidate = {
                "type": kind, "id": comment["id"], "author": login,
                "body": body, "created_at": created_at,
            }
            if thread is not None:
                candidate.update(
                    thread_id=thread["id"], path=comment.get("path"),
                    line=comment.get("line"), original_line=comment.get("original_line"),
                    diff_hunk=comment.get("diff_hunk", ""),
                )
            candidates.append(candidate)
    return candidates, dict(skipped)


def ci_decision(failing: list[dict], head: str, context: dict) -> str:
    if not failing:
        return "no"
    previous = context.get("previous_failing_checks")
    if previous is None or head != context.get("previous_head_ref_oid"):
        return "yes"
    return "yes" if {c["name"] for c in failing} != {c["name"] for c in previous} else "no"


def validate_checks(value: Any) -> list[dict]:
    if not isinstance(value, list) or any(
        not isinstance(c, dict) or any(not isinstance(c.get(k), str) for k in ("name", "state", "bucket"))
        for c in value
    ):
        raise ValueError("Checks must be a JSON array with name, state, and bucket strings")
    return value


def collect_snapshot(repo: str, number: int | None, context: dict) -> dict:
    owner, repo_name = repo.split("/")
    pr_args = [str(number)] if number is not None else []
    metadata = run_gh(["pr", "view", *pr_args, "--repo", repo, "--json", "number,headRefOid"])
    number = metadata["number"]
    head = metadata["headRefOid"]
    if not isinstance(number, int) or not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("PR metadata has an invalid number or head SHA")
    agent = context.get("agent_login")
    if not agent:
        agent = run_gh(["api", "user"])["login"]
    if not isinstance(agent, str):
        raise ValueError("Agent login must be a string")

    prefix = f"repos/{repo}"
    inline = paginated_items(f"{prefix}/pulls/{number}/comments")
    reviews = paginated_items(f"{prefix}/pulls/{number}/reviews")
    conversation = paginated_items(f"{prefix}/issues/{number}/comments")
    threads = fetch_threads(owner, repo_name, number)
    candidates, skipped = collect_candidates(
        inline, reviews, conversation, threads, agent, Authorizer(owner, repo_name),
    )

    # gh pr checks returns nonzero for failing/pending checks. Valid JSON is
    # still evidence; unavailable or malformed output must fail the snapshot.
    checks = validate_checks(run_gh([
        "pr", "checks", str(number), "--repo", repo, "--json", "name,state,bucket,link",
    ], allow_failure_json=True))
    failing = filter_checks(checks)
    final_head = run_gh(["pr", "view", str(number), "--repo", repo, "--json", "headRefOid"])["headRefOid"]
    if final_head != head:
        raise RuntimeError("PR head changed during collection; retry")
    return {
        "head_ref_oid": head, "comment_candidates": candidates,
        "ci_work": ci_decision(failing, head, context),
        "failing_checks": failing, "skipped": skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int)
    parser.add_argument("--repo")
    parser.add_argument("--context-stdin", action="store_true", help="Read optional caller context as JSON from stdin")
    args = parser.parse_args()
    try:
        context = json.load(sys.stdin) if args.context_stdin else {}
        if not isinstance(context, dict):
            raise ValueError("Caller context must be a JSON object")
        if context.get("previous_failing_checks") is not None:
            validate_checks(context["previous_failing_checks"])
        repo = args.repo or run_gh(["repo", "view", "--json", "nameWithOwner"])["nameWithOwner"]
        if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("Repository must be owner/repo")
        if args.pr is not None and args.pr < 1:
            raise ValueError("PR number must be positive")
        snapshot = collect_snapshot(repo, args.pr, context)
    except (
        RuntimeError, ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired,
        check_authorized.OwnersLookupError, check_authorized.OrgMembershipLookupError,
    ) as err:
        print(f"ERROR: cannot collect review work: {err}", file=sys.stderr)
        return 1
    print(json.dumps(snapshot, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
