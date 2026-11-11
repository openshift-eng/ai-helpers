#!/usr/bin/env python3
"""Line up per-run signals across a before and an after cohort.

Reads the parser output for each run (`parse_disruption.py --format json`,
saved by disruption-analyze-run as <runs-dir>/<build_id>/parsed.json) and
builds a candidate x cohort matrix. Each row is one signal, with how many runs
in each cohort show it and its median size there:

- disruption on the selected backends: disruptions, episodes, waves, and the
  count in the upgrade and conformance phases
- run-wide stress (run_context): every context source over the whole run,
  so a clean before run still shows the etcd, OVS, CPU, or cloud stress it had
- stress during disruption (concurrent_events): the same sources, only near
  disruption windows
- static-pod revision rollouts per operator, and how many of them had
  disruption episodes inside

Each row gets a suggested label (new, more in after, pre-existing similar,
less in after, before only, sporadic). The label only compares counts; the
skill decides what the evidence shows.

Usage:
    python3 compare_cohorts.py --state-file .work/disruption-analysis/<id>/investigation.json \
        --runs-dir .work/disruption-analysis/<id>/runs
    python3 compare_cohorts.py --before a.json,b.json --after c.json,d.json [--format json]

Exit status: 0 on success, 1 on bad input or when a cohort has no parsed run.
"""
import argparse
import json
import os
import statistics
import sys

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

from disruption_common import state  # noqa: E402

PARSED_NAME = "parsed.json"
RATE_SHIFT = 0.3
SIZE_RATIO = 1.5


class CompareError(RuntimeError):
    """The cohorts cannot be compared; the message says why."""


def _size(source, value):
    """The magnitude of one context source in one run."""
    if source == "OVSVswitchdLog":
        return value.get("max_poll_interval_ms") or 0
    if source == "CPUMonitor":
        return len({n.get("node") for n in value.get("nodes") or []})
    if source == "CloudMetrics":
        return max([m.get("max_value") or 0 for m in (value.get("metrics") or {}).values()] or [0])
    return value.get("count") or 0


_UNITS = {"OVSVswitchdLog": "max poll ms", "CPUMonitor": "nodes >95% CPU", "CloudMetrics": "max metric value"}


def run_features(parsed):
    """{feature: (kind, size)} for one run's parser output. Absent features are not listed."""
    features = {}
    summary = parsed.get("summary") or {}
    for key, label in (("disruption_count", "disruptions"), ("episode_count", "episodes"),
                       ("wave_count", "waves")):
        if summary.get(key):
            features[label] = ("disruption", summary[key])
    for phase, count in (summary.get("phase_breakdown") or {}).items():
        if count:
            features["disruptions in %s phase" % phase] = ("disruption", count)
    for source, value in (parsed.get("run_context") or {}).items():
        size = _size(source, value)
        if size:
            features["%s (%s)" % (source, _UNITS.get(source, "events"))] = ("run-wide", size)
    for source, value in (parsed.get("concurrent_events") or {}).items():
        size = _size(source, value)
        if size:
            features["%s during disruption (%s)" % (source, _UNITS.get(source, "events"))] = ("during", size)
    rollouts = {}
    inside = {}
    for rollout in parsed.get("revision_rollouts") or []:
        operator = rollout.get("operator", "?")
        rollouts[operator] = rollouts.get(operator, 0) + 1
        if rollout.get("episode_indices"):
            inside[operator] = inside.get(operator, 0) + 1
    for operator, count in rollouts.items():
        features["%s revision rollouts" % operator] = ("rollout", count)
    for operator, count in inside.items():
        features["%s rollouts with disruption inside" % operator] = ("rollout", count)
    return features


def _side(values, n):
    sizes = values + [0] * (n - len(values))
    return {"runs": len(values), "of": n, "median": statistics.median(sizes) if sizes else 0,
            "max": max(values) if values else 0}


def suggest(before, after):
    """Suggested label from presence rates and median sizes. The skill judges the evidence."""
    rate_b = before["runs"] / before["of"] if before["of"] else 0
    rate_a = after["runs"] / after["of"] if after["of"] else 0
    if before["runs"] == 0:
        return "new" if rate_a >= 0.5 else "sporadic in after"
    if after["runs"] == 0:
        return "before only"
    if rate_a - rate_b >= RATE_SHIFT or after["median"] >= SIZE_RATIO * before["median"] > 0 \
            or (before["median"] == 0 and after["median"] > 0):
        return "more in after"
    if rate_b - rate_a >= RATE_SHIFT or before["median"] >= SIZE_RATIO * after["median"] > 0 \
            or (after["median"] == 0 and before["median"] > 0):
        return "less in after"
    return "pre-existing, similar"


_KIND_ORDER = {"disruption": 0, "rollout": 1, "during": 2, "run-wide": 3}
_LABEL_ORDER = {"new": 0, "more in after": 1, "sporadic in after": 2, "pre-existing, similar": 3,
                "less in after": 4, "before only": 5}


def build_matrix(cohort_runs):
    """cohort_runs: {"before": {build_id: parsed}, "after": {...}}. Returns (rows, per_run)."""
    per_run = {side: {bid: run_features(parsed) for bid, parsed in runs.items()}
               for side, runs in cohort_runs.items()}
    names = {}
    for side in per_run.values():
        for features in side.values():
            for name, (kind, _size_value) in features.items():
                names[name] = kind
    rows = []
    for name, kind in names.items():
        sides = {}
        for side in ("before", "after"):
            values = [f[name][1] for f in per_run[side].values() if name in f]
            sides[side] = _side(values, len(per_run[side]))
            sides[side]["build_ids"] = sorted(bid for bid, f in per_run[side].items() if name in f)
        rows.append({"signal": name, "kind": kind, "before": sides["before"], "after": sides["after"],
                     "suggested": suggest(sides["before"], sides["after"])})
    rows.sort(key=lambda r: (_KIND_ORDER.get(r["kind"], 9), _LABEL_ORDER.get(r["suggested"], 9), r["signal"]))
    return rows, per_run


def run_facts(cohort_runs):
    """Per run: payload pair, liveness status, and episode summary, for the report."""
    facts = {}
    for side, runs in cohort_runs.items():
        for bid, parsed in runs.items():
            summary = parsed.get("summary") or {}
            pay = parsed.get("payloads") or {}
            facts[bid] = {"cohort": side, "initial_payload": pay.get("initial"), "target_payload": pay.get("target"),
                          "network_liveness": summary.get("network_liveness_status"),
                          "episodes": summary.get("episode_summary")}
    return facts


def _load(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise CompareError("cannot read parser output %s: %s" % (path, e))
    if not isinstance(data, dict) or "summary" not in data:
        raise CompareError("%s is not parse_disruption.py --format json output" % path)
    return data


def _build_id(path):
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    return parent if parent.isdigit() else os.path.splitext(os.path.basename(path))[0]


def load_cohorts(args):
    """{"before": {build_id: parsed}, "after": {...}} and notes about runs that were skipped."""
    notes = []
    cohort_runs = {"before": {}, "after": {}}
    if args.before or args.after:
        if not (args.before and args.after):
            raise CompareError("pass both --before and --after")
        for side in ("before", "after"):
            for path in getattr(args, side).split(","):
                path = path.strip()
                if path:
                    cohort_runs[side][_build_id(path)] = _load(path)
    else:
        if not args.state_file or not args.runs_dir:
            raise CompareError("pass --state-file and --runs-dir, or --before and --after parser outputs")
        cohorts = state.load_state(args.state_file).get("cohorts") or {}
        if not cohorts.get("before") or not cohorts.get("after"):
            raise CompareError("the state file has no cohorts; run disruption-find-runs first")
        for side in ("before", "after"):
            for run in cohorts[side]:
                bid = str(run.get("prow_id"))
                path = os.path.join(args.runs_dir, bid, PARSED_NAME)
                if not os.path.exists(path):
                    notes.append("Run %s (%s) has no %s; analyze it with disruption-analyze-run first."
                                 % (bid, side, path))
                    continue
                cohort_runs[side][bid] = _load(path)
    for side, runs in cohort_runs.items():
        if not runs:
            raise CompareError("the %s cohort has no parsed run" % side)
    return cohort_runs, notes


def _fmt(value):
    return ("%g" % value) if isinstance(value, (int, float)) else str(value)


def print_text(result, out=None):
    out = out or sys.stdout
    n_before, n_after = len(result["runs"]["before"]), len(result["runs"]["after"])
    out.write("Signals across cohorts (before: %d run(s), after: %d run(s))\n\n" % (n_before, n_after))
    header = "%-62s %-11s %-16s %-16s %s\n" % ("signal", "kind", "before runs/med", "after runs/med", "suggested")
    out.write(header)
    out.write("-" * (len(header) - 1) + "\n")
    for row in result["matrix"]:
        b, a = row["before"], row["after"]
        out.write("%-62s %-11s %-16s %-16s %s\n" % (
            row["signal"][:62], row["kind"], "%d/%d  %s" % (b["runs"], b["of"], _fmt(b["median"])),
            "%d/%d  %s" % (a["runs"], a["of"], _fmt(a["median"])), row["suggested"]))
    out.write("\nRuns:\n")
    for bid, fact in sorted(result["facts"].items(), key=lambda kv: (kv[1]["cohort"] != "before", kv[0])):
        out.write("  %-6s %s  liveness=%s  %s -> %s  %s\n" % (
            fact["cohort"], bid, fact["network_liveness"], fact["initial_payload"] or "?",
            fact["target_payload"] or "?", fact["episodes"] or ""))
    for note in result["notes"]:
        out.write("Note: %s\n" % note)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--state-file", help="investigation.json with cohorts from disruption-find-runs")
    parser.add_argument("--runs-dir", help="directory holding <build_id>/parsed.json per run")
    parser.add_argument("--before", help="comma-separated parser JSON files (instead of the state's cohorts)")
    parser.add_argument("--after", help="comma-separated parser JSON files")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        cohort_runs, notes = load_cohorts(args)
    except (CompareError, state.StateError) as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1
    rows, _per_run = build_matrix(cohort_runs)
    result = {"matrix": rows, "runs": {side: sorted(runs) for side, runs in cohort_runs.items()},
              "facts": run_facts(cohort_runs), "notes": notes}
    unreliable = sorted(bid for bid, f in result["facts"].items() if f["network_liveness"] in ("degraded", "unreliable"))
    if unreliable:
        notes.append("Network liveness is degraded or unreliable in %s: do not rest a conclusion on their "
                     "disruption counts alone." % ", ".join(unreliable))
    if args.state_file and not (args.before or args.after):
        try:
            current = state.load_state(args.state_file)
            current["comparison"] = dict(current.get("comparison") or {}, matrix=rows, runs=result["runs"],
                                         facts=result["facts"], notes=notes)
            state.write_json_atomic(args.state_file, current, indent=2)
        except (state.StateError, OSError) as e:
            print("Error: comparison not recorded: %s" % e, file=sys.stderr)
            return 1
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
