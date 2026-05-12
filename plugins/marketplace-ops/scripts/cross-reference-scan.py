#!/usr/bin/env python3
"""
Scan for cross-references to items being removed.

Checks whether any item being removed is referenced by files NOT being removed.
Outputs JSON warnings.

Usage: cross-reference-scan.py --removals path1,path2,... [--repo-root .]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def grep_references(repo_root, pattern, exclude_dirs):
    refs = []
    plugins_dir = Path(repo_root) / "plugins"
    if not plugins_dir.is_dir():
        return refs

    for md_file in plugins_dir.rglob("*.md"):
        rel = str(md_file.relative_to(repo_root))
        if any(rel.startswith(d.rstrip("/")) for d in exclude_dirs):
            continue
        try:
            content = md_file.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if re.search(pattern, content):
            refs.append(rel)
    return refs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--removals", required=True)
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    removals = [p.strip() for p in args.removals.split(",") if p.strip()]
    warnings = []

    for removal in removals:
        parts = removal.strip("/").split("/")

        if len(parts) >= 2 and parts[0] == "plugins":
            plugin_name = parts[1]

            if len(parts) == 2 or (len(parts) == 3 and parts[2] == ""):
                patterns = [
                    re.escape(f"/{plugin_name}:"),
                    re.escape(f"plugins/{plugin_name}"),
                ]
            elif len(parts) >= 4 and parts[2] == "commands":
                item_name = parts[-1].replace(".md", "")
                patterns = [
                    re.escape(f"/{plugin_name}:{item_name}"),
                ]
            elif len(parts) >= 4 and parts[2] == "skills":
                skill_name = parts[3]
                patterns = [
                    re.escape(f"{plugin_name}:{skill_name}"),
                ]
            else:
                patterns = [
                    re.escape(removal.strip("/")),
                ]

            exclude = [removal]
            for pattern in patterns:
                refs = grep_references(args.repo_root, pattern, exclude)
                for ref in refs:
                    warnings.append({
                        "removed": removal,
                        "referenced_by": ref,
                        "pattern": pattern.replace("\\", ""),
                    })

    seen = set()
    unique = []
    for w in warnings:
        key = (w["removed"], w["referenced_by"])
        if key not in seen:
            seen.add(key)
            unique.append(w)

    print(json.dumps({"warnings": unique}, indent=2))


if __name__ == "__main__":
    main()
