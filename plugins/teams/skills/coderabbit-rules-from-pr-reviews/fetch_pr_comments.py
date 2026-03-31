#!/usr/bin/env python3
"""
Fetch human review comments from recent merged PRs in a GitHub repository.

Collects inline code review comments and general PR discussion comments,
filtering out bot accounts, prow commands, approvals, and short noise.

Prerequisites:
    GitHub CLI (gh) must be installed and authenticated.

Usage:
    python3 fetch_pr_comments.py openshift/origin
    python3 fetch_pr_comments.py openshift/origin --count 50
    python3 fetch_pr_comments.py https://github.com/openshift/origin --count 20
"""

import argparse
import json
import re
import subprocess
import sys
import time

API_SLEEP = 0.5
RETRY_SLEEP = 15
MAX_RETRIES = 3

BOT_SUFFIXES = ("[bot]",)
BOT_LOGINS = frozenset({
    "coderabbitai",
    "openshift-ci",
    "openshift-bot",
    "openshift-merge-robot",
    "openshift-merge-bot",
    "codecov",
    "codecov-commenter",
    "netlify",
    "dependabot",
    "renovate",
    "github-actions",
    "stale",
    "k8s-ci-robot",
    "fejta-bot",
})

# Patterns that indicate a comment is just a prow command or approval
PROW_COMMAND_RE = re.compile(r"^\s*/\w+", re.MULTILINE)
APPROVAL_PATTERNS = frozenset({
    "/lgtm",
    "/approve",
    "lgtm",
    "/hold",
    "/unhold",
    "/retest",
    "/test",
    "/cc",
    "/uncc",
    "/assign",
    "/unassign",
    "/close",
    "/reopen",
    "/cherry-pick",
    "/label",
    "/remove-label",
    "/kind",
    "/priority",
    "/sig",
    "/area",
    "/milestone",
    "/retitle",
    "/lifecycle",
    "/ok-to-test",
    "/override",
})

MIN_COMMENT_LENGTH = 20


def is_bot(login):
    """Check if a login is a known bot account."""
    if not login:
        return True
    login_lower = login.lower()
    for suffix in BOT_SUFFIXES:
        if login_lower.endswith(suffix):
            return True
    # Strip [bot] suffix for matching
    clean = login_lower.replace("[bot]", "")
    return clean in BOT_LOGINS


def is_noise(body):
    """Check if a comment body is just noise (prow command, approval, too short)."""
    if not body:
        return True
    stripped = body.strip()
    if len(stripped) < MIN_COMMENT_LENGTH:
        return True
    # Check if the entire comment is just prow commands
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    if all(l.startswith("/") for l in lines):
        return True
    # Check if it's just an approval keyword
    if stripped.lower() in APPROVAL_PATTERNS:
        return True
    return False


def gh_api(endpoint, paginate=True):
    """Call gh api and return parsed JSON. Returns list for paginated, dict otherwise."""
    cmd = ["gh", "api"]
    if paginate:
        cmd.append("--paginate")
    cmd.append(endpoint)

    for attempt in range(MAX_RETRIES):
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            print(f"  Timeout on {endpoint} (attempt {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
            time.sleep(RETRY_SLEEP)
            continue

        if result.returncode == 0:
            text = result.stdout.strip()
            if not text:
                return [] if paginate else {}
            # gh --paginate can concatenate multiple JSON arrays, handle that
            if paginate:
                # Try direct parse first
                try:
                    data = json.loads(text)
                    return data if isinstance(data, list) else [data]
                except json.JSONDecodeError:
                    pass
                # Try concatenated arrays: ][
                try:
                    fixed = "[" + text.replace("]\n[", ",").replace("][", ",").lstrip("[").rstrip("]") + "]"
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    # Try line-by-line
                    items = []
                    for line in text.splitlines():
                        line = line.strip()
                        if line:
                            try:
                                parsed = json.loads(line)
                                if isinstance(parsed, list):
                                    items.extend(parsed)
                                else:
                                    items.append(parsed)
                            except json.JSONDecodeError:
                                pass
                    return items
            else:
                return json.loads(text)

        stderr = result.stderr.lower()
        if "rate limit" in stderr or "403" in stderr or "secondary" in stderr:
            wait = RETRY_SLEEP * (attempt + 1)
            print(f"  Rate limited on {endpoint}, waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
        elif "404" in stderr or "not found" in stderr.lower():
            return [] if paginate else {}
        else:
            print(f"  API error on {endpoint}: {result.stderr.strip()}", file=sys.stderr)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_SLEEP)
            else:
                return [] if paginate else {}

    return [] if paginate else {}


def parse_repo(repo_arg):
    """Extract owner/repo from a full URL or short form."""
    repo = repo_arg.strip().rstrip("/")
    # Strip common URL prefixes
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if repo.startswith(prefix):
            repo = repo[len(prefix):]
            break
    # Validate format
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        print(f"Error: Invalid repo format '{repo_arg}'. Expected 'owner/repo' or full URL.", file=sys.stderr)
        sys.exit(1)
    return repo


def fetch_merged_prs(repo, count):
    """Fetch recent merged PRs."""
    cmd = [
        "gh", "pr", "list",
        "--repo", repo,
        "--state", "merged",
        "--limit", str(count),
        "--json", "number,title,url,author,mergedAt",
    ]
    for attempt in range(MAX_RETRIES):
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            print(f"  Timeout fetching PR list (attempt {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
            time.sleep(RETRY_SLEEP)
            continue

        if result.returncode == 0:
            return json.loads(result.stdout)
        print(f"  Error fetching PRs: {result.stderr.strip()}", file=sys.stderr)
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_SLEEP)

    print("Error: Failed to fetch PR list after retries.", file=sys.stderr)
    sys.exit(1)


def fetch_comments_for_pr(repo, pr_number):
    """Fetch all review and issue comments for a single PR, filtering noise."""
    comments = []

    # Inline code review comments
    review_comments = gh_api(f"repos/{repo}/pulls/{pr_number}/comments")
    for c in review_comments:
        user = (c.get("user") or {}).get("login", "")
        body = c.get("body", "")
        path = c.get("path", "")
        if is_bot(user) or is_noise(body):
            continue
        comments.append({
            "pr": pr_number,
            "user": user,
            "body": body,
            "path": path,
            "type": "review",
        })

    time.sleep(API_SLEEP)

    # General issue/PR discussion comments
    issue_comments = gh_api(f"repos/{repo}/issues/{pr_number}/comments")
    for c in issue_comments:
        user = (c.get("user") or {}).get("login", "")
        body = c.get("body", "")
        if is_bot(user) or is_noise(body):
            continue
        comments.append({
            "pr": pr_number,
            "user": user,
            "body": body,
            "path": "",
            "type": "issue",
        })

    return comments


def main():
    parser = argparse.ArgumentParser(description="Fetch human PR review comments")
    parser.add_argument("repo", help="GitHub repo (owner/repo or full URL)")
    parser.add_argument("--count", type=int, default=30, help="Number of recent merged PRs to analyze (default: 30)")
    args = parser.parse_args()

    repo = parse_repo(args.repo)
    count = args.count

    print(f"Fetching {count} recent merged PRs from {repo}...", file=sys.stderr)
    prs = fetch_merged_prs(repo, count)
    print(f"  Found {len(prs)} merged PRs", file=sys.stderr)

    all_comments = []
    reviewers = set()

    for i, pr in enumerate(prs, 1):
        pr_number = pr["number"]
        pr_title = pr.get("title", "")
        pr_author = (pr.get("author") or {}).get("login", "")
        print(f"  [{i}/{len(prs)}] PR #{pr_number}: {pr_title[:60]}", file=sys.stderr)

        comments = fetch_comments_for_pr(repo, pr_number)
        for c in comments:
            c["pr_title"] = pr_title
            c["pr_author"] = pr_author
            reviewers.add(c["user"])
        all_comments.extend(comments)
        time.sleep(API_SLEEP)

    print(f"\nCollected {len(all_comments)} human review comments from {len(reviewers)} reviewers", file=sys.stderr)

    output = {
        "repo": repo,
        "prs_analyzed": len(prs),
        "total_comments": len(all_comments),
        "unique_reviewers": len(reviewers),
        "reviewers": sorted(reviewers),
        "prs": [
            {
                "number": pr["number"],
                "title": pr.get("title", ""),
                "author": (pr.get("author") or {}).get("login", ""),
                "url": pr.get("url", ""),
                "merged_at": pr.get("mergedAt", ""),
            }
            for pr in prs
        ],
        "comments": all_comments,
    }

    json.dump(output, sys.stdout, indent=2)
    print(file=sys.stdout)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
