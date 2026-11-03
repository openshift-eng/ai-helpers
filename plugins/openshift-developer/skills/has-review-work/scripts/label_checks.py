#!/usr/bin/env python3
"""Map PR labels to synthetic FAILING_CHECKS entries for CI work.

Usage:
    gh pr view 1234 --repo org/repo --json labels | label_checks.py

Reads a `gh pr view --json labels` object from stdin and writes the JSON
array of synthetic check entries for mapped labels. has-review-work appends
these to FAILING_CHECKS; address-ci-failures runs this directly when it is
invoked without --failing-checks, so both use one mapping.
"""

from __future__ import annotations

import json
import sys
from typing import Any

# The bucket tells address-ci-failures what to do; the label/ prefix keeps
# names distinct from real check contexts.
LABEL_CHECKS: dict[str, dict[str, str]] = {
    "needs-rebase": {"name": "label/needs-rebase", "state": "LABEL", "bucket": "rebase", "link": ""},
}


def validate_labels(value: Any) -> list[dict]:
    if not isinstance(value, list) or any(
        not isinstance(label, dict) or not isinstance(label.get("name"), str) for label in value
    ):
        raise ValueError("PR metadata has invalid labels")
    return value


def label_checks(labels: list[dict]) -> list[dict]:
    names = {label["name"] for label in labels}
    return [dict(check) for label, check in LABEL_CHECKS.items() if label in names]


def main() -> int:
    try:
        metadata = json.load(sys.stdin)
        if not isinstance(metadata, dict):
            raise ValueError("Expected a gh pr view JSON object")
        checks = label_checks(validate_labels(metadata.get("labels")))
    except (ValueError, json.JSONDecodeError) as err:
        print(f"ERROR: cannot map PR labels: {err}", file=sys.stderr)
        return 1
    print(json.dumps(checks, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
