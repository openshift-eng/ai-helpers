#!/usr/bin/env python3
"""
Update a pruning PR body after processing /save and /drop directives.

For saves: applies strikethrough markup to the matching manifest row.
For drops that undo a save: removes strikethrough markup.
For new drops: adds a new row to the manifest.

Usage: update-pr-body.py --repo OWNER/REPO --pr-number N [--saves p1,p2] [--drops p1,p2] [--drop-usernames u1,u2] [--save-usernames u1,u2]
"""

import argparse
import json
import re
import subprocess
import sys


def gh_pr_view(repo, pr_number):
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", "body", "-q", ".body"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"Failed to fetch PR body: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def gh_pr_edit(repo, pr_number, body):
    result = subprocess.run(
        ["gh", "pr", "edit", str(pr_number), "--repo", repo, "--body", body],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"Failed to update PR body: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--saves", default="")
    parser.add_argument("--drops", default="")
    parser.add_argument("--save-usernames", default="")
    parser.add_argument("--drop-usernames", default="")
    args = parser.parse_args()

    saves = [p.strip() for p in args.saves.split(",") if p.strip()]
    drops = [p.strip() for p in args.drops.split(",") if p.strip()]
    save_users = [u.strip() for u in args.save_usernames.split(",") if u.strip()]
    drop_users = [u.strip() for u in args.drop_usernames.split(",") if u.strip()]

    body = gh_pr_view(args.repo, args.pr_number)
    lines = body.splitlines()
    new_lines = []
    manifest_end_idx = None

    for i, line in enumerate(lines):
        modified = False

        for j, save_path in enumerate(saves):
            norm = save_path.rstrip("/")
            if f"`{norm}" in line and "~~" not in line:
                parts = line.split("|")
                if len(parts) >= 4:
                    username = save_users[j] if j < len(save_users) else "unknown"
                    parts[1] = f" ~~{parts[1].strip()}~~ "
                    parts[2] = f" ~~{parts[2].strip()}~~ "
                    parts[3] = f" ~~SAVED by @{username}~~ "
                    line = "|".join(parts)
                    modified = True
                    break

        if not modified:
            for k, drop_path in enumerate(drops):
                norm = drop_path.rstrip("/")
                if f"`{norm}" in line and "~~" in line:
                    line = line.replace("~~", "")
                    username = drop_users[k] if k < len(drop_users) else "unknown"
                    parts = line.split("|")
                    if len(parts) >= 4:
                        parts[3] = f" Dropped by @{username} "
                    line = "|".join(parts)
                    break

        if line.strip().startswith("|") and "Removal Manifest" not in line:
            manifest_end_idx = len(new_lines)

        new_lines.append(line)

    for k, drop_path in enumerate(drops):
        norm = drop_path.rstrip("/")
        already_in_body = any(f"`{norm}" in l for l in new_lines)
        if not already_in_body and manifest_end_idx is not None:
            username = drop_users[k] if k < len(drop_users) else "unknown"
            new_row = f"| item | `{norm}` | Manually dropped by @{username} |"
            new_lines.insert(manifest_end_idx + 1, new_row)
            manifest_end_idx += 1

    updated_body = "\n".join(new_lines)
    gh_pr_edit(args.repo, args.pr_number, updated_body)
    print("PR body updated successfully.")


if __name__ == "__main__":
    main()
