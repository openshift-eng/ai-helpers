#!/usr/bin/env python3
"""
Triage pre-gathered issue JSON files by activity and R/Y/G status.

Scans all issue files in a weekly-status directory and classifies them
as significant or skippable for feature update reports. Outputs a
structured summary with activity signals and R/Y/G color status.

Usage:
    python3 triage_issues.py .work/weekly-status/2026-03-04/issues/
    python3 triage_issues.py .work/weekly-status/2026-03-04/issues/ --json
"""

import json
import glob
import os
import sys


def parse_color(text: str | None) -> str | None:
    """Extract Red/Yellow/Green from status summary text."""
    if not text:
        return None
    # Handle both "* Color Status: Green" and "{color:#d04437}Red{color}"
    for color in ("Red", "Yellow", "Green"):
        if color in text:
            return color
    return None


def triage(data_dir: str) -> tuple[list[dict], list[dict]]:
    significant = []
    skipped = []

    for path in sorted(glob.glob(os.path.join(data_dir, "*.json"))):
        with open(path) as f:
            d = json.load(f)

        issue = d["issue"]
        key = issue["key"]
        summary = issue["summary"]
        status_summary = issue.get("current_status_summary", "")
        desc = d["descendants"]
        prs = d["prs"]
        changelog = d["changelog_in_range"]
        comments = d["comments_in_range"]
        human_comments = [c for c in comments if not c.get("is_bot")]

        color = parse_color(status_summary)

        # Check for color change in changelog
        color_changed = False
        old_color = None
        new_color = None
        for entry in changelog:
            for item in entry.get("items", []):
                field = item.get("field", "")
                field_id = str(item.get("fieldId", ""))
                if "Status Summary" in field or "customfield_12320841" in field_id:
                    oc = parse_color(item.get("fromString", ""))
                    nc = parse_color(item.get("toString", ""))
                    if oc != nc and oc is not None and nc is not None:
                        color_changed = True
                        old_color = oc
                        new_color = nc

        # Activity signals
        merged_prs = [
            pr
            for pr in prs
            if pr["state"] == "MERGED"
            and pr.get("activity_summary", {}).get("commits_in_range", 0) > 0
        ]
        active_prs = [
            pr
            for pr in prs
            if pr.get("activity_summary", {}).get("commits_in_range", 0) > 0
            or pr.get("activity_summary", {}).get("reviews_in_range", 0) > 0
        ]
        updated_desc = desc.get("updated_in_range", [])
        status_changes = [
            c
            for c in changelog
            if any(item.get("field") == "status" for item in c.get("items", []))
        ]

        has_activity = bool(
            merged_prs
            or active_prs
            or status_changes
            or updated_desc
            or human_comments
            or color_changed
        )

        record = {
            "key": key,
            "summary": summary,
            "color": color,
            "color_changed": color_changed,
            "old_color": old_color,
            "new_color": new_color,
            "has_activity": has_activity,
            "merged_prs": len(merged_prs),
            "active_prs": len(active_prs),
            "updated_desc": len(updated_desc),
            "human_comments": len(human_comments),
            "status_changes": len(status_changes),
            "completion": desc.get("completion_pct", 0),
            "total_desc": desc.get("total", 0),
            "status_summary_excerpt": (status_summary or "")[:200],
        }

        if has_activity:
            significant.append(record)
        else:
            skipped.append(record)

    return significant, skipped


def print_text(significant: list[dict], skipped: list[dict]) -> None:
    print(f"=== SIGNIFICANT ACTIVITY ({len(significant)} issues) ===\n")
    for r in significant:
        flags = []
        if r["color_changed"]:
            flags.append(f"COLOR_CHANGED ({r['old_color']}->{r['new_color']})")
        if r["color"] in ("Red", "Yellow"):
            flags.append(r["color"].upper())
        if r["merged_prs"]:
            flags.append(f"{r['merged_prs']} merged")
        if r["active_prs"]:
            flags.append(f"{r['active_prs']} active PRs")
        if r["updated_desc"]:
            flags.append(f"{r['updated_desc']} desc updated")
        if r["human_comments"]:
            flags.append(f"{r['human_comments']} comments")
        if r["status_changes"]:
            flags.append(f"{r['status_changes']} status changes")

        print(f"  {r['key']}: {r['summary'][:80]}")
        print(f"    Color: {r['color'] or 'None'} | Completion: {r['completion']}% | {' | '.join(flags)}")
        print()

    print(f"=== SKIPPED ({len(skipped)} issues) ===\n")
    for r in skipped:
        print(f"  {r['key']}: {r['summary'][:80]} [Color: {r['color'] or 'None'}]")


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <issues-dir> [--json]", file=sys.stderr)
        sys.exit(1)

    data_dir = sys.argv[1]
    json_mode = "--json" in sys.argv

    significant, skipped = triage(data_dir)

    if json_mode:
        print(json.dumps({"significant": significant, "skipped": skipped}, indent=2))
    else:
        print_text(significant, skipped)


if __name__ == "__main__":
    main()
