#!/usr/bin/env python3
"""Validate a payload-results YAML file against the canonical schema."""

import sys
import yaml

REQUIRED_METADATA = ["payload_tag", "version", "stream", "architecture"]
REQUIRED_JOB_FIELDS = ["job_name", "failure_type", "root_cause_summary"]
REQUIRED_CANDIDATE_FIELDS = ["pr_url", "confidence_score", "failing_jobs"]
REQUIRED_RHCOS_SUSPECT_FIELDS = ["rhcos_tag", "package", "failing_jobs"]


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

    meta = data.get("metadata")
    if not isinstance(meta, dict):
        errors.append("'metadata' is not a mapping")
        meta = {}
    for field in REQUIRED_METADATA:
        if field not in meta:
            errors.append(f"metadata missing '{field}'")

    if "failing_jobs" not in data:
        errors.append("missing 'failing_jobs' key")
    elif not isinstance(data["failing_jobs"], list):
        errors.append("'failing_jobs' is not a list")
    else:
        for i, job in enumerate(data["failing_jobs"]):
            if not isinstance(job, dict):
                errors.append(f"failing_jobs[{i}] is not an object")
                continue
            for field in REQUIRED_JOB_FIELDS:
                if field not in job:
                    errors.append(f"failing_jobs[{i}] missing '{field}'")

    if "candidates" not in data:
        errors.append("missing 'candidates' key")
    elif not isinstance(data["candidates"], list):
        errors.append("'candidates' is not a list")
    else:
        for i, cand in enumerate(data["candidates"]):
            if not isinstance(cand, dict):
                errors.append(f"candidates[{i}] is not an object")
                continue
            for field in REQUIRED_CANDIDATE_FIELDS:
                if field not in cand:
                    errors.append(f"candidates[{i}] missing '{field}'")

    rhcos_suspects = data.get("rhcos_suspects")
    if rhcos_suspects is not None:
        if not isinstance(rhcos_suspects, list):
            errors.append("'rhcos_suspects' is not a list")
        else:
            for i, suspect in enumerate(rhcos_suspects):
                if not isinstance(suspect, dict):
                    errors.append(f"rhcos_suspects[{i}] is not an object")
                    continue
                for field in REQUIRED_RHCOS_SUSPECT_FIELDS:
                    if field not in suspect:
                        errors.append(
                            f"rhcos_suspects[{i}] missing '{field}'"
                        )

    if errors:
        print(f"FAIL: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1

    jobs = len(data.get("failing_jobs", []))
    cands = len(data.get("candidates", []))
    suspects = len(data.get("rhcos_suspects", []))
    parts = [f"{jobs} failing jobs", f"{cands} candidates"]
    if suspects:
        parts.append(f"{suspects} RHCOS suspects")
    print(f"OK: {', '.join(parts)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <payload-results-*.yaml>")
        sys.exit(2)
    sys.exit(validate(sys.argv[1]))
