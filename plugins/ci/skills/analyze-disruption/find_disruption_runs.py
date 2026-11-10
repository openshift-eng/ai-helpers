"""Find Prow job runs with disruption from Grafana dashboard parameters.

Takes Grafana disruption dashboard URL parameters (platform, backend,
upgrade type, etc.), queries Sippy for matching runs, enriches them with
actual disruption seconds from BigQuery, and outputs a candidate table.

Series resolution and Sippy access live in the shared disruption_common
library (plugins/ci/lib/disruption_common).

Usage:
    python3 find_disruption_runs.py --grafana-url <url>
    python3 find_disruption_runs.py --alert-text <pasted alert>
    python3 find_disruption_runs.py --release 5.0 --platform gcp --backend host-to-host-new-connections --upgrade-type micro --architecture amd64 --topology ha --network ovn

Output formats:
    --format table   (default) Human-readable table with disruption status
    --format json    Machine-readable JSON array
"""
import argparse
import json
import math
import os
import re
import sys

# disruption_common is in plugins/ci/lib when the whole plugin is installed, or
# beside the skill directories when a Chai persona lists it in supporting_dirs.
_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB_PARENTS = (os.path.join(_HERE, "..", "..", "lib"), os.path.join(_HERE, ".."))
for _parent in _LIB_PARENTS:
    if os.path.isfile(os.path.join(_parent, "disruption_common", "__init__.py")):
        sys.path.insert(0, os.path.abspath(_parent))
        break
else:
    sys.exit("Error: disruption_common library not found. Install the whole ci plugin, or add "
             "`supporting_dirs: [lib/disruption_common]` to the persona's ci plugin entry. Looked in: %s"
             % ", ".join(os.path.abspath(p) for p in _LIB_PARENTS))

from disruption_common import series, sippy  # noqa: E402
from disruption_common.series import (  # noqa: E402
    GRAFANA_TO_VARIANT,
    disruption_peak,
    is_all_sentinel,
    selector_bases,
)

# A single page is not the candidate set — scoring happens after the scan.
MAX_SCANNED_RUNS = 5000


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


def select_representative_runs(rows, disruption_data, base_backend, n=5):
    """Select a diverse, representative sample of job runs for analysis.

    Algorithm:
    1. Deduplicate same-job runs within 60s (keep highest disruption)
    2. Deduplicate cross-job runs within 5s (keep highest disruption)
    3. Categorize into high/moderate/low disruption tiers
    4. Round-robin across jobs within each tier for diversity
    """
    if not rows or n <= 0:
        return []

    def get_disruption(row):
        pid = str(row.get("prow_id", ""))
        return max_disruption_for_backend(disruption_data.get(pid), base_backend)

    enriched = []
    for i, row in enumerate(rows):
        enriched.append({
            "index": i,
            "job": row.get("job", ""),
            "timestamp": sippy.parse_timestamp(row.get("timestamp", "")),
            "disruption_seconds": get_disruption(row),
        })

    def dedup_key(e):
        return (e["disruption_seconds"] if e["disruption_seconds"] is not None else -1, -e["index"])

    # Phase 2: Deduplicate same-job runs within 60s (chaining)
    by_job_ts = sorted(enriched, key=lambda e: (e["job"], e["timestamp"]))
    groups = [[by_job_ts[0]]]
    for entry in by_job_ts[1:]:
        prev = groups[-1][-1]
        if entry["job"] == prev["job"] and abs((entry["timestamp"] - prev["timestamp"]).total_seconds()) <= 60:
            groups[-1].append(entry)
        else:
            groups.append([entry])
    deduped = [max(g, key=dedup_key) for g in groups]

    # Phase 3: Deduplicate cross-job runs within 5s (anchor-based)
    by_ts = sorted(deduped, key=lambda e: e["timestamp"])
    clusters = [[by_ts[0]]]
    for entry in by_ts[1:]:
        anchor = clusters[-1][0]
        if abs((entry["timestamp"] - anchor["timestamp"]).total_seconds()) <= 5:
            clusters[-1].append(entry)
        else:
            clusters.append([entry])
    candidates = [max(c, key=dedup_key) for c in clusters]

    # Exclude runs with no disruption data (None = BQ data unavailable)
    candidates = [c for c in candidates if c["disruption_seconds"] is not None]

    # Separate 0s runs — they're only useful as a dedicated clean comparison, not
    # for diversity selection. A same-job 0s run is added when n is at least 3.
    zero_runs = [c for c in candidates if c["disruption_seconds"] == 0]
    candidates = [c for c in candidates if c["disruption_seconds"] > 0]

    if not candidates:
        return []

    if len(candidates) <= n:
        selected = [c["index"] for c in candidates]
        if n >= 3:
            selected_jobs = {c["job"] for c in candidates}
            clean = [c for c in zero_runs if c["job"] in selected_jobs]
            if clean:
                clean_pick = min(clean, key=lambda c: c["index"])
                if len(selected) < n:
                    selected.append(clean_pick["index"])
                else:
                    selected = _replace_disrupted_with_clean(selected, candidates, clean_pick)
        return sorted(selected)

    # Phase 4: Categorize by disruption level
    non_zero = sorted([c["disruption_seconds"] for c in candidates])

    if len(non_zero) < 3:
        p50 = non_zero[len(non_zero) // 2]
        high = [c for c in candidates if c["disruption_seconds"] >= p50]
        low = [c for c in candidates if c not in high]
        tiers = [high, low]
        high_slots = min(len(high), max(1, n // 2))
        low_slots = n - high_slots
        slot_counts = [high_slots, low_slots]
    else:
        p33_idx = len(non_zero) // 3
        p66_idx = 2 * len(non_zero) // 3
        low_thresh = non_zero[p33_idx]
        high_thresh = non_zero[p66_idx]

        high = [c for c in candidates if c["disruption_seconds"] >= high_thresh]
        moderate = [c for c in candidates if low_thresh <= c["disruption_seconds"] < high_thresh]
        low = [c for c in candidates if c not in high and c not in moderate]
        tiers = [high, moderate, low]
        high_slots = math.ceil(n * 0.4)
        mod_slots = math.floor(n * 0.4)
        low_slots = n - high_slots - mod_slots
        slot_counts = [high_slots, mod_slots, low_slots]

    # Redistribute slots from empty/small tiers
    for _ in range(len(tiers)):
        overflow = 0
        for i, (tier, slots) in enumerate(zip(tiers, slot_counts)):
            if len(tier) < slots:
                overflow += slots - len(tier)
                slot_counts[i] = len(tier)
        if overflow == 0:
            break
        for i in range(len(tiers)):
            available = len(tiers[i]) - slot_counts[i]
            give = min(overflow, available)
            slot_counts[i] += give
            overflow -= give
            if overflow == 0:
                break

    # Phase 6: Round-robin within tiers for job diversity
    selected = []
    for tier, slots in zip(tiers, slot_counts):
        selected.extend(_select_by_job_diversity(tier, slots))

    # Phase 6.5: Reserve one slot for a clean comparison (0s disruption) when available.
    # Only pick a clean run from a job that is actually in the selected set — a clean run
    # from a job that has disrupted runs in the pool but is not in that set is not useful.
    idx_to_job = {c["index"]: c["job"] for c in candidates}
    selected_jobs = set(idx_to_job[idx] for idx in selected if idx in idx_to_job)
    clean = [c for c in zero_runs if c["job"] in selected_jobs]
    if clean and n >= 3 and len(selected) >= n:
        clean_pick = min(clean, key=lambda c: c["index"])
        selected = _replace_disrupted_with_clean(selected, candidates, clean_pick)

    return sorted(selected)


def _replace_disrupted_with_clean(selected, candidates, clean_pick):
    """Swap one selected disrupted run for clean_pick without breaking its pair.

    The only selected disrupted run from clean_pick's job stays. When a
    disrupted run from another job is selected, that run is the one replaced.
    """
    job_of = {c["index"]: c["job"] for c in candidates}
    clean_job = clean_pick["job"]
    same_job = [idx for idx in selected if job_of.get(idx) == clean_job]
    others = [idx for idx in selected if job_of.get(idx) != clean_job]
    if len(same_job) <= 1:
        if not others:
            return list(selected)
        drop = others[-1]
    else:
        drop = selected[-1]
    return [clean_pick["index"] if idx == drop else idx for idx in selected]


def _select_by_job_diversity(candidates, n):
    """Select n candidates with maximum job diversity via round-robin."""
    if not candidates or n <= 0:
        return []
    if len(candidates) <= n:
        return [c["index"] for c in candidates]

    by_job = {}
    for c in candidates:
        by_job.setdefault(c["job"], []).append(c)
    for job in by_job:
        by_job[job].sort(key=lambda c: (-(c["disruption_seconds"] or 0), c["index"]))

    job_order = sorted(by_job.keys(), key=lambda j: (len(by_job[j]), j))

    selected = []
    pointers = {j: 0 for j in job_order}
    while len(selected) < n:
        picked_this_round = False
        for job in job_order:
            if len(selected) >= n:
                break
            if pointers[job] < len(by_job[job]):
                selected.append(by_job[job][pointers[job]]["index"])
                pointers[job] += 1
                picked_this_round = True
        if not picked_this_round:
            break

    return selected


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
    if isinstance(selectors, str):
        return selectors
    return ", ".join(selectors)


def print_table(rows, grafana_params, selectors, disruption_data, selected_indices=None,
                scanned_count=None, window_start=None, truncated=False):
    """Print human-readable candidate table."""
    dashboard_name = grafana_params.get("_dashboard_name", "")
    filters = []
    for gkey, variant_key in GRAFANA_TO_VARIANT.items():
        val = grafana_params.get(gkey)
        if val and not is_all_sentinel(val):
            filters.append("%s=%s" % (variant_key, val))
    masters = grafana_params.get("master_nodes_updated")
    if masters and not is_all_sentinel(masters):
        filters.append("MasterNodesUpdated=%s" % masters)
    backend = grafana_params.get("backend", "")
    release = grafana_params.get("releases", "")
    percentile = grafana_params.get("percentile", "")
    summary_extra = []
    lookback = grafana_params.get("lookback")
    if lookback:
        summary_extra.append("Lookback=%sd" % lookback)
    compare_release = grafana_params.get("compare_release")
    if compare_release:
        summary_extra.append("CompareRelease=%s" % compare_release)

    print("Dashboard: %s" % dashboard_name)
    print("Filters: %s" % " | ".join(filters))
    release_line = "Release: %s | Percentile: %s | Backend: %s" % (release, percentile, backend)
    if summary_extra:
        release_line += " | " + " | ".join(summary_extra)
    print(release_line)
    if window_start is not None:
        print("Window start: %s" % format_timestamp(window_start.isoformat().replace("+00:00", "Z")))
    if scanned_count is not None:
        print("Scanned %d runs." % scanned_count)
    if truncated:
        print("Warning: stopped after %d runs; the lookback window was not fully scanned." % (
            scanned_count if scanned_count is not None else len(rows)))
    print()

    positive = sum(1 for row in rows if (disruption_peak(
        disruption_data.get(str(row.get("prow_id", ""))), selectors)[0] or 0) > 0)
    percentile_label = percentile or "the dashboard percentile"
    print("Showing %d runs with disruption > 0s on %s (per-run seconds, not %s):" % (
        positive, _backend_label(selectors), percentile_label))
    print()

    selected_set = set(selected_indices) if selected_indices else set()
    has_selection = bool(selected_set)

    if has_selection:
        header = "| # | Rec | Job | Build ID | Result | Disruption (s) | Backend | Disruption Failures | Timestamp |"
        sep = "|---|-----|-----|----------|--------|----------------|---------|---------------------|-----------|"
    else:
        header = "| # | Job | Build ID | Result | Disruption (s) | Backend | Disruption Failures | Timestamp |"
        sep = "|---|-----|----------|--------|----------------|---------|---------------------|-----------|"
    print(header)
    print(sep)

    for i, row in enumerate(rows):
        job = row.get("job", "?")
        prow_id = row.get("prow_id", "?")
        result = row.get("overall_result", "?")
        ts = format_timestamp(row.get("timestamp", ""))
        disruption = extract_disruption_failures(row.get("failed_test_names"))
        disruption_str = ", ".join(disruption) if disruption else "—"

        pid = str(prow_id)
        secs, peak_backend = disruption_peak(disruption_data.get(pid), selectors)
        secs_str = str(secs) if secs is not None else "—"
        peak_str = peak_backend or "—"

        if len(job) > 60:
            job = "..." + job[-57:]

        if has_selection:
            if i in selected_set and secs == 0:
                rec = "C"
            elif i in selected_set:
                rec = "*"
            else:
                rec = " "
            print("| %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                i + 1, rec, job, prow_id, result, secs_str, peak_str, disruption_str, ts))
        else:
            print("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
                i + 1, job, prow_id, result, secs_str, peak_str, disruption_str, ts))

    print()
    clean_rows = sum(1 for i in selected_set if disruption_peak(
        disruption_data.get(str(rows[i].get("prow_id", "")), []), selectors)[0] == 0)
    if clean_rows:
        print("Total: %d (%d disrupted, %d clean comparison)" % (len(rows), positive, clean_rows))
    else:
        print("Total: %d" % len(rows))
    if has_selection:
        if clean_rows:
            print("Auto-selected %d runs (* = disrupted, C = clean comparison from same job) for diverse coverage." % len(selected_set))
        else:
            print("Auto-selected %d runs (marked with *) for diverse coverage." % len(selected_set))


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
    parser = argparse.ArgumentParser(
        description="Find Prow job runs with disruption from Grafana dashboard parameters")

    parser.add_argument("--grafana-url",
                        help="Full Grafana disruption dashboard URL — all var-* params are extracted automatically")
    parser.add_argument("--alert-text",
                        help="Pasted DisruptionRegression alert. A link: annotation is the dashboard "
                             "URL; other series labels fill vars that link omits. With no link, "
                             "lookback is %s days." % series.ALERT_LOOKBACK_DAYS)

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
                        help="Only show runs with disruption > 0 for the selected backends")
    parser.add_argument("--auto-select", type=int, default=None, metavar="N",
                        help="Auto-select N representative runs for diverse coverage")
    args = parser.parse_args(argv)

    try:
        resolved = series.resolve_series(
            args.grafana_url, args.alert_text, release=args.release, backend=args.backend,
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
    raw_disruption = sippy.fetch_disruption_data(prow_ids)
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
    if args.auto_select is not None:
        selected_indices_full = select_representative_runs(
            rows, disruption_data, selectors, n=args.auto_select)
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
        print("Re-run without --disruption-only to see all runs.", file=sys.stderr)
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
        print_table(display, grafana_params, selectors, disruption_data, selected_indices,
                    scanned_count=scanned_count, window_start=since, truncated=truncated)


if __name__ == "__main__":
    main()
