#!/usr/bin/env python3
"""Validate and export a portable payload informing-job analysis report."""

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

DISPOSITIONS = {"PROPOSE_FIX", "RETIREMENT_CANDIDATE", "SHARED_FAILURE",
                "ALREADY_FIXED", "INSUFFICIENT_EVIDENCE", "KEEP_MONITOR"}
RETIREMENT_VERDICTS = {"VALIDATED_CANDIDATE", "REJECTED", "INSUFFICIENT_EVIDENCE"}
EXECUTION_PHASES = {"NOT_STARTED", "SETUP_FAILED", "WORKLOAD_FAILED_BEFORE_REAL_TESTS",
                    "REAL_TEST_FAILURE", "POST_TEST_FAILURE", "INTENTIONAL_TESTLESS", "UNKNOWN"}


class ExportError(Exception):
    pass


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ExportError("cannot read %s: %s" % (path, exc)) from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return result.hexdigest()
            result.update(chunk)


def safe_relative(root, value):
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ExportError("evidence path leaves workspace: " + str(value)) from exc
    return path


def validate_evidence(root, records):
    if records is None:
        return []
    if not isinstance(records, list):
        raise ExportError("evidence must be a list")
    paths = []
    for record in records:
        if not isinstance(record, dict):
            raise ExportError("evidence record must be an object")
        required = ("source_url", "retrieved_at", "sha256", "retained_path", "location", "role")
        missing = [key for key in required if not record.get(key)]
        if missing:
            raise ExportError("evidence record missing " + ", ".join(missing))
        path = safe_relative(root, record["retained_path"])
        if not path.is_file():
            raise ExportError("retained evidence does not exist: " + str(path))
        if file_digest(path) != record["sha256"]:
            raise ExportError("retained evidence hash mismatch: " + str(path))
        paths.append(path)
    return paths


def load_records(directory):
    if not directory.exists():
        return []
    records = []
    for path in sorted(directory.glob("*.json")):
        value = read_json(path)
        if not isinstance(value, dict):
            raise ExportError(str(path) + " must contain an object")
        records.append((path, value))
    return records


def validate_finding(root, path, finding, cohort_ids):
    if finding.get("schema_version") != 1:
        raise ExportError(str(path) + " has unsupported schema_version")
    if finding.get("cohort_id") not in cohort_ids:
        raise ExportError(str(path) + " refers to an unknown ranked cohort")
    if finding.get("disposition") not in DISPOSITIONS:
        raise ExportError(str(path) + " has invalid disposition")
    if not finding.get("investigation_status"):
        raise ExportError(str(path) + " lacks investigation_status")
    for key in ("title", "summary", "next_action"):
        if not isinstance(finding.get(key), str) or not finding[key].strip():
            raise ExportError(str(path) + " needs authored " + key + " for its readable handoff")
    if not isinstance(finding.get("sampled_runs", []), list) or any(
            not isinstance(item, dict) for item in finding.get("sampled_runs", [])):
        raise ExportError(str(path) + " sampled_runs must be a list of run records")
    execution = finding.get("execution")
    if not isinstance(execution, dict) or execution.get("phase") not in EXECUTION_PHASES:
        raise ExportError(str(path) + " lacks a valid execution classification")
    counts = [execution.get(key) for key in ("real_test_count", "failed_real_test_count", "synthetic_case_count")]
    if any(value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0)
           for value in counts):
        raise ExportError(str(path) + " execution counts must be nonnegative integers or null")
    real, failed, synthetic = counts
    if real is not None and failed is not None and failed > real:
        raise ExportError(str(path) + " failed real-test count exceeds real-test count")
    phase = execution["phase"]
    if phase == "REAL_TEST_FAILURE" and (not real or not failed):
        raise ExportError(str(path) + " real-test failure needs positive real and failed-real counts")
    if phase == "POST_TEST_FAILURE" and (not real or failed not in (0, None)):
        raise ExportError(str(path) + " post-test failure needs real tests without failed assertions")
    if phase == "WORKLOAD_FAILED_BEFORE_REAL_TESTS" and real not in (0, None):
        raise ExportError(str(path) + " pre-test failure cannot report executed real tests")
    if phase == "INTENTIONAL_TESTLESS" and not execution.get("intended_testless"):
        raise ExportError(str(path) + " intentional-testless classification needs purpose evidence")
    if phase == "REAL_TEST_FAILURE" and synthetic and real == 0:
        raise ExportError(str(path) + " synthetic JUnit cases do not establish real-test execution")
    if not finding.get("intended_verification_purpose"):
        raise ExportError(str(path) + " lacks intended verification purpose")
    if finding["disposition"] == "PROPOSE_FIX":
        for key in ("mechanism", "current_source_state", "proposed_change", "acceptance_criteria"):
            if not finding.get(key):
                raise ExportError(str(path) + " proposed fix lacks " + key)
    validate_evidence(root, finding.get("evidence", []))
    return finding


def recommendation_body(candidate):
    return {key: value for key, value in candidate.items() if key not in ("review", "review_status")}


def validate_retirement(root, path, candidate, cohort_ids):
    if candidate.get("schema_version") != 1 or candidate.get("disposition") != "RETIREMENT_CANDIDATE":
        raise ExportError(str(path) + " is not a schema v1 retirement candidate")
    if candidate.get("cohort_id") not in cohort_ids:
        raise ExportError(str(path) + " refers to an unknown cohort")
    required = ("population", "persistence", "localization", "investigation", "configuration",
                "impact", "restoration_condition", "investigator_context_identity")
    missing = [key for key in required if not candidate.get(key)]
    if missing:
        raise ExportError(str(path) + " missing recommendation gates: " + ", ".join(missing))
    configuration = candidate["configuration"]
    required_config = ("verification_entry", "prow_job", "source_revision", "periodic_definition",
                       "current_schedule", "proposed_yearly_schedule", "unapplied_change")
    if not isinstance(configuration, dict) or any(not configuration.get(key) for key in required_config):
        raise ExportError(str(path) + " lacks exact current/proposed configuration")
    proposed = configuration["proposed_yearly_schedule"]
    if isinstance(proposed, dict) and proposed.get("cron") and proposed.get("interval"):
        raise ExportError(str(path) + " proposes mutually exclusive cron and interval")
    validate_evidence(root, candidate.get("evidence", []))
    review_path = path.with_name(path.stem + ".review.json")
    if not review_path.exists():
        return "UNREVIEWED", None
    review = read_json(review_path)
    expected = digest(recommendation_body(candidate))
    if review.get("recommendation_digest") != expected:
        raise ExportError(str(review_path) + " does not match current recommendation digest")
    if review.get("verdict") not in RETIREMENT_VERDICTS:
        raise ExportError(str(review_path) + " has invalid verdict")
    if review.get("reviewer_context_identity") == candidate.get("investigator_context_identity"):
        raise ExportError(str(review_path) + " is not an independent review context")
    for key in ("reviewed_at", "evidence_checked", "counterarguments", "outstanding_concerns"):
        if key not in review:
            raise ExportError(str(review_path) + " missing " + key)
    return review["verdict"], review


def copy_evidence(workspace, report_root, records):
    copied = []
    for source in validate_evidence(workspace, records):
        relative = source.resolve().relative_to(workspace.resolve())
        target = report_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(str(target.relative_to(report_root)))
    return copied


def metric_text(metric):
    if not metric:
        return "Not recorded"
    if metric.get("value") is None:
        return "undefined (0 terminal runs)"
    return "%.1f%% (%d/%d)" % (metric["value"] * 100, metric["numerator"], metric["denominator"])


def md(value):
    """Render authored text literally, including within table cells."""
    return re.sub(r"([\\`*_{}\[\]()#+!|>~])", r"\\\1", html.escape(str(value), quote=False))


def table_text(value):
    return md(" ".join(str(value).split()))


def details(value):
    """Keep structured source/action records readable without dumping JSON."""
    if value is None or value == [] or value == {} or value == "":
        return "Not recorded."
    if isinstance(value, dict):
        rendered = ["**%s:**%s%s" % (md(key.replace("_", " ").capitalize()),
                    "\n\n" if isinstance(item, (dict, list)) else " ", details(item))
                    for key, item in value.items() if item is not None and item != [] and item != {} and item != ""
                    and key != "evidence_refs"]
        return "\n\n".join(rendered) or "Not recorded."
    if isinstance(value, list):
        separator = "\n\n" if any(isinstance(item, (dict, list)) for item in value) else "\n"
        return separator.join("- " + details(item).replace("\n", "\n  ") for item in value)
    return md(value)


def external_link(label, url):
    if url and urlsplit(str(url)).scheme in ("http", "https"):
        return "[%s](%s)" % (md(label), quote(str(url), safe="/:?=&%#@+,-._~"))
    return md(label)


def cohort_name(cohort):
    return ", ".join(cohort.get("verification_aliases") or cohort.get("actual_prow_jobs") or
                     cohort.get("provisional_prow_jobs") or [cohort["cohort_id"]])


def sample_text(cohort):
    return {True: "Adequate", False: "Sparse"}.get(cohort.get("sample_sufficient"), "Unknown")


def cohort_status(finding, retirement, cohort=None):
    if finding:
        status = finding["disposition"] + " / " + finding["investigation_status"]
    else:
        status = "RETIREMENT_CANDIDATE" if retirement else (cohort or {}).get(
            "investigation_queue", {}).get("status", "PENDING")
    if retirement:
        status += " / retirement review: " + retirement["status"]
    return status


def pending_reason(cohort):
    queued = cohort.get("investigation_queue")
    if queued:
        return "Scheduling: %s. %s. No current investigation is recorded; cause and action remain unassessed." % (
            queued["status"], queued["reason"])
    return cohort.get("pending_reason") or "No completed investigation record; cause and action remain unassessed."


def window_text(manifest, population):
    window = (manifest.get("history", {}).get("window") if population == "previous_release_history"
              else manifest.get("current_window")) or {}
    return "%s through %s" % (window.get("start", "unknown"), window.get("end", "unknown"))


def analysis_reviews(workspace, manifest, findings):
    """Expose recorded analysis reviews without treating them as repair proof."""
    path = workspace / "analysis-review.json"
    if not path.exists():
        return None, {}
    document = read_json(path)
    if not isinstance(document, dict) or not isinstance(document.get("findings"), list):
        raise ExportError(str(path) + " needs a findings list")
    result = {}
    for record in document["findings"]:
        if not isinstance(record, dict):
            raise ExportError(str(path) + " finding review must be an object")
        cohort_id = record.get("cohort_id")
        finding = findings.get(cohort_id)
        if not finding:
            continue
        current = (record.get("finding_sha256") == digest(
            {key: value for key, value in finding.items() if key != "review"}) and
            document.get("selection_version_checked") == manifest.get("selection_version"))
        independent = (document.get("reviewer_context_identity") and
                       finding.get("investigator_context_identity") and
                       document["reviewer_context_identity"] != finding["investigator_context_identity"])
        complete = all(document.get(key) for key in ("reviewed_at", "scope")) and all(
            record.get(key) for key in ("verdict", "reasoning", "evidence_checked"))
        result[cohort_id] = {
            "status": "RECORDED" if current and independent and complete else "STALE_OR_INCOMPLETE",
            "record": record, "reviewer": document.get("reviewer_context_identity"),
            "reviewed_at": document.get("reviewed_at"), "scope": document.get("scope"),
        }
    return document, result


def cohort_readme(manifest, cohort, population, finding=None, retirement=None, analysis_review=None):
    title = finding["title"] if finding else cohort_name(cohort)
    status = cohort_status(finding, retirement, cohort)
    metrics = cohort.get("metrics", {})
    scope = dict(manifest["effective_inputs"], **{key: cohort[key] for key in
                 ("release", "architecture", "stream") if cohort.get(key)})
    lines = ["# " + md(title), "", "**Disposition / investigation: %s**" % md(status), ""]
    if finding:
        review_status = ((analysis_review["record"]["verdict"] if analysis_review["status"] == "RECORDED"
                         else analysis_review["status"]) if analysis_review else "UNAVAILABLE / PENDING")
        lines += ["Analysis review: %s (does not establish repair proof)." % md(review_status), ""]
    lines += ["## Summary", ""]
    if finding:
        lines += [md(finding["summary"]), "", "Next action: " + md(finding["next_action"]), ""]
    elif retirement:
        lines += ["A retirement proposal is recorded; its review status is %s. " % md(retirement["status"]) +
                  "See the scoped recommendation below; no repair proof is implied.", ""]
    else:
        lines += [md(pending_reason(cohort)), ""]
    prior = cohort.get("investigation_queue", {}).get("prior_investigation")
    if prior:
        lines += ["## Previous investigation", "",
                  "Historical scheduling context; this is not a current diagnosis or renewed review.", "",
                  details({key: prior.get(key) for key in ("analysis_id", "recorded_at", "disposition",
                      "summary", "next_action", "revisit_condition", "finding_sha256")}), ""]
    lines += ["## Impact and affected runs", "",
              "- Verification alias: " + md(cohort_name(cohort)),
              "- Prow job (%s): %s" % (md(cohort.get("identity_state", "PROVISIONAL")),
                  md(", ".join(cohort.get("actual_prow_jobs") or cohort.get("provisional_prow_jobs") or ["unresolved"]))),
              "- Cohort: " + md(cohort["cohort_id"]),
              "- Population: %s; %s / %s / %s" % (md(population), md(scope["release"]),
                  md(scope["architecture"]), md(scope["stream"])),
              "- Frozen window: " + md(window_text(manifest, population)),
              "- Unique terminal-run success: " + metric_text(metrics.get("unique_run_success")),
              "- Payload-association success: " + metric_text(metrics.get("association_success")),
              "- Distinct runs: %s; eligible payload exposures: %s; sample: %s" % (
                  metrics.get("distinct_runs", "unknown"), metrics.get("payload_exposures", "unknown"),
                  sample_text(cohort)),
              "- Recent three exposures, association success: " + metric_text(
                  cohort.get("recent_three_exposures", {}).get("association_success")),
              "- Last pass: %s; consecutive failing payloads: %s" % (
                  md((metrics["last_pass"] or "None observed in this window")
                     if "last_pass" in metrics else "unknown"),
                  metrics.get("consecutive_failing_payloads", "unknown")), "",
              "Configuration / upgrade route:", "", details({"configuration": cohort.get("configuration"),
                  "upgrade_route": cohort.get("upgrade_route")}), ""]
    if not finding and not retirement:
        lines += ["Investigation: " + md(status) + ". " + md(pending_reason(cohort)), "",
                  "Sparse observations do not establish chronic failure; pending status does not clear the job.", ""]
        return "\n".join(lines)
    if finding:
        samples = finding.get("sampled_runs", [])
        sample_ids = {str(item.get("run_id") or item.get("prow_run_id")) for item in samples
                      if item.get("run_id") or item.get("prow_run_id")}
        lines += ["Deeply inspected runs: %d; this is separate from the ranked terminal-run denominator." % len(sample_ids), "",
                  "Execution phase: " + md(finding["execution"]["phase"]), "",
                  "Purpose: " + md(finding["intended_verification_purpose"]), "", details(finding["execution"]), ""]
        for item in samples:
            run_id = str(item.get("run_id") or item.get("prow_run_id") or "unknown")
            lines.append("- %s: %s; payload %s; phase %s" % (
                external_link(run_id, item.get("url") or item.get("prow_url")),
                md(item.get("result") or item.get("normalized_outcome") or "unknown"),
                md(item.get("payload_id", "unknown")), md(item.get("execution", {}).get("phase", "UNKNOWN"))))
        lines += ["", "[Full finding](finding.json)", ""]
        if finding.get("previous_release_metrics"):
            lines += ["Supplementary predecessor metrics (excluded from the current denominator):", "",
                      details(finding["previous_release_metrics"]), ""]
    candidate = retirement["candidate"] if retirement else {}
    proposed_change = (finding or {}).get("proposed_change")
    owner = (finding or {}).get("owner")
    if not owner and isinstance(proposed_change, dict):
        owner = proposed_change.get("owner")
    sections = [
        ("Root cause / demonstrated mechanism", (finding or {}).get("mechanism") or
         candidate.get("localization") or "Unknown; no demonstrated cause recorded."),
        ("Current source and fix status", (finding or {}).get("current_source_state") or candidate.get("configuration")),
        ("Suggested action and owner", {"next_action": (finding or {}).get("next_action") or
         candidate.get("configuration", {}).get("unapplied_change"),
         "owner": owner or candidate.get("owner") or "Unknown; owner needs identification.",
         "proposal": proposed_change or (finding or {}).get("proposed_followup") or candidate.get("configuration")}),
        ("Validation and acceptance", {"acceptance_criteria": (finding or {}).get("acceptance_criteria"),
         "restoration_condition": candidate.get("restoration_condition")}),
        ("Limits and unresolved cofailures", {"limitations": (finding or {}).get("limitations"),
         "contrary_evidence": (finding or {}).get("contrary_evidence"),
         "controls": (finding or {}).get("passing_controls") or (finding or {}).get("passing_control") or
         (finding or {}).get("controls"), "coverage_impact": candidate.get("impact")}),
    ]
    for heading, value in sections:
        lines += ["## " + heading, "", details(value), ""]
    lines += ["## Independent review", ""]
    if analysis_review and analysis_review["status"] == "RECORDED":
        record = analysis_review["record"]
        lines += ["Analysis review: " + md(record["verdict"]) + ". This does not establish a proven repair.", "",
                  details({"scope": analysis_review["scope"], "reviewer": analysis_review["reviewer"],
                           "reviewed_at": analysis_review["reviewed_at"], "reasoning": record["reasoning"],
                           "counterargument": record.get("counterargument"),
                           "outstanding_concerns": record.get("outstanding_concerns")}), "",
                  "[Recorded analysis review](../../analysis-review.json)", ""]
    else:
        lines += ["Analysis review: %s; no current independent analysis attestation is available." % (
            analysis_review["status"] if analysis_review else "UNAVAILABLE / PENDING"), ""]
    if retirement:
        lines += ["Retirement review: " + md(retirement["status"]) + ". This concerns candidacy, not repair proof.", "",
                  "[Scoped recommendation](recommendation.json)", ""]
        if retirement["review"]:
            lines += [details(retirement["review"]), "", "[Retirement review](review.json)", ""]
    if (finding or {}).get("disposition") == "PROPOSE_FIX":
        lines += ["Repair proposal is unvalidated. Proven repair handoffs use the sibling reliability export under `fixes/`.", ""]
    lines += ["## Evidence", ""]
    evidence = (finding or {}).get("evidence", []) + candidate.get("evidence", [])
    for record in evidence:
        retained = quote("../../" + record["retained_path"], safe="/-._~")
        lines += ["- [%s](%s): %s. %s. Retrieved %s. SHA256: `%s`." % (
            md(record["role"]), retained, md(record["location"]), external_link("Source", record["source_url"]),
            md(record["retrieved_at"]), record["sha256"])]
    if not evidence:
        lines.append("No retained evidence recorded.")
    return "\n".join(lines) + "\n"


def report_readme(manifest, rankings, findings, validated, unresolved, fixes, retirements=None):
    current = rankings.get("current", [])
    worst = current[0] if current else None
    lines = ["# Payload informing-job analysis", "", "Analysis `%s` for `%s` / `%s` / `%s`." % (
        manifest["analysis_id"], manifest["effective_inputs"]["release"],
        manifest["effective_inputs"]["architecture"], manifest["effective_inputs"]["stream"]), ""]
    if worst:
        name = (worst.get("actual_prow_jobs") or worst.get("provisional_prow_jobs") or
                worst.get("verification_aliases") or [worst["cohort_id"]])[0]
        lines += ["Worst raw performer: `%s`, unique-run success %s." % (
            name, metric_text(worst["metrics"]["unique_run_success"])), ""]
    else:
        lines += ["No current-release informing cohort was rankable in the selected population.", ""]
    lines += ["## Coverage", "", "- Inspected payloads: %d" % manifest["counts"].get("payloads_inspected", 0),
              "- Selected healthy payloads: %d" % manifest["counts"].get("selected_payloads", 0),
              "- Current ranked cohorts: %d" % len(current),
              "- Historical ranked cohorts: %d" % len(rankings.get("previous_release_history", [])),
              "- Deep findings recorded: %d" % len(findings),
              "- Proven repair handoffs: %d" % fixes,
              "- Validated retirement candidates: %d" % len(validated),
              "- Unresolved or pending records: %d" % len(unresolved), ""]
    if manifest.get("investigation_workflow"):
        progress = manifest["investigation_workflow"]
        limits = progress["limits"]
        lines += ["## Investigation progress", "",
                  "Started %d/%d candidate cohorts; completed %d. Validated recommendations: %d/%d." % (
                      progress["attempted"], limits["max_candidates"], progress["completed"],
                      progress["validated_recommendations"], limits["max_recommendations"]), "",
                  "Pending: %d; rechecks: %d; unchanged prior investigations deferred: %d." % (
                      progress["pending"], progress["rechecks"], progress["deferred"]), "",
                  "Discovery: %s. Budget: %d minutes; deadline: %s." % (
                      progress["stop_reason"] or "ACTIVE", limits["time_budget_minutes"], progress["deadline"]), "",
                  "Next cohort: " + md(progress["next_job"] or progress["next_cohort"] or "None queued") + ".", "",
                  "[Investigation queue and prior-history context](investigation-queue.json)", ""]
        lines += ["History gap: " + md(gap) + ".\n" for gap in progress["history_gaps"]]
    if manifest.get("missing_evidence"):
        lines += ["## Gaps", ""] + ["- " + item for item in manifest["missing_evidence"]] + [""]
    findings_by_cohort = {item["cohort_id"]: item for item in findings}
    retirements = retirements or {}
    for population, heading in (("current", "Current ranked cohorts"),
                                ("previous_release_history", "Previous-release history")):
        lines += ["## " + heading, "", "Frozen window: " + md(window_text(manifest, population)) + ".", ""]
        cohorts = rankings.get(population, [])
        if not cohorts:
            lines += ["No ranked cohorts in this population.", ""]
            continue
        lines += ["| Rank | Job / cohort | Unique-run success | Sample | Disposition / investigation | Finding / pending reason |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for cohort in cohorts:
            finding = findings_by_cohort.get(cohort["cohort_id"])
            retirement = retirements.get(cohort["cohort_id"])
            summary = finding["summary"] if finding else (
                "Retirement proposal; review " + retirement["status"] if retirement else pending_reason(cohort))
            lines.append("| %s | [%s](findings/%s/README.md) | %s | %s | %s | %s |" % (
                cohort.get("rank", ""), table_text(cohort_name(cohort)), quote(cohort["cohort_id"], safe=""),
                metric_text(cohort["metrics"].get("unique_run_success")), sample_text(cohort),
                table_text(cohort_status(finding, retirement, cohort)), table_text(summary)))
        lines.append("")
    lines += ["## Recommendations", ""]
    if not validated and not fixes:
        lines += ["No repair or retirement recommendation passed its review gate.", ""]
    for candidate in validated:
        lines.append("- Validated retirement candidate: `%s`" % candidate["cohort_id"])
    lines += ["", "This is a local analysis deliverable. Its configuration changes are unapplied and require a separate request.", ""]
    return "\n".join(lines)


def run(workspace, output, repairs=None):
    workspace, output = Path(workspace), Path(output)
    if output.exists():
        raise ExportError("output already exists; choose a fresh destination")
    manifest = read_json(workspace / "manifest.json")
    payloads = read_json(workspace / "payloads.json")
    rankings = read_json(workspace / "job-rankings.json")
    if manifest.get("stage") not in ("RANKED", "INVESTIGATING", "REVIEW_PENDING", "EXPORTED"):
        raise ExportError("workspace has not been ranked")
    if rankings.get("selection_version") != manifest.get("selection_version"):
        raise ExportError("ranking selection version does not match manifest")
    queue_path = workspace / "investigation-queue.json"
    queue = read_json(queue_path) if queue_path.exists() else None
    if manifest.get("investigation_workflow") and queue is None:
        raise ExportError("investigation progress refers to a missing queue")
    if queue:
        if queue.get("analysis_id") != manifest["analysis_id"] or queue.get(
                "selection_version") != manifest["selection_version"]:
            raise ExportError("investigation queue is stale; regenerate it against the current rankings")
        queued = {item["cohort_id"]: item for item in queue["queue"] + queue["deferred"]}
        for population in ("current", "previous_release_history"):
            for cohort in rankings.get(population, []):
                if cohort["cohort_id"] in queued:
                    cohort["investigation_queue"] = queued[cohort["cohort_id"]]
        manifest["investigation_workflow"] = {
            "session_id": queue["session_id"], "limits": queue["limits"],
            "started_at": queue["started_at"], "deadline": queue["deadline"],
            "attempted": len(queue["attempted_cohorts"]), "completed": len(queue["completed_cohorts"]),
            "validated_recommendations": queue["validated_recommendations"],
            "stop_reason": queue["stop_reason"], "history_gaps": queue["history_gaps"],
            "pending": sum(item["status"] == "PENDING" for item in queue["queue"]),
            "rechecks": sum(item["status"] == "RECHECK" for item in queue["queue"]),
            "deferred": len(queue["deferred"]),
            "next_cohort": queue["queue"][0]["cohort_id"] if queue["queue"] else None,
            "next_job": ", ".join(queue["queue"][0].get("verification_aliases", [])) if queue["queue"] else None}
    cohorts = [(population, item) for population in ("current", "previous_release_history")
               for item in rankings.get(population, [])]
    cohort_ids = set()
    for _, item in cohorts:
        cohort_id = item.get("cohort_id")
        if not isinstance(cohort_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", cohort_id):
            raise ExportError("ranked cohort ID must be a safe directory name")
        if cohort_id in cohort_ids:
            raise ExportError("duplicate ranked cohort ID: " + cohort_id)
        cohort_ids.add(cohort_id)
    finding_pairs = load_records(workspace / "findings")
    findings = [validate_finding(workspace, path, value, cohort_ids) for path, value in finding_pairs]
    findings_by_cohort = {item["cohort_id"]: item for item in findings}
    if len(findings_by_cohort) != len(findings):
        raise ExportError("multiple findings for the same cohort")
    review_document, reviews = analysis_reviews(workspace, manifest, findings_by_cohort)
    retirement_pairs = [(path, value) for path, value in load_records(workspace / "retirement-candidates")
                        if not path.name.endswith(".review.json")]
    validated, unresolved = [], []
    retirement_export, retirements_by_cohort = [], {}
    for path, candidate in retirement_pairs:
        verdict, review = validate_retirement(workspace, path, candidate, cohort_ids)
        if candidate["cohort_id"] in retirements_by_cohort:
            raise ExportError("multiple retirement recommendations for the same cohort")
        retirements_by_cohort[candidate["cohort_id"]] = {
            "status": verdict, "candidate": candidate, "review": review}
        item = dict(candidate, review_status=verdict)
        if verdict == "VALIDATED_CANDIDATE":
            validated.append(item)
            retirement_export.append((path, candidate, review))
        else:
            unresolved.append({"cohort_id": candidate["cohort_id"], "status": verdict,
                               "record": candidate, "review": review})
    for cohort_id in sorted(cohort_ids):
        if cohort_id not in findings_by_cohort and not any(item[1].get("cohort_id") == cohort_id for item in retirement_pairs):
            cohort = next(item for _, item in cohorts if item["cohort_id"] == cohort_id)
            unresolved.append({"cohort_id": cohort_id,
                               "status": cohort.get("investigation_queue", {}).get("status", "PENDING"),
                               "reason": pending_reason(cohort)})
    validated_ids = {item["cohort_id"] for item in validated}
    for finding in findings:
        status = finding["disposition"]
        if status == "PROPOSE_FIX":
            status = "PROPOSED_FIX_UNVALIDATED"
        elif status == "RETIREMENT_CANDIDATE" and finding["cohort_id"] in validated_ids:
            continue
        elif status == "RETIREMENT_CANDIDATE":
            status = "UNREVIEWED_RETIREMENT_CANDIDATE"
        unresolved.append({"cohort_id": finding["cohort_id"], "status": status,
                           "record": finding})

    output.mkdir(parents=True)
    associations = read_json(workspace / "associations.json")
    for name, value in (("payloads.json", payloads), ("associations.json", associations),
                        ("job-rankings.json", rankings)):
        write_json(output / name, value)
    exported_manifest = dict(manifest)
    exported_manifest["stage"] = "EXPORTED"
    exported_manifest["exported_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    exported_manifest["report_counts"] = {"findings": len(findings), "validated_retirements": len(validated),
                                          "unresolved": len(unresolved), "proven_fixes": 0,
                                          "cohort_summaries": len(cohorts)}
    if queue:
        write_json(output / "investigation-queue.json", queue)
    if review_document is not None:
        write_json(output / "analysis-review.json", review_document)
    for population, cohort in cohorts:
        cohort_id = cohort["cohort_id"]
        target = output / "findings" / cohort_id
        target.mkdir(parents=True)
        finding = findings_by_cohort.get(cohort_id)
        retirement = retirements_by_cohort.get(cohort_id)
        if finding:
            write_json(target / "finding.json", finding)
            copy_evidence(workspace, output, finding.get("evidence", []))
        if retirement:
            write_json(target / "recommendation.json", retirement["candidate"])
            if retirement["review"]:
                write_json(target / "review.json", retirement["review"])
            copy_evidence(workspace, output, retirement["candidate"].get("evidence", []))
        (target / "README.md").write_text(cohort_readme(
            exported_manifest, cohort, population, finding, retirement, reviews.get(cohort_id)))
    for path, candidate, review in retirement_export:
        target = output / "retirement-candidates" / path.stem
        write_json(target / "recommendation.json", candidate)
        write_json(target / "review.json", review)
        copy_evidence(workspace, output, candidate.get("evidence", []))

    fixes = 0
    repair_source = Path(repairs) if repairs else workspace / "validated-repairs"
    if repair_source.exists():
        issues = repair_source / "issues"
        if not issues.is_dir():
            raise ExportError("repair export exists but has no validated issues directory")
        shutil.copytree(issues, output / "fixes")
        fixes = sum(path.is_dir() for path in (output / "fixes").iterdir())
    else:
        (output / "fixes").mkdir()
    exported_manifest["report_counts"]["proven_fixes"] = fixes
    write_json(output / "manifest.json", exported_manifest)
    write_json(output / "unresolved.json", {"schema_version": 1, "items": unresolved})
    (output / "README.md").write_text(report_readme(exported_manifest, rankings, findings,
                                                       validated, unresolved, fixes, retirements_by_cohort))
    manifest["stage"] = "EXPORTED"
    manifest["last_export"] = str(output)
    write_json(workspace / "manifest.json", manifest)
    return exported_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output", help="fresh report destination (defaults to a timestamped workspace path)")
    parser.add_argument("--repairs", help="existing output from investigate-ci-reliability publish")
    args = parser.parse_args(argv)
    try:
        output = args.output or str(Path(args.workspace) / (
            "report-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
        manifest = run(args.workspace, output, args.repairs)
        print(json.dumps({"output": output, "counts": manifest["report_counts"]}, indent=2))
        return 0
    except (ExportError, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
