#!/usr/bin/env python3
"""Tests for payload-autodl JSON validator."""

import json
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
        ("HyperShift identity without OCP coercion", f"{TESTDATA}/valid_hypershift.json", 0),
        ("invalid no table_name", f"{TESTDATA}/invalid_no_table_name.json", 1),
        ("invalid non-string values", f"{TESTDATA}/invalid_non_string_values.json", 1),
        ("invalid empty rows", f"{TESTDATA}/invalid_empty_rows.json", 1),
        ("invalid stream", f"{TESTDATA}/invalid_stream.json", 1),
        ("invalid version", f"{TESTDATA}/invalid_version.json", 1),
        ("empty stream", f"{TESTDATA}/empty_stream.json", 1),
        ("empty version", f"{TESTDATA}/empty_version.json", 1),
        ("file not found", f"{TESTDATA}/nonexistent.json", 1),
    ]

    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        f.write("{bad json")
        tmp_path = f.name
        cases.append(("invalid JSON syntax", tmp_path, 1))

    with tempfile.TemporaryDirectory() as directory:
        variants = [
            ("ci release minor", "ci", "4.22", "4.22.0-0.ci", 0),
            ("nightly rejects OCP patch version", "nightly", "4.22.0", "4.22.0-0.nightly", 1),
            ("ci rejects OCP patch version", "ci", "4.22.0", "4.22.0-0.ci", 1),
            ("HyperShift requires component patch version", "hypershift", "0.1", "hypershift", 1),
            ("stream typo", "nighlty", "4.22", "4.22.0-0.nightly", 1),
            ("unnormalized OKD stream", "okd-scos-nightly", "4.22", "4.22.0-0.okd-scos-nightly", 1),
            ("normalized OKD stream", "nightly", "4.22", "4.22.0-0.okd-scos-nightly", 0),
            ("custom controller stream is not an export group", "hypershift.v2", "0.1.87", "hypershift.v2", 1),
            ("custom stream retains HyperShift export group", "hypershift", "0.1.87", "hypershift.v2", 0),
        ]
        for index, (name, stream, version, stream_name, expected) in enumerate(variants):
            fixture_name = "valid_hypershift.json" if version.startswith("0.") else "valid.json"
            with open(os.path.join(TESTDATA, fixture_name)) as fixture:
                data = json.load(fixture)
            data["rows"][0].update(stream=stream, version=version, stream_name=stream_name)
            if fixture_name == "valid.json":
                data["rows"][0]["payload_tag"] = f"{stream_name}-2026-02-25-152806"
            path = os.path.join(directory, f"stream-{index}.json")
            with open(path, "w") as output:
                json.dump(data, output)
            cases.append((name, path, expected))

        for name, path, expected in cases:
            if test(name, path, expected):
                passed += 1
            else:
                failed += 1

    os.unlink(tmp_path)

    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)
