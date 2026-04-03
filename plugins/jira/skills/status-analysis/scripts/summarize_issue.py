#!/usr/bin/env python3
"""
Summarize a pre-gathered issue JSON file for LLM analysis.

Reads a per-issue JSON file produced by gather_status_data.py and prints
a concise, structured summary suitable for status analysis.

Usage:
    # By JSON file path:
    python3 summarize_issue.py .work/weekly-status/2026-03-11/issues/OCPSTRAT-1234.json

    # By issue key (requires --date-dir):
    python3 summarize_issue.py OCPSTRAT-1234 --date-dir .work/weekly-status/2026-03-11

    # Multiple files:
    python3 summarize_issue.py .work/weekly-status/2026-03-11/issues/*.json
"""

import json
import glob
import os
import sys


def pr_author(pr: dict) -> str:
    """Extract author name from a PR's commit or review data."""
    for commit in pr.get("commits_in_range", []):
        name = commit.get("author_name")
        if name:
            return name
    for review in pr.get("reviews_in_range", []):
        name = review.get("author_name")
        if name:
            return name
    return ""


def is_significant(d: dict) -> bool:
    """Check if an issue has significant activity (inline triage logic)."""
    desc = d["descendants"]
    prs = d.get("prs", [])
    changelog = d["changelog_in_range"]
    comments = d["comments_in_range"]
    status_summary = d["issue"].get("current_status_summary", "")

    human_comments = [c for c in comments if not c.get("is_bot")]
    merged_prs = [
        pr for pr in prs
        if pr["state"] == "MERGED"
        and pr.get("activity_summary", {}).get("commits_in_range", 0) > 0
    ]
    active_prs = [
        pr for pr in prs
        if pr.get("activity_summary", {}).get("commits_in_range", 0) > 0
        or pr.get("activity_summary", {}).get("reviews_in_range", 0) > 0
    ]
    updated_desc = desc.get("updated_in_range", [])
    status_changes = [
        c for c in changelog
        if any(item.get("field") == "status" for item in c.get("items", []))
    ]

    # Check for color change
    color_changed = False
    for entry in changelog:
        for item in entry.get("items", []):
            field = item.get("field", "")
            field_id = str(item.get("fieldId", ""))
            if "Status Summary" in field or "customfield_12320841" in field_id:
                for color in ("Red", "Yellow", "Green"):
                    from_has = color in (item.get("fromString") or "")
                    to_has = color in (item.get("toString") or "")
                    if from_has != to_has:
                        color_changed = True

    return bool(
        merged_prs or active_prs or status_changes
        or updated_desc or human_comments or color_changed
    )


def summarize(path: str, date_start: str | None = None) -> None:
    with open(path) as f:
        d = json.load(f)

    issue = d["issue"]
    desc = d["descendants"]
    prs = d.get("prs", [])
    changelog = d["changelog_in_range"]
    comments = d["comments_in_range"]

    # Header
    print(f"=== {issue['key']}: {issue['summary']} ===")
    print(f"Status: {issue['status']}")
    assignee = issue["assignee"]
    print(f"Assignee: {assignee['name']} ({assignee['email']})")
    print(f"Current Status Summary: {issue.get('current_status_summary') or 'None'}")
    print(f"Last Status Summary Update: {issue.get('last_status_summary_update') or 'None'}")
    print()

    # Descendants
    print(f"=== Descendants ({desc['total']} total, {desc['completion_pct']:.1f}% complete) ===")
    print(f"By status: {json.dumps(desc['by_status'], indent=2)}")
    updated = desc["updated_in_range"]
    print(f"Updated in range ({len(updated)}):")
    for u in updated:
        print(f"  {u['key']} - {u['status']} - {u['summary']}")
    print()

    # Changelog - formatted readably
    print(f"=== Changelog in range ({len(changelog)} entries) ===")
    for c in changelog:
        items_str = ", ".join(
            f"{i.get('field', '?')}: {i.get('fromString', '?')} -> {i.get('toString', '?')}"
            for i in c.get("items", [])
        )
        print(f"  {c['date'][:10]} by {c.get('author', '?')}: {items_str}")
    if not changelog:
        print("  (none)")
    print()

    # Comments (skip bots)
    human_comments = [c for c in comments if not c.get("is_bot")]
    print(f"=== Comments in range ({len(human_comments)} non-bot) ===")
    for c in human_comments:
        body = c["body"].replace("\r\n", " ").replace("\n", " ")[:300]
        author = c.get("author_name", c["author"])
        print(f"  {c['date'][:10]} {author}: {body}")
    if not human_comments:
        print("  (none)")
    print()

    # PRs - categorized
    active = [
        pr
        for pr in prs
        if pr.get("activity_summary", {}).get("commits_in_range", 0) > 0
        or pr.get("activity_summary", {}).get("reviews_in_range", 0) > 0
    ]

    # Merged this week: filter by date range start if available
    if date_start:
        merged_recent = [
            pr for pr in prs
            if pr["state"] == "MERGED"
            and (pr["dates"].get("merged_at") or "") >= date_start
        ]
    else:
        merged_recent = [pr for pr in prs if pr["state"] == "MERGED" and pr in active]

    open_prs = [pr for pr in prs if pr["state"] == "OPEN"]

    print(f"=== PRs ({len(prs)} total) ===")
    print(f"Active in range ({len(active)}):")
    for pr in active:
        act = pr.get("activity_summary", {})
        author = pr_author(pr)
        by = f" by {author}" if author else ""
        print(f"  #{pr['number']} ({pr['state']}, draft={pr.get('is_draft', False)}){by} - {pr['title']}")
        print(f"    commits: {act.get('commits_in_range', 0)}, reviews: {act.get('reviews_in_range', 0)}, review_comments: {act.get('review_comments_in_range', 0)}")
    if not active:
        print("  (none)")

    print(f"Merged this week ({len(merged_recent)}):")
    for pr in merged_recent:
        merged_date = (pr["dates"].get("merged_at") or "")[:10]
        author = pr_author(pr)
        by = f" by {author}" if author else ""
        print(f"  #{pr['number']} merged {merged_date}{by} - {pr['title']}")
    if not merged_recent:
        print("  (none)")

    print(f"Open ({len(open_prs)}):")
    for pr in open_prs:
        d_flag = " [DRAFT]" if pr.get("is_draft") else ""
        print(f"  #{pr['number']}{d_flag} - {pr['title']}")
    if not open_prs:
        print("  (none)")
    print()


def resolve_path(arg: str, date_dir: str | None) -> str:
    """Resolve an argument to a JSON file path.

    If arg looks like a file path (contains / or ends with .json), use it directly.
    Otherwise treat it as an issue key and combine with date_dir.
    """
    if "/" in arg or arg.endswith(".json"):
        return arg
    if not date_dir:
        print(f"Error: '{arg}' looks like an issue key but --date-dir was not provided.", file=sys.stderr)
        sys.exit(1)
    return os.path.join(date_dir, "issues", f"{arg}.json")


def extract_date_start(date_dir: str | None) -> str | None:
    """Try to read date_range.start from the manifest in the date directory."""
    if not date_dir:
        return None
    manifest = os.path.join(date_dir, "manifest.json")
    try:
        with open(manifest) as f:
            m = json.load(f)
        return m.get("config", {}).get("date_range", {}).get("start")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def parse_flag(args: list[str], flag: str) -> tuple[bool, list[str]]:
    """Remove a boolean flag from args, return (found, remaining_args)."""
    if flag in args:
        args = [a for a in args if a != flag]
        return True, args
    return False, args


def parse_option(args: list[str], flag: str) -> tuple[str | None, list[str]]:
    """Remove a --flag VALUE pair from args, return (value, remaining_args)."""
    if flag not in args:
        return None, args
    idx = args.index(flag)
    if idx + 1 >= len(args):
        print(f"Error: {flag} requires an argument", file=sys.stderr)
        sys.exit(1)
    value = args[idx + 1]
    args = args[:idx] + args[idx + 2:]
    return value, args


if __name__ == "__main__":
    args = sys.argv[1:]

    # Parse flags
    only_significant, args = parse_flag(args, "--only-significant")
    date_dir, args = parse_option(args, "--date-dir")
    label_filter, args = parse_option(args, "--label")

    if not args:
        print(f"Usage: {sys.argv[0]} <ISSUE-KEY|issue.json|issues-dir/> [...]  [--date-dir DIR] [--only-significant] [--label LABEL]", file=sys.stderr)
        print(f"Examples:", file=sys.stderr)
        print(f"  {sys.argv[0]} OCPSTRAT-1234 --date-dir .work/weekly-status/2026-03-11", file=sys.stderr)
        print(f"  {sys.argv[0]} .work/weekly-status/2026-03-11/issues/OCPSTRAT-1234.json", file=sys.stderr)
        print(f"  {sys.argv[0]} .work/weekly-status/2026-03-11/issues/ --only-significant --label control-plane-work", file=sys.stderr)
        sys.exit(1)

    # If a single arg is a directory, expand to all JSON files in it
    if len(args) == 1 and os.path.isdir(args[0]):
        dir_path = args[0]
        args = sorted(glob.glob(os.path.join(dir_path, "*.json")))
        if not date_dir:
            # Infer date_dir from directory path (parent of issues/)
            if dir_path.rstrip("/").endswith("/issues"):
                date_dir = os.path.dirname(dir_path.rstrip("/"))
            elif os.path.exists(os.path.join(dir_path, "..", "manifest.json")):
                date_dir = os.path.normpath(os.path.join(dir_path, ".."))

    date_start = extract_date_start(date_dir)

    # Also try to infer date_start from file path if not using --date-dir
    if not date_start and not date_dir:
        for arg in args:
            if "weekly-status/" in arg:
                inferred_dir = arg.split("/issues/")[0] if "/issues/" in arg else None
                if inferred_dir:
                    date_start = extract_date_start(inferred_dir)
                    break

    # When --only-significant, pre-filter files
    if only_significant:
        filtered = []
        for arg in args:
            path = resolve_path(arg, date_dir)
            try:
                with open(path) as f:
                    d = json.load(f)
                if is_significant(d):
                    filtered.append(arg)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
        skipped = len(args) - len(filtered)
        args = filtered
        print(f"=== Batch: {len(args)} significant issues ({skipped} skipped) ===\n")

    # When --label is set, separate issues missing the label
    unlabeled = []
    if label_filter:
        labeled = []
        for arg in args:
            path = resolve_path(arg, date_dir)
            try:
                with open(path) as f:
                    d = json.load(f)
                labels = d.get("issue", {}).get("labels", [])
                if label_filter in labels:
                    labeled.append(arg)
                else:
                    key = d["issue"]["key"]
                    summary = d["issue"]["summary"]
                    unlabeled.append({"arg": arg, "key": key, "summary": summary})
            except (FileNotFoundError, json.JSONDecodeError):
                labeled.append(arg)
        args = labeled
        if unlabeled:
            print(f"=== MISSING LABEL '{label_filter}' ({len(unlabeled)} issues) ===")
            print(f"These issues appeared as descendants but do not carry the '{label_filter}' label.")
            print(f"Confirm with the user whether to include them in the report.\n")
            for u in unlabeled:
                print(f"  {u['key']}: {u['summary']}")
            print()

    for i, arg in enumerate(args):
        if i > 0:
            print("=" * 80)
            print()
        path = resolve_path(arg, date_dir)
        summarize(path, date_start)
