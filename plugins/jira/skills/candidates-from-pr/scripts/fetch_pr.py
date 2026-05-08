#!/usr/bin/env python3
"""Fetch GitHub PR metadata and diff for candidates-from-pr.

Resolves a PR URL or (number + --repo) into normalized JSON containing the
fields the rest of the pipeline needs. Diff is capped to keep downstream
processing bounded.

Usage:
    fetch_pr.py <pr-url-or-number> [--repo <org/repo>] [--diff-max-lines N]

Output: JSON on stdout with keys:
    org, repo, number, url, title, body, base_ref, head_ref,
    labels[], author, files[{path}], commits[{oid, headline, body}],
    diff (capped), diff_truncated (bool), diff_total_lines
"""

import argparse
import json
import re
import subprocess
import sys
from typing import Any

PR_URL_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?$")


def resolve_pr(arg: str, repo: str | None) -> tuple[str, str, int]:
    """Return (org, repo, number) from a URL or number+repo."""
    m = PR_URL_RE.match(arg)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    if not arg.isdigit():
        sys.exit(f"error: '{arg}' is not a PR URL or numeric PR number")
    if not repo or "/" not in repo:
        sys.exit("error: --repo <org/repo> is required when passing a numeric PR")
    org, name = repo.split("/", 1)
    return org, name, int(arg)


def gh_json(args: list[str]) -> Any:
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"error: {' '.join(args)} failed:\n{res.stderr}")
    return json.loads(res.stdout)


def gh_text(args: list[str]) -> tuple[str, str, int]:
    res = subprocess.run(args, capture_output=True, text=True)
    return res.stdout, res.stderr, res.returncode


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("pr", help="PR URL or number")
    p.add_argument("--repo", help="org/repo (required when pr is numeric)")
    p.add_argument("--diff-max-lines", type=int, default=4000)
    args = p.parse_args()

    org, repo, number = resolve_pr(args.pr, args.repo)
    slug = f"{org}/{repo}"

    pr = gh_json(
        [
            "gh", "pr", "view", str(number), "--repo", slug,
            "--json",
            "number,url,title,body,headRefName,baseRefName,labels,author,commits,files",
        ]
    )

    diff, diff_err, rc = gh_text(["gh", "pr", "diff", str(number), "--repo", slug])
    diff_unavailable_reason: str | None = None
    if rc != 0:
        # Common failure modes: PR too large (HTTP 406, >300 files), private,
        # network glitch. Don't fail the whole pipeline — signals can still be
        # extracted from titles/bodies/file paths/commit messages.
        diff = ""
        _err_lines = (diff_err or "").strip().splitlines()
        diff_unavailable_reason = _err_lines[-1] if _err_lines else "unknown error"

    diff_lines = diff.splitlines()
    truncated = len(diff_lines) > args.diff_max_lines
    capped = "\n".join(diff_lines[: args.diff_max_lines])

    out = {
        "org": org,
        "repo": repo,
        "number": number,
        "url": pr.get("url"),
        "title": pr.get("title") or "",
        "body": pr.get("body") or "",
        "base_ref": pr.get("baseRefName") or "",
        "head_ref": pr.get("headRefName") or "",
        "labels": [lab.get("name") for lab in pr.get("labels") or [] if lab.get("name")],
        "author": (pr.get("author") or {}).get("login"),
        "files": [{"path": f.get("path")} for f in pr.get("files") or [] if f.get("path")],
        "commits": [
            {
                "oid": c.get("oid"),
                "headline": c.get("messageHeadline") or "",
                "body": c.get("messageBody") or "",
            }
            for c in pr.get("commits") or []
        ],
        "diff": capped,
        "diff_truncated": truncated,
        "diff_total_lines": len(diff_lines),
        "diff_unavailable_reason": diff_unavailable_reason,
    }
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
