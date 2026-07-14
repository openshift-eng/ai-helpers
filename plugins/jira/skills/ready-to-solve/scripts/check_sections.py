#!/usr/bin/env python3
"""
Deterministic section checker for Jira issue readiness validation.

Reads a JSON object with a 'description' field from stdin and validates
that the issue description contains required sections with adequate content.

Usage:
    echo '{"description": "..."}' | python3 check_sections.py
    echo '{"description": "..."}' | python3 check_sections.py --verbose

Exit codes:
    0 - Checks completed (see JSON output for results)
    1 - Script error (bad input)
    2 - No description provided
"""

import argparse
import json
import re
import sys
from typing import List, Pattern, Tuple


CONTEXT_HEADINGS = ["Context", "Description", "Background", "Overview", "Why"]
AC_HEADINGS = ["Acceptance Criteria", "AC", "Definition of Done"]
TECH_HEADINGS = ["Technical Details", "Technical Context", "Implementation Details",
                 "Implementation Notes", "Technical Notes"]

HEADING_PATTERNS = [
    r"^h[1-6]\.\s+{heading}\s*$",          # Jira wiki: h2. Context
    r"^#{{1,6}}\s+{heading}\s*$",          # Markdown: ## Context
    r"^\*\*{heading}\*\*\s*$",              # Bold: **Context**
    r"^{heading}\s*:\s*$",                  # Colon: Context:
    r"^{heading}\s*$",                      # Plain heading on its own line
]

ANY_HEADING_RE = re.compile(
    r"^(?:h[1-6]\.\s+.+|#{1,6}\s+.+|\*\*.+\*\*)\s*$",
    re.MULTILINE,
)


def build_heading_regex(headings: List[str]) -> Pattern:
    parts = []
    for heading in headings:
        escaped = re.escape(heading)
        for pattern in HEADING_PATTERNS:
            parts.append(pattern.format(heading=escaped))
    return re.compile("|".join(parts), re.MULTILINE | re.IGNORECASE)


def find_section(text: str, headings: List[str]) -> Tuple[bool, str]:
    regex = build_heading_regex(headings)
    match = regex.search(text)
    if not match:
        return False, ""

    start = match.end()
    next_heading = ANY_HEADING_RE.search(text, start)
    end = next_heading.start() if next_heading else len(text)
    content = text[start:end].strip()
    return True, content


def count_list_items(text: str) -> int:
    patterns = [
        r"^\s*[\*\-]\s+",        # * item or - item
        r"^\s*#\s+",             # Jira wiki ordered: # item
        r"^\s*\d+[\.\)]\s+",    # 1. item or 1) item
    ]
    count = 0
    for line in text.splitlines():
        for pattern in patterns:
            if re.match(pattern, line):
                count += 1
                break
    return count


def make_check(check_id: str, name: str, severity: str, passed: bool,
               details: str, content: str = "") -> dict:
    result = {
        "id": check_id,
        "name": name,
        "severity": severity,
        "passed": passed,
        "details": details,
    }
    if content:
        result["content"] = content
    return result


def run_checks(description: str, verbose: bool = False) -> dict:
    checks = []

    ctx_found, ctx_content = find_section(description, CONTEXT_HEADINGS)
    ac_found, ac_content = find_section(description, AC_HEADINGS)
    tech_found, tech_content = find_section(description, TECH_HEADINGS)

    checks.append(make_check(
        "has_context", "Context section present", "REQUIRED",
        ctx_found,
        "Found context/description section" if ctx_found
        else "Missing section. Expected one of: " + ", ".join(CONTEXT_HEADINGS),
        ctx_content if verbose else "",
    ))

    checks.append(make_check(
        "has_ac", "Acceptance Criteria present", "REQUIRED",
        ac_found,
        "Found acceptance criteria section" if ac_found
        else "Missing section. Expected one of: " + ", ".join(AC_HEADINGS),
        ac_content if verbose else "",
    ))

    if ctx_found:
        ctx_len = len(ctx_content)
        checks.append(make_check(
            "context_not_empty", "Context has content", "REQUIRED",
            ctx_len >= 50,
            f"Context has {ctx_len} characters (minimum 50)"
            if ctx_len >= 50
            else f"Context too short: {ctx_len} characters (minimum 50)",
        ))
    else:
        checks.append(make_check(
            "context_not_empty", "Context has content", "REQUIRED",
            False, "Skipped: no context section found",
        ))

    if ac_found:
        ac_len = len(ac_content)
        checks.append(make_check(
            "ac_not_empty", "Acceptance Criteria has content", "REQUIRED",
            ac_len >= 30,
            f"AC has {ac_len} characters (minimum 30)"
            if ac_len >= 30
            else f"AC too short: {ac_len} characters (minimum 30)",
        ))
    else:
        checks.append(make_check(
            "ac_not_empty", "Acceptance Criteria has content", "REQUIRED",
            False, "Skipped: no AC section found",
        ))

    checks.append(make_check(
        "has_tech", "Technical Details present", "REQUIRED",
        tech_found,
        "Found technical details section" if tech_found
        else "Missing section. Expected one of: " + ", ".join(TECH_HEADINGS),
        tech_content if verbose else "",
    ))

    if tech_found:
        tech_len = len(tech_content)
        checks.append(make_check(
            "tech_not_empty", "Technical Details has content", "REQUIRED",
            tech_len >= 30,
            f"Technical Details has {tech_len} characters (minimum 30)"
            if tech_len >= 30
            else f"Technical Details too short: {tech_len} characters (minimum 30)",
        ))
    else:
        checks.append(make_check(
            "tech_not_empty", "Technical Details has content", "REQUIRED",
            False, "Skipped: no technical details section found",
        ))

    if ac_found:
        item_count = count_list_items(ac_content)
        checks.append(make_check(
            "ac_has_items", "AC has multiple items", "WARNING",
            item_count >= 2,
            f"AC has {item_count} list items (recommended minimum 2)"
            if item_count >= 2
            else f"AC has only {item_count} list item(s) (recommended minimum 2)",
        ))
    else:
        checks.append(make_check(
            "ac_has_items", "AC has multiple items", "WARNING",
            False, "Skipped: no AC section found",
        ))

    desc_len = len(description.strip())
    checks.append(make_check(
        "min_description_length", "Adequate overall length", "WARNING",
        desc_len >= 200,
        f"Description has {desc_len} characters (recommended minimum 200)"
        if desc_len >= 200
        else f"Description has only {desc_len} characters (recommended minimum 200)",
    ))

    required_checks = [c for c in checks if c["severity"] == "REQUIRED"]
    overall_pass = all(c["passed"] for c in required_checks)

    stats = {
        "total": len(checks),
        "passed": sum(1 for c in checks if c["passed"]),
        "failed": sum(1 for c in checks if not c["passed"] and c["severity"] == "REQUIRED"),
        "warnings": sum(1 for c in checks if not c["passed"] and c["severity"] == "WARNING"),
    }

    return {
        "overall_pass": overall_pass,
        "checks": checks,
        "stats": stats,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true",
                        help="Include matched section content in output")
    args = parser.parse_args()

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({
                "overall_pass": False,
                "checks": [],
                "stats": {"total": 0, "passed": 0, "failed": 0, "warnings": 0},
                "error": "No input provided on stdin",
            }))
            sys.exit(2)

        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stdout)
        sys.exit(1)

    description = data.get("description")
    if not description or not description.strip():
        print(json.dumps({
            "overall_pass": False,
            "checks": [
                make_check("has_description", "Issue has a description",
                           "REQUIRED", False,
                           "Issue description is empty or null"),
            ],
            "stats": {"total": 1, "passed": 0, "failed": 1, "warnings": 0},
        }))
        sys.exit(2)

    result = run_checks(description, verbose=args.verbose)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
