"""Build a disruption time series for one series and locate transitions and onset.

Fetches every run in the window for the series (release, exact backends,
Sippy variants, master_nodes_updated), takes each run's peak disruption
seconds among the exact selected backends, buckets the runs over time, and
runs binary segmentation with a Mann-Whitney statistic on the per-run values
to find step changes. It reports facts and caveats. Interpreting them is the
skill's job.

Usage:
    python3 disruption_series.py --alert-text "<alert>" [--days 30]
    python3 disruption_series.py --grafana-url "<url>"
    python3 disruption_series.py --release 5.0 --backend kube-api-new-connections --platform gcp --upgrade-type micro
    python3 disruption_series.py ... --format json --state-file .work/disruption-analysis/<id>/investigation.json
"""
import argparse
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
# disruption_common is at plugins/ci/lib/ when the whole plugin is installed,
# and beside the skills when a Chai persona installs it with supporting_dirs.
_LIB_PARENTS = (
    os.path.join(_HERE, "..", "..", "lib"),
    os.path.join(_HERE, ".."),
)
for _parent in _LIB_PARENTS:
    if os.path.isfile(os.path.join(_parent, "disruption_common", "__init__.py")):
        sys.path.insert(0, os.path.abspath(_parent))
        break
else:
    sys.exit("Error: disruption_common library not found. Install the whole ci plugin, or add "
             "`supporting_dirs: [lib/disruption_common]` to the persona's ci plugin entry. "
             "Looked in: %s" % ", ".join(os.path.abspath(p) for p in _LIB_PARENTS))

from disruption_common import series as series_mod  # noqa: E402
from disruption_common import sippy  # noqa: E402

DEFAULT_DAYS = 30
STATE_SCHEMA_VERSION = 1
LIVENESS_BACKENDS = {
    "ci-cluster-network-liveness-new-connections",
    "ci-cluster-network-liveness-reused-connections",
}
# Under a no-change null, the max |z| over all split points of a few hundred
# to a few thousand zero-heavy runs stays below ~4 (simulated). Recursion adds
# more tests, so the bar is set above that.
Z_STRONG = 5.0
Z_MODERATE = 4.0
MAX_TRANSITIONS = 4
MIN_BUCKET_RUNS = 5
BIGQUERY_LAG = timedelta(hours=4)
# The public Sippy runs API returns roughly this many days, for any release, so windows are capped here.
SIPPY_RETENTION_DAYS = 90
MAX_DAYS = SIPPY_RETENTION_DAYS
ONSET_BASELINE_RATE = 0.1


def percentile(values, q):
    """Linear-interpolated percentile (q in 0..100) of a non-empty list."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def summarize(values):
    """Count, nonzero rate, P50/P75/P95, mean, and max of per-run seconds."""
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "nonzero_rate": round(sum(1 for v in values if v > 0) / len(values), 3),
        "p50": round(percentile(values, 50), 1),
        "p75": round(percentile(values, 75), 1),
        "p95": round(percentile(values, 95), 1),
        "mean": round(sum(values) / len(values), 2),
        "max": max(values),
    }


def _ranks(values):
    """Average ranks (1-based) and the tie term sum(t^3 - t)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    ties = 0
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        t = j - i + 1
        ties += t ** 3 - t
        i = j + 1
    return ranks, ties


def best_split(values, min_seg):
    """Split index k (values[:k] | values[k:]) with the largest Mann-Whitney |z|.

    Returns (k, z) where z > 0 means the later segment is higher, or
    (None, 0.0) when no split leaves min_seg runs on both sides or every
    value is tied.
    """
    n = len(values)
    if n < 2 * min_seg:
        return None, 0.0
    ranks, ties = _ranks(values)
    correction = (n + 1) - ties / float(n * (n - 1))
    if correction <= 0:
        return None, 0.0
    best_k, best_z = None, 0.0
    prefix = 0.0
    for k in range(1, n):
        prefix += ranks[k - 1]
        if k < min_seg or n - k < min_seg:
            continue
        u_before = prefix - k * (k + 1) / 2.0
        mean = k * (n - k) / 2.0
        var = k * (n - k) / 12.0 * correction
        # u_before above its mean means the earlier segment is higher.
        z = (mean - u_before) / math.sqrt(var)
        if abs(z) > abs(best_z):
            best_k, best_z = k, z
    return best_k, best_z


def find_transitions(values, min_seg, max_transitions=MAX_TRANSITIONS):
    """Binary segmentation. Returns sorted [(k, z)] with |z| >= Z_MODERATE."""
    found = []
    pending = [(0, len(values))]
    while pending and len(found) < max_transitions:
        scored = []
        for lo, hi in pending:
            k, z = best_split(values[lo:hi], min_seg)
            if k is not None:
                scored.append((abs(z), lo, hi, lo + k, z))
        if not scored:
            break
        scored.sort(reverse=True)
        strength, lo, hi, k, z = scored[0]
        pending.remove((lo, hi))
        if strength < Z_MODERATE:
            break
        found.append((k, z))
        pending.extend([(lo, k), (k, hi)])
    return sorted(found)


def spearman(xs, ys):
    """Spearman rank correlation, or None when undefined."""
    if len(xs) < 3:
        return None
    rx, _ = _ranks(xs)
    ry, _ = _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return None
    return round(cov / math.sqrt(vx * vy), 3)


def bucket_key(ts, size):
    if size == "day":
        return ts.strftime("%Y-%m-%d")
    if size == "week":
        monday = ts - timedelta(days=ts.weekday())
        return monday.strftime("%Y-%m-%d")
    return ts.strftime("%Y-%m")


def choose_bucket(days):
    if days <= 45:
        return "day"
    if days <= 270:
        return "week"
    return "month"


def build_runs(rows, disruption_data, selectors):
    """Per-run records, oldest first.

    seconds is None when the disruption API has no rows for the run (BigQuery
    lag, or the run ended before disruption was measured).
    """
    runs = []
    for row in rows:
        pid = str(row.get("prow_id", ""))
        entries = disruption_data.get(pid) or []
        seconds, backend = series_mod.disruption_peak(entries, selectors)
        liveness = any(e.get("backend_name") in LIVENESS_BACKENDS and (e.get("disruption_seconds") or 0) > 0
                       for e in entries)
        tag = next((e.get("release_tag") for e in entries if e.get("release_tag")), "")
        runs.append({
            "prow_id": pid,
            "job": row.get("job", ""),
            "timestamp": sippy.rfc3339(sippy.parse_timestamp(row.get("timestamp", ""))),
            "seconds": seconds,
            "backend": backend,
            "release_tag": tag,
            "liveness_unreliable": liveness,
            "url": row.get("url") or row.get("test_grid_url") or "",
        })
    runs.sort(key=lambda r: r["timestamp"])
    return runs


def _run_ref(run):
    if not run:
        return None
    return {key: run[key] for key in ("prow_id", "job", "timestamp", "seconds", "release_tag", "url")}


def _nearest_tag(runs, start, step):
    i = start
    while 0 <= i < len(runs):
        if runs[i]["release_tag"]:
            return runs[i]["release_tag"]
        i += step
    return ""


def per_job_shift(before, after, min_runs):
    """How many jobs with enough runs on both sides moved up or down in mean seconds."""
    by_job_before, by_job_after = {}, {}
    for run in before:
        by_job_before.setdefault(run["job"], []).append(run["seconds"])
    for run in after:
        by_job_after.setdefault(run["job"], []).append(run["seconds"])
    compared = up = down = 0
    for job, vals in by_job_before.items():
        later = by_job_after.get(job) or []
        if len(vals) < min_runs or len(later) < min_runs:
            continue
        compared += 1
        delta = sum(later) / len(later) - sum(vals) / len(vals)
        if delta > 0.5:
            up += 1
        elif delta < -0.5:
            down += 1
    return {"jobs_compared": compared, "jobs_increased": up, "jobs_decreased": down}


def job_mix_shift(before, after):
    """Total variation distance between job shares before and after (0 same, 1 disjoint)."""
    cb, ca = Counter(r["job"] for r in before), Counter(r["job"] for r in after)
    nb, na = sum(cb.values()) or 1, sum(ca.values()) or 1
    return round(0.5 * sum(abs(cb[j] / nb - ca[j] / na) for j in set(cb) | set(ca)), 3)


def is_practical(before, after):
    """A shift large enough to matter, not only detectable with many runs."""
    if after["nonzero_rate"] - before["nonzero_rate"] >= 0.1 or before["nonzero_rate"] - after["nonzero_rate"] >= 0.1:
        return True
    if abs(after["p50"] - before["p50"]) >= 1:
        return True
    hi, lo = max(after["p95"], before["p95"]), min(after["p95"], before["p95"])
    return hi - lo >= 2 and (lo == 0 or hi / lo >= 1.5)


def describe_transitions(scored, splits, min_seg):
    out = []
    bounds = [0] + [k for k, _z in splits] + [len(scored)]
    for i, (k, z) in enumerate(splits):
        before = scored[bounds[i]:k]
        after = scored[k:bounds[i + 2]]
        sb = summarize([r["seconds"] for r in before])
        sa = summarize([r["seconds"] for r in after])
        out.append({
            "at": after[0]["timestamp"],
            "between": [before[-1]["timestamp"], after[0]["timestamp"]],
            "direction": "increase" if z > 0 else "decrease",
            "z": round(z, 2),
            "strength": "strong" if abs(z) >= Z_STRONG else "moderate",
            "practical": is_practical(sb, sa),
            "before": dict(sb, start=before[0]["timestamp"]),
            "after": dict(sa, end=after[-1]["timestamp"]),
            "last_run_before": _run_ref(before[-1]),
            "first_run_after": _run_ref(after[0]),
            "payload_before": _nearest_tag(scored, k - 1, -1),
            "payload_after": _nearest_tag(scored, k, 1),
            "job_mix_shift": job_mix_shift(before, after),
            "per_job": per_job_shift(before, after, max(3, min_seg // 4)),
        })
    return out


def classify_shape(scored, transitions):
    """Heuristic shape: none, step, multiple, or gradual. The skill confirms it."""
    practical = [t for t in transitions if t["practical"]]
    times = list(range(len(scored)))
    rho = spearman(times, [r["seconds"] for r in scored])
    if not practical:
        return ("gradual" if rho is not None and abs(rho) >= 0.3 else "none"), rho
    if len(practical) >= 2:
        return "multiple", rho
    return "step", rho


def detect_onset(scored, transitions, window_start):
    """When disruption began, relative to the window.

    in_window: an increase from a near-zero baseline (nonzero rate <= 10%).
    before_window: disruption is already present in the earliest runs and no
    increase from a near-zero baseline is found. sporadic: occasional
    disruption throughout, with no sustained start. none: no disruption.
    """
    nonzero = [r for r in scored if r["seconds"] > 0]
    if not nonzero:
        return {"status": "none", "first_nonzero_run": None}
    first = _run_ref(nonzero[0])
    for t in transitions:
        if t["direction"] == "increase" and t["before"]["nonzero_rate"] <= ONSET_BASELINE_RATE:
            return {"status": "in_window", "at": t["at"], "between": t["between"],
                    "baseline_nonzero_rate": t["before"]["nonzero_rate"],
                    "after_nonzero_rate": t["after"]["nonzero_rate"],
                    "payload_before": t["payload_before"], "payload_after": t["payload_after"],
                    "first_nonzero_run": first}
    head = scored[:max(10, len(scored) // 10)]
    head_rate = sum(1 for r in head if r["seconds"] > 0) / len(head)
    status = "before_window" if head_rate > ONSET_BASELINE_RATE else "sporadic"
    return {"status": status, "earliest_runs_nonzero_rate": round(head_rate, 3),
            "window_start": sippy.rfc3339(window_start), "first_nonzero_run": first}


def build_buckets(scored, size):
    groups = {}
    for run in scored:
        key = bucket_key(sippy.parse_timestamp(run["timestamp"]), size)
        groups.setdefault(key, []).append(run)
    buckets = []
    for key in sorted(groups):
        runs = groups[key]
        jobs = Counter(r["job"] for r in runs)
        top_job, top_count = jobs.most_common(1)[0]
        tags = [r["release_tag"] for r in runs if r["release_tag"]]
        buckets.append(dict(
            summarize([r["seconds"] for r in runs]),
            bucket=key,
            sparse=len(runs) < MIN_BUCKET_RUNS,
            jobs=len(jobs),
            top_job=top_job,
            top_job_share=round(top_count / len(runs), 2),
            first_payload=min(tags) if tags else "",
            last_payload=max(tags) if tags else "",
        ))
    return buckets


def analyze(series, runs, window_start, now, bucket, truncated):
    """Assemble the trend result from per-run records."""
    no_data = [r for r in runs if r["seconds"] is None]
    unreliable = [r for r in runs if r["seconds"] is not None and r["liveness_unreliable"]]
    scored = [r for r in runs if r["seconds"] is not None and not r["liveness_unreliable"]]
    min_seg = max(8, min(40, len(scored) // 25))
    splits = find_transitions([r["seconds"] for r in scored], min_seg)
    transitions = describe_transitions(scored, splits, min_seg)
    shape, rho = classify_shape(scored, transitions)
    buckets = build_buckets(scored, bucket)

    caveats = []
    if truncated:
        caveats.append("The scan stopped before the window start; older runs are missing.")
    if runs:
        oldest = sippy.parse_timestamp(runs[0]["timestamp"])
        if oldest - window_start > timedelta(days=2):
            caveats.append(
                "No runs before %s were returned, so the window effectively starts there. Sippy keeps "
                "about %d days of job runs, and release %s only has runs since its branch opened."
                % (oldest.strftime("%Y-%m-%d"), SIPPY_RETENTION_DAYS, series["release"]))
    recent_missing = [r for r in no_data if now - sippy.parse_timestamp(r["timestamp"]) < BIGQUERY_LAG]
    if recent_missing:
        caveats.append("%d run(s) from the last 4 hours have no disruption data yet (BigQuery lag)."
                       % len(recent_missing))
    if len(no_data) > len(recent_missing):
        caveats.append("%d older run(s) have no disruption data (often runs that ended before "
                       "disruption was measured); they are excluded." % (len(no_data) - len(recent_missing)))
    if unreliable:
        caveats.append("%d run(s) had ci-cluster-network-liveness disruption, so their disruption data is "
                       "unreliable; they are excluded from the statistics." % len(unreliable))
    sparse = [b["bucket"] for b in buckets if b["sparse"]]
    if sparse:
        caveats.append("%d of %d %s bucket(s) have fewer than %d runs; their percentiles are noisy."
                       % (len(sparse), len(buckets), bucket, MIN_BUCKET_RUNS))
    for t in transitions:
        if t["job_mix_shift"] >= 0.3:
            caveats.append("The job mix changed across the %s transition (shift %.2f); check per_job before "
                           "treating it as a product change." % (t["at"][:10], t["job_mix_shift"]))
    if len(scored) < 2 * min_seg:
        caveats.append("Only %d usable runs; too few to test for a transition." % len(scored))

    return {
        "window": {"start": sippy.rfc3339(window_start), "end": sippy.rfc3339(now), "bucket": bucket},
        "runs": {"scanned": len(runs), "used": len(scored), "no_data": len(no_data),
                 "liveness_unreliable": len(unreliable)},
        "overall": summarize([r["seconds"] for r in scored]),
        "shape": shape,
        "trend_rho": rho,
        "transitions": transitions,
        "onset": detect_onset(scored, transitions, window_start),
        "buckets": buckets,
        "caveats": caveats,
        "method": {"test": "Mann-Whitney binary segmentation on per-run peak seconds",
                   "min_segment_runs": min_seg, "z_moderate": Z_MODERATE, "z_strong": Z_STRONG},
    }


def series_summary(series):
    out = {key: series[key] for key in ("release", "selectors", "variants", "master_nodes_updated",
                                        "percentile", "compare_release", "dashboard")}
    out["backends"] = out.pop("selectors")
    return out


def write_state(path, series, trend, runs_file):
    state = {}
    if os.path.exists(path):
        with open(path) as f:
            state = json.load(f)
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state["series"] = series_summary(series)
    state["trend"] = dict(trend, runs_file=runs_file)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def _fmt(value):
    return "—" if value is None else ("%g" % value)


def print_table(series, trend, out=None):
    out = out or sys.stdout
    s = series_summary(series)
    filters = " | ".join("%s=%s" % kv for kv in s["variants"].items()) or "(none)"
    if s["master_nodes_updated"]:
        filters += " | MasterNodesUpdated=%s" % s["master_nodes_updated"]
    w = trend["window"]
    print("Series: release %s | backends %s" % (s["release"], ", ".join(s["backends"])), file=out)
    print("Filters: %s" % filters, file=out)
    print("Window: %s to %s (%s buckets) | runs scanned %d, used %d" % (
        w["start"][:10], w["end"][:10], w["bucket"], trend["runs"]["scanned"], trend["runs"]["used"]), file=out)
    print("Per-run peak seconds on the selected backends (not the dashboard percentile).", file=out)
    print("", file=out)
    print("| Bucket | Runs | Nonzero | P50 | P75 | P95 | Max | Jobs | Payloads |", file=out)
    print("|---|---|---|---|---|---|---|---|---|", file=out)
    for b in trend["buckets"]:
        payloads = b["first_payload"] if b["first_payload"] == b["last_payload"] else (
            "%s … %s" % (b["first_payload"], b["last_payload"]))
        print("| %s%s | %d | %d%% | %s | %s | %s | %s | %d | %s |" % (
            b["bucket"], " (sparse)" if b["sparse"] else "", b["n"], round(100 * b["nonzero_rate"]),
            _fmt(b["p50"]), _fmt(b["p75"]), _fmt(b["p95"]), _fmt(b["max"]), b["jobs"], payloads or "—"), file=out)
    print("", file=out)
    print("Shape (heuristic): %s | trend rho %s" % (trend["shape"], _fmt(trend["trend_rho"])), file=out)
    if not trend["transitions"]:
        print("Transitions: none detected (|z| < %g)" % Z_MODERATE, file=out)
    for t in trend["transitions"]:
        print("Transition %s at %s (z=%s, %s%s): P50 %s→%s, P95 %s→%s, nonzero %d%%→%d%%, payloads %s → %s, "
              "job mix shift %s, jobs up/down %d/%d of %d" % (
                  t["direction"], t["at"][:16], t["z"], t["strength"], "" if t["practical"] else ", small effect",
                  _fmt(t["before"]["p50"]), _fmt(t["after"]["p50"]), _fmt(t["before"]["p95"]),
                  _fmt(t["after"]["p95"]), round(100 * t["before"]["nonzero_rate"]),
                  round(100 * t["after"]["nonzero_rate"]), t["payload_before"] or "?", t["payload_after"] or "?",
                  t["job_mix_shift"], t["per_job"]["jobs_increased"], t["per_job"]["jobs_decreased"],
                  t["per_job"]["jobs_compared"]), file=out)
    o = trend["onset"]
    if o["status"] == "in_window":
        print("Onset: %s (nonzero rate %d%% → %d%%, payloads %s → %s)" % (
            o["at"][:16], round(100 * o["baseline_nonzero_rate"]), round(100 * o["after_nonzero_rate"]),
            o["payload_before"] or "?", o["payload_after"] or "?"), file=out)
    elif o["status"] == "before_window":
        print("Onset: before the window start (%s); %d%% of the earliest runs already had disruption." % (
            o["window_start"][:10], round(100 * o["earliest_runs_nonzero_rate"])), file=out)
    elif o["status"] == "sporadic":
        print("Onset: none sustained; disruption is occasional throughout the window.", file=out)
    else:
        print("Onset: no disruption in the window.", file=out)
    for c in trend["caveats"]:
        print("Caveat: %s" % c, file=out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Disruption time series, transitions, and onset for one series")
    parser.add_argument("--grafana-url", help="Grafana disruption dashboard URL")
    parser.add_argument("--alert-text", help="Pasted DisruptionRegression alert text")
    parser.add_argument("--release", help="OpenShift release (e.g., 5.0)")
    parser.add_argument("--backend", help="Exact backend name(s), comma-separated")
    parser.add_argument("--platform")
    parser.add_argument("--upgrade-type")
    parser.add_argument("--architecture")
    parser.add_argument("--topology")
    parser.add_argument("--network")
    parser.add_argument("--days", type=float, default=None,
                        help="Window in days (default %d, or the dashboard lookback if longer; maximum %d, "
                             "because Sippy only keeps about that much run history)." % (DEFAULT_DAYS, MAX_DAYS))
    parser.add_argument("--bucket", choices=["auto", "day", "week", "month"], default="auto")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--state-file", help="Investigation state JSON to update with series and trend")
    parser.add_argument("--runs-out", help="Write per-run records here (default: beside --state-file)")
    parser.add_argument("--cache-dir", default=".work/disruption-analysis/cache",
                        help="Disruption data cache directory (default: %(default)s). Use '' to disable.")
    args = parser.parse_args(argv)

    try:
        series = series_mod.resolve_series(
            args.grafana_url, args.alert_text, release=args.release, backend=args.backend,
            platform=args.platform, upgrade_type=args.upgrade_type, architecture=args.architecture,
            topology=args.topology, network=args.network)
    except series_mod.SeriesError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    days = args.days if args.days is not None else max(DEFAULT_DAYS, series["lookback_days"] or 0)
    if days <= 0:
        print("Error: --days must be positive.", file=sys.stderr)
        return 1
    requested_days = days
    if days > MAX_DAYS:
        days = MAX_DAYS
        print("Warning: a %g-day window was requested; using the maximum of %d days." % (requested_days, MAX_DAYS),
              file=sys.stderr)
    window_start = now - timedelta(days=days)
    bucket = choose_bucket(days) if args.bucket == "auto" else args.bucket

    def run_progress(count, oldest):
        if oldest is not None:
            print("  fetched %d runs (back to %s)" % (count, oldest.strftime("%Y-%m-%d")), file=sys.stderr)

    def disruption_progress(done, total):
        print("  disruption data %d/%d runs" % (done, total), file=sys.stderr)

    print("Fetching runs for release %s since %s..." % (series["release"], window_start.strftime("%Y-%m-%d")),
          file=sys.stderr)
    try:
        rows, truncated = sippy.collect_runs(series["release"], series["variants"], window_start,
                                             progress=run_progress)
    except sippy.SippyError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1
    if not rows:
        print("No runs found for release %s with %s since %s. Widen --days or relax filters." % (
            series["release"], series["variants"] or "no variant filters", window_start.strftime("%Y-%m-%d")),
            file=sys.stderr)
        return 0

    cache_path = os.path.join(args.cache_dir, "disruption.json") if args.cache_dir else None
    disruption = sippy.fetch_disruption_data([r["prow_id"] for r in rows if r.get("prow_id")],
                                             cache_path=cache_path, progress=disruption_progress)
    if series["master_nodes_updated"]:
        selected = series_mod.filter_disruption_data(disruption, series["selectors"])
        rows = series_mod.apply_master_nodes_filter(
            rows, selected, series["master_nodes_updated"],
            series_mod.disruption_api_has_master_field(disruption))
        if not rows:
            print("No runs matched master_nodes_updated=%s." % series["master_nodes_updated"], file=sys.stderr)
            return 0

    runs = build_runs(rows, disruption, series["selectors"])
    trend = analyze(series, runs, window_start, now, bucket, truncated)
    if requested_days > days:
        trend["caveats"].insert(0, "A %g-day window was requested, but the maximum is %d days because Sippy only "
                                   "keeps about that much run history." % (requested_days, MAX_DAYS))

    runs_file = args.runs_out
    if not runs_file and args.state_file:
        runs_file = os.path.join(os.path.dirname(args.state_file) or ".", "trend-runs.json")
    if runs_file:
        directory = os.path.dirname(runs_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(runs_file, "w") as f:
            json.dump(runs, f, indent=1)
    if args.state_file:
        write_state(args.state_file, series, trend, runs_file)

    if args.format == "json":
        print(json.dumps({"series": series_summary(series), "trend": dict(trend, runs_file=runs_file)}, indent=2))
    else:
        print_table(series, trend)
    return 0


if __name__ == "__main__":
    sys.exit(main())
