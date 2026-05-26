#!/usr/bin/env python3
"""Generate a markdown classification report from classifications.json.

Usage: generate-report.py <classifications.json> <output.md>
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

JIRA_BASE_URL = "https://redhat.atlassian.net/browse"

ACTIVITY_TYPES = [
    "Associate Wellness & Development",
    "Incidents & Support",
    "Security & Compliance",
    "Quality / Stability / Reliability",
    "Future Sustainability",
    "Product / Portfolio Work",
]


def escape_md(text: str) -> str:
    """Escape pipe characters for markdown table cells."""
    return text.replace("|", "&#124;").replace("\n", " ").strip()


def generate_report(classifications: list) -> str:
    grouped = defaultdict(list)
    for entry in classifications:
        grouped[entry["activityType"]].append(entry)

    total = len(classifications)
    lines = []

    inherited = [e for e in classifications if e.get("reasoning", "").startswith("Inherited from ")]
    classified = [e for e in classifications if not e.get("reasoning", "").startswith("Inherited from ")]

    # Header
    lines.append("# Activity Type Classification Report")
    lines.append("")
    lines.append(f"**Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Total Issues**: {total} ({len(inherited)} inherited from parent, {len(classified)} classified)")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Activity Type | Count | Percentage |")
    lines.append("|---|---|---|")
    for at in ACTIVITY_TYPES:
        count = len(grouped.get(at, []))
        pct = round(count / total * 100) if total > 0 else 0
        lines.append(f"| {at} | {count} | {pct}% |")
    lines.append(f"| **Total** | **{total}** | **100%** |")
    lines.append("")

    # Per-type sections
    lines.append("## Classifications by Activity Type")
    lines.append("")
    for at in ACTIVITY_TYPES:
        entries = grouped.get(at, [])
        lines.append(f"### {at}")
        lines.append("")
        if not entries:
            lines.append("No issues classified in this category.")
            lines.append("")
            continue
        lines.append("| Issue | Summary | Confidence | Reasoning |")
        lines.append("|---|---|---|---|")
        for e in entries:
            key = e["key"]
            link = f"[{key}]({JIRA_BASE_URL}/{key})"
            summary = escape_md(e.get("summary", "")[:80])
            confidence = e.get("confidence", "Unknown")
            reasoning = escape_md(e.get("reasoning", "")[:120])
            lines.append(f"| {link} | {summary} | {confidence} | {reasoning} |")
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print("Usage: generate-report.py <classifications.json> <output.md>", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path) as f:
        classifications = json.load(f)

    report = generate_report(classifications)

    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report generated: {output_path}")
    print(f"Total issues: {len(classifications)}")


if __name__ == "__main__":
    main()
