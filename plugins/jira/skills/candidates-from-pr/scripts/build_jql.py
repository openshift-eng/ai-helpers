#!/usr/bin/env python3
"""Build the JQL string for the candidate Jira search.

Reads a derive_filters.py JSON object on stdin and prints a JQL string on
stdout. Component clause and version clause are conditional; the
statusCategory exclusion is always included.

Usage:
    derive_filters.py ... | build_jql.py [--project OCPBUGS]
"""

from __future__ import annotations

import argparse
import json
import sys


def quote(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--project", default="OCPBUGS")
    args = p.parse_args()

    filters = json.load(sys.stdin)
    parts: list[str] = [f"project = {quote(args.project)}", "statusCategory != Done"]

    components = filters.get("components") or []
    if components:
        comps = ", ".join(quote(c) for c in components)
        parts.append(f"component in ({comps})")

    target_release = filters.get("target_release")
    if target_release and target_release.strip():
        parts.append(
            f'("Target Version" = {quote(target_release)} '
            f"OR fixVersion = {quote(target_release)})"
        )

    jql = " AND ".join(parts) + " ORDER BY updated DESC"
    sys.stdout.write(jql + "\n")


if __name__ == "__main__":
    main()
