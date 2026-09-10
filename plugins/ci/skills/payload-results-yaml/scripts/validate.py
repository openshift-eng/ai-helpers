#!/usr/bin/env python3
"""Validate a payload-results YAML file against the canonical schema."""

import sys
import yaml

REQUIRED_METADATA = ["payload_tag", "version", "stream", "architecture"]
REQUIRED_JOB_FIELDS = ["job_name", "failure_type", "root_cause_summary"]
REQUIRED_CANDIDATE_FIELDS = ["type", "confidence_score", "rationale", "failing_jobs", "actions"]
REQUIRED_CANDIDATE_FIELDS_BY_TYPE = {
    "pr": ["pr_url"],
    "rhcos_rpm": ["package", "rhcos_tag", "changelog_evidence"],
}
SHIP_STATUS_ACTIONS = {"pending", "created", "linked", "skipped"}
ESCAPE_OUTCOMES = {
    "coverage_gap", "signal_handling", "false_negative", "mixed", "unknown",
}
ESCAPE_REQUIRED_FIELDS = {
    "outcome", "summary", "relevant_presubmits", "factors", "merge",
    "recommendations", "limitations",
}
ESCAPE_FACTOR_TYPES = {
    "coverage_gap", "conditional_not_selected", "optional_signal",
    "did_not_run", "retry_masking", "override", "verification_bypass",
    "test_false_negative", "unknown",
}
ACTOR_KINDS = {"human", "chai", "automation", "unknown"}


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
            if "ship_status" not in job:
                continue
            ship_status = job["ship_status"]
            if ship_status is None:
                errors.append(
                    f"failing_jobs[{i}].ship_status must be an object "
                    f"(omit the key if unavailable, do not set null)"
                )
                continue
            if not isinstance(ship_status, dict):
                errors.append(f"failing_jobs[{i}].ship_status is not an object")
                continue
            action = ship_status.get("action")
            if not isinstance(action, str) or not action:
                errors.append(
                    f"failing_jobs[{i}].ship_status.action must be a non-empty "
                    f"string one of {sorted(SHIP_STATUS_ACTIONS)}, got {action!r}"
                )
            elif action not in SHIP_STATUS_ACTIONS:
                errors.append(
                    f"failing_jobs[{i}].ship_status.action must be one of "
                    f"{sorted(SHIP_STATUS_ACTIONS)}, got {action!r}"
                )

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
            cand_type = cand.get("type")
            if not isinstance(cand_type, str):
                if "type" in cand:
                    errors.append(f"candidates[{i}] has invalid type {cand_type!r}")
                continue
            if cand_type not in REQUIRED_CANDIDATE_FIELDS_BY_TYPE:
                if "type" in cand:
                    errors.append(
                        f"candidates[{i}] has unknown type '{cand_type}' "
                        f"(expected one of {sorted(REQUIRED_CANDIDATE_FIELDS_BY_TYPE)})"
                    )
                continue
            for field in REQUIRED_CANDIDATE_FIELDS_BY_TYPE[cand_type]:
                if field not in cand:
                    errors.append(
                        f"candidates[{i}] (type '{cand_type}') missing '{field}'"
                    )
            score = cand.get("confidence_score")
            if (
                cand_type == "pr"
                and isinstance(score, int)
                and score >= 85
                and "escape_analysis" not in cand
            ):
                errors.append(
                    f"candidates[{i}] (high-confidence PR) missing "
                    "'escape_analysis'"
                )
            if "escape_analysis" in cand:
                _validate_escape_analysis(cand["escape_analysis"], i, errors)

    if errors:
        print(f"FAIL: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1

    jobs = len(data.get("failing_jobs", []))
    candidates = data.get("candidates", [])
    rhcos_rpm_cands = sum(1 for c in candidates if c.get("type") == "rhcos_rpm")
    parts = [f"{jobs} failing jobs", f"{len(candidates)} candidates"]
    if rhcos_rpm_cands:
        parts.append(f"{rhcos_rpm_cands} RHCOS RPM candidates")
    print(f"OK: {', '.join(parts)}")
    return 0


def _validate_escape_analysis(escape, candidate_index, errors):
    prefix = f"candidates[{candidate_index}].escape_analysis"
    if not isinstance(escape, dict):
        errors.append(f"{prefix} is not an object")
        return
    for field in sorted(ESCAPE_REQUIRED_FIELDS):
        if field not in escape:
            errors.append(f"{prefix} missing '{field}'")
    outcome = escape.get("outcome")
    if outcome not in ESCAPE_OUTCOMES:
        errors.append(
            f"{prefix}.outcome must be one of {sorted(ESCAPE_OUTCOMES)}, "
            f"got {outcome!r}"
        )
    for field in ("relevant_presubmits", "factors", "recommendations", "limitations"):
        if field in escape and not isinstance(escape[field], list):
            errors.append(f"{prefix}.{field} is not a list")
    for index, factor in enumerate(escape.get("factors", [])):
        factor_prefix = f"{prefix}.factors[{index}]"
        if not isinstance(factor, dict):
            errors.append(f"{factor_prefix} is not an object")
            continue
        if factor.get("type") not in ESCAPE_FACTOR_TYPES:
            errors.append(
                f"{factor_prefix}.type must be one of "
                f"{sorted(ESCAPE_FACTOR_TYPES)}, got {factor.get('type')!r}"
            )
        if not factor.get("evidence"):
            errors.append(f"{factor_prefix}.evidence is required")
        if "actor_kind" in factor and factor["actor_kind"] not in ACTOR_KINDS:
            errors.append(
                f"{factor_prefix}.actor_kind must be one of "
                f"{sorted(ACTOR_KINDS)}, got {factor['actor_kind']!r}"
            )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <payload-results-*.yaml>")
        sys.exit(2)
    sys.exit(validate(sys.argv[1]))
