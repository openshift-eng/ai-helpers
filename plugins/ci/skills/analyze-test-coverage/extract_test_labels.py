#!/usr/bin/env python3
"""
Extract Ginkgo test labels from Go test files.
Handles various Ginkgo test description formats.
"""

import re
import sys
from pathlib import Path


def extract_labels_from_line(line):
    """
    Extract all [Label] tags from a test description.

    Args:
        line: A line from a Go test file

    Returns:
        List of label strings (without brackets)
    """
    # Match patterns like: [sig-cli], [Suite:openshift/conformance/parallel]
    pattern = r'\[([^\]]+)\]'
    matches = re.findall(pattern, line)
    return matches


def extract_from_file(filepath):
    """
    Extract all unique labels from a test file.

    Args:
        filepath: Path to Go test file

    Returns:
        Set of unique label strings
    """
    labels = set()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                # Look for Ginkgo test descriptions
                # Patterns: g.It("...", ...), It("...", ...), g.Describe("...", ...)
                if re.search(r'\b(It|g\.It|Describe|g\.Describe|Context|g\.Context|Specify|g\.Specify)\s*\(', line):
                    found_labels = extract_labels_from_line(line)
                    labels.update(found_labels)
    except Exception as e:
        print(f"Error reading file {filepath}: {e}", file=sys.stderr)
        return set()

    return labels


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: extract_test_labels.py <test-file.go>", file=sys.stderr)
        print("", file=sys.stderr)
        print("Extracts Ginkgo test labels from Go test files.", file=sys.stderr)
        print("Outputs one label per line (without brackets).", file=sys.stderr)
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    labels = extract_from_file(filepath)

    if not labels:
        print("Warning: No test labels found", file=sys.stderr)
        print("Make sure test descriptions include labels like [sig-cli]", file=sys.stderr)

    # Output one label per line, sorted
    for label in sorted(labels):
        print(label)


if __name__ == '__main__':
    main()
