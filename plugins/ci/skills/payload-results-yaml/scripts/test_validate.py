#!/usr/bin/env python3
"""Tests for payload-results YAML validator."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from validate import validate

TESTDATA = os.path.join(os.path.dirname(__file__), "testdata")


def test(name, path, expected_exit):
    result = validate(path)
    status = "PASS" if result == expected_exit else "FAIL"
    if status == "FAIL":
        print(f"  {status}: {name} (expected exit {expected_exit}, got {result})")
    else:
        print(f"  {status}: {name}")
    return status == "PASS"


if __name__ == "__main__":
    passed = 0
    failed = 0

    cases = [
        ("valid full schema", f"{TESTDATA}/valid.yaml", 0),
        ("valid no candidates", f"{TESTDATA}/valid_no_candidates.yaml", 0),
        ("invalid flat schema (no metadata wrapper)", f"{TESTDATA}/invalid_flat_schema.yaml", 1),
        ("invalid metadata is string", f"{TESTDATA}/invalid_metadata_string.yaml", 1),
        ("invalid missing job/candidate fields", f"{TESTDATA}/invalid_missing_job_fields.yaml", 1),
        ("file not found", f"{TESTDATA}/nonexistent.yaml", 1),
    ]

    # Test with a non-YAML file
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write("{{invalid yaml")
        cases.append(("invalid YAML syntax", f.name, 1))

    for name, path, expected in cases:
        if test(name, path, expected):
            passed += 1
        else:
            failed += 1

    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)
