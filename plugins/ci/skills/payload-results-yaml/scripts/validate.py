#!/usr/bin/env python3
"""Validate a payload-results YAML file against the canonical schema."""

import sys
import yaml

REQUIRED_METADATA = ["payload_tag", "version", "stream", "architecture"]
REQUIRED_JOB_FIELDS = ["job_name", "failure_type", "root_cause_summary"]
REQUIRED_CANDIDATE_FIELDS = ["pr_url", "confidence_score", "failing_jobs"]


def validate(path):
    errors = []

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"FAIL: file not found: {path}")
        return 1
    except yaml.YAMLError as e:
        print(f"FAIL: invalid YAML: {e}")
        return 1

    if not isinstance(data, dict):
        print("FAIL: root is not a mapping")
        return 1

    meta = data.get("metadata", {})
    for field in REQUIRED_METADATA:
        if field not in meta:
            errors.append(f"metadata missing '{field}'")

    if "failing_jobs" not in data:
        errors.append("missing 'failing_jobs' key")
    elif not isinstance(data["failing_jobs"], list):
        errors.append("'failing_jobs' is not a list")
    else:
        for i, job in enumerate(data["failing_jobs"]):
            for field in REQUIRED_JOB_FIELDS:
                if field not in job:
                    errors.append(f"failing_jobs[{i}] missing '{field}'")

    if "candidates" not in data:
        errors.append("missing 'candidates' key")
    elif not isinstance(data["candidates"], list):
        errors.append("'candidates' is not a list")
    else:
        for i, cand in enumerate(data["candidates"]):
            for field in REQUIRED_CANDIDATE_FIELDS:
                if field not in cand:
                    errors.append(f"candidates[{i}] missing '{field}'")

    if errors:
        print(f"FAIL: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1

    jobs = len(data.get("failing_jobs", []))
    cands = len(data.get("candidates", []))
    print(f"OK: {jobs} failing jobs, {cands} candidates")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <payload-results-*.yaml>")
        sys.exit(2)
    sys.exit(validate(sys.argv[1]))
