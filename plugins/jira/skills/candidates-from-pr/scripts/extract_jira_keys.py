#!/usr/bin/env python3
"""Extract explicitly referenced Jira keys from a PR.

Reads PR JSON (output of fetch_pr.py) on stdin, scans the title, body, branch
name, and each commit headline+body for keys matching a set of project
prefixes, and emits a deduplicated JSON array on stdout.

Usage:
    fetch_pr.py ... | extract_jira_keys.py [--projects OCPBUGS,SDN]

Output:
    [{"key": "OCPBUGS-1234", "sources": ["title", "commit:abcd1234"]}, ...]

The Jira keys are *not* validated here — the skill caller is expected to
validate via mcp__atlassian__jira_get_issue.
"""

import argparse
import json
import re
import sys

KEY_RE = re.compile(r"\b([A-Z][A-Z0-9_]+)-([0-9]+)\b")


def scan(text: str, source: str, projects: set[str]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for m in KEY_RE.finditer(text or ""):
        proj, num = m.group(1), m.group(2)
        if num == "0":
            continue
        if proj not in projects:
            continue
        found.append((f"{proj}-{num}", source))
    return found


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--projects",
        default="OCPBUGS",
        help="Comma-separated Jira project prefixes to recognize (default: OCPBUGS)",
    )
    args = p.parse_args()
    projects = {x.strip() for x in args.projects.split(",") if x.strip()}

    pr = json.load(sys.stdin)
    hits: dict[str, set[str]] = {}

    def add(matches: list[tuple[str, str]]) -> None:
        for key, src in matches:
            hits.setdefault(key, set()).add(src)

    add(scan(pr.get("title", ""), "title", projects))
    add(scan(pr.get("body", ""), "body", projects))
    add(scan(pr.get("head_ref", ""), "branch", projects))
    for c in pr.get("commits") or []:
        oid = (c.get("oid") or "")[:8]
        add(scan(c.get("headline", ""), f"commit:{oid}:headline", projects))
        add(scan(c.get("body", ""), f"commit:{oid}:body", projects))

    out = [{"key": k, "sources": sorted(hits[k])} for k in sorted(hits)]
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
