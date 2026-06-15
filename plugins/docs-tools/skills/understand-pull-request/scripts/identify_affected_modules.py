#!/usr/bin/env python3
"""Map changed files from a PR to their modules and compute per-module change stats.

Reads PR metadata (changed_files) and detection data (module map) to identify
which modules are affected by the PR. Classifies modules as "epicenter" (>50%
of PR changes) or "touched".

Outputs JSON to stdout.

Usage:
    python3 identify_affected_modules.py --metadata pr-metadata.json --detection detection.json
"""

import argparse
import json
import os
import sys


def identify_affected_modules(metadata: dict, detection: dict) -> dict:
    changed_files = metadata.get("changed_files", [])
    modules = detection.get("modules", {})

    if not changed_files:
        return {
            "affected_modules": [],
            "unmatched_files": [],
            "total_modules_affected": 0,
            "total_files_changed": 0,
        }

    module_changes: dict[str, dict] = {}
    unmatched_files: list[str] = []

    total_pr_additions = sum(f.get("additions", 0) for f in changed_files)
    total_pr_deletions = sum(f.get("deletions", 0) for f in changed_files)
    total_pr_lines = total_pr_additions + total_pr_deletions

    for cf in changed_files:
        file_path = cf.get("path", "")
        matched = False

        for mod_name, mod_data in modules.items():
            mod_files = mod_data.get("files", [])
            norm_path = file_path.replace(os.sep, "/")
            norm_mod_files = [f.replace(os.sep, "/") for f in mod_files]

            if norm_path in norm_mod_files:
                matched = True
                if mod_name not in module_changes:
                    module_changes[mod_name] = {
                        "module": mod_name,
                        "files_changed": [],
                        "lines_added": 0,
                        "lines_deleted": 0,
                        "total_module_lines": mod_data.get("total_lines", 0),
                    }
                module_changes[mod_name]["files_changed"].append(file_path)
                module_changes[mod_name]["lines_added"] += cf.get("additions", 0)
                module_changes[mod_name]["lines_deleted"] += cf.get("deletions", 0)
                break

            mod_path = mod_data.get("path", mod_name).replace(os.sep, "/")
            if mod_path == "root":
                mod_path = ""

            if mod_path and norm_path.startswith(mod_path + "/"):
                matched = True
                if mod_name not in module_changes:
                    module_changes[mod_name] = {
                        "module": mod_name,
                        "files_changed": [],
                        "lines_added": 0,
                        "lines_deleted": 0,
                        "total_module_lines": mod_data.get("total_lines", 0),
                    }
                module_changes[mod_name]["files_changed"].append(file_path)
                module_changes[mod_name]["lines_added"] += cf.get("additions", 0)
                module_changes[mod_name]["lines_deleted"] += cf.get("deletions", 0)
                break

        if not matched:
            unmatched_files.append(file_path)

    affected = []
    for mod_name, mc in module_changes.items():
        total_mod_lines = mc["total_module_lines"]
        lines_changed = mc["lines_added"] + mc["lines_deleted"]

        pct_of_module = 0.0
        if total_mod_lines > 0:
            pct_of_module = round((lines_changed / total_mod_lines) * 100, 1)

        pct_of_pr = 0.0
        if total_pr_lines > 0:
            pct_of_pr = round((lines_changed / total_pr_lines) * 100, 1)

        classification = "epicenter" if pct_of_pr > 50 else "touched"

        affected.append(
            {
                "module": mod_name,
                "files_changed": mc["files_changed"],
                "lines_added": mc["lines_added"],
                "lines_deleted": mc["lines_deleted"],
                "total_module_lines": total_mod_lines,
                "pct_of_module_changed": pct_of_module,
                "pct_of_pr": pct_of_pr,
                "classification": classification,
            }
        )

    affected.sort(key=lambda m: m["lines_added"] + m["lines_deleted"], reverse=True)

    return {
        "affected_modules": affected,
        "unmatched_files": unmatched_files,
        "total_modules_affected": len(affected),
        "total_files_changed": len(changed_files),
    }


def main():
    parser = argparse.ArgumentParser(description="Identify modules affected by a PR")
    parser.add_argument("--metadata", required=True, help="Path to PR metadata JSON")
    parser.add_argument("--detection", required=True, help="Path to detection JSON")
    args = parser.parse_args()

    with open(args.metadata) as f:
        metadata = json.load(f)
    with open(args.detection) as f:
        detection = json.load(f)

    result = identify_affected_modules(metadata, detection)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
