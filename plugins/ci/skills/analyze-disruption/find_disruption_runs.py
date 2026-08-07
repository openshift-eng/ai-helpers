"""Find Prow job runs with disruption from Grafana dashboard parameters.

Takes Grafana disruption dashboard URL parameters (platform, backend,
upgrade type, etc.), queries Sippy for matching runs, enriches them with
actual disruption seconds from BigQuery, and outputs a candidate table.

Usage:
    python3 find_disruption_runs.py --grafana-url <url>
    python3 find_disruption_runs.py --release 5.0 --platform gcp --backend host-to-host-new-connections --upgrade-type micro --architecture amd64 --topology ha --network ovn

Output formats:
    --format table   (default) Human-readable table with disruption status
    --format json    Machine-readable JSON array
"""
import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SIPPY_BASE = "https://sippy.dptools.openshift.org/api/jobs/runs"
SIPPY_DISRUPTION_URL = "https://sippy.dptools.openshift.org/api/jobs/runs/disruption"

GRAFANA_TO_VARIANT = {
    "platform": "Platform",
    "architectures": "Architecture",
    "topologies": "Topology",
    "networks": "Network",
    "upgrade_type": "Upgrade",
}


def parse_grafana_url(url):
    """Extract var-* parameters from a Grafana dashboard URL.

    Multi-value params (e.g. var-platform=azure&var-platform=gcp) are stored
    as comma-joined strings so downstream code stays simple.
    """
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    result = {}
    for key, values in params.items():
        if key.startswith("var-"):
            name = key[4:]
            result[name] = ",".join(values) if len(values) > 1 else values[0]

    dashboard_name = ""
    path_parts = parsed.path.rstrip("/").split("/")
    if len(path_parts) >= 2:
        dashboard_name = path_parts[-1]

    result["_dashboard_name"] = dashboard_name
    return result


def parse_backend(backend_value):
    """Parse backend name into base name and connection type.

    Examples:
        host-to-host-new-connections -> (host-to-host, new)
        cache-kube-api-reused-connections -> (cache-kube-api, reused)
        oauth-api -> (oauth-api, None)
    """
    if backend_value.endswith("-new-connections"):
        base = backend_value[: -len("-new-connections")]
        return base, "new"
    if backend_value.endswith("-reused-connections"):
        base = backend_value[: -len("-reused-connections")]
        return base, "reused"
    return backend_value, None


def build_sippy_filter(variants, since_ms):
    """Build Sippy filter dict from variant key-value pairs."""
    items = []
    for key, value in variants.items():
        items.append(
            {"columnField": "variants", "operatorValue": "has entry", "value": "%s:%s" % (key, value)}
        )
    if since_ms is not None:
        items.append(
            {"columnField": "timestamp", "operatorValue": ">", "value": str(since_ms)}
        )
    return {"items": items, "linkOperator": "and"}


def fetch_runs(release, filter_dict, limit):
    """Query Sippy /api/jobs/runs and return rows."""
    params = {
        "release": release,
        "filter": json.dumps(filter_dict),
        "limit": str(limit),
        "sortField": "timestamp",
        "sort": "desc",
    }
    url = "%s?%s" % (SIPPY_BASE, urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            detail = "<unable to read response body>"
        print("Error: HTTP %d from Sippy API: %s" % (e.code, detail.strip()), file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print("Error: failed to connect to Sippy API: %s" % e.reason, file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(body)
    except (ValueError, json.JSONDecodeError):
        print("Error: invalid JSON from Sippy API", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, dict):
        print("Error: unexpected response type from Sippy API", file=sys.stderr)
        sys.exit(1)
    return data.get("rows") or []


def fetch_disruption_data(prow_ids, backend_name=None):
    """Query Sippy disruption endpoint for per-run disruption seconds.

    Returns dict keyed by prow_id -> list of {backend_name, disruption_seconds}.
    """
    if not prow_ids:
        return {}
    params = {"job_run_names": ",".join(str(p) for p in prow_ids)}
    if backend_name:
        params["backend_name"] = backend_name
    url = "%s?%s" % (SIPPY_DISRUPTION_URL, urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print("Warning: could not fetch disruption data: %s" % e, file=sys.stderr)
        return {}
    try:
        data = json.loads(body)
    except (ValueError, json.JSONDecodeError):
        print("Warning: invalid JSON from disruption API", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print("Warning: unexpected response type from disruption API", file=sys.stderr)
        return {}
    lookup = {}
    for row in data.get("rows") or []:
        pid = str(row.get("job_run_name", ""))
        if pid not in lookup:
            lookup[pid] = []
        lookup[pid].append({
            "backend_name": row.get("backend_name", ""),
            "disruption_seconds": row.get("disruption_seconds", 0),
        })
    return lookup


def _backend_matches(backend_name, base_backend):
    """Check if a backend name matches the base backend, respecting cache-ness.

    Matches 'kube-api-new-connections' for base 'kube-api', but excludes
    'cache-kube-api-new-connections'. When the base itself is a cache backend
    (e.g. 'cache-kube-api'), only cache variants match.
    """
    if backend_name.startswith("cache-") != base_backend.startswith("cache-"):
        return False
    return backend_name == base_backend or backend_name.startswith(base_backend + "-")


def max_disruption_for_backend(disruption_entries, base_backend):
    """Find the max disruption seconds matching the base backend name."""
    if not disruption_entries:
        return None
    matching = [e["disruption_seconds"] for e in disruption_entries if _backend_matches(e["backend_name"], base_backend)]
    if not matching:
        return 0
    return max(matching)


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
            "timestamp": row.get("timestamp", 0),
            "disruption_seconds": get_disruption(row),
        })

    def dedup_key(e):
        return (e["disruption_seconds"] if e["disruption_seconds"] is not None else -1, -e["index"])

    # Phase 2: Deduplicate same-job runs within 60s (chaining)
    by_job_ts = sorted(enriched, key=lambda e: (e["job"], e["timestamp"]))
    groups = [[by_job_ts[0]]]
    for entry in by_job_ts[1:]:
        prev = groups[-1][-1]
        if entry["job"] == prev["job"] and abs(entry["timestamp"] - prev["timestamp"]) <= 60000:
            groups[-1].append(entry)
        else:
            groups.append([entry])
    deduped = [max(g, key=dedup_key) for g in groups]

    # Phase 3: Deduplicate cross-job runs within 5s (anchor-based)
    by_ts = sorted(deduped, key=lambda e: e["timestamp"])
    clusters = [[by_ts[0]]]
    for entry in by_ts[1:]:
        anchor = clusters[-1][0]
        if abs(entry["timestamp"] - anchor["timestamp"]) <= 5000:
            clusters[-1].append(entry)
        else:
            clusters.append([entry])
    candidates = [max(c, key=dedup_key) for c in clusters]

    # Exclude runs with no disruption data (None = BQ data unavailable)
    candidates = [c for c in candidates if c["disruption_seconds"] is not None]

    # Separate 0s runs — they're only useful as a dedicated clean comparison, not
    # for diversity selection. They'll be considered in Phase 5.5 if they share a
    # job with a disrupted run.
    zero_runs = [c for c in candidates if c["disruption_seconds"] == 0]
    candidates = [c for c in candidates if c["disruption_seconds"] > 0]

    if not candidates:
        return []

    if len(candidates) <= n:
        return sorted([c["index"] for c in candidates])

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
    # from a job that has disrupted runs in the pool but wasn't selected is not useful.
    idx_to_job = {c["index"]: c["job"] for c in candidates}
    selected_jobs = set(idx_to_job[idx] for idx in selected if idx in idx_to_job)
    clean = [c for c in zero_runs if c["job"] in selected_jobs]
    if clean and n >= 3 and len(selected) >= n:
        clean_pick = min(clean, key=lambda c: c["index"])
        selected[-1] = clean_pick["index"]

    return sorted(selected)


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


def format_timestamp(ts_millis):
    """Convert epoch milliseconds to human-readable date string."""
    ts_sec = ts_millis / 1000.0
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts_sec))


def print_table(rows, grafana_params, base_backend, disruption_data, selected_indices=None):
    """Print human-readable candidate table."""
    dashboard_name = grafana_params.get("_dashboard_name", "")
    filters = []
    for gkey, variant_key in GRAFANA_TO_VARIANT.items():
        val = grafana_params.get(gkey)
        if val:
            filters.append("%s=%s" % (variant_key, val))
    backend = grafana_params.get("backend", "")
    release = grafana_params.get("releases", "")
    percentile = grafana_params.get("percentile", "")

    print("Dashboard: %s" % dashboard_name)
    print("Filters: %s" % " | ".join(filters))
    print("Release: %s | Percentile: %s | Backend: %s" % (release, percentile, backend))
    print()

    runs_with_disruption = 0
    for row in rows:
        pid = str(row.get("prow_id", ""))
        secs = max_disruption_for_backend(disruption_data.get(pid), base_backend)
        if secs is not None and secs > 0:
            runs_with_disruption += 1

    print("Found %d runs, %d with disruption > 0s for %s:" % (
        len(rows), runs_with_disruption, base_backend))
    print()

    selected_set = set(selected_indices) if selected_indices else set()
    has_selection = bool(selected_set)

    if has_selection:
        header = "| # | Rec | Job | Build ID | Result | Disruption (s) | Disruption Failures | Timestamp |"
        sep = "|---|-----|-----|----------|--------|----------------|---------------------|-----------|"
    else:
        header = "| # | Job | Build ID | Result | Disruption (s) | Disruption Failures | Timestamp |"
        sep = "|---|-----|----------|--------|----------------|---------------------|-----------|"
    print(header)
    print(sep)

    for i, row in enumerate(rows):
        job = row.get("job", "?")
        prow_id = row.get("prow_id", "?")
        result = row.get("overall_result", "?")
        ts = format_timestamp(row.get("timestamp", 0))
        disruption = extract_disruption_failures(row.get("failed_test_names"))
        disruption_str = ", ".join(disruption) if disruption else "—"

        pid = str(prow_id)
        secs = max_disruption_for_backend(disruption_data.get(pid), base_backend)
        secs_str = str(secs) if secs is not None else "—"

        if len(job) > 60:
            job = "..." + job[-57:]

        if has_selection:
            if i in selected_set and secs == 0:
                rec = "C"
            elif i in selected_set:
                rec = "*"
            else:
                rec = " "
            print("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
                i + 1, rec, job, prow_id, result, secs_str, disruption_str, ts))
        else:
            print("| %d | %s | %s | %s | %s | %s | %s |" % (
                i + 1, job, prow_id, result, secs_str, disruption_str, ts))

    print()
    print("Total: %d" % len(rows))
    if has_selection:
        has_clean = any(
            max_disruption_for_backend(disruption_data.get(str(rows[i].get("prow_id", "")), []), base_backend) == 0
            for i in selected_set
        )
        if has_clean:
            print("Auto-selected %d runs (* = disrupted, C = clean comparison from same job) for diverse coverage." % len(selected_set))
        else:
            print("Auto-selected %d runs (marked with *) for diverse coverage." % len(selected_set))


def print_json(rows, base_backend, disruption_data, selected_indices=None):
    """Print machine-readable JSON with disruption info added."""
    selected_set = set(selected_indices) if selected_indices else set()
    output = []
    for i, row in enumerate(rows):
        disruption = extract_disruption_failures(row.get("failed_test_names"))
        has_target = any(base_backend in b for b in disruption)
        pid = str(row.get("prow_id", ""))
        entries = disruption_data.get(pid, [])
        secs = max_disruption_for_backend(entries, base_backend)
        entry = {
            "build_id": row.get("prow_id"),
            "prow_id": row.get("prow_id"),
            "job": row.get("job"),
            "url": row.get("url"),
            "overall_result": row.get("overall_result"),
            "timestamp": row.get("timestamp"),
            "timestamp_human": format_timestamp(row.get("timestamp", 0)),
            "disruption_seconds": secs,
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

    parser.add_argument("--release", help="OpenShift release (e.g., 5.0)")
    parser.add_argument("--platform", help="Platform (e.g., gcp, aws, azure)")
    parser.add_argument("--backend", help="Disruption backend (e.g., host-to-host-new-connections)")
    parser.add_argument("--upgrade-type", help="Upgrade type (e.g., micro, minor, none)")
    parser.add_argument("--architecture", help="Architecture (e.g., amd64, arm64)")
    parser.add_argument("--topology", help="Topology (e.g., ha, single)")
    parser.add_argument("--network", help="Network (e.g., ovn, sdn)")

    parser.add_argument("--since-hours", type=float, default=720,
                        help="Lookback window in hours (default: 720 = 30 days)")
    parser.add_argument("--limit", type=int, default=50,
                        help="Max runs to fetch (default: 50)")
    parser.add_argument("--format", choices=["table", "json"], default="table",
                        help="Output format (default: table)")
    parser.add_argument("--disruption-only", action="store_true",
                        help="Only show runs with disruption > 0 for the target backend")
    parser.add_argument("--auto-select", type=int, default=None, metavar="N",
                        help="Auto-select N representative runs for diverse coverage")
    args = parser.parse_args(argv)

    grafana_params = {}
    if args.grafana_url:
        grafana_params = parse_grafana_url(args.grafana_url)

    release = args.release or grafana_params.get("releases")
    backend = args.backend or grafana_params.get("backend")

    if not release:
        print("Error: --release is required (or provide --grafana-url with var-releases)", file=sys.stderr)
        sys.exit(1)
    if not backend:
        print("Error: --backend is required (or provide --grafana-url with var-backend)", file=sys.stderr)
        sys.exit(1)

    base_backend, _conn_type = parse_backend(backend)

    cli_overrides = {
        "platform": args.platform,
        "upgrade_type": args.upgrade_type,
        "architectures": args.architecture,
        "topologies": args.topology,
        "networks": args.network,
    }

    variants = {}
    for gkey, variant_key in GRAFANA_TO_VARIANT.items():
        val = cli_overrides.get(gkey) or grafana_params.get(gkey)
        if val:
            variants[variant_key] = val

    since_ms = int((time.time() - args.since_hours * 3600) * 1000)

    multi_keys = [(k, v.split(",")) for k, v in variants.items() if "," in v]
    if multi_keys:
        seen_prow_ids = set()
        rows = []
        variant_combos = [{}]
        for mk, mv in multi_keys:
            variant_combos = [
                dict(combo, **{mk: val}) for combo in variant_combos for val in mv
            ]
        max_combos = 20
        if len(variant_combos) > max_combos:
            print("Error: %d variant combinations exceeds limit of %d" % (
                len(variant_combos), max_combos), file=sys.stderr)
            sys.exit(1)
        for combo in variant_combos:
            query_variants = dict(variants, **combo)
            filter_dict = build_sippy_filter(query_variants, since_ms)
            batch = fetch_runs(release, filter_dict, args.limit)
            for r in batch:
                pid = str(r.get("prow_id", ""))
                if pid not in seen_prow_ids:
                    seen_prow_ids.add(pid)
                    rows.append(r)
        rows.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        rows = rows[:args.limit]
    else:
        filter_dict = build_sippy_filter(variants, since_ms)
        rows = fetch_runs(release, filter_dict, args.limit)

    if not rows:
        filters_desc = ", ".join("%s:%s" % (k, v) for k, v in variants.items())
        print("No runs found for release=%s with variants [%s] in the last %d hours." % (
            release, filters_desc, int(args.since_hours)), file=sys.stderr)
        print("Try widening --since-hours or relaxing filters.", file=sys.stderr)
        sys.exit(0)

    prow_ids = [str(r["prow_id"]) for r in rows if r.get("prow_id")]
    disruption_data = fetch_disruption_data(prow_ids, base_backend)

    total_before_filter = len(rows)
    if args.disruption_only:
        rows = [r for r in rows if (
            max_disruption_for_backend(
                disruption_data.get(str(r.get("prow_id", "")), []),
                base_backend,
            ) or 0) > 0]
        if not rows:
            print("No runs with disruption > 0 for %s in %d runs (last %d hours)." % (
                base_backend, total_before_filter, int(args.since_hours)), file=sys.stderr)
            print("Re-run without --disruption-only to see all runs.", file=sys.stderr)
            sys.exit(0)

    if not grafana_params:
        grafana_params = {
            "releases": release,
            "backend": backend,
            "_dashboard_name": "(manual query)",
        }
        for gkey in GRAFANA_TO_VARIANT:
            val = cli_overrides.get(gkey)
            if val:
                grafana_params[gkey] = val

    selected_indices = None
    if args.auto_select is not None:
        selected_indices = select_representative_runs(
            rows, disruption_data, base_backend, n=args.auto_select)

    if args.format == "json":
        print_json(rows, base_backend, disruption_data, selected_indices)
    else:
        print_table(rows, grafana_params, base_backend, disruption_data, selected_indices)


if __name__ == "__main__":
    main()
