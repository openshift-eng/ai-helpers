#!/usr/bin/env python3
"""
Parse /save and /drop directives from PR comments.

Fetches issue comments via `gh api`, filters to trusted collaborators,
validates paths, deduplicates (last-writer-wins), and outputs JSON.

Usage: process-comments.py --repo OWNER/REPO --pr-number N [--since-comment-id ID]
"""

import argparse
import json
import re
import subprocess
import sys


TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
DIRECTIVE_RE = re.compile(r"^/(save|drop)\s+(\S+)\s*$", re.MULTILINE)


def gh_api(endpoint):
    result = subprocess.run(
        ["gh", "api", "--paginate", endpoint],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"gh api failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def parse_directives(body):
    return DIRECTIVE_RE.findall(body or "")


def validate_path(path):
    path = path.strip().rstrip("/")
    parts = path.split("/")
    if len(parts) < 2:
        return None, f"Path must have at least 2 components: {path}"
    if not path.startswith("plugins/"):
        return None, f"Path must start with 'plugins/': {path}"
    return path, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--since-comment-id", type=int, default=0)
    args = parser.parse_args()

    comments = gh_api(f"repos/{args.repo}/issues/{args.pr_number}/comments")

    directives = []
    errors = []

    for comment in comments:
        comment_id = comment["id"]
        if comment_id <= args.since_comment_id:
            continue

        association = comment.get("author_association", "")
        author = comment.get("user", {}).get("login", "unknown")

        if association not in TRUSTED_ASSOCIATIONS:
            matches = parse_directives(comment.get("body", ""))
            if matches:
                errors.append(
                    f"Ignoring directives from @{author} — "
                    f"association '{association}' is not trusted"
                )
            continue

        for action, raw_path in parse_directives(comment.get("body", "")):
            path, err = validate_path(raw_path)
            if err:
                errors.append(f"@{author}: {err}")
                continue

            directives.append({
                "action": action,
                "path": path,
                "author": author,
                "comment_id": comment_id,
                "created_at": comment["created_at"],
            })

    path_map = {}
    for d in sorted(directives, key=lambda x: (x["created_at"], x["comment_id"])):
        path_map[d["path"]] = d

    saves = []
    drops = []
    for d in path_map.values():
        entry = {"path": d["path"], "author": d["author"]}
        if d["action"] == "save":
            saves.append(entry)
        else:
            drops.append(entry)

    last_comment_id = 0
    if comments:
        last_comment_id = max(c["id"] for c in comments)

    output = {
        "saves": saves,
        "drops": drops,
        "errors": errors,
        "last_comment_id": last_comment_id,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
