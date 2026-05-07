#!/usr/bin/env python3
"""Render the final report (text table or JSON passthrough).

Reads several intermediate JSON files and emits either a human-readable text
report or the canonical JSON payload to stdout.

Usage:
    render_report.py \
        --pr pr.json \
        --filters filters.json \
        --jql "<jql string>" \
        --explicit explicit.json \
        --candidates scored.json \
        [--rationales rationales.json] \
        [--format text|json]

`rationales.json` (optional) maps {"OCPBUGS-1234": "1-2 sentence rationale"}
produced by the skill caller. If absent, rationale defaults to a comma-joined
list of matched signal values.
"""

import argparse
import json
import sys
from datetime import datetime, timezone


COL_HEADERS = ["#", "Verdict", "Score", "Key", "Status", "Pri", "Assignee", "Summary", "Top signals"]


def load(path: str | None) -> object:
    if not path:
        return None
    with open(path) as f:
        return json.load(f)


def assignee_str(value: object) -> str:
    if not value:
        return "unassigned"
    if isinstance(value, dict):
        return value.get("display_name") or value.get("email") or value.get("name") or "unassigned"
    return str(value)


def truncate(value: str, length: int) -> str:
    value = (value or "").replace("\n", " ").strip()
    return value if len(value) <= length else value[: length - 1] + "…"


def signals_summary(matched: list[dict]) -> str:
    parts: list[str] = []
    for s in matched[:3]:
        t = s.get("type", "")
        v = s.get("value", "")
        parts.append(f"{t}={v}" if t else str(v))
    return "; ".join(parts)


def render_text(
    pr: dict,
    filters: dict,
    jql: str,
    explicit: list[dict],
    cands: list[dict],
    rationales: dict[str, str] | None,
) -> str:
    lines: list[str] = []
    lines.append(
        f"PR: {pr['org']}/{pr['repo']}#{pr['number']} — {pr.get('title','')}"
    )
    lines.append(
        f"Base ref: {pr.get('base_ref','')} → "
        f"target release {filters.get('target_release') or 'unknown'} "
        f"({filters.get('target_release_source','')})"
    )
    components = filters.get("components") or []
    if components:
        lines.append(
            f"Component(s): {', '.join(components)} ({filters.get('component_source','')})"
        )
    else:
        lines.append("Component(s): (none — JQL did not filter by component)")
    for w in filters.get("warnings") or []:
        lines.append(f"Warning: {w}")
    lines.append("")

    lines.append(f"Explicit references in PR ({len(explicit)}):")
    if explicit:
        for r in explicit:
            lines.append(
                f"  {r.get('key')} [{r.get('status','?')}, "
                f"target {r.get('target_release','?')}, "
                f"assignee: {assignee_str(r.get('assignee'))}] — {r.get('summary','')}"
            )
            if r.get("url"):
                lines.append(f"    {r['url']}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append(f"Candidate matches ({len(cands)}):")
    if cands:
        rows: list[list[str]] = [COL_HEADERS]
        for i, c in enumerate(cands, 1):
            rationale = (rationales or {}).get(c.get("key", ""))
            top = rationale or signals_summary(c.get("matched_signals") or [])
            rows.append([
                str(i),
                c.get("verdict", ""),
                str(c.get("score", "")),
                c.get("key", ""),
                c.get("status", ""),
                c.get("priority", ""),
                assignee_str(c.get("assignee")),
                truncate(c.get("summary", ""), 50),
                truncate(top, 60),
            ])
        widths = [max(len(r[i]) for r in rows) for i in range(len(COL_HEADERS))]
        sep = "+".join("-" * (w + 2) for w in widths)
        sep = f"+{sep}+"
        for idx, row in enumerate(rows):
            cells = " | ".join(c.ljust(widths[i]) for i, c in enumerate(row))
            lines.append(f"| {cells} |")
            if idx == 0:
                lines.append(sep)
        lines.append("")
        for c in cands:
            if c.get("url"):
                lines.append(f"  {c['key']}: {c['url']}")
    else:
        lines.append("  (none above min-score)")
    lines.append("")

    lines.append("JQL used:")
    lines.append(f"  {jql}")
    return "\n".join(lines) + "\n"


def render_json(
    pr: dict,
    filters: dict,
    jql: str,
    explicit: list[dict],
    cands: list[dict],
    rationales: dict[str, str] | None,
) -> str:
    for c in cands:
        rat = (rationales or {}).get(c.get("key", ""))
        if rat:
            c["rationale"] = rat

    payload = {
        "schema_version": "1.0",
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "command": "candidates-from-pr",
            "jql": jql,
        },
        "pr": {
            "url": pr.get("url"),
            "number": pr.get("number"),
            "title": pr.get("title"),
            "base_ref": pr.get("base_ref"),
            "head_ref": pr.get("head_ref"),
            "labels": pr.get("labels") or [],
            "files_changed": len(pr.get("files") or []),
        },
        "derived": {
            "components": filters.get("components") or [],
            "target_release": filters.get("target_release"),
            "component_source": filters.get("component_source"),
            "target_release_source": filters.get("target_release_source"),
        },
        "explicit_references": explicit,
        "candidates": cands,
    }
    return json.dumps(payload, indent=2) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pr", required=True)
    p.add_argument("--filters", required=True)
    p.add_argument("--jql", required=True)
    p.add_argument("--explicit", required=True)
    p.add_argument("--candidates", required=True)
    p.add_argument("--rationales", default=None)
    p.add_argument("--format", choices=("text", "json"), default="text")
    args = p.parse_args()

    pr = load(args.pr)
    filters = load(args.filters)
    explicit = load(args.explicit) or []
    cands = load(args.candidates) or []
    rationales = load(args.rationales) if args.rationales else None

    if args.format == "json":
        sys.stdout.write(render_json(pr, filters, args.jql, explicit, cands, rationales))
    else:
        sys.stdout.write(render_text(pr, filters, args.jql, explicit, cands, rationales))


if __name__ == "__main__":
    main()
