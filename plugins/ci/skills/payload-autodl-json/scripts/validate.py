#!/usr/bin/env python3
"""Validate a payload-analysis autodl JSON file against the canonical schema."""

import json
import re
import sys

REQUIRED_ROW_FIELDS = [
    "payload_tag", "version", "stream", "architecture", "phase",
    "job_name", "prow_url", "failure_type", "root_cause_summary",
]

VALID_STREAMS = {"ci", "nightly"}
VERSION_RE = re.compile(r"^\d+\.\d+$")


def validate(path):
    errors = []

    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"FAIL: file not found: {path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON: {e}")
        return 1

    if not isinstance(data, dict):
        print("FAIL: root is not an object")
        return 1

    if "table_name" not in data:
        errors.append("missing 'table_name'")

    if "schema" not in data or not isinstance(data.get("schema"), dict):
        errors.append("missing or invalid 'schema'")

    rows = data.get("rows", [])
    if not isinstance(rows, list):
        errors.append("'rows' is not an array")
    elif len(rows) == 0:
        errors.append("'rows' is empty")
    else:
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"rows[{i}] is not an object")
                continue
            for field in REQUIRED_ROW_FIELDS:
                if field not in row:
                    errors.append(f"rows[{i}] missing '{field}'")
            non_string = [k for k, v in row.items() if not isinstance(v, str)]
            if non_string:
                errors.append(f"rows[{i}] has non-string values: {', '.join(non_string)}")
            stream = row.get("stream")
            if isinstance(stream, str) and stream not in VALID_STREAMS:
                errors.append(f"rows[{i}] invalid stream '{stream}' (must be 'ci' or 'nightly')")
            version = row.get("version")
            if isinstance(version, str) and not VERSION_RE.fullmatch(version):
                errors.append(f"rows[{i}] invalid version '{version}' (must be 'X.Y')")

    if errors:
        print(f"FAIL: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: {len(rows)} rows, table_name={data.get('table_name')}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <*-autodl.json>")
        sys.exit(2)
    sys.exit(validate(sys.argv[1]))
