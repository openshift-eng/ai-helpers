#!/usr/bin/env python3
"""Extract the title from a requirements markdown file.

Reads the file at the given path, finds the first level-1 markdown heading,
strips ticket-ID prefixes, truncates to 80 characters, and emits JSON to stdout.

Usage: parse_title.py <file-path>

Output (stdout): {"title": "..."}
Errors go to stderr; exits non-zero on failure.
"""

import json
import re
import sys


def extract_title(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                heading = stripped.lstrip("#").strip()
                heading = re.sub(r"^\[?[A-Z][A-Z0-9]+-\d+\]?\s*[:\-]?\s*", "", heading)
                return heading[:80] if heading else None
    return None


def main():
    if len(sys.argv) != 2:
        print("Usage: parse_title.py <file-path>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    try:
        title = extract_title(path)
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if title is None:
        title = "Requirements Analysis"

    json.dump({"title": title}, sys.stdout)
    print()


if __name__ == "__main__":
    main()
