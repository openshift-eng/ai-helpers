#!/usr/bin/env python3
"""Tests for payload-autodl JSON validator."""

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
        ("valid", f"{TESTDATA}/valid.json", 0),
        ("invalid no table_name", f"{TESTDATA}/invalid_no_table_name.json", 1),
        ("invalid non-string values", f"{TESTDATA}/invalid_non_string_values.json", 1),
        ("invalid empty rows", f"{TESTDATA}/invalid_empty_rows.json", 1),
        ("file not found", f"{TESTDATA}/nonexistent.json", 1),
    ]

    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        f.write("{bad json")
        tmp_path = f.name
        cases.append(("invalid JSON syntax", tmp_path, 1))

    for name, path, expected in cases:
        if test(name, path, expected):
            passed += 1
        else:
            failed += 1

    os.unlink(tmp_path)

    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)
