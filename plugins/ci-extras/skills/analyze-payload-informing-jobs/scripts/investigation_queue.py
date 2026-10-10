#!/usr/bin/env python3
"""Persist investigation progress and schedule pending cohorts before repeat work."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DISPOSITIONS = {"PROPOSE_FIX", "RETIREMENT_CANDIDATE", "SHARED_FAILURE",
                "ALREADY_FIXED", "INSUFFICIENT_EVIDENCE", "KEEP_MONITOR"}


class QueueError(Exception):
    pass


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise QueueError("cannot read %s: %s" % (path, exc)) from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def stamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.utcoffset() != timedelta(0):
            raise ValueError("UTC required")
        return result
    except (AttributeError, ValueError) as exc:
        raise QueueError("invalid UTC time: " + str(value)) from exc


def scope(manifest):
    settings = manifest["effective_inputs"]
    return {key: settings[key] for key in ("release", "architecture", "stream")}


def observation(cohort):
    # New runs warrant a recheck, not automatic reuse of an old diagnosis.
    return digest({key: cohort.get(key) for key in (
        "cohort_id", "population_role", "release", "architecture", "stream",
        "verification_aliases", "actual_prow_jobs", "provisional_prow_jobs",
        "upgrade_route", "run_ids", "metrics", "recent_three_exposures",
        "investigation_inputs")})


def load_workspace(workspace):
    manifest = read_json(workspace / "manifest.json")
    rankings = read_json(workspace / "job-rankings.json")
    if rankings.get("selection_version") != manifest.get("selection_version"):
        raise QueueError("rankings do not match the frozen selection revision")
    cohorts = rankings.get("current", []) + rankings.get("previous_release_history", [])
    return manifest, cohorts


def load_history(path):
    if not path.exists():
        return {"schema_version": 1, "records": {}}
    history = read_json(path)
    if history.get("schema_version") != 1 or not isinstance(history.get("records"), dict):
        raise QueueError("unsupported investigation history")
    return history


def history_key(manifest, cohort):
    return digest({"scope": scope(manifest), "cohort_id": cohort["cohort_id"]})


def store_finding(history, workspace, manifest, cohort, path, now, imported=False):
    finding = read_json(path)
    if finding.get("cohort_id") != cohort["cohort_id"]:
        raise QueueError("finding does not match the scheduled cohort")
    status = finding.get("investigation_status", "")
    if not isinstance(status, str) or not status.startswith("COMPLETE") or finding.get("disposition") not in DISPOSITIONS:
        return False  # Partial/blocked work must remain eligible for continuation.
    if not all(isinstance(finding.get(key), str) and finding[key].strip()
               for key in ("summary", "next_action")):
        raise QueueError("completed finding needs summary and next_action")
    record = {"scope": scope(manifest), "cohort_id": cohort["cohort_id"],
              "analysis_id": manifest["analysis_id"],
              "observation_sha256": observation(cohort), "finding_sha256": digest(finding),
              "finding_path": str(path.resolve()), "workspace": str(workspace.resolve()),
              "recorded_at": stamp(now), "disposition": finding["disposition"],
              "summary": finding["summary"], "next_action": finding["next_action"],
              "revisit_condition": finding.get("revisit_condition")}
    key = history_key(manifest, cohort)
    previous = history["records"].get(key)
    if imported and previous and previous["finding_path"] == record["finding_path"]:
        # Re-ranking or editing an old finding is not a newly executed investigation.
        return False
    if previous and parse_time(previous["recorded_at"]) > now:
        return False
    history["records"][key] = record
    return True


def import_workspace(history, source, target_scope):
    manifest, cohorts = load_workspace(source)
    if scope(manifest) != target_scope:
        return 0
    by_id = {cohort["cohort_id"]: cohort for cohort in cohorts}
    completed = manifest.get("investigation_coverage", {}).get("completed_at")
    imported_at = parse_time(completed or manifest["collected_at"])
    count = 0
    for path in sorted((source / "findings").glob("*.json")):
        cohort = by_id.get(read_json(path).get("cohort_id"))
        if cohort:
            count += store_finding(history, source, manifest, cohort, path, imported_at, imported=True)
    return count


def limits(settings, overrides):
    result = {"max_recommendations": settings.get("max_recommendations", 10),
              "max_candidates": settings.get("max_candidates", 100),
              "time_budget_minutes": settings.get("time_budget_minutes", 120)}
    result.update({key: value for key, value in overrides.items() if value is not None})
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
           for value in result.values()):
        raise QueueError("investigation ceilings must be positive integers")
    return result


def stop_reason(state, now):
    if state.get("discovery_closed_reason"):
        return state["discovery_closed_reason"]
    if state["validated_recommendations"] >= state["limits"]["max_recommendations"]:
        return "RECOMMENDATION_LIMIT"
    if now >= parse_time(state["deadline"]):
        return "TIME_LIMIT"
    if len(state["attempted_cohorts"]) >= state["limits"]["max_candidates"]:
        return "CANDIDATE_LIMIT"
    if not state["queue"]:
        return "QUEUE_EXHAUSTED"
    return None


def retained_finding_matches(record):
    try:
        return digest(read_json(Path(record["finding_path"]))) == record["finding_sha256"]
    except (QueueError, KeyError):
        return False


def plan(workspace, history_path=None, prior_workspaces=(), revisit_path=None,
         new_session=False, now=None, validated_recommendations=None, closed_reason=None, **overrides):
    now = now or datetime.now(timezone.utc)
    workspace = Path(workspace).expanduser().resolve()
    manifest, cohorts = load_workspace(workspace)
    state_path = workspace / "investigation-queue.json"
    previous = read_json(state_path) if state_path.exists() else None
    history_path = Path(history_path).expanduser().resolve() if history_path else Path(
        previous["history_path"] if previous else workspace.parent / "investigation-history.json")
    history = load_history(history_path)
    imports = list(previous.get("history_imports", [])) if previous else []
    gaps = list(history.get("import_gaps", []))
    if previous:
        gaps += previous.get("history_gaps", [])
    sources = [Path(item).expanduser().resolve() for item in prior_workspaces]
    # Bootstrap older runs once. Read only bounded metadata, never scan artifact trees.
    if not history_path.exists():
        siblings = sorted(workspace.parent.glob("*/manifest.json"), reverse=True)
        if len(siblings) > 50:
            gaps.append("prior-workspace discovery limited to 50; use --prior-workspace for older history")
        sources += [path.parent for path in siblings[:50]
                    if path.parent != workspace and (path.parent / "job-rankings.json").exists()]
    sources.append(workspace)
    for source in dict.fromkeys(sources):
        try:
            count = import_workspace(history, source, scope(manifest))
            if count:
                imports.append({"workspace": str(source), "findings": count})
        except (QueueError, KeyError, TypeError) as exc:
            if source in [Path(item).expanduser().resolve() for item in prior_workspaces] or source == workspace:
                raise
            gaps.append(str(source) + ": " + str(exc))

    revisits = dict(previous.get("revisit_decisions", {})) if previous else {}
    if revisit_path:
        document = read_json(Path(revisit_path))
        for item in document["revisits"]:
            if not item.get("reason") or not item.get("evidence"):
                raise QueueError("a revisit needs a reason and evidence of changed inputs or a feasible follow-up")
            if item.get("cohort_id") not in {cohort["cohort_id"] for cohort in cohorts}:
                raise QueueError("revisit refers to an unknown cohort")
            revisits[item["cohort_id"]] = item

    if previous and not new_session:
        state = previous
        effective = limits(state["limits"], overrides)
        if effective != state["limits"]:
            raise QueueError("limits are frozen for a session; use --new-session to change them")
        if state["analysis_id"] != manifest["analysis_id"]:
            raise QueueError("queue belongs to a different analysis")
    else:
        effective = limits(manifest["effective_inputs"], overrides)
        started = now if new_session else parse_time(manifest["collected_at"])
        state = {"schema_version": 1, "analysis_id": manifest["analysis_id"],
                 "session_id": stamp(now), "started_at": stamp(started),
                 "deadline": stamp(started + timedelta(minutes=effective["time_budget_minutes"])),
                 "limits": effective, "attempted_cohorts": [], "completed_cohorts": [],
                 "validated_recommendations": 0}

    if validated_recommendations is not None:
        if isinstance(validated_recommendations, bool) or not isinstance(validated_recommendations, int) or validated_recommendations < 0:
            raise QueueError("validated count must be a nonnegative integer")
        if validated_recommendations < state["validated_recommendations"]:
            raise QueueError("validated count cannot decrease within a session")
        state["validated_recommendations"] = validated_recommendations
    if closed_reason:
        if closed_reason not in ("REVIEW_EXPORT_RESERVE", "NO_FEASIBLE_WORK"):
            raise QueueError("unsupported discovery stop reason")
        state["discovery_closed_reason"] = closed_reason

    pending, rechecks, deferred = [], [], []
    for cohort in cohorts:
        prior = history["records"].get(history_key(manifest, cohort))
        item = {"cohort_id": cohort["cohort_id"], "population_role": cohort.get("population_role"),
                "rank": cohort["rank"], "verification_aliases": cohort.get("verification_aliases", []),
                "observation_sha256": observation(cohort)}
        if prior:
            item["prior_investigation"] = prior
        if not prior:
            item.update(status="PENDING", reason="no completed investigation recorded")
            pending.append(item)
        elif cohort["cohort_id"] in revisits:
            item.update(status="RECHECK", reason=revisits[cohort["cohort_id"]]["reason"],
                        evidence=revisits[cohort["cohort_id"]]["evidence"])
            rechecks.append(item)
        elif prior["observation_sha256"] != item["observation_sha256"]:
            item.update(status="RECHECK", reason="ranked observations changed; reassess prior applicability")
            rechecks.append(item)
        elif not retained_finding_matches(prior):
            item.update(status="RECHECK", reason="prior finding is missing or changed; cannot reuse its conclusion")
            rechecks.append(item)
        else:
            item.update(status="DEFERRED", reason="unchanged completed investigation; await revisit condition")
            deferred.append(item)
    gaps = list(dict.fromkeys(gaps))
    history["import_gaps"] = gaps
    state.update(selection_version=manifest["selection_version"], history_path=str(history_path),
                 queue=pending + rechecks, deferred=deferred, history_imports=imports, history_gaps=gaps,
                 revisit_decisions=revisits)
    state["stop_reason"] = stop_reason(state, now)
    write_json(history_path, history)
    write_json(state_path, state)
    manifest["investigation_workflow"] = {
        "session_id": state["session_id"], "limits": state["limits"],
        "started_at": state["started_at"], "deadline": state["deadline"],
        "pending": len(pending), "rechecks": len(rechecks), "deferred": len(deferred),
        "attempted": len(state["attempted_cohorts"]), "completed": len(state["completed_cohorts"]),
        "validated_recommendations": state["validated_recommendations"],
        "stop_reason": state["stop_reason"], "history_gaps": gaps}
    write_json(workspace / "manifest.json", manifest)
    return state


def begin(workspace, cohort_id, validated_recommendations=None, reason=None, now=None):
    now = now or datetime.now(timezone.utc)
    state = plan(workspace, now=now, validated_recommendations=validated_recommendations)
    stopped = stop_reason(state, now)
    if stopped and not (stopped == "CANDIDATE_LIMIT" and cohort_id in state["attempted_cohorts"]):
        state["stop_reason"] = stopped
        write_json(Path(workspace).expanduser() / "investigation-queue.json", state)
        raise QueueError("stop new discovery: " + stopped)
    candidates = {item["cohort_id"]: item for item in state["queue"]}
    if cohort_id not in candidates:
        raise QueueError("cohort is not queued; provide a justified revisit if its inputs are unchanged")
    if cohort_id != state["queue"][0]["cohort_id"] and not reason:
        raise QueueError("changing investigation order needs an explicit reason")
    if cohort_id not in state["attempted_cohorts"]:
        state["attempted_cohorts"].append(cohort_id)
    state["active_cohort"] = cohort_id
    state["active_observation_sha256"] = candidates[cohort_id]["observation_sha256"]
    state.setdefault("priority_decisions", []).append({"cohort_id": cohort_id, "reason": reason})
    state["stop_reason"] = stop_reason(state, now)
    write_json(Path(workspace).expanduser() / "investigation-queue.json", state)
    return state


def record(workspace, finding_path, now=None):
    now = now or datetime.now(timezone.utc)
    workspace = Path(workspace).expanduser().resolve()
    state = read_json(workspace / "investigation-queue.json")
    manifest, cohorts = load_workspace(workspace)
    finding_path = Path(finding_path).expanduser().resolve()
    cohort_id = read_json(finding_path)["cohort_id"]
    if cohort_id not in state["attempted_cohorts"]:
        raise QueueError("begin the cohort investigation before recording completion")
    cohort = next((item for item in cohorts if item["cohort_id"] == cohort_id), None)
    if not cohort:
        raise QueueError("finding refers to an unknown cohort")
    if state.get("active_cohort") != cohort_id or state.get("active_observation_sha256") != observation(cohort):
        raise QueueError("investigation inputs changed or cohort is not active; begin again before completion")
    history_path = Path(state["history_path"])
    history = load_history(history_path)
    if not store_finding(history, workspace, manifest, cohort, finding_path, now):
        raise QueueError("finding is not a completed bounded investigation")
    write_json(history_path, history)
    if cohort_id not in state["completed_cohorts"]:
        state["completed_cohorts"].append(cohort_id)
    state.pop("active_cohort", None)
    state.pop("active_observation_sha256", None)
    state.get("revisit_decisions", {}).pop(cohort_id, None)
    write_json(workspace / "investigation-queue.json", state)
    return plan(workspace, now=now)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "begin", "record"))
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--history-file")
    parser.add_argument("--prior-workspace", action="append", default=[])
    parser.add_argument("--revisit-decisions")
    parser.add_argument("--new-session", action="store_true")
    for name in ("max-recommendations", "max-candidates", "time-budget-minutes"):
        parser.add_argument("--" + name, type=int)
    parser.add_argument("--cohort-id")
    parser.add_argument("--reason")
    parser.add_argument("--validated-recommendations", type=int)
    parser.add_argument("--stop-reason", choices=("REVIEW_EXPORT_RESERVE", "NO_FEASIBLE_WORK"))
    parser.add_argument("--finding")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            state = plan(args.workspace, args.history_file, args.prior_workspace, args.revisit_decisions,
                         args.new_session, max_recommendations=args.max_recommendations,
                         max_candidates=args.max_candidates, time_budget_minutes=args.time_budget_minutes,
                         validated_recommendations=args.validated_recommendations, closed_reason=args.stop_reason)
        elif args.command == "begin":
            if not args.cohort_id:
                raise QueueError("begin requires --cohort-id")
            state = begin(args.workspace, args.cohort_id, args.validated_recommendations, args.reason)
        else:
            if not args.finding:
                raise QueueError("record requires --finding")
            state = record(args.workspace, args.finding)
        text = {key: state[key] for key in ("session_id", "limits", "deadline", "stop_reason")}
        text.update(queued=len(state["queue"]), deferred=len(state["deferred"]),
                    attempted=len(state["attempted_cohorts"]), completed=len(state["completed_cohorts"]),
                    next_cohort=state["queue"][0]["cohort_id"] if state["queue"] else None)
        print(json.dumps(text, indent=2))
        return 0
    except (QueueError, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
