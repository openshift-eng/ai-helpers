#!/usr/bin/env python3
"""
Parse test suite definitions from standard_suites.go
Extracts suite names and their filter qualifiers.
"""

import re
import sys
import json
from pathlib import Path


def parse_suites(filepath):
    """
    Parse standard_suites.go and extract suite definitions.

    Args:
        filepath: Path to standard_suites.go

    Returns:
        dict mapping suite names to their qualifiers
        Example: {
            "openshift/conformance/parallel": [
                "name.contains('[Suite:openshift/conformance/parallel')"
            ],
            "openshift/conformance/serial": [
                "name.contains('[Suite:openshift/conformance/serial')"
            ],
            "all": ["true"]
        }
    """
    suites = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match suite definitions
    # Looks for: Name: "suite-name", followed by Qualifiers: []string{...}
    # Handle multi-line definitions
    suite_pattern = r'Name:\s*"([^"]+)"[\s\S]*?Qualifiers:\s*\[\]string\{([^}]+)\}'

    for match in re.finditer(suite_pattern, content):
        suite_name = match.group(1)
        qualifiers_block = match.group(2)

        # Extract individual qualifier strings
        qualifier_pattern = r'"([^"]+)"'
        qualifiers = re.findall(qualifier_pattern, qualifiers_block)

        # Handle empty qualifiers (should default to "true")
        if not qualifiers:
            qualifiers = ["true"]

        suites[suite_name] = qualifiers

    return suites


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: parse_suites.py <origin-repo-path>", file=sys.stderr)
        print("", file=sys.stderr)
        print("Parses pkg/testsuites/standard_suites.go and extracts suite definitions.", file=sys.stderr)
        print("Outputs JSON mapping suite names to qualifier arrays.", file=sys.stderr)
        sys.exit(1)

    origin_path = Path(sys.argv[1])
    suites_file = origin_path / "pkg/testsuites/standard_suites.go"

    if not suites_file.exists():
        print(f"Error: Suite definitions not found: {suites_file}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Make sure you're pointing to the openshift/origin repository root.", file=sys.stderr)
        sys.exit(1)

    try:
        suites = parse_suites(suites_file)

        if not suites:
            print("Warning: No suite definitions found", file=sys.stderr)
            print("The parsing may have failed. Check standard_suites.go format.", file=sys.stderr)

        # Output as JSON
        print(json.dumps(suites, indent=2))

    except Exception as e:
        print(f"Error parsing suites file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
