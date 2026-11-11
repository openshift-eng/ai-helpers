#!/usr/bin/env python3
"""Build or check before/after run cohorts for a disruption comparison.

Two modes:

around    Propose a before and an after cohort around a transition found by
          disruption-trend. Reads the trend's per-run records (trend.runs_file
          in the state file), so it makes no Sippy request. Each cohort comes
          from jobs that ran on both sides, nearest the step, one run per
          launch batch. Runs whose disruption data is missing or unreliable
          (ci-cluster-network-liveness disrupted) are left out and counted.

validate  Check cohorts the user supplied as Prow URLs and keep them as given.
          Reads each run's prowjob.json (job, start time, payload pair) and
          its disruption seconds on the series backends from Sippy, then
          reports what makes the cohorts hard to compare.

Both modes print the cohorts and comparability notes, and with --state-file
record them under `cohorts` in the investigation state, with the Prow URLs and
job:build_id list that disruption-analyze-run takes.

Usage:
    python3 cohorts.py around --state-file .work/disruption-analysis/<id>/investigation.json \
        [--transition N | --at 2026-11-04T10:00:00Z] [--per-side 5] [--window-days 7]
    python3 cohorts.py validate --before <url>,<url> --after <url>,<url> \
        [--backends kube-api-new-connections] [--state-file <path>]

Exit status: 0 on success, 1 on bad input or when no cohort could be built.
"""
import argparse
import json
import math
import os
import re
import sys
from datetime import timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
# disruption_common is in the disruption plugin's scripts/ directory: two levels
# up when the whole plugin is installed (Claude Code), and inside each skill's
# scripts/ when Chai installs the skill, because it copies the plugin's scripts/
# tree into every skill.
# Search from the skill directory as reached, then from its resolved target,
# since a symlinked skill directory can sit outside the plugin checkout. abspath
# keeps ".." textual, the way sys.path entries resolve it.
_LIB_PARENTS = list(dict.fromkeys(
    os.path.abspath(os.path.join(base, *rel))
    for base in (_HERE, os.path.realpath(_HERE))
    for rel in (("scripts",), ("..", "..", "scripts"))))
for _parent in _LIB_PARENTS:
    if os.path.isfile(os.path.join(_parent, "disruption_common", "__init__.py")):
        sys.path.insert(0, _parent)
        break
else:
    sys.exit("Error: disruption_common library not found. Install the whole disruption plugin; "
             "the library is its scripts/disruption_common. Looked in: %s" % ", ".join(_LIB_PARENTS))

from disruption_common import payloads, sippy, state  # noqa: E402
from disruption_common.series import disruption_peak, split_backends  # noqa: E402

DEFAULT_PER_SIDE = 5
DEFAULT_WINDOW_DAYS = 7
LAUNCH_BATCH_GAP = timedelta(minutes=10)
LIVENESS_BACKENDS = {"ci-cluster-network-liveness-new-connections", "ci-cluster-network-liveness-reused-connections"}
PROW_VIEW = "https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/%s/%s"
# .../logs/<job>/<build_id>; presubmits live under .../pr-logs/pull/<org_repo>/<pr>/<job>/<build_id>
_PROW_PATH = re.compile(r"/logs/([^/]+)/(\d{6,})(?:/|$)")
_PR_LOGS = re.compile(r"/pr-logs/pull/")
_JOB_RELEASE = re.compile(r"-(\d+\.\d+)-")


class CohortError(RuntimeError):
    """The inputs cannot produce a cohort; the message says why."""


def nearest_rank(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct / 100.0 * len(ordered)) - 1)]


def stats(values):
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0, "nonzero": 0, "p50": None, "p95": None, "max": None}
    return {"n": len(values), "nonzero": sum(1 for v in values if v > 0),
            "p50": nearest_rank(values, 50), "p95": nearest_rank(values, 95), "max": max(values)}


def _time(run):
    return sippy.parse_timestamp(run["timestamp"])


def _same_batch(run, chosen):
    return any(other["job"] == run["job"] and abs(_time(other) - _time(run)) <= LAUNCH_BATCH_GAP
               for other in chosen)


def _ref(run):
    keys = ("prow_id", "job", "timestamp", "seconds", "url", "initial_payload", "target_payload")
    return {key: run.get(key) for key in keys if key in run}


def pick_transition(transitions, index=None):
    """The transition to build cohorts around: the one asked for, or the strongest practical increase."""
    if not transitions:
        raise CohortError("the trend found no transitions; pass --at with the date to compare around")
    if index is not None:
        if not 0 <= index < len(transitions):
            raise CohortError("--transition %d is out of range; the trend has %d transition(s) (0-%d)"
                              % (index, len(transitions), len(transitions) - 1))
        return index, transitions[index]
    increases = [(i, t) for i, t in enumerate(transitions) if t.get("practical") and t.get("direction") == "increase"]
    if not increases:
        raise CohortError("the trend has no practical increase; pass --transition N or --at to choose a point")
    return max(increases, key=lambda item: abs(item[1].get("z") or 0))


def _pick_side(candidates, jobs, split, per_side):
    """Up to per_side runs, round-robin over jobs, nearest the split first, one per launch batch."""
    by_job = {job: sorted((r for r in candidates if r["job"] == job), key=lambda r: abs(_time(r) - split))
              for job in jobs}
    chosen = []
    while len(chosen) < per_side and any(by_job.values()):
        for job in jobs:
            queue = by_job[job]
            while queue and _same_batch(queue[0], chosen):
                queue.pop(0)
            if queue and len(chosen) < per_side:
                chosen.append(queue.pop(0))
    return sorted(chosen, key=_time)


def build_around(runs, split, per_side=DEFAULT_PER_SIDE, window_days=DEFAULT_WINDOW_DAYS):
    """Propose cohorts around `split` (a datetime). Returns the cohorts dict."""
    window = timedelta(days=window_days)
    in_window = [r for r in runs if split - window <= _time(r) <= split + window]
    lost = {"before": 0, "after": 0}
    for r in in_window:
        if r.get("fetch_failed") or r.get("seconds") is None:
            lost["before" if _time(r) < split else "after"] += 1
    usable = [r for r in in_window if not r.get("fetch_failed") and r.get("seconds") is not None]
    skipped_liveness = [r for r in usable if r.get("liveness_unreliable")]
    usable = [r for r in usable if not r.get("liveness_unreliable")]
    before = [r for r in usable if _time(r) < split]
    after = [r for r in usable if _time(r) >= split]
    if not before or not after:
        raise CohortError("no usable runs on the %s side within %d day(s) of %s; widen --window-days"
                          % ("before" if not before else "after", window_days, sippy.rfc3339(split)))
    jobs_before = {r["job"] for r in before}
    jobs_after = {r["job"] for r in after}
    shared = jobs_before & jobs_after
    notes = []
    if shared:
        count = {job: min(sum(1 for r in before if r["job"] == job), sum(1 for r in after if r["job"] == job))
                 for job in shared}
        jobs = sorted(shared, key=lambda job: (-count[job], job))
    else:
        jobs = sorted(jobs_before | jobs_after)
        notes.append("No job ran on both sides within the window, so the cohorts come from different jobs. "
                     "A difference between them may come from the jobs, not from a change.")
    picked_before = _pick_side(before, jobs, split, per_side)
    picked_after = _pick_side(after, jobs, split, per_side)
    for side, picked in (("before", picked_before), ("after", picked_after)):
        if len(picked) < per_side:
            notes.append("Only %d %s run(s) fit (asked for %d): the shared jobs have few runs in the window."
                         % (len(picked), side, per_side))
    population = {"before": stats([r["seconds"] for r in before]), "after": stats([r["seconds"] for r in after])}
    cohort_stats = {"before": stats([r["seconds"] for r in picked_before]),
                    "after": stats([r["seconds"] for r in picked_after])}
    for side in ("before", "after"):
        pop, got = population[side], cohort_stats[side]
        if got["n"] and (got["p50"] > pop["p95"] or got["max"] < pop["p50"]):
            notes.append("The %s cohort (median %gs, max %gs) is not typical of the %s side (median %gs, P95 %gs)."
                         % (side, got["p50"], got["max"], side, pop["p50"], pop["p95"]))
    if lost["before"] or lost["after"]:
        notes.append("DEGRADED: disruption data is missing for %d before and %d after run(s) in the window "
                     "(Sippy fetch failed or no value), so the cohorts and population stats leave them out."
                     % (lost["before"], lost["after"]))
    if skipped_liveness:
        notes.append("%d run(s) in the window were left out because ci-cluster-network-liveness was disrupted."
                     % len(skipped_liveness))
    only_before = sorted(jobs_before - jobs_after)
    only_after = sorted(jobs_after - jobs_before)
    if only_after:
        notes.append("Jobs that ran only after the split (not in the cohorts): %s" % ", ".join(only_after))
    if only_before:
        notes.append("Jobs that ran only before the split (not in the cohorts): %s" % ", ".join(only_before))
    return {
        "source": "proposed",
        "at": sippy.rfc3339(split),
        "window_days": window_days,
        "before": [_ref(r) for r in picked_before],
        "after": [_ref(r) for r in picked_after],
        "population": population,
        "cohort_stats": cohort_stats,
        "jobs": jobs,
        "data_loss": lost,
        "notes": notes,
    }


def parse_prow_url(url):
    """(job, build_id) from a Prow or gcsweb URL. Raises CohortError when it is neither."""
    path = url.split("?", 1)[0]
    if _PR_LOGS.search(path):
        raise CohortError("presubmit (pr-logs) runs are not supported; the timeline download reads only "
                          "periodic and release job artifacts under /logs/: %s" % url)
    match = _PROW_PATH.search(path)
    if not match:
        raise CohortError("not a Prow job URL: %s" % url)
    return match.group(1), match.group(2)


def _start_time(prowjob):
    return ((prowjob or {}).get("status") or {}).get("startTime") or ""


def build_validated(before_urls, after_urls, selectors, fetch=payloads.fetch_prowjob,
                    fetch_disruption=sippy.fetch_disruption_data_with_failures, cache_dir=None):
    """Check user cohorts. Returns the cohorts dict, keeping the runs exactly as given."""
    sides = {}
    for side, urls in (("before", before_urls), ("after", after_urls)):
        if not urls:
            raise CohortError("the %s cohort is empty" % side)
        sides[side] = []
        for url in urls:
            job, build_id = parse_prow_url(url)
            sides[side].append({"prow_id": build_id, "job": job, "url": PROW_VIEW % (job, build_id)})
    all_runs = sides["before"] + sides["after"]
    seen = {}
    for run in all_runs:
        if run["prow_id"] in seen:
            raise CohortError("run %s is listed twice" % run["prow_id"])
        seen[run["prow_id"]] = run
    notes = []
    for run in all_runs:
        try:
            prowjob = fetch(run["job"], run["prow_id"])
        except payloads.PayloadError as e:
            run["prowjob_error"] = str(e)
            continue
        pair = payloads.payloads_from_prowjob(prowjob)
        run["initial_payload"], run["target_payload"] = pair["initial"], pair["target"]
        run["timestamp"] = _start_time(prowjob)
    missing = [r["prow_id"] for r in all_runs if "prowjob_error" in r]
    if missing:
        notes.append("prowjob.json could not be read for %d run(s) (%s): their start time and payloads are unknown."
                     % (len(missing), ", ".join(missing)))
    cache_path = os.path.join(cache_dir, "disruption.json") if cache_dir else None
    lookup, failed = fetch_disruption(list(seen), cache_path=cache_path)
    for run in all_runs:
        entries = lookup.get(run["prow_id"]) or []
        run["seconds"], run["backend"] = disruption_peak(entries, selectors) if entries else (None, None)
        run["liveness_unreliable"] = any(e.get("backend_name") in LIVENESS_BACKENDS
                                         and (e.get("disruption_seconds") or 0) > 0 for e in entries)
    if failed:
        notes.append("The Sippy disruption API failed for %d run(s) (%s); their seconds are unknown, not zero."
                     % (len(failed), ", ".join(sorted(failed))))
    no_data = [r["prow_id"] for r in all_runs if r["seconds"] is None and r["prow_id"] not in failed]
    if no_data:
        notes.append("Sippy has no disruption data for %d run(s) (%s) on these backends."
                     % (len(no_data), ", ".join(no_data)))
    unreliable = [r["prow_id"] for r in all_runs if r["liveness_unreliable"]]
    if unreliable:
        notes.append("ci-cluster-network-liveness was disrupted in %s: their disruption data is unreliable."
                     % ", ".join(unreliable))
    notes.extend(comparability_notes(sides["before"], sides["after"]))
    return {
        "source": "user",
        "before": [_ref(r) for r in sides["before"]],
        "after": [_ref(r) for r in sides["after"]],
        "cohort_stats": {side: stats([r.get("seconds") for r in sides[side]]) for side in sides},
        "jobs": sorted({r["job"] for r in all_runs}),
        "notes": notes,
    }


def comparability_notes(before, after):
    """What makes two cohorts hard to compare: different jobs, releases, time order, payloads, overlap."""
    notes = []
    jobs_before, jobs_after = {r["job"] for r in before}, {r["job"] for r in after}
    if not jobs_before & jobs_after:
        notes.append("No job appears in both cohorts. A difference may come from the jobs, not from a change.")
    else:
        for side, only in (("before", jobs_before - jobs_after), ("after", jobs_after - jobs_before)):
            if only:
                notes.append("Jobs only in the %s cohort: %s" % (side, ", ".join(sorted(only))))
    releases = {m.group(1) for r in before + after for m in [_JOB_RELEASE.search(r["job"])] if m}
    if len(releases) > 1:
        notes.append("The cohorts mix releases (%s)." % ", ".join(sorted(releases)))
    times_before = [sippy.parse_timestamp(r["timestamp"]) for r in before if r.get("timestamp")]
    times_after = [sippy.parse_timestamp(r["timestamp"]) for r in after if r.get("timestamp")]
    if times_before and times_after and max(times_before) > min(times_after):
        notes.append("Some before runs started after some after runs; the cohorts are not separated in time.")
    note = payload_note(before, after)
    if note:
        notes.append(note)
    secs_before = [r["seconds"] for r in before if r.get("seconds") is not None]
    secs_after = [r["seconds"] for r in after if r.get("seconds") is not None]
    if secs_before and secs_after and nearest_rank(secs_after, 50) <= nearest_rank(secs_before, 50):
        notes.append("The after cohort's median disruption is not above the before cohort's, so the cohorts "
                     "may not show a regression.")
    return notes


def payload_note(before, after):
    """A note when some after run tested a payload no newer than a before run did, else None."""
    targets_before = [r.get("target_payload") for r in before if payloads.payload_time(r.get("target_payload"))]
    targets_after = [r.get("target_payload") for r in after if payloads.payload_time(r.get("target_payload"))]
    if not targets_before or not targets_after:
        return None
    newest = max(payloads.payload_time(t) for t in targets_before)
    old = sum(1 for t in targets_after if payloads.payload_time(t) <= newest)
    if not old:
        return None
    return ("%d after run(s) tested a payload no newer than the newest before payload, so a payload "
            "change does not separate the cohorts." % old)


def add_handoff(cohorts):
    refs = cohorts["before"] + cohorts["after"]
    cohorts["handoff"] = {
        "prow_urls": {side: [r["url"] for r in cohorts[side] if r.get("url")] for side in ("before", "after")},
        "download_runs": ",".join("%s:%s" % (r["job"], r["prow_id"]) for r in refs),
    }
    return cohorts


def _fmt(value):
    return "—" if value is None else "%g" % value


def print_text(cohorts, out=None):
    out = out or sys.stdout
    if cohorts["source"] == "proposed":
        out.write("Cohorts around %s (±%d days), jobs that ran on both sides:\n"
                  % (cohorts["at"], cohorts["window_days"]))
    else:
        out.write("Cohorts as given by the user (kept unchanged):\n")
    for side in ("before", "after"):
        got = cohorts["cohort_stats"][side]
        line = "\n%s: %d run(s), %d disrupted, median %ss, max %ss" % (
            side.capitalize(), got["n"], got["nonzero"], _fmt(got["p50"]), _fmt(got["max"]))
        pop = (cohorts.get("population") or {}).get(side)
        if pop:
            line += "  (all %d %s runs: median %ss, P95 %ss)" % (pop["n"], side, _fmt(pop["p50"]), _fmt(pop["p95"]))
        out.write(line + "\n")
        for run in cohorts[side]:
            pair = ""
            if run.get("target_payload"):
                pair = "  %s -> %s" % (run.get("initial_payload") or "?", run["target_payload"])
            out.write("  %-20s %6ss  %s  %s%s\n" % (run.get("timestamp") or "?", _fmt(run.get("seconds")),
                                                     run["job"], run.get("url") or run["prow_id"], pair))
    if cohorts["notes"]:
        out.write("\nComparability notes:\n")
        for note in cohorts["notes"]:
            out.write("  - %s\n" % note)
    out.write("\nFor disruption-analyze-run: --runs \"%s\"\n" % cohorts["handoff"]["download_runs"])


def record(state_path, cohorts):
    current = state.load_state(state_path)
    current["cohorts"] = cohorts
    state.write_json_atomic(state_path, current, indent=2)


def _load_runs(path):
    try:
        with open(path) as f:
            runs = json.load(f)
    except (OSError, ValueError) as e:
        raise CohortError("cannot read runs file %s: %s" % (path, e))
    if not isinstance(runs, list):
        raise CohortError("runs file %s is not a list of runs" % path)
    return runs


def run_around(args):
    current = state.load_state(args.state_file) if args.state_file else {}
    trend = current.get("trend") or {}
    runs_path = args.runs_file or trend.get("runs_file")
    if not runs_path:
        raise CohortError("no runs file: run disruption-trend with --state-file first, or pass --runs-file")
    if not args.runs_file and not os.path.exists(runs_path):
        # The investigation directory moved, or an older state file kept a relative path.
        beside_state = os.path.join(os.path.dirname(os.path.abspath(args.state_file)), os.path.basename(runs_path))
        if os.path.exists(beside_state):
            runs_path = beside_state
    runs = _load_runs(runs_path)
    transition_index = None
    if args.at:
        split = sippy.parse_timestamp(args.at)
        if split == sippy.parse_timestamp(None):
            raise CohortError("cannot parse --at %r; use an RFC 3339 time such as 2026-11-04T10:00:00Z" % args.at)
    else:
        transition_index, transition = pick_transition(trend.get("transitions") or [], args.transition)
        split = sippy.parse_timestamp(transition["at"])
    cohorts = build_around(runs, split, args.per_side, args.window_days)
    if transition_index is not None:
        cohorts["transition"] = transition_index
    if not args.no_payloads:
        cache = os.path.join(args.cache_dir, "prowjob-payloads.json") if args.cache_dir else None
        chosen = cohorts["before"] + cohorts["after"]
        pairs, failed = payloads.fetch_payloads(chosen, cache_path=cache, write=state.write_json_atomic)
        for run in chosen:
            pair = pairs.get(str(run["prow_id"]))
            if pair:
                run["initial_payload"], run["target_payload"] = pair["initial"], pair["target"]
        if failed:
            cohorts["notes"].append("prowjob.json could not be read for %d chosen run(s); their payloads are unknown."
                                    % len(failed))
        note = payload_note(cohorts["before"], cohorts["after"])
        if note:
            cohorts["notes"].append(note)
    return cohorts


def run_validate(args):
    selectors = split_backends(args.backends) if args.backends else []
    if not selectors and args.state_file:
        selectors = (state.load_state(args.state_file).get("series") or {}).get("backends") or []
    if not selectors:
        raise CohortError("pass --backends, or a --state-file whose series names the backends")
    return build_validated(split_backends(args.before), split_backends(args.after), selectors,
                           cache_dir=args.cache_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    around = sub.add_parser("around", help="propose cohorts around a transition")
    around.add_argument("--state-file", help="investigation.json written by disruption-trend")
    around.add_argument("--runs-file", help="per-run records (trend.runs_file); defaults to the state's")
    around.add_argument("--transition", type=int, help="index into trend.transitions (default: strongest increase)")
    around.add_argument("--at", help="split time instead of a transition, e.g. 2026-11-04T10:00:00Z")
    around.add_argument("--per-side", type=int, default=DEFAULT_PER_SIDE)
    around.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    around.add_argument("--no-payloads", action="store_true", help="skip reading prowjob.json for payload pairs")
    validate = sub.add_parser("validate", help="check user-supplied cohorts and keep them as given")
    validate.add_argument("--before", required=True, help="comma-separated Prow URLs")
    validate.add_argument("--after", required=True, help="comma-separated Prow URLs")
    validate.add_argument("--backends", help="exact backend names (default: the state file's series)")
    validate.add_argument("--state-file", help="investigation.json to read the series from and record into")
    for p in (around, validate):
        p.add_argument("--cache-dir", default=".work/disruption-analysis/cache")
        p.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    if getattr(args, "per_side", 1) < 1 or getattr(args, "window_days", 1) < 1:
        print("Error: --per-side and --window-days must be positive", file=sys.stderr)
        return 1
    try:
        cohorts = add_handoff(run_around(args) if args.mode == "around" else run_validate(args))
    except (CohortError, state.StateError) as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1
    if args.state_file:
        try:
            record(args.state_file, cohorts)
        except (state.StateError, OSError) as e:
            print("Error: cohorts not recorded: %s" % e, file=sys.stderr)
            return 1
        cohorts["state_file"] = args.state_file
    if args.format == "json":
        print(json.dumps(cohorts, indent=2))
    else:
        print_text(cohorts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
