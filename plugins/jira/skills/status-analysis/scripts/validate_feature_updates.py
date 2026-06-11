#!/usr/bin/env python3
"""
Validate feature updates markdown and HTML output.

Checks:
  1. Generated markdown uses author names (from author_name fields)
     instead of raw GitHub logins.
  2. Generated HTML has proper UTF-8 charset declaration and DOCTYPE
     so that emoji (color circles) render correctly in browsers.

Usage:
    # Validate markdown for GitHub handles:
    python3 validate_feature_updates.py \
      --markdown /tmp/feature-updates.md \
      --data-dir .work/weekly-status/2026-03-04/issues/

    # Validate HTML encoding (run after markdown-to-HTML conversion):
    python3 validate_feature_updates.py \
      --html /tmp/feature-updates.html

    # Both at once:
    python3 validate_feature_updates.py \
      --markdown /tmp/feature-updates.md \
      --data-dir .work/weekly-status/2026-03-04/issues/ \
      --html /tmp/feature-updates.html

Exit codes:
    0: No violations found
    1: Violations detected
"""

import argparse
import json
import re
import sys
from pathlib import Path


def collect_authors_from_data(data_dir: Path) -> dict[str, str]:
    """Extract unique GitHub logins and their display names from issue JSON files.

    Returns a dict mapping login -> author_name.
    """
    authors: dict[str, str] = {}

    for json_file in sorted(data_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        prs = data.get("external_links", {}).get("github_prs", [])
        for pr in prs:
            for source_key in ("reviews_in_range", "review_comments_in_range", "commits_in_range"):
                for entry in pr.get(source_key, []):
                    login = entry.get("author", "")
                    name = entry.get("author_name", "")

                    # Skip emails (commits use email as author) and unknowns
                    if not login or "@" in login or login == "Unknown":
                        continue

                    # Prefer the longest/most complete name seen
                    if login not in authors or (name and len(name) > len(authors[login])):
                        authors[login] = name if name else login

    return authors


def find_handle_violations(markdown_text: str, authors: dict[str, str]) -> list[dict]:
    """Find GitHub handles used as standalone words in the markdown.

    Returns list of dicts with 'login', 'name', and 'occurrences' (count).
    """
    violations = []

    for login, name in sorted(authors.items()):
        # Word-boundary match to avoid false positives
        pattern = rf"\b{re.escape(login)}\b"
        matches = re.findall(pattern, markdown_text)
        if matches:
            # Suggest first name from the full name
            first_name = name.split()[0] if name and name != login else None
            violations.append({
                "login": login,
                "name": name,
                "first_name": first_name,
                "occurrences": len(matches),
            })

    return violations


def validate_html(html_path: Path) -> list[str]:
    """Validate that the HTML file has proper encoding for emoji rendering.

    Returns a list of error messages (empty if valid).
    """
    errors = []

    try:
        raw = html_path.read_bytes()
    except OSError as e:
        return [f"Cannot read HTML file: {e}"]

    # Check BOM or encoding declaration
    text = raw.decode("utf-8", errors="replace")

    # Must have DOCTYPE
    if "<!DOCTYPE" not in text.upper() and "<!doctype" not in text:
        errors.append("Missing <!DOCTYPE html> declaration")

    # Must have charset meta tag
    if 'charset="utf-8"' not in text.lower() and "charset=utf-8" not in text.lower():
        errors.append('Missing <meta charset="utf-8"> in <head>')

    # Check that emoji circles survived encoding (not mojibake)
    has_circles = any(c in text for c in "\U0001f7e2\U0001f7e1\U0001f534")  # 🟢🟡🔴
    has_mojibake = "Ã°" in text or "â" in text or "ðŸ" in text
    if has_mojibake:
        errors.append(
            "Mojibake detected: emoji circles are garbled "
            "(likely written without encoding='utf-8' or missing charset meta)"
        )
    elif not has_circles:
        # No circles at all — not necessarily an error, but worth noting
        pass

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate feature updates markdown and HTML output"
    )
    parser.add_argument(
        "--markdown",
        help="Path to the markdown file to validate for GitHub handles"
    )
    parser.add_argument(
        "--data-dir",
        help="Path to the issues data directory containing JSON files"
    )
    parser.add_argument(
        "--html",
        help="Path to the HTML file to validate for encoding"
    )
    args = parser.parse_args()

    if not args.markdown and not args.html:
        parser.error("At least one of --markdown or --html is required")

    failed = False

    # --- Markdown validation (GitHub handles) ---
    if args.markdown:
        markdown_path = Path(args.markdown)
        if not markdown_path.exists():
            print(f"Error: Markdown file not found: {markdown_path}", file=sys.stderr)
            sys.exit(2)

        if not args.data_dir:
            parser.error("--data-dir is required when using --markdown")

        data_dir = Path(args.data_dir)
        if not data_dir.exists():
            print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
            sys.exit(2)

        authors = collect_authors_from_data(data_dir)
        if not authors:
            print("No GitHub authors found in data files.")
        else:
            markdown_text = markdown_path.read_text()
            violations = find_handle_violations(markdown_text, authors)

            if not violations:
                print(f"OK: No GitHub handles found in {markdown_path.name} "
                      f"({len(authors)} authors checked)")
            else:
                failed = True
                total = sum(v["occurrences"] for v in violations)
                print(f"FAIL: {total} GitHub handle occurrence(s) found "
                      f"in {markdown_path.name}\n")
                for v in violations:
                    suggestion = ""
                    if v["first_name"] and v["first_name"] != v["login"]:
                        suggestion = (f' -> use "{v["first_name"]}" '
                                      f'(from "{v["name"]}")')
                    elif v["name"] and v["name"] != v["login"]:
                        suggestion = f' -> use first name from "{v["name"]}"'
                    print(f"  {v['login']} ({v['occurrences']}x){suggestion}")

    # --- HTML validation (encoding / charset) ---
    if args.html:
        html_path = Path(args.html)
        if not html_path.exists():
            print(f"Error: HTML file not found: {html_path}", file=sys.stderr)
            sys.exit(2)

        html_errors = validate_html(html_path)
        if html_errors:
            failed = True
            print(f"\nFAIL: HTML encoding issues in {html_path.name}:")
            for err in html_errors:
                print(f"  - {err}")
        else:
            print(f"OK: HTML encoding valid in {html_path.name}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
