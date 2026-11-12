"""Find Prow job runs with disruption from Grafana dashboard parameters.

Takes Grafana disruption dashboard URL parameters (platform, backend,
upgrade type, etc.), queries Sippy for matching runs, enriches them with
actual disruption seconds from BigQuery, and outputs a candidate table.

Series resolution and Sippy access live in the shared disruption_common
library (the plugin's scripts/disruption_common).

Usage:
    python3 find_disruption_runs.py --grafana-url <url>
    python3 find_disruption_runs.py --alert-file alert.txt
    python3 find_disruption_runs.py --release 5.0 --platform gcp --backend host-to-host-new-connections --upgrade-type micro --architecture amd64 --topology ha --network ovn

Output formats:
    --format table   (default) Compact report: series header, per-backend and
                     per-job summaries, recommended rows, and the top --top rows.
                     The full table is written to --full-table-out (or a default
                     path under .work/disruption-analysis/) when rows are cut.
    --format json    Machine-readable JSON array of every row
"""
import argparse
import functools
import json
import math
import os
import re
import statistics
import sys
from datetime import datetime, timezone

# disruption_common is in the disruption plugin's scripts/ directory: two levels
# up when the whole plugin is installed (Claude Code), and inside each skill's
# scripts/ when Chai installs the skill, because it copies the plugin's scripts/
# tree into every skill.
_HERE = os.path.dirname(os.path.abspath(__file__))
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

from disruption_common import series, sippy  # noqa: E402
from disruption_common.series import (  # noqa: E402
    GRAFANA_TO_VARIANT,
    disruption_peak,
    expand_backend_selectors,
    is_all_sentinel,
    master_nodes_means_all,
    selector_bases,
    split_backends,
)

# A single page is not the candidate set — scoring happens after the scan.
MAX_SCANNED_RUNS = 5000
# Same-job runs starting this close to a batch's first run share a launch (and payload).
BATCH_WINDOW_SECONDS = 300
CROSS_JOB_WINDOW_SECONDS = 5
# Sister shards of one job (-1of2, -2of2) launched together share an event.
_SHARD_SUFFIX = re.compile(r"-\d+of\d+$")
# Runs above this multiple of the percentile value are outliers; the rest set the tail.
OUTLIER_FACTOR = 2
DEFAULT_PERCENTILE = 95.0
TIERS = ("outlier", "tail")
# Rows printed by default in table format; the full table goes to a file.
DEFAULT_TOP_ROWS = 20
# A disrupted run is correlated when every selected backend is within this fraction of its max.
CORRELATION_TOLERANCE = 0.15


def max_disruption_for_backend(disruption_entries, selectors):
    """Max disruption seconds among the exact names `selectors` expands to."""
    secs, _name = disruption_peak(disruption_entries, selectors)
    return secs


def extract_disruption_failures(failed_test_names):
    """Extract disruption backend names from failed test names.

    Test name format:
        [Monitor:...] disruption/{backend} ... connection/{type} should be available ...
    """
    if not failed_test_names:
        return []
    backends = []
    for name in failed_test_names:
        match = re.search(r"disruption/([^\s]+)", name)
        if match:
            backends.append(match.group(1))
    return sorted(set(backends))


def is_upgrade_job(job):
    """True when the job name says it is an upgrade job."""
    return "upgrade" in (job or "").lower()


def is_upgrade_series(variants):
    """True when the series' Upgrade filter names at least one value other than none."""
    values = split_backends((variants or {}).get("Upgrade"))
    return any(value.lower() != "none" for value in values)


def select_representative_runs(rows, disruption_data, base_backend, n=5, upgrade_series=False,
                               percentile=None, explain=None):
    """Select a representative sample of job runs for analysis.

    Rules (documented in references/run-discovery.md):
    1. The top run (most seconds, newest on a tie) is always picked.
    2. One pick per event. Same-job runs that start within BATCH_WINDOW_SECONDS
       of the batch's first run keep only the worst. Runs of any job that start
       within CROSS_JOB_WINDOW_SECONDS, and sister shards (-1of2, -2of2) that
       start within BATCH_WINDOW_SECONDS, are one event. Runs in the top run's
       event add no weight to their jobs.
    3. Runs split into two tiers at the dashboard percentile (P95 by default)
       of all runs in the series: outliers above OUTLIER_FACTOR times that
       value, and tail runs at or below it. Picks alternate between populated
       tiers, so both the large outages and the runs that set the percentile
       are covered. The top run is the first pick of its tier.
    4. Within a tier, a job's weight is its disrupted events times their
       median seconds, so one large run cannot buy a job extra picks. In an
       upgrade series a non-upgrade job counts half. Each next pick goes to
       the job with the most weight per pick it already has in that tier.
    5. A job's first pick in a tier is its worst batch, the next its most
       typical (closest to the median), then down by seconds.
    6. With n >= 3, a 0s run from a picked job is added as a clean comparison.

    explain, when a dict, receives the cutoff, tier sizes, and the runs merged
    into each picked event, for the table summary.
    """
    if not rows or n <= 0:
        return []
    known = [e for e in _enrich_runs(rows, disruption_data, base_backend)
             if e["disruption_seconds"] is not None]
    disrupted = [e for e in known if e["disruption_seconds"] > 0]
    if not disrupted:
        return []

    pct = _percentile_number(percentile)
    cutoff = _nearest_rank([e["disruption_seconds"] for e in known], pct)
    tier_of = functools.partial(_tier, cutoff=cutoff)
    top = max(disrupted, key=_rank_key)
    candidates = _dedupe_batches(known)
    zero_runs = [c for c in candidates if c["disruption_seconds"] == 0]
    clusters = _event_clusters(candidates)
    top_event = clusters[top["index"]]
    # Weight comes from every disrupted run, except the ones the top run already stands for.
    weighed = [e for e in _dedupe_batches(disrupted) if e is top or clusters.get(e["index"]) != top_event]
    batches = [c for c in candidates if c["disruption_seconds"] > 0 and c is not top]

    picks = [top] + _tiered_picks(batches, weighed, upgrade_series, n - 1, top, clusters, tier_of)
    if n >= 3:
        picks = _add_clean_comparison(picks, zero_runs, n, top)
    if explain is not None:
        explain.update(_explanation(rows, known, disrupted, picks, clusters, pct, cutoff, tier_of))
    return sorted(p["index"] for p in picks)


def _percentile_number(value):
    """95 from "P95", 95, or None; the dashboard default when unreadable."""
    match = re.search(r"\d+(\.\d+)?", str(value or ""))
    number = float(match.group(0)) if match else DEFAULT_PERCENTILE
    return number if 0 < number <= 100 else DEFAULT_PERCENTILE


def _nearest_rank(values, pct):
    """Nearest-rank percentile of values; 0 for none."""
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct / 100.0 * len(ordered)) - 1)]


def _tier(seconds, cutoff):
    """"outlier" above OUTLIER_FACTOR times the cutoff, else "tail". A 0s cutoff makes every disrupted run an outlier."""
    return "outlier" if seconds > OUTLIER_FACTOR * cutoff else "tail"


def _shard_family(job):
    """The job name without a -1of2 style shard suffix, or None when it has none."""
    stripped = _SHARD_SUFFIX.sub("", job or "")
    return stripped if stripped != job else None


def _enrich_runs(rows, disruption_data, selectors):
    """Run rows with their index, job, start time, and peak seconds for the selected backends."""
    enriched = []
    for i, row in enumerate(rows):
        pid = str(row.get("prow_id", ""))
        enriched.append({
            "index": i,
            "job": row.get("job", ""),
            "timestamp": sippy.parse_timestamp(row.get("timestamp", "")),
            "disruption_seconds": max_disruption_for_backend(disruption_data.get(pid), selectors),
        })
    return enriched


def _rank_key(entry):
    """Most seconds first, then newest, then earliest row: the display order."""
    return (entry["disruption_seconds"], entry["timestamp"], -entry["index"])


def _dedupe_batches(entries):
    """Keep the worst run of each launch batch (same job, start within the batch window)."""
    groups = []
    for entry in sorted(entries, key=lambda e: (e["job"], e["timestamp"])):
        anchor = groups[-1][0] if groups else None
        if (anchor and entry["job"] == anchor["job"]
                and (entry["timestamp"] - anchor["timestamp"]).total_seconds() <= BATCH_WINDOW_SECONDS):
            groups[-1].append(entry)
        else:
            groups.append([entry])
    return [max(g, key=_rank_key) for g in groups]


def _event_clusters(entries):
    """Map row index to an event ID.

    One event is runs of any job that start within the cross-job window of
    the first, or sister shards that start within the batch window of the
    first. Each window is anchored at its first run, not chained.
    """
    parent = {e["index"]: e["index"] for e in entries}

    def find(index):
        """The root of an index's group, compressing the path on the way."""
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def link(groups, window):
        """Join each group's runs that start within window seconds of the run anchoring their event."""
        for _key, items in groups:
            anchor = None
            for entry in sorted(items, key=lambda e: e["timestamp"]):
                if anchor is None or (entry["timestamp"] - anchor["timestamp"]).total_seconds() > window:
                    anchor = entry
                parent[find(entry["index"])] = find(anchor["index"])

    link([(None, entries)], CROSS_JOB_WINDOW_SECONDS)
    shards = {}
    for entry in entries:
        family = _shard_family(entry["job"])
        if family:
            shards.setdefault(family, []).append(entry)
    link(shards.items(), BATCH_WINDOW_SECONDS)
    return {index: find(index) for index in parent}


def _group_weights(weighed, upgrade_series, tier_of):
    """(tier, job) -> disrupted events times their median seconds; non-upgrade jobs count half in an upgrade series."""
    seconds = {}
    for entry in weighed:
        key = (tier_of(entry["disruption_seconds"]), entry["job"])
        seconds.setdefault(key, []).append(entry["disruption_seconds"])
    weights = {}
    for key, values in seconds.items():
        weights[key] = len(values) * statistics.median(values)
        if upgrade_series and not is_upgrade_job(key[1]):
            weights[key] /= 2.0
    return weights, {key: statistics.median(values) for key, values in seconds.items()}


def _tiered_picks(batches, weighed, upgrade_series, slots, top, clusters, tier_of):
    """Hand out slots, alternating between tiers, to the job with the most weight per pick.

    The tier with fewer picks goes next (outliers first on a tie). Within it,
    ties go to the job with fewer picks in any tier, then the job name. The top run
    already holds one pick. A batch in the same event as an earlier pick is
    skipped.
    """
    weights, medians = _group_weights(weighed, upgrade_series, tier_of)
    top_key = (tier_of(top["disruption_seconds"]), top["job"])
    by_key = {}
    for batch in batches:
        key = (tier_of(batch["disruption_seconds"]), batch["job"])
        if key in weights:
            by_key.setdefault(key, []).append(batch)
    queues = {key: _pick_order(items, medians[key], key == top_key) for key, items in by_key.items()}
    counts = {top_key: 1}
    job_counts = {top["job"]: 1}
    tier_counts = {top_key[0]: 1}
    used = {clusters[top["index"]]}

    picks = []
    while len(picks) < slots:
        for queue in queues.values():
            while queue and clusters[queue[0]["index"]] in used:
                queue.pop(0)
        open_keys = [key for key, queue in queues.items() if queue]
        if not open_keys:
            break
        tier = min({key[0] for key in open_keys}, key=lambda t: (tier_counts.get(t, 0), TIERS.index(t)))
        key = min((k for k in open_keys if k[0] == tier),
                  key=lambda k: (-weights[k] / (counts.get(k, 0) + 1), job_counts.get(k[1], 0), k[1]))
        picks.append(queues[key].pop(0))
        used.add(clusters[picks[-1]["index"]])
        counts[key] = counts.get(key, 0) + 1
        job_counts[key[1]] = job_counts.get(key[1], 0) + 1
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    return picks


def _explanation(rows, known, disrupted, picks, clusters, pct, cutoff, tier_of):
    """What the table summary says about the picks."""
    outliers = sum(1 for e in disrupted if tier_of(e["disruption_seconds"]) == "outlier")
    by_event = {}
    for entry in disrupted:
        by_event.setdefault(clusters.get(entry["index"]), []).append(entry)
    shared = []
    for pick in picks:
        if pick["disruption_seconds"] == 0:
            continue
        others = [e for e in by_event.get(clusters.get(pick["index"]), []) if e is not pick]
        if others:
            shared.append({"prow_id": str(rows[pick["index"]].get("prow_id", "")),
                           "with": [str(rows[e["index"]].get("prow_id", "")) for e in others]})
    return {"percentile": pct, "cutoff": cutoff, "outlier_above": OUTLIER_FACTOR * cutoff,
            "runs": len(known), "outliers": outliers, "tail": len(disrupted) - outliers, "shared": shared}


def _pick_order(batches, median, worst_taken):
    """One job's batches in pick order: worst, most typical, then down by seconds."""
    ordered = sorted(batches, key=_rank_key, reverse=True)
    first = [] if worst_taken else ordered[:1]
    rest = ordered[len(first):]
    if rest:
        typical = min(rest, key=lambda b: (abs(b["disruption_seconds"] - median), -b["disruption_seconds"], b["index"]))
        rest.remove(typical)
        first.append(typical)
    return first + rest


def _add_clean_comparison(picks, zero_runs, n, top):
    """Add a 0s run from the highest-priority picked job, in a free slot or by replacement."""
    picked_jobs = [p["job"] for p in picks]
    clean = [z for z in zero_runs if z["job"] in picked_jobs]
    if not clean:
        return picks
    clean_pick = min(clean, key=lambda z: (picked_jobs.index(z["job"]), z["index"]))
    if len(picks) < n:
        return picks + [clean_pick]
    return _replace_disrupted_with_clean(picks, clean_pick, top)


def _replace_disrupted_with_clean(picks, clean_pick, top):
    """Swap the last droppable pick for clean_pick.

    The top run and the only pick from clean_pick's job are never dropped,
    so the clean run always has a disrupted partner.
    """
    same_job = [p for p in picks if p["job"] == clean_pick["job"]]
    droppable = [p for p in picks if p is not top and not (len(same_job) == 1 and p is same_job[0])]
    if not droppable:
        return picks
    drop = droppable[-1]
    return [clean_pick if p is drop else p for p in picks]


def format_timestamp(ts):
    """Reformat an RFC 3339 timestamp to a shorter display form (YYYY-MM-DD HH:MM).

    A missing timestamp — None or an empty string — returns an empty string
    rather than a 1970 epoch date, since callers pass "" when the timestamp is
    absent. A numeric 0 is a valid epoch-ms value and formats normally.
    """
    if ts is None or ts == "":
        return ""
    return sippy.parse_timestamp(ts).strftime("%Y-%m-%d %H:%M")


def _backend_label(selectors):
    """The selected backends as one display string."""
    if isinstance(selectors, str):
        return selectors
    return ", ".join(selectors)


# Derived probe families; any other name is a main (load-balancer or in-cluster) backend.
_PROBE_FAMILIES = (
    ("*-localhost-*", lambda name: "-localhost-" in name),
    ("*-service-network-*", lambda name: "-service-network-" in name),
    ("*-internal-lb-*", lambda name: "-internal-lb-" in name),
    ("cache-*", lambda name: name.startswith("cache-")),
)


def probe_family(name):
    """The derived probe family of a backend name, or None for a main backend."""
    for family, matches in _PROBE_FAMILIES:
        if matches(name):
            return family
    return None


def _fmt_secs(value):
    """Seconds without a decimal when whole, else with one."""
    return "%d" % value if float(value).is_integer() else "%.1f" % value


def _run_secs(row, disruption_data, selectors):
    """Peak seconds of a run row for the selected backends."""
    return disruption_peak(disruption_data.get(str(row.get("prow_id", ""))), selectors)


def backend_summary(rows, disruption_data, selectors):
    """Per exact selected backend: runs > 0, runs where it was the max, median seconds when > 0."""
    stats = {name: {"name": name, "nonzero": [], "max_in": 0} for name in expand_backend_selectors(selectors)}
    for row in rows:
        entries = disruption_data.get(str(row.get("prow_id", ""))) or []
        for entry in entries:
            name = entry.get("backend_name")
            if name in stats and (entry.get("disruption_seconds") or 0) > 0:
                stats[name]["nonzero"].append(entry["disruption_seconds"])
        secs, peak = disruption_peak(entries, selectors)
        if peak and secs > 0:
            stats[peak]["max_in"] += 1
    summary = [{"name": s["name"], "nonzero": len(s["nonzero"]), "max_in": s["max_in"],
                "median": statistics.median(s["nonzero"]) if s["nonzero"] else None}
               for s in stats.values()]
    return sorted(summary, key=lambda s: (-s["max_in"], -s["nonzero"], s["name"]))


def dominant_probe_family(summary):
    """(family, runs, disrupted runs) when one derived probe family is the max in most disrupted runs.

    Only reported when the selection spans more than one family (main
    backends count as one), since then the ranking may not be what was meant.
    """
    families = {probe_family(s["name"]) for s in summary}
    disrupted = sum(s["max_in"] for s in summary)
    if len(families) < 2 or not disrupted:
        return None
    by_family = {}
    for s in summary:
        family = probe_family(s["name"])
        if family:
            by_family[family] = by_family.get(family, 0) + s["max_in"]
    for family, count in sorted(by_family.items(), key=lambda item: -item[1]):
        if count * 2 > disrupted:
            return family, count, disrupted
    return None


def correlated_runs(rows, disruption_data, selectors, tolerance=CORRELATION_TOLERANCE):
    """(correlated, disrupted): disrupted runs where every selected backend with data is
    nonzero and within tolerance of that run's max."""
    allowed = expand_backend_selectors(selectors)
    correlated = disrupted = 0
    for row in rows:
        entries = [e for e in disruption_data.get(str(row.get("prow_id", ""))) or []
                   if e.get("backend_name") in allowed]
        peak = max([e.get("disruption_seconds") or 0 for e in entries] or [0])
        if peak <= 0:
            continue
        disrupted += 1
        if len(entries) > 1 and all((e.get("disruption_seconds") or 0) >= peak * (1 - tolerance) for e in entries):
            correlated += 1
    return correlated, disrupted


def job_summary(rows, disruption_data, selectors):
    """Per job with disruption: runs, disrupted runs, total and median seconds, sorted by total."""
    jobs = {}
    for row in rows:
        job = jobs.setdefault(row.get("job", "?"), {"job": row.get("job", "?"), "runs": 0, "secs": []})
        job["runs"] += 1
        secs = _run_secs(row, disruption_data, selectors)[0]
        if secs:
            job["secs"].append(secs)
    summary = [{"job": j["job"], "runs": j["runs"], "disrupted": len(j["secs"]),
                "total": sum(j["secs"]), "median": statistics.median(j["secs"])}
               for j in jobs.values() if j["secs"]]
    return sorted(summary, key=lambda j: (-j["total"], j["job"]))


def _print_header(emit, grafana_params, window_start, scanned_count, truncated, row_count):
    """Print the dashboard name, filters, window, and how many runs were scanned."""
    dashboard_name = grafana_params.get("_dashboard_name", "")
    filters = []
    for gkey, variant_key in GRAFANA_TO_VARIANT.items():
        val = grafana_params.get(gkey)
        if val and not is_all_sentinel(val):
            filters.append("%s=%s" % (variant_key, val))
    masters = grafana_params.get("master_nodes_updated")
    if masters and not is_all_sentinel(masters) and not master_nodes_means_all(masters):
        filters.append("MasterNodesUpdated=%s" % masters)
    summary_extra = []
    lookback = grafana_params.get("lookback")
    if lookback:
        summary_extra.append("Lookback=%sd" % lookback)
    compare_release = grafana_params.get("compare_release")
    if compare_release:
        summary_extra.append("CompareRelease=%s" % compare_release)

    emit("Dashboard: %s" % dashboard_name)
    emit("Filters: %s" % " | ".join(filters))
    release_line = "Release: %s | Percentile: %s | Backend: %s" % (
        grafana_params.get("releases", ""), grafana_params.get("percentile", ""), grafana_params.get("backend", ""))
    if summary_extra:
        release_line += " | " + " | ".join(summary_extra)
    emit(release_line)
    if window_start is not None:
        emit("Window start: %s" % format_timestamp(window_start.isoformat().replace("+00:00", "Z")))
    if scanned_count is not None:
        emit("Scanned %d runs." % scanned_count)
    if truncated:
        emit("Warning: stopped after %d runs; the lookback window was not fully scanned." % (
            scanned_count if scanned_count is not None else row_count))
    emit()


def _print_backend_summary(emit, rows, disruption_data, selectors, limit):
    """Print how often each selected backend was disrupted and how badly."""
    summary = backend_summary(rows, disruption_data, selectors)
    active = [s for s in summary if s["nonzero"]]
    shown = summary if limit is None else active[:limit]
    emit("Selected backends (runs > 0, runs where it was the max, median seconds when > 0):")
    emit()
    emit("| Backend | Runs > 0 | Max in | Median (s) |")
    emit("|---------|----------|--------|------------|")
    for s in shown:
        median = _fmt_secs(s["median"]) if s["median"] is not None else "—"
        emit("| %s | %d | %d | %s |" % (s["name"], s["nonzero"], s["max_in"], median))
    hidden_active = len(active) - len([s for s in shown if s["nonzero"]])
    zero = len(summary) - len(active)
    if limit is not None and (hidden_active or zero):
        emit("(%d more backends with seconds > 0 and %d with 0s in every run are in the full table.)" % (
            hidden_active, zero))
    emit()

    if len(summary) > 1:
        correlated, disrupted = correlated_runs(rows, disruption_data, selectors)
        emit("Selected backends correlated (every selected backend in the run within %d%% of that run's "
             "max) in %d of %d disrupted runs." % (round(CORRELATION_TOLERANCE * 100), correlated, disrupted))
    dominant = dominant_probe_family(summary)
    if dominant:
        emit("Note: %s backends were the max in %d of %d disrupted runs, so that probe family drives this "
             "ranking. Ask the user which backend family they mean before choosing runs." % dominant)
    if len(summary) > 1 or dominant:
        emit()


def _print_job_summary(emit, rows, disruption_data, selectors, limit):
    """Print the disrupted seconds per job."""
    summary = job_summary(rows, disruption_data, selectors)
    if not summary:
        return
    grand_total = sum(j["total"] for j in summary)
    shown = summary if limit is None else summary[:limit]
    emit("Per-job disruption (sorted by total seconds on the selected backends):")
    emit()
    emit("| Job | Runs | Disrupted | Total (s) | Share | Median (s) |")
    emit("|-----|------|-----------|-----------|-------|------------|")
    for j in shown:
        emit("| %s | %d | %d | %s | %d%% | %s |" % (
            j["job"], j["runs"], j["disrupted"], _fmt_secs(j["total"]),
            round(100.0 * j["total"] / grand_total), _fmt_secs(j["median"])))
    if len(shown) < len(summary):
        emit("(%d more jobs are in the full table.)" % (len(summary) - len(shown)))
    emit()


def _visible_rows(row_count, selected_set, top):
    """Row indexes to print: the first top rows plus every selected row."""
    if top is None or row_count <= top:
        return list(range(row_count))
    return sorted(set(range(top)) | {i for i in selected_set if i < row_count})


def print_table(rows, grafana_params, selectors, disruption_data, selected_indices=None,
                scanned_count=None, window_start=None, truncated=False,
                scanned_rows=None, top=None, full_table_path=None, selection=None, out=None):
    """Print the candidate report: header, backend and job summaries, then run rows.

    top limits the run rows to the first top plus recommended rows, and the
    summaries to top lines; None prints everything. scanned_rows (default
    rows) are every run in the series, for run counts in the summaries.
    selection is select_representative_runs' explain dict.
    """
    emit = functools.partial(print, file=out or sys.stdout)
    _print_header(emit, grafana_params, window_start, scanned_count, truncated, len(rows))
    summary_rows = scanned_rows if scanned_rows is not None else rows
    _print_backend_summary(emit, summary_rows, disruption_data, selectors, top)
    _print_job_summary(emit, summary_rows, disruption_data, selectors, top)

    positive = sum(1 for row in rows if (_run_secs(row, disruption_data, selectors)[0] or 0) > 0)
    percentile_label = grafana_params.get("percentile", "") or "the dashboard percentile"
    emit("Showing %d runs with disruption > 0s on %s (per-run seconds, not %s):" % (
        positive, _backend_label(selectors), percentile_label))
    emit()

    selected_set = set(selected_indices) if selected_indices else set()
    has_selection = bool(selected_set)
    if has_selection:
        emit("| # | Rec | Job | Build ID | Result | Disruption (s) | Backend | Disruption Failures | Timestamp |")
        emit("|---|-----|-----|----------|--------|----------------|---------|---------------------|-----------|")
    else:
        emit("| # | Job | Build ID | Result | Disruption (s) | Backend | Disruption Failures | Timestamp |")
        emit("|---|-----|----------|--------|----------------|---------|---------------------|-----------|")

    visible = _visible_rows(len(rows), selected_set, top)
    for i in visible:
        emit(_format_row(i, rows[i], disruption_data, selectors, selected_set if has_selection else None))

    emit()
    if len(visible) < len(rows):
        extra = len(visible) - top
        emit("Showing rows 1-%d%s of %d." % (
            top, " plus %d recommended row(s) below them" % extra if extra else "", len(rows)))
    if full_table_path:
        emit("Full table (%d rows, all backends and jobs): %s" % (len(rows), full_table_path))
    clean_rows = sum(1 for i in selected_set if _run_secs(rows[i], disruption_data, selectors)[0] == 0)
    if clean_rows:
        emit("Total: %d (%d disrupted, %d clean comparison)" % (len(rows), positive, clean_rows))
    else:
        emit("Total: %d" % len(rows))
    if has_selection:
        if clean_rows:
            emit("Auto-selected %d runs (* = disrupted, C = clean comparison from same job)." % len(selected_set))
        else:
            emit("Auto-selected %d runs (marked with *)." % len(selected_set))
        _print_selection(emit, rows, selection)


def _print_selection(emit, rows, selection):
    """Two lines on how the picks were made: the tiers, and runs that share a picked event."""
    if not selection:
        return
    emit("Tiers: P%s of %d runs is %ss, so outliers are > %ss (%d runs) and the tail is the rest (%d runs). "
         "Picks alternate between tiers." % (
             _fmt_secs(selection["percentile"]), selection["runs"], _fmt_secs(selection["cutoff"]),
             _fmt_secs(selection["outlier_above"]), selection["outliers"], selection["tail"]))
    number = {str(row.get("prow_id", "")): i + 1 for i, row in enumerate(rows)}
    notes = []
    for event in selection.get("shared", []):
        others = ["#%d" % number[pid] for pid in event["with"] if pid in number]
        if others and event["prow_id"] in number:
            notes.append("%s with #%d" % (", ".join(others), number[event["prow_id"]]))
    if notes:
        emit("Same event, not picked separately: %s." % "; ".join(notes))


def _format_row(i, row, disruption_data, selectors, selected_set):
    """One markdown run row. selected_set is None when nothing was auto-selected."""
    job = row.get("job", "?")
    if len(job) > 60:
        job = "..." + job[-57:]
    disruption = extract_disruption_failures(row.get("failed_test_names"))
    secs, peak_backend = _run_secs(row, disruption_data, selectors)
    cells = [str(i + 1)]
    if selected_set is not None:
        cells.append(("C" if secs == 0 else "*") if i in selected_set else " ")
    cells += [job, str(row.get("prow_id", "?")), str(row.get("overall_result", "?")),
              str(secs) if secs is not None else "—", peak_backend or "—",
              ", ".join(disruption) if disruption else "—", format_timestamp(row.get("timestamp", ""))]
    return "| %s |" % " | ".join(cells)


def default_full_table_path(now=None):
    """Where the full table goes when --full-table-out is not given."""
    now = now or datetime.now(timezone.utc)
    return os.path.join(".work", "disruption-analysis", now.strftime("%Y-%m-%d"),
                        "find-runs-%s.md" % now.strftime("%H%M%S"))


def write_full_table(path, *args, **kwargs):
    """Write the uncapped report to path. Returns path, or None after warning on failure."""
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            print_table(*args, top=None, out=f, **kwargs)
    except OSError as e:
        print("Warning: could not write the full table to %s: %s" % (path, e), file=sys.stderr)
        return None
    return path


def print_json(rows, selectors, disruption_data, selected_indices=None):
    """Print machine-readable JSON with disruption info added."""
    selected_set = set(selected_indices) if selected_indices else set()
    bases = selector_bases(selectors)
    output = []
    for i, row in enumerate(rows):
        disruption = extract_disruption_failures(row.get("failed_test_names"))
        has_target = any(name in bases for name in disruption)
        pid = str(row.get("prow_id", ""))
        entries = disruption_data.get(pid, [])
        secs, peak_backend = disruption_peak(entries, selectors)
        entry = {
            "build_id": row.get("prow_id"),
            "prow_id": row.get("prow_id"),
            "job": row.get("job"),
            "url": row.get("url"),
            "overall_result": row.get("overall_result"),
            "timestamp": row.get("timestamp"),
            "timestamp_human": format_timestamp(row.get("timestamp", "")),
            "disruption_seconds": secs,
            "disruption_backend": peak_backend,
            "disruption_backends": entries,
            "disruption_failures": disruption,
            "has_target_disruption": has_target,
        }
        if selected_set:
            entry["recommended"] = i in selected_set
            if i in selected_set and secs == 0:
                entry["role"] = "clean-comparison"
        output.append(entry)
    print(json.dumps(output, indent=2))


def main(argv=None):
    """Find disrupted runs for the series, select representative ones, and print them."""
    parser = argparse.ArgumentParser(
        description="Find Prow job runs with disruption from Grafana dashboard parameters")

    parser.add_argument("--grafana-url",
                        help="Full Grafana disruption dashboard URL — all var-* params are extracted automatically")
    parser.add_argument("--alert-text",
                        help="Pasted DisruptionRegression alert. A link: annotation is the dashboard "
                             "URL; other series labels fill vars that link omits. With no link, "
                             "lookback is %s days." % series.ALERT_LOOKBACK_DAYS)
    parser.add_argument("--alert-file",
                        help="File holding the pasted alert text ('-' for stdin); same as --alert-text")

    parser.add_argument("--release", help="OpenShift release (e.g., 5.0)")
    parser.add_argument("--platform", help="Platform (e.g., gcp, aws, azure)")
    parser.add_argument("--backend", help="Disruption backend (e.g., host-to-host-new-connections)")
    parser.add_argument("--upgrade-type", help="Upgrade type (e.g., micro, minor, none)")
    parser.add_argument("--architecture", help="Architecture (e.g., amd64, arm64)")
    parser.add_argument("--topology", help="Topology (e.g., ha, single)")
    parser.add_argument("--network", help="Network (e.g., ovn, sdn)")

    parser.add_argument("--since-hours", type=float, default=None,
                        help="Lookback window in hours. Overrides var-lookback. "
                             "Default when the URL has no lookback: %d (30 days)." % series.DEFAULT_SINCE_HOURS)
    parser.add_argument("--limit", type=int, default=None,
                        help="Max runs to scan (default: the full window, capped at %d)" % MAX_SCANNED_RUNS)
    parser.add_argument("--format", choices=["table", "json"], default="table",
                        help="Output format (default: table)")
    parser.add_argument("--disruption-only", action="store_true",
                        help="Leave out the 0s clean-comparison run that --auto-select adds; "
                             "runs with disruption > 0 are listed either way")
    parser.add_argument("--auto-select", type=int, default=None, metavar="N",
                        help="Auto-select N representative runs, weighted by each job's share of the seconds")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_ROWS, metavar="N",
                        help="Table format: print the top N rows plus recommended rows, and up to N "
                             "backend and job summary lines (default: %d; 0 prints everything)" % DEFAULT_TOP_ROWS)
    parser.add_argument("--full-table-out", metavar="PATH",
                        help="Table format: write the full table here. Default when rows are cut: "
                             ".work/disruption-analysis/<UTC date>/find-runs-<HHMMSS>.md")
    args = parser.parse_args(argv)

    try:
        alert_text = series.read_alert_file(args.alert_file) if args.alert_file else args.alert_text
        resolved = series.resolve_series(
            args.grafana_url, alert_text, release=args.release, backend=args.backend,
            platform=args.platform, upgrade_type=args.upgrade_type, architecture=args.architecture,
            topology=args.topology, network=args.network)
    except series.SeriesError as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)
    grafana_params = resolved["grafana_params"]
    release = resolved["release"]
    selectors = resolved["selectors"]
    variants = resolved["variants"]

    lookback = resolved["lookback_days"] if args.since_hours is None else None
    since = series.resolve_window_start(args.since_hours, lookback)

    max_runs = args.limit if args.limit is not None else MAX_SCANNED_RUNS
    try:
        rows, truncated = sippy.collect_runs(release, variants, since, max_runs=max_runs)
    except sippy.SippyError as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)

    if not rows:
        filters_desc = ", ".join("%s:%s" % (k, v) for k, v in variants.items())
        print("No runs found for release=%s with variants [%s] since %s." % (
            release, filters_desc, sippy.rfc3339(since)), file=sys.stderr)
        print("Try widening --since-hours or relaxing filters.", file=sys.stderr)
        sys.exit(0)

    scanned_count = len(rows)
    prow_ids = [str(r["prow_id"]) for r in rows if r.get("prow_id")]
    lost_ids = []
    raw_disruption = sippy.fetch_disruption_data(prow_ids, failed=lost_ids)
    if lost_ids:
        print("Warning: the Sippy disruption API failed for %d of %d runs (rate limit or error). Their "
              "disruption is unknown, not zero, and they are missing from the table. Rerun later; "
              "Sippy allows about 25 disruption requests per hour across all users."
              % (len(lost_ids), len(prow_ids)), file=sys.stderr)
    for warning in series.backend_name_warnings(selectors, raw_disruption):
        print("Warning: %s" % warning, file=sys.stderr)
    master_wanted = resolved["master_nodes_updated"]
    field_present = series.disruption_api_has_master_field(raw_disruption)
    disruption_data = series.filter_disruption_data(raw_disruption, selectors)
    if master_wanted:
        rows = series.apply_master_nodes_filter(rows, disruption_data, master_wanted, field_present)
        if not rows:
            print("No runs matched master_nodes_updated=%s in %d scanned runs." % (
                master_wanted, scanned_count), file=sys.stderr)
            sys.exit(0)

    if not grafana_params:
        grafana_params = {
            "releases": release,
            "backend": args.backend,
            "_dashboard_name": "(manual query)",
        }
        cli_overrides = {"platform": args.platform, "upgrade_type": args.upgrade_type,
                         "architecture": args.architecture, "topology": args.topology,
                         "network": args.network}
        for key, val in cli_overrides.items():
            if val:
                grafana_params[series.OVERRIDE_TO_GRAFANA[key]] = val
    else:
        grafana_params["backend"] = ",".join(selectors)

    selected_ids = set()
    selection = {}
    if args.auto_select is not None:
        selected_indices_full = select_representative_runs(
            rows, disruption_data, selectors, n=args.auto_select,
            upgrade_series=is_upgrade_series(variants),
            percentile=grafana_params.get("percentile"), explain=selection)
        selected_ids = {str(rows[i].get("prow_id", "")) for i in selected_indices_full}

    include_clean = bool(selected_ids) and not args.disruption_only
    display = []
    for row in rows:
        pid = str(row.get("prow_id", ""))
        secs, _peak = disruption_peak(disruption_data.get(pid), selectors)
        if secs is not None and secs > 0:
            display.append(row)
        elif include_clean and secs == 0 and pid in selected_ids:
            display.append(row)
    display.sort(key=lambda row: (
        disruption_peak(disruption_data.get(str(row.get("prow_id", ""))), selectors)[0] or 0,
        sippy.parse_timestamp(row.get("timestamp", "")),
    ), reverse=True)

    if args.disruption_only and not display:
        print("No runs with disruption > 0 for %s in %d runs since %s." % (
            _backend_label(selectors), scanned_count, sippy.rfc3339(since)), file=sys.stderr)
        sys.exit(0)

    selected_indices = None
    if selected_ids:
        selected_indices = [i for i, row in enumerate(display) if str(row.get("prow_id", "")) in selected_ids]

    if args.format == "json":
        print("Scanned %d runs since %s." % (scanned_count, sippy.rfc3339(since)), file=sys.stderr)
        if truncated:
            print("Warning: stopped after %d runs; the lookback window was not fully scanned." % scanned_count,
                  file=sys.stderr)
        print_json(display, selectors, disruption_data, selected_indices)
    else:
        table_args = (display, grafana_params, selectors, disruption_data, selected_indices)
        table_kwargs = {"scanned_count": scanned_count, "window_start": since,
                        "truncated": truncated, "scanned_rows": rows, "selection": selection}
        top = args.top if args.top and args.top > 0 else None
        full_path = None
        if args.full_table_out or (top is not None and len(display) > top):
            full_path = write_full_table(args.full_table_out or default_full_table_path(),
                                         *table_args, **table_kwargs)
        print_table(*table_args, top=top, full_table_path=full_path, **table_kwargs)


if __name__ == "__main__":
    main()
