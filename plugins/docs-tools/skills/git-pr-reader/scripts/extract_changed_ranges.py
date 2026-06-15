#!/usr/bin/env python3
"""
Extract changed line ranges from unified diff output.

Reads a unified diff from stdin and outputs JSON mapping each changed file
to its changed line ranges. Used by docs-review-style and docs-review-technical
to scope review agents to only changed content.

Usage:
    # Local mode (git diff)
    git diff main...HEAD -- file1.adoc file2.adoc | python3 extract_changed_ranges.py

    # PR mode (via git_pr_reader)
    python3 git_pr_reader.py diff <PR_URL> | python3 extract_changed_ranges.py

    # With context padding (adds N lines around each hunk)
    git diff main...HEAD | python3 extract_changed_ranges.py --context 3

Output format (JSON):
    {
      "modules/new-file.adoc": "new",
      "modules/modified-file.adoc": [[10, 15], [42, 48]]
    }

    - "new" means the entire file is new (all lines are in scope)
    - [[start, end], ...] are inclusive 1-based line ranges for modified files
"""

import argparse
import json
import re
import sys
from typing import Dict, List, Union


def parse_diff_linewise(diff_text: str, context: int = 0) -> Dict[str, Union[str, List[List[int]]]]:
    """
    Parse unified diff line-by-line to extract exact changed line numbers.

    This is more precise than hunk-level parsing — it tracks only lines
    that were actually added or modified ('+' lines), not context lines.

    Args:
        diff_text: Unified diff content.
        context: Number of lines to pad around each changed line.

    Returns:
        Dict mapping file paths to either "new" or list of [start, end] ranges.
    """
    result: Dict[str, Union[str, List[List[int]]]] = {}
    current_file = None
    is_new_file = False
    changed_lines: List[int] = []
    file_line = 0

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            # Flush previous file
            if current_file:
                if is_new_file:
                    result[current_file] = "new"
                elif changed_lines:
                    result[current_file] = _lines_to_ranges(changed_lines, context)

            match = re.search(r" b/(.+)$", line)
            current_file = match.group(1) if match else None
            is_new_file = False
            changed_lines = []
            file_line = 0
            continue

        if line.startswith("new file"):
            is_new_file = True
            continue

        if (
            line.startswith("---")
            or line.startswith("+++")
            or line.startswith("index")
            or line.startswith("deleted file")
        ):
            continue

        if line.startswith("@@") and current_file:
            match = re.search(r"\+(\d+)", line)
            if match:
                file_line = int(match.group(1)) - 1
            continue

        if current_file and not is_new_file:
            if line.startswith("-"):
                # Deleted line — doesn't exist in new file, skip
                continue
            elif line.startswith("+"):
                file_line += 1
                changed_lines.append(file_line)
            elif line.startswith(" ") or line == "":
                file_line += 1

    # Flush last file
    if current_file:
        if is_new_file:
            result[current_file] = "new"
        elif changed_lines:
            result[current_file] = _lines_to_ranges(changed_lines, context)

    return result


def _lines_to_ranges(lines: List[int], context: int = 0) -> List[List[int]]:
    """
    Collapse a sorted list of line numbers into [start, end] ranges,
    with optional context padding.
    """
    if not lines:
        return []

    ranges: List[List[int]] = []
    start = max(1, lines[0] - context)
    end = lines[0] + context

    for line_num in lines[1:]:
        padded_start = max(1, line_num - context)
        if padded_start <= end + 1:
            # Merge with current range
            end = line_num + context
        else:
            ranges.append([start, end])
            start = padded_start
            end = line_num + context

    ranges.append([start, end])
    return ranges


def main():
    parser = argparse.ArgumentParser(
        description="Extract changed line ranges from unified diff output."
    )
    parser.add_argument(
        "--context",
        "-C",
        type=int,
        default=3,
        help="Lines of context to include around each change (default: 3)",
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    args = parser.parse_args()

    diff_text = sys.stdin.read()
    if not diff_text.strip():
        result = {}
    else:
        result = parse_diff_linewise(diff_text, context=args.context)

    output = json.dumps(result, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
            f.write("\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
