#!/usr/bin/env python3
"""Validate a payload-results YAML file against the canonical schema."""

import sys
import yaml

REQUIRED_METADATA = ["payload_tag", "version", "stream", "architecture"]
REQUIRED_JOB_FIELDS = ["job_name", "failure_type", "root_cause_summary"]
REQUIRED_CANDIDATE_FIELDS = [
    "pr_url",
    "confidence_score",
    "revert_eligible",
    "revert_gates",
    "failing_jobs",
]
REQUIRED_REVERT_GATES = [
    "changed_path_executed",
    "full_causal_chain",
    "exact_signature_timing",
    "alternatives_excluded",
    "experiment_isolates_change",
]
REVERT_GATE_STATUSES = {"pass", "fail", "unknown"}
EXPERIMENT_GATE_STATUSES = REVERT_GATE_STATUSES | {"not_applicable"}
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
            confidence = cand.get("confidence_score")
            if not isinstance(confidence, int) or isinstance(confidence, bool):
                errors.append(
                    f"candidates[{i}].confidence_score is not an integer"
                )
            elif not 0 <= confidence <= 100:
                errors.append(
                    f"candidates[{i}].confidence_score must be between 0 and 100"
                )

            revert_eligible = cand.get("revert_eligible")
            if not isinstance(revert_eligible, bool):
                errors.append(
                    f"candidates[{i}].revert_eligible is not a boolean"
                )

            gates = cand.get("revert_gates")
            gates_authorize_revert = False
            if not isinstance(gates, dict):
                errors.append(f"candidates[{i}].revert_gates is not a mapping")
            else:
                missing_gates = [
                    gate for gate in REQUIRED_REVERT_GATES if gate not in gates
                ]
                extra_gates = [
                    gate for gate in gates if gate not in REQUIRED_REVERT_GATES
                ]
                for gate in missing_gates:
                    errors.append(
                        f"candidates[{i}].revert_gates missing '{gate}'"
                    )
                for gate in extra_gates:
                    errors.append(
                        f"candidates[{i}].revert_gates has unknown gate '{gate}'"
                    )
                gate_statuses = []
                for gate in REQUIRED_REVERT_GATES:
                    gate_data = gates.get(gate)
                    if not isinstance(gate_data, dict):
                        if gate in gates:
                            errors.append(
                                f"candidates[{i}].revert_gates.{gate} "
                                "is not a mapping"
                            )
                        continue
                    status = gate_data.get("status")
                    evidence = gate_data.get("evidence")
                    allowed_statuses = (
                        EXPERIMENT_GATE_STATUSES
                        if gate == "experiment_isolates_change"
                        else REVERT_GATE_STATUSES
                    )
                    if status not in allowed_statuses:
                        errors.append(
                            f"candidates[{i}].revert_gates.{gate}.status "
                            f"must be one of {sorted(allowed_statuses)}"
                        )
                    else:
                        gate_statuses.append(status)
                    if not isinstance(evidence, str) or not evidence.strip():
                        errors.append(
                            f"candidates[{i}].revert_gates.{gate}.evidence "
                            "must be a non-empty string"
                        )
                gates_authorize_revert = (
                    len(gate_statuses) == len(REQUIRED_REVERT_GATES)
                    and all(status == "pass" for status in gate_statuses[:4])
                    and gate_statuses[4] in {"pass", "not_applicable"}
                )

            expected_eligible = (
                isinstance(confidence, int)
                and not isinstance(confidence, bool)
                and confidence >= 85
                and gates_authorize_revert
            )
            if isinstance(revert_eligible, bool):
                if revert_eligible != expected_eligible:
                    errors.append(
                        f"candidates[{i}].revert_eligible must equal "
                        "(confidence_score >= 85, all core gates pass, and "
                        "the experiment gate passes or is not_applicable)"
                    )

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
