#!/usr/bin/env python3
"""Select healthy payloads and deterministically rank informing job cohorts."""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

TERMINAL = {"SUCCEEDED", "FAILED"}
NONTERMINAL = {"RUNNING", "ABORTED"}


class RankingError(Exception):
    pass


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise RankingError("cannot read %s: %s" % (path, exc)) from exc


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def fraction(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def stable_id(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]


def load_decisions(path):
    if not path:
        return {}
    value = read_json(Path(path))
    items = value.get("payload_decisions") if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise RankingError("shared-failure decisions must be a list or payload_decisions object")
    decisions = {}
    for item in items:
        if not isinstance(item, dict) or not item.get("payload_id"):
            raise RankingError("each decision needs payload_id")
        classification = item.get("classification")
        if classification not in ("CONFIRMED_SHARED_FAILURE", "NO_SHARED_FAILURE", "UNCERTAIN"):
            raise RankingError("invalid shared-failure classification")
        if classification == "CONFIRMED_SHARED_FAILURE" and not item.get("evidence"):
            raise RankingError("confirmed shared failures need evidence")
        decisions[str(item["payload_id"])] = item
    return decisions


def load_mappings(path, current_ids, historical_ids):
    if not path:
        return []
    value = read_json(Path(path))
    items = value.get("cross_release_mappings") if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise RankingError("cross-release mappings must be a list or cross_release_mappings object")
    for item in items:
        if not isinstance(item, dict):
            raise RankingError("cross-release mapping must be an object")
        if item.get("current_cohort_id") not in current_ids:
            raise RankingError("mapping refers to unknown current cohort")
        if item.get("previous_cohort_id") not in historical_ids:
            raise RankingError("mapping refers to unknown previous-release cohort")
        if item.get("confidence") not in ("LOW", "MEDIUM", "HIGH"):
            raise RankingError("mapping confidence must be LOW, MEDIUM, or HIGH")
        if not item.get("equivalence_evidence") or "known_configuration_changes" not in item:
            raise RankingError("mapping needs equivalence evidence and known configuration changes")
    return items


def health_decision(payload, threshold, shared):
    reasons, evidence = [], []
    blockers = payload.get("outcome_counts", {}).get("blocking", {})
    succeeded = blockers.get("Succeeded", 0)
    failed = blockers.get("Failed", 0)
    terminal = succeeded + failed
    other = sum(blockers.values()) - terminal
    health = fraction(succeeded, terminal)
    if not payload.get("inventory_complete"):
        reasons.append("INCOMPLETE_INVENTORY")
    if other:
        reasons.append("NONTERMINAL_RESULTS")
    if not terminal:
        reasons.append("HEALTH_CHECK_UNCERTAIN")
        evidence.append("No terminal blocker rows; blocker health is undefined")
    elif health["value"] < threshold:
        reasons.append("LOW_BLOCKER_HEALTH")
        evidence.append("%d/%d blockers succeeded; threshold is %.3f" % (succeeded, terminal, threshold))
    phase = payload.get("phase")
    if phase in ("Pending", "Ready", "Running", "") or phase is None:
        if "NONTERMINAL_RESULTS" not in reasons:
            reasons.append("NONTERMINAL_RESULTS")
    review = shared.get(str(payload.get("id")))
    if review:
        evidence.extend(review.get("evidence", []))
        if review["classification"] == "CONFIRMED_SHARED_FAILURE":
            reasons.append("CONFIRMED_SHARED_FAILURE")
        elif review["classification"] == "UNCERTAIN":
            reasons.append("HEALTH_CHECK_UNCERTAIN")
    eligible = not reasons
    return eligible, sorted(set(reasons)), evidence, health


def route_key(route):
    route = route or {}
    return (bool(route.get("upgrade")), route.get("from") or "", route.get("to") or "")


def identity(association):
    job = association.get("actual_prow_job") or association.get("provisional_prow_job")
    state = "RESOLVED" if association.get("actual_prow_job") else "PROVISIONAL"
    basis = {
        "population_role": association.get("population_role"),
        "prow_job": job,
        "alias": association.get("raw_alias") if not job else None,
        "upgrade_route": route_key(association.get("upgrade_route")),
    }
    return stable_id(basis), state, job


def outcome_counts(rows):
    counts = Counter(row.get("normalized_outcome") or "OTHER" for row in rows)
    return {name.lower(): counts.get(name, 0) for name in
            ("SUCCEEDED", "FAILED", "ABORTED", "RUNNING", "OTHER")}


def terminal_metric(rows):
    successes = sum(row.get("normalized_outcome") == "SUCCEEDED" for row in rows)
    failures = sum(row.get("normalized_outcome") == "FAILED" for row in rows)
    return fraction(successes, successes + failures)


def newest_payload_rows(rows, payload_by_id, limit=3):
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row["payload_id"])].append(row)
    ordered = sorted(grouped, key=lambda item: payload_by_id[item].get("release_time") or "", reverse=True)
    return [item for payload_id in ordered[:limit] for item in grouped[payload_id]]


def failure_streak(rows, payload_by_id):
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row["payload_id"])].append(row)
    ordered = sorted(grouped, key=lambda item: payload_by_id[item].get("release_time") or "", reverse=True)
    streak = 0
    for payload_id in ordered:
        outcomes = {row.get("normalized_outcome") for row in grouped[payload_id]}
        if "SUCCEEDED" in outcomes:
            break
        if "FAILED" in outcomes:
            streak += 1
        else:
            break
    return streak


def cohort_record(cohort_id, rows, payload_by_id, settings):
    associations = list(rows)
    unique_groups = defaultdict(list)
    missing_run_rows = []
    for row in rows:
        run_id = row.get("prow_run_id")
        if run_id:
            unique_groups[str(run_id)].append(row)
        else:
            missing_run_rows.append(row)
    unique, conflicting_runs = {}, []
    for run_id, run_rows in unique_groups.items():
        outcomes = {row.get("normalized_outcome") for row in run_rows}
        representative = dict(run_rows[0])
        if "SUCCEEDED" in outcomes and "FAILED" in outcomes:
            representative["normalized_outcome"] = "OTHER"
            conflicting_runs.append(run_id)
        unique[run_id] = representative
    unique_rows = list(unique.values())
    assoc_metric = terminal_metric(associations)
    run_metric = terminal_metric(unique_rows)
    payload_ids = sorted({str(row["payload_id"]) for row in associations})
    terminal_payloads = {str(row["payload_id"]) for row in associations
                         if row.get("normalized_outcome") in TERMINAL}
    terminal_runs = sum(row.get("normalized_outcome") in TERMINAL for row in unique_rows)
    sufficient = terminal_runs >= settings["min_job_runs"] and len(terminal_payloads) >= settings["min_job_payloads"]
    recent_rows = newest_payload_rows(associations, payload_by_id)
    sample = associations[0]
    aliases = sorted({row.get("raw_alias") for row in associations if row.get("raw_alias")})
    actual = sorted({row.get("actual_prow_job") for row in associations if row.get("actual_prow_job")})
    provisional = sorted({row.get("provisional_prow_job") for row in associations if row.get("provisional_prow_job")})
    pass_times = [payload_by_id[str(row["payload_id"])].get("release_time") for row in associations
                  if row.get("normalized_outcome") == "SUCCEEDED"]
    record = {
        "schema_version": 1,
        "cohort_id": cohort_id,
        "population_role": sample.get("population_role"),
        "release": sample.get("release"),
        "architecture": sample.get("architecture"),
        "stream": sample.get("stream"),
        "identity_state": "RESOLVED" if actual and len(actual) == 1 else "PROVISIONAL",
        "verification_aliases": aliases,
        "actual_prow_jobs": actual,
        "provisional_prow_jobs": provisional,
        "upgrade_route": sample.get("upgrade_route"),
        "payload_ids": payload_ids,
        "association_ids": [row.get("association_id") for row in associations],
        "run_ids": sorted(unique),
        "metrics": {
            "association_success": assoc_metric,
            "unique_run_success": run_metric,
            "payload_exposures": len(payload_ids),
            "terminal_payload_exposures": len(terminal_payloads),
            "distinct_runs": len(unique_rows),
            "terminal_runs": terminal_runs,
            "missing_run_identity_associations": len(missing_run_rows),
            "conflicting_run_outcomes": sorted(conflicting_runs),
            "outcomes": outcome_counts(associations),
            "last_pass": max((item for item in pass_times if item), default=None),
            "consecutive_failing_payloads": failure_streak(associations, payload_by_id),
            "retry_history_available": False,
        },
        "recent_three_exposures": {
            "payload_ids": sorted({str(row["payload_id"]) for row in recent_rows}),
            "association_success": terminal_metric(recent_rows),
            "outcomes": outcome_counts(recent_rows),
        },
        "sample_sufficient": sufficient,
        "sample_requirements": {"min_terminal_runs": settings["min_job_runs"],
                                "min_payload_exposures": settings["min_job_payloads"]},
        "execution_phase": "UNKNOWN",
        "signature_ids": [],
        "investigation_state": "PENDING",
        "disposition": "PENDING",
    }
    value = run_metric["value"]
    fail_rate = 1 - value if value is not None else -1
    streak = record["metrics"]["consecutive_failing_payloads"]
    failures = record["metrics"]["outcomes"]["failed"]
    if sufficient and value == 0:
        rank_key = [0, -failures, -len(terminal_payloads), cohort_id]
        tier = "ADEQUATE_ZERO_PASS"
    elif sufficient and value is not None and value < settings["poor_job_pass_rate"]:
        rank_key = [1, value, -streak, -terminal_runs, cohort_id]
        tier = "ADEQUATE_POOR"
    elif sufficient:
        rank_key = [2, value if value is not None else 2, cohort_id]
        tier = "ADEQUATE_REMAINING"
    else:
        rank_key = [3, -fail_rate, -terminal_runs, cohort_id]
        tier = "SPARSE"
    record["ranking"] = {"tier": tier, "sort_key": rank_key}
    return record


def rank_population(associations, payload_by_id, settings):
    cohorts = defaultdict(list)
    for row in associations:
        if row.get("normalized_role") != "INFORMING":
            continue
        cohort_id, _, _ = identity(row)
        cohorts[cohort_id].append(row)
    records = [cohort_record(key, rows, payload_by_id, settings) for key, rows in cohorts.items()]
    records.sort(key=lambda item: tuple(item["ranking"]["sort_key"]))
    for index, record in enumerate(records, 1):
        record["rank"] = index
    return records


def run(workspace, decisions_path=None, mappings_path=None):
    workspace = Path(workspace)
    manifest = read_json(workspace / "manifest.json")
    payload_doc = read_json(workspace / "payloads.json")
    assoc_doc = read_json(workspace / "associations.json")
    payloads = payload_doc.get("payloads")
    associations = assoc_doc.get("associations")
    if not isinstance(payloads, list) or not isinstance(associations, list):
        raise RankingError("collector outputs have invalid shapes")
    settings = manifest["effective_inputs"]
    shared = load_decisions(decisions_path)
    eligible_by_role = defaultdict(list)
    for payload in payloads:
        eligible, reasons, evidence, blocker_rate = health_decision(
            payload, settings["min_blocker_pass_rate"], shared)
        payload["eligibility"] = "ELIGIBLE" if eligible else "EXCLUDED"
        payload["reason_codes"] = reasons
        payload["evidence"] = evidence
        payload["blocker_success"] = blocker_rate
        if eligible:
            eligible_by_role[payload["population_role"]].append(payload)
    for values in eligible_by_role.values():
        values.sort(key=lambda item: item.get("release_time") or "", reverse=True)
    selected = eligible_by_role["current"][:settings["healthy_payloads"]]
    remaining = max(0, settings["healthy_payloads"] - len(selected))
    selected += eligible_by_role["previous-release-history"][:remaining]
    selected_ids = {str(payload["id"]) for payload in selected}
    for payload in payloads:
        payload["selected"] = str(payload["id"]) in selected_ids
        if payload["eligibility"] == "ELIGIBLE" and not payload["selected"]:
            payload["eligibility"] = "ELIGIBLE_NOT_SELECTED_LIMIT"
    selected_associations = [row for row in associations if str(row.get("payload_id")) in selected_ids]
    payload_by_id = {str(payload["id"]): payload for payload in payloads}
    current = rank_population([row for row in selected_associations if row.get("population_role") == "current"],
                              payload_by_id, settings)
    historical = rank_population([row for row in selected_associations
                                  if row.get("population_role") == "previous-release-history"],
                                 payload_by_id, settings)
    mappings = load_mappings(mappings_path, {item["cohort_id"] for item in current},
                             {item["cohort_id"] for item in historical})
    rankings = {
        "schema_version": 1,
        "analysis_id": manifest["analysis_id"],
        "selection_version": manifest.get("selection_version", 0) + 1,
        "ordering": [
            "adequately sampled zero-pass: failing runs desc, payloads desc",
            "adequately sampled poor: success asc, failure streak desc, terminal runs desc",
            "remaining adequate: success asc",
            "sparse: observed failure rate desc, terminal runs desc",
            "stable cohort ID breaks ties",
        ],
        "current": current,
        "previous_release_history": historical,
        "cross_release_mappings": mappings,
        "mapping_status": ("reviewed mappings supplied" if mappings else
                           "AI review required; no mapping inferred from names"),
    }
    prior = {"version": manifest.get("selection_version", 0),
             "selected_payload_ids": manifest.get("selected_payload_ids", []),
             "recorded_at": manifest.get("ranked_at") or manifest.get("collected_at")}
    manifest.setdefault("selection_history", []).append(prior)
    manifest["selection_version"] = rankings["selection_version"]
    manifest["selected_payload_ids"] = sorted(selected_ids)
    manifest["stage"] = "RANKED"
    manifest["ranked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest["counts"].update({
        "eligible_current_payloads": len(eligible_by_role["current"]),
        "eligible_historical_payloads": len(eligible_by_role["previous-release-history"]),
        "selected_payloads": len(selected),
        "current_job_cohorts": len(current),
        "historical_job_cohorts": len(historical),
    })
    if len(eligible_by_role["current"]) < settings["min_healthy_payloads"] and not historical:
        manifest["missing_evidence"].append("minimum healthy current payload population not met and no usable predecessor cohort selected")
    write_json(workspace / "payloads.json", {"schema_version": 1, "payloads": payloads})
    write_json(workspace / "job-rankings.json", rankings)
    write_json(workspace / "manifest.json", manifest)
    return rankings, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--shared-failure-decisions")
    parser.add_argument("--cross-release-mappings")
    args = parser.parse_args(argv)
    try:
        rankings, manifest = run(args.workspace, args.shared_failure_decisions,
                                 args.cross_release_mappings)
        print(json.dumps({"analysis_id": manifest["analysis_id"], "selection_version": manifest["selection_version"],
                          "current_cohorts": len(rankings["current"]),
                          "historical_cohorts": len(rankings["previous_release_history"])}, indent=2))
        return 0
    except (RankingError, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
