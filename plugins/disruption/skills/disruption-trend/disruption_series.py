"""Build a disruption time series for one series and locate transitions and onset.

Fetches every run in the window for the series (release, exact backends,
Sippy variants, master_nodes_updated), takes each run's peak disruption
seconds among the exact selected backends, buckets the runs over time, and
runs binary segmentation with a Mann-Whitney statistic on the per-run values
to find step changes. For each transition it adds a per-job table, the
initial and target payloads of the runs nearest the step (from their public
prowjob.json), and suggested before/after run pairs for disruption-analyze-run.
It reports facts and caveats. Interpreting them is the skill's job.

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

from disruption_common import series as series_mod  # noqa: E402
from disruption_common import payloads as payload_pairs  # noqa: E402
from disruption_common import sippy, state  # noqa: E402

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
# Runs lost to disruption API failures above this share mark the result degraded.
DEGRADED_LOST_FRACTION = 0.03
DEFAULT_RATE_LIMIT_WAIT = 300
# prowjob.json is read for at most this many runs on each side of a transition.
PAYLOAD_SAMPLE_PER_SIDE = 20
PAIRS_PER_TRANSITION = 3
# Runs of one job that start this close together came from one launch and share a payload.
LAUNCH_BATCH_GAP = timedelta(minutes=10)


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


def build_runs(rows, disruption_data, selectors, failed=None):
    """Per-run records, oldest first.

    seconds is None when the disruption API has no rows for the run (BigQuery
    lag, or the run ended before disruption was measured), or when the API
    failed for it. `failed` holds the prow IDs the API failed for; those runs
    get fetch_failed=True so they are not mistaken for runs without data.
    """
    failed = set(failed or ())
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
            "fetch_failed": pid in failed and not entries,
            "url": row.get("url") or row.get("test_grid_url") or "",
        })
    # Sort on the parsed time: as strings, "…05Z" sorts after "…05.5Z".
    runs.sort(key=lambda run: sippy.parse_timestamp(run["timestamp"]))
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


def _p(values, q):
    return round(percentile(values, q), 1) if values else None


def per_job_table(before, after, min_runs):
    """One row per job with at least one run after the step, most after-step runs first.

    small_n flags a job with fewer than `min_runs` runs on either side instead
    of dropping it. after_vs_before places the job's after-step P50 against
    its own before-step distribution.
    """
    by_job_before, by_job_after = {}, {}
    for run in before:
        by_job_before.setdefault(run["job"], []).append(run["seconds"])
    for run in after:
        by_job_after.setdefault(run["job"], []).append(run["seconds"])
    rows = []
    for job, later in by_job_after.items():
        earlier = by_job_before.get(job) or []
        row = {"job": job, "n_before": len(earlier), "n_after": len(later),
               "before_p50": _p(earlier, 50), "before_p95": _p(earlier, 95),
               "after_p50": _p(later, 50), "after_max": max(later),
               "small_n": len(earlier) < min_runs or len(later) < min_runs, "after_vs_before": None}
        if earlier:
            if row["after_p50"] > row["before_p95"]:
                row["after_vs_before"] = "above_p95"
            elif row["after_p50"] > row["before_p50"]:
                row["after_vs_before"] = "above_p50"
            else:
                row["after_vs_before"] = "at_or_below_p50"
        rows.append(row)
    rows.sort(key=lambda row: (-row["n_after"], row["job"]))
    return rows


def _time(run):
    return sippy.parse_timestamp(run["timestamp"])


def _same_batch(run, others):
    return any(other["job"] == run["job"] and abs(_time(other) - _time(run)) <= LAUNCH_BATCH_GAP
               for other in others)


def _pair_ref(run, representative):
    return dict(_run_ref(run), representative=representative)


def suggest_pairs(before, after, direction, limit=PAIRS_PER_TRANSITION):
    """Before/after run pairs from the same job, nearest the step, for disruption-analyze-run.

    Each job is judged against its own before-step runs, because jobs differ
    in baseline. For an increase, a representative after-step run is above
    the job's before P95 and a representative before-step run is at or below
    its before P95 (not an outlier); for a decrease, the after-step run is at
    or below the job's before P50 and the before-step run at or above it.
    Representative runs are preferred, then the nearest. At most one run is
    taken from a launch batch (same job, starts within LAUNCH_BATCH_GAP), on
    either side. Jobs with a representative after-step run come first, then
    those with the most after-step runs, and each job gives one pair per round.
    """
    step = _time(after[0]) if after else None
    by_job_before, by_job_after = {}, {}
    for run in before:
        by_job_before.setdefault(run["job"], []).append(run)
    for run in after:
        by_job_after.setdefault(run["job"], []).append(run)
    candidates, moved = {}, {}
    for job in by_job_after:
        if job not in by_job_before:
            continue
        values = [r["seconds"] for r in by_job_before[job]]
        p50, p95 = percentile(values, 50), percentile(values, 95)

        def after_rep(run, p50=p50, p95=p95):
            return run["seconds"] > p95 if direction == "increase" else run["seconds"] <= p50

        def before_rep(run, p50=p50, p95=p95):
            return run["seconds"] <= p95 if direction == "increase" else run["seconds"] >= p50

        afters = sorted(by_job_after[job], key=lambda r: (not after_rep(r), _time(r) - step))
        befores = sorted(by_job_before[job], key=lambda r: (not before_rep(r), step - _time(r)))
        candidates[job] = (afters, befores, after_rep, before_rep)
        moved[job] = any(after_rep(r) for r in afters)
    jobs = sorted(candidates, key=lambda job: (not moved[job], -len(by_job_after[job]), job))

    pairs, used = [], []
    while len(pairs) < limit:
        added = False
        for job in jobs:
            if len(pairs) >= limit:
                break
            afters, befores, after_rep, before_rep = candidates[job]
            after_run = next((r for r in afters if not _same_batch(r, used)), None)
            if after_run is None:
                continue
            before_run = next((r for r in befores if not _same_batch(r, used + [after_run])), None)
            if before_run is None:
                continue
            used.extend([after_run, before_run])
            pairs.append({"job": job, "before": _pair_ref(before_run, before_rep(before_run)),
                          "after": _pair_ref(after_run, after_rep(after_run))})
            added = True
        if not added:
            break
    return {
        "pairs": pairs,
        "prow_urls": [ref["url"] for pair in pairs for ref in (pair["before"], pair["after"]) if ref["url"]],
        "download_runs": ",".join("%s:%s" % (ref["job"], ref["prow_id"])
                                  for pair in pairs for ref in (pair["before"], pair["after"])),
    }


def job_mix_shift(before, after):
    """Total variation distance between job shares before and after (0 same, 1 disjoint)."""
    jobs_before, jobs_after = Counter(r["job"] for r in before), Counter(r["job"] for r in after)
    total_before, total_after = sum(jobs_before.values()) or 1, sum(jobs_after.values()) or 1
    return round(0.5 * sum(abs(jobs_before[job] / total_before - jobs_after[job] / total_after)
                           for job in set(jobs_before) | set(jobs_after)), 3)


def is_practical(before, after):
    """A shift large enough to matter, not only detectable with many runs."""
    if after["nonzero_rate"] - before["nonzero_rate"] >= 0.1 or before["nonzero_rate"] - after["nonzero_rate"] >= 0.1:
        return True
    if abs(after["p50"] - before["p50"]) >= 1:
        return True
    hi, lo = max(after["p95"], before["p95"]), min(after["p95"], before["p95"])
    return hi - lo >= 2 and (lo == 0 or hi / lo >= 1.5)


def describe_transitions(scored, splits, min_seg):
    transitions = []
    bounds = [0] + [split_at for split_at, _z in splits] + [len(scored)]
    min_runs = max(3, min_seg // 4)
    for i, (split_at, z) in enumerate(splits):
        before = scored[bounds[i]:split_at]
        after = scored[split_at:bounds[i + 2]]
        before_stats = summarize([r["seconds"] for r in before])
        after_stats = summarize([r["seconds"] for r in after])
        transitions.append({
            "at": after[0]["timestamp"],
            "between": [before[-1]["timestamp"], after[0]["timestamp"]],
            "direction": "increase" if z > 0 else "decrease",
            "z": round(z, 2),
            "strength": "strong" if abs(z) >= Z_STRONG else "moderate",
            "practical": is_practical(before_stats, after_stats),
            "before": dict(before_stats, start=before[0]["timestamp"]),
            "after": dict(after_stats, end=after[-1]["timestamp"]),
            "last_run_before": _run_ref(before[-1]),
            "first_run_after": _run_ref(after[0]),
            "payload_before": _nearest_tag(scored, split_at - 1, -1),
            "payload_after": _nearest_tag(scored, split_at, 1),
            "job_mix_shift": job_mix_shift(before, after),
            "per_job": dict(per_job_shift(before, after, min_runs), min_runs=min_runs,
                            jobs=per_job_table(before, after, min_runs)),
            "handoff": suggest_pairs(before, after, "increase" if z > 0 else "decrease"),
        })
    return transitions


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
    unknown: no run had usable disruption data, so nothing can be said.
    """
    if not scored:
        return {"status": "unknown", "first_nonzero_run": None}
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


def partition_runs(runs):
    """Split runs into (lost, no_data, unreliable, scored), keeping their order.

    lost: the disruption API failed for the run, so whether it has data is
    unknown. no_data: the API answered with no rows for it.
    """
    lost, no_data, unreliable, scored = [], [], [], []
    for run in runs:
        if run.get("fetch_failed"):
            lost.append(run)
        elif run["seconds"] is None:
            no_data.append(run)
        elif run["liveness_unreliable"]:
            unreliable.append(run)
        else:
            scored.append(run)
    return lost, no_data, unreliable, scored


def transition_segments(scored, transitions):
    """(transition, before runs, after runs) for each transition, as describe_transitions split them."""
    index = {run["prow_id"]: i for i, run in enumerate(scored)}
    splits = [index[t["first_run_after"]["prow_id"]] for t in transitions]
    bounds = [0] + splits + [len(scored)]
    return [(t, scored[bounds[i]:bounds[i + 1]], scored[bounds[i + 1]:bounds[i + 2]])
            for i, t in enumerate(transitions)]


def _lost_fraction(lost, kept):
    return lost / float(lost + kept) if lost + kept else 0.0


def describe_data_loss(lost, scanned, transitions, bucket):
    """How many runs the disruption API failed for, when, and whether that degrades the result.

    Each transition gets lost_runs (lost runs inside its before and after
    time ranges) and degraded, when either side lost more than
    DEGRADED_LOST_FRACTION of its runs. The result is degraded when the whole
    window or any transition is.
    """
    times = [sippy.parse_timestamp(r["timestamp"]) for r in lost]
    for i, transition in enumerate(transitions):
        lower = sippy.parse_timestamp(transitions[i - 1]["at"]) if i else None
        at = sippy.parse_timestamp(transition["at"])
        upper = sippy.parse_timestamp(transitions[i + 1]["at"]) if i + 1 < len(transitions) else None
        lost_before = sum(1 for ts in times if ts < at and (lower is None or ts >= lower))
        lost_after = sum(1 for ts in times if ts >= at and (upper is None or ts < upper))
        transition["lost_runs"] = {"before": lost_before, "after": lost_after}
        transition["degraded"] = (_lost_fraction(lost_before, transition["before"]["n"]) > DEGRADED_LOST_FRACTION
                                  or _lost_fraction(lost_after, transition["after"]["n"]) > DEGRADED_LOST_FRACTION)
    fraction = len(lost) / float(scanned) if scanned else 0.0
    by_bucket = Counter(bucket_key(ts, bucket) for ts in times)
    return {
        "runs": len(lost),
        "fraction": round(fraction, 3),
        "first": sippy.rfc3339(min(times)) if times else None,
        "last": sippy.rfc3339(max(times)) if times else None,
        "buckets": dict(sorted(by_bucket.items())),
        "degraded": fraction > DEGRADED_LOST_FRACTION or any(t["degraded"] for t in transitions),
    }


def analyze(series, runs, window_start, now, bucket, truncated):
    """Assemble the trend result from per-run records."""
    lost, no_data, unreliable, scored = partition_runs(runs)
    min_seg = max(8, min(40, len(scored) // 25))
    splits = find_transitions([r["seconds"] for r in scored], min_seg)
    transitions = describe_transitions(scored, splits, min_seg)
    data_loss = describe_data_loss(lost, len(runs), transitions, bucket)
    shape, rho = classify_shape(scored, transitions)
    buckets = build_buckets(scored, bucket)

    caveats = []
    if lost:
        caveats.append(
            "%d run(s) from %s to %s (%.1f%% of the runs scanned) have no disruption data because the Sippy "
            "disruption API failed for them (HTTP 429 rate limit or another error); they are excluded and are "
            "not counted as runs without data. Affected %s bucket(s): %s. Rerun later: the cache keeps what was "
            "fetched, so the rerun only asks for these runs."
            % (len(lost), data_loss["first"][:16], data_loss["last"][:16], 100 * data_loss["fraction"], bucket,
               ", ".join("%s (%d)" % kv for kv in data_loss["buckets"].items())))
    if data_loss["degraded"]:
        degraded = [t["at"][:10] for t in transitions if t["degraded"]]
        caveats.append(
            "The result is degraded: more than %d%% of the runs %s are missing because of disruption API "
            "failures, so the baseline, the transitions, and the onset may be wrong. Do not present it as "
            "clean." % (round(100 * DEGRADED_LOST_FRACTION),
                        "around the %s transition(s)" % ", ".join(degraded) if degraded else "in the window"))
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
    for transition in transitions:
        if transition["job_mix_shift"] >= 0.3:
            caveats.append("The job mix changed across the %s transition (shift %.2f); check per_job before "
                           "treating it as a product change." % (transition["at"][:10], transition["job_mix_shift"]))
    if len(scored) < 2 * min_seg:
        caveats.append("Only %d usable runs; too few to test for a transition." % len(scored))

    return {
        "window": {"start": sippy.rfc3339(window_start), "end": sippy.rfc3339(now), "bucket": bucket},
        "runs": {"scanned": len(runs), "used": len(scored), "no_data": len(no_data),
                 "fetch_failed": len(lost), "liveness_unreliable": len(unreliable)},
        "degraded": data_loss["degraded"],
        "data_loss": data_loss,
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


def payload_sample(trend, runs):
    """Runs whose prowjob.json is read: the PAYLOAD_SAMPLE_PER_SIDE scored runs
    nearest each transition on both sides, plus every suggested pair run."""
    _lost, _no_data, _unreliable, scored = partition_runs(runs)
    sample, seen = [], set()
    for transition, before, after in transition_segments(scored, trend["transitions"]):
        refs = [ref for pair in transition["handoff"]["pairs"] for ref in (pair["before"], pair["after"])]
        for run in before[-PAYLOAD_SAMPLE_PER_SIDE:] + after[:PAYLOAD_SAMPLE_PER_SIDE] + refs:
            if run["prow_id"] not in seen:
                seen.add(run["prow_id"])
                sample.append({"prow_id": run["prow_id"], "job": run["job"]})
    return sample


def _group(runs):
    values = [r["seconds"] for r in runs]
    return {"n": len(values), "p50": _p(values, 50), "max": max(values) if values else None}


def payload_summary(before, after, payloads, failed):
    """Place a transition by target payload and test whether it depends on the initial payload.

    `before` and `after` are the sampled runs on each side, nearest the step.
    The target payloads separate when every after-step target is newer than
    the newest before-step target. The step payload is estimated as the
    oldest after-step target; after-step upgrades are then grouped by whether
    they started from an initial payload older than it (pre_step) or not
    (post_step). If only the pre_step group is high, the step depends on the
    payload upgraded from, not only the one upgraded to.
    """
    failed = set(failed)

    def pair(run):
        return payloads.get(run["prow_id"]) or {}

    sampled = before + after
    summary = {
        "sampled_before": len(before), "sampled_after": len(after),
        "fetch_failed": sum(1 for r in sampled if r["prow_id"] in failed),
        "no_payload": sum(1 for r in sampled if r["prow_id"] in payloads and not pair(r).get("target")),
        "newest_target_before": "", "oldest_target_after": "", "after_on_old_target": None,
        "target_separates": None, "after_upgrades_by_initial": None, "version_pairs": [],
    }
    targets_before = [pair(r)["target"] for r in before if payload_pairs.payload_time(pair(r).get("target"))]
    targets_after = [pair(r)["target"] for r in after if payload_pairs.payload_time(pair(r).get("target"))]
    if targets_before:
        summary["newest_target_before"] = max(targets_before, key=payload_pairs.payload_time)
    if targets_after:
        summary["oldest_target_after"] = min(targets_after, key=payload_pairs.payload_time)
    if targets_before and targets_after:
        newest = payload_pairs.payload_time(summary["newest_target_before"])
        old = sum(1 for t in targets_after if payload_pairs.payload_time(t) <= newest)
        summary["after_on_old_target"] = old
        summary["target_separates"] = old == 0
    if targets_after:
        step = payload_pairs.payload_time(summary["oldest_target_after"])
        groups = {"pre_step": [], "post_step": [], "not_upgrade": []}
        for run in after:
            if not pair(run).get("target"):
                continue
            if not payload_pairs.is_upgrade(pair(run)):
                groups["not_upgrade"].append(run)
                continue
            initial = payload_pairs.payload_time(pair(run)["initial"])
            if initial:
                groups["pre_step" if initial < step else "post_step"].append(run)
        summary["after_upgrades_by_initial"] = dict({key: _group(value) for key, value in groups.items()},
                                                    step_payload=summary["oldest_target_after"])
    versions = {}
    for side, runs in (("before", before), ("after", after)):
        for run in runs:
            if payload_pairs.is_upgrade(pair(run)):
                key = (payload_pairs.payload_minor(pair(run)["initial"]) or "?",
                       payload_pairs.payload_minor(pair(run)["target"]) or "?")
                versions.setdefault(key, {"before": [], "after": []})[side].append(run)
    for (initial, target), sides in sorted(versions.items()):
        summary["version_pairs"].append({"from": initial, "to": target, "before": _group(sides["before"]),
                                         "after": _group(sides["after"])})
    return summary


def apply_payloads(trend, runs, payloads, failed):
    """Record payload pairs on runs, transitions, and suggested pairs, and add caveats."""
    for run in runs:
        pair = payloads.get(run["prow_id"])
        if pair is not None:
            run["initial_payload"], run["target_payload"] = pair["initial"], pair["target"]
    _lost, _no_data, _unreliable, scored = partition_runs(runs)
    for transition, before, after in transition_segments(scored, trend["transitions"]):
        summary = payload_summary(before[-PAYLOAD_SAMPLE_PER_SIDE:], after[:PAYLOAD_SAMPLE_PER_SIDE],
                                  payloads, failed)
        transition["payloads"] = summary
        for pair in transition["handoff"]["pairs"]:
            for ref in (pair["before"], pair["after"]):
                known = payloads.get(ref["prow_id"]) or {}
                ref["initial_payload"], ref["target_payload"] = known.get("initial", ""), known.get("target", "")
        day = transition["at"][:10]
        sampled = summary["sampled_before"] + summary["sampled_after"]
        if summary["fetch_failed"]:
            trend["caveats"].append(
                "prowjob.json could not be fetched for %d of %d sampled run(s) near the %s transition; the payload "
                "findings use the rest." % (summary["fetch_failed"], sampled, day))
        if not summary["newest_target_before"] and not summary["oldest_target_after"]:
            trend["caveats"].append(
                "No sampled run near the %s transition recorded a release payload in prowjob.json (jobs not "
                "started by the release controller, or fetch failures), so the transition cannot be placed by "
                "payload; use the Sippy payload range with care." % day)


def series_summary(series):
    out = {key: series[key] for key in ("release", "selectors", "variants", "master_nodes_updated",
                                        "percentile", "compare_release", "dashboard")}
    out["backends"] = out.pop("selectors")
    return out


def write_state(path, series, trend, runs_file):
    """Merge series and trend into the state file. Raises state.StateError if it is unreadable."""
    current = state.load_state(path)
    current.setdefault("schema_version", STATE_SCHEMA_VERSION)
    current["series"] = series_summary(series)
    current["trend"] = dict(trend, runs_file=runs_file)
    state.write_json_atomic(path, current, indent=2)


def _fmt(value):
    return "—" if value is None else ("%g" % value)


def print_table(series, trend, out=None):
    out = out or sys.stdout
    summary = series_summary(series)
    filters = " | ".join("%s=%s" % kv for kv in summary["variants"].items()) or "(none)"
    if summary["master_nodes_updated"]:
        filters += " | MasterNodesUpdated=%s" % summary["master_nodes_updated"]
    window = trend["window"]
    print("Series: release %s | backends %s" % (summary["release"], ", ".join(summary["backends"])), file=out)
    print("Filters: %s" % filters, file=out)
    print("Window: %s to %s (%s buckets) | runs scanned %d, used %d" % (
        window["start"][:10], window["end"][:10], window["bucket"], trend["runs"]["scanned"],
        trend["runs"]["used"]), file=out)
    loss = trend.get("data_loss") or {}
    if trend.get("degraded"):
        print("DEGRADED: %d run(s) (%.1f%%) lost to Sippy disruption API failures between %s and %s; the baseline "
              "and transitions are incomplete. Rerun later; the cache keeps what was fetched." % (
                  loss["runs"], 100 * loss["fraction"], (loss["first"] or "?")[:16], (loss["last"] or "?")[:16]),
              file=out)
    print("Per-run peak seconds on the selected backends (not the dashboard percentile).", file=out)
    print("", file=out)
    print("| Bucket | Runs | Nonzero | P50 | P75 | P95 | Max | Jobs | Payloads |", file=out)
    print("|---|---|---|---|---|---|---|---|---|", file=out)
    for row in trend["buckets"]:
        payloads = row["first_payload"] if row["first_payload"] == row["last_payload"] else (
            "%s … %s" % (row["first_payload"], row["last_payload"]))
        print("| %s%s | %d | %d%% | %s | %s | %s | %s | %d | %s |" % (
            row["bucket"], " (sparse)" if row["sparse"] else "", row["n"], round(100 * row["nonzero_rate"]),
            _fmt(row["p50"]), _fmt(row["p75"]), _fmt(row["p95"]), _fmt(row["max"]), row["jobs"],
            payloads or "—"), file=out)
    print("", file=out)
    print("Shape (heuristic): %s | trend rho %s" % (trend["shape"], _fmt(trend["trend_rho"])), file=out)
    if not trend["transitions"]:
        print("Transitions: none detected (|z| < %g)" % Z_MODERATE, file=out)
    for transition in trend["transitions"]:
        before, after, per_job = transition["before"], transition["after"], transition["per_job"]
        print("Transition %s at %s (z=%s, %s%s): P50 %s→%s, P95 %s→%s, nonzero %d%%→%d%%, payloads %s → %s, "
              "job mix shift %s, jobs up/down %d/%d of %d" % (
                  transition["direction"], transition["at"][:16], transition["z"], transition["strength"],
                  "" if transition["practical"] else ", small effect",
                  _fmt(before["p50"]), _fmt(after["p50"]), _fmt(before["p95"]), _fmt(after["p95"]),
                  round(100 * before["nonzero_rate"]), round(100 * after["nonzero_rate"]),
                  transition["payload_before"] or "?", transition["payload_after"] or "?",
                  transition["job_mix_shift"], per_job["jobs_increased"], per_job["jobs_decreased"],
                  per_job["jobs_compared"]), file=out)
        if transition.get("degraded"):
            lost = transition["lost_runs"]
            print("  DEGRADED: %d run(s) before and %d after this step were lost to disruption API failures."
                  % (lost["before"], lost["after"]), file=out)
        print_transition_details(transition, out)
    onset = trend["onset"]
    if onset["status"] == "in_window":
        print("Onset: %s (nonzero rate %d%% → %d%%, payloads %s → %s)" % (
            onset["at"][:16], round(100 * onset["baseline_nonzero_rate"]), round(100 * onset["after_nonzero_rate"]),
            onset["payload_before"] or "?", onset["payload_after"] or "?"), file=out)
    elif onset["status"] == "before_window":
        print("Onset: before the window start (%s); %d%% of the earliest runs already had disruption." % (
            onset["window_start"][:10], round(100 * onset["earliest_runs_nonzero_rate"])), file=out)
    elif onset["status"] == "sporadic":
        print("Onset: none sustained; disruption is occasional throughout the window.", file=out)
    elif onset["status"] == "unknown":
        print("Onset: unknown; no run had usable disruption data (see caveats).", file=out)
    else:
        print("Onset: no disruption in the window.", file=out)
    for caveat in trend["caveats"]:
        print("Caveat: %s" % caveat, file=out)


def _job_note(row):
    notes = []
    if row["small_n"]:
        notes.append("small n")
    if row["n_before"] == 0:
        notes.append("new after the step")
    elif row["after_vs_before"] == "above_p95":
        notes.append("after P50 above before P95")
    elif row["after_vs_before"] == "above_p50":
        notes.append("after P50 above before P50")
    return ", ".join(notes)


def _fmt_group(group):
    if not group or not group["n"]:
        return "n=0"
    return "n=%d P50 %s max %s" % (group["n"], _fmt(group["p50"]), _fmt(group["max"]))


def print_transition_details(transition, out):
    """The per-job table, payload findings, and suggested pairs for one transition."""
    per_job = transition["per_job"]
    print("", file=out)
    print("Per job, every job with a run after the step (small n: fewer than %d runs on a side):"
          % per_job["min_runs"], file=out)
    print("| Job | n before | n after | Before P50 | Before P95 | After P50 | After max | Note |", file=out)
    print("|---|---|---|---|---|---|---|---|", file=out)
    for row in per_job["jobs"]:
        print("| %s | %d | %d | %s | %s | %s | %s | %s |" % (
            row["job"], row["n_before"], row["n_after"], _fmt(row["before_p50"]), _fmt(row["before_p95"]),
            _fmt(row["after_p50"]), _fmt(row["after_max"]), _job_note(row)), file=out)
    payloads = transition.get("payloads")
    if payloads:
        print("", file=out)
        print("Payloads (prowjob.json of the %d/%d runs nearest the step; %d not fetched, %d without a payload):" % (
            payloads["sampled_before"], payloads["sampled_after"], payloads["fetch_failed"],
            payloads["no_payload"]), file=out)
        if payloads["target_separates"] is None:
            print("  By target payload: not enough runs with a recorded target on both sides.", file=out)
        else:
            print("  By target payload: newest before %s, oldest after %s; %s" % (
                payloads["newest_target_before"], payloads["oldest_target_after"],
                "targets separate cleanly" if payloads["target_separates"] else
                "%d of the after-step runs used a target no newer than the newest before-step target"
                % payloads["after_on_old_target"]), file=out)
        groups = payloads["after_upgrades_by_initial"]
        if groups:
            print("  After the step, by initial payload: upgrades from before %s %s; from %s or later %s; "
                  "not upgrades %s" % (groups["step_payload"], _fmt_group(groups["pre_step"]), groups["step_payload"],
                                       _fmt_group(groups["post_step"]), _fmt_group(groups["not_upgrade"])), file=out)
        for pair in payloads["version_pairs"]:
            print("  Upgrades %s → %s: before %s; after %s" % (
                pair["from"], pair["to"], _fmt_group(pair["before"]), _fmt_group(pair["after"])), file=out)
    handoff = transition["handoff"]
    print("", file=out)
    if not handoff["pairs"]:
        print("Suggested pairs: none (no job ran on both sides of the step).", file=out)
        return
    print("Suggested before/after pairs for disruption-analyze-run (same job, nearest the step, one run per launch):",
          file=out)
    for pair in handoff["pairs"]:
        sides = []
        for label, ref in (("before", pair["before"]), ("after", pair["after"])):
            payload = ""
            if ref.get("target_payload"):
                payload = ", %s → %s" % (ref.get("initial_payload") or "?", ref["target_payload"])
            sides.append("%s %s (%ss %s%s%s)" % (label, ref["url"] or ref["prow_id"], _fmt(ref["seconds"]),
                                                 ref["timestamp"][:16], "" if ref["representative"] else
                                                 ", not representative", payload))
        print("- %s: %s" % (pair["job"], "; ".join(sides)), file=out)
    print("  download_timelines.py --runs \"%s\"" % handoff["download_runs"], file=out)


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
                        help="Disruption data and prowjob payload cache directory (default: %(default)s). "
                             "Use '' to disable.")
    parser.add_argument("--rate-limit-wait", type=float, default=DEFAULT_RATE_LIMIT_WAIT,
                        help="Most seconds to wait in total on Sippy disruption API rate limits (HTTP 429) "
                             "before giving up on the remaining runs (default: %(default)s)")
    parser.add_argument("--no-payloads", action="store_true",
                        help="Do not read prowjob.json from GCS for the payload pairs near each transition")
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
    disruption, failed = sippy.fetch_disruption_data_with_failures(
        [r["prow_id"] for r in rows if r.get("prow_id")], cache_path=cache_path, progress=disruption_progress,
        max_wait=args.rate_limit_wait)
    if failed:
        print("Warning: the disruption API failed for %d run(s); they are reported as lost, not as runs without "
              "data." % len(failed), file=sys.stderr)
    if series["master_nodes_updated"]:
        selected = series_mod.filter_disruption_data(disruption, series["selectors"])
        failed_ids = set(failed)
        lost_rows = [r for r in rows if str(r.get("prow_id", "")) in failed_ids]
        rows = series_mod.apply_master_nodes_filter(
            rows, selected, series["master_nodes_updated"],
            series_mod.disruption_api_has_master_field(disruption))
        # Lost runs cannot be classified Y or N. They stay in, so the loss is reported
        # instead of "no runs matched".
        rows = rows + lost_rows
        if not rows:
            print("No runs matched master_nodes_updated=%s." % series["master_nodes_updated"], file=sys.stderr)
            return 0

    runs = build_runs(rows, disruption, series["selectors"], failed)
    trend = analyze(series, runs, window_start, now, bucket, truncated)
    if requested_days > days:
        trend["caveats"].insert(0, "A %g-day window was requested, but the maximum is %d days because Sippy only "
                                   "keeps about that much run history." % (requested_days, MAX_DAYS))
    sample = [] if args.no_payloads else payload_sample(trend, runs)
    if sample:
        print("Reading payloads from prowjob.json for %d run(s) near the transitions..." % len(sample),
              file=sys.stderr)
        payload_cache = os.path.join(args.cache_dir, "prowjob-payloads.json") if args.cache_dir else None
        payloads, payload_failed = payload_pairs.fetch_payloads(sample, cache_path=payload_cache,
                                                                write=state.write_json_atomic)
        apply_payloads(trend, runs, payloads, payload_failed)

    runs_file = args.runs_out
    if not runs_file and args.state_file:
        runs_file = os.path.join(os.path.dirname(args.state_file) or ".", "trend-runs.json")
    code = 0
    if runs_file:
        try:
            state.write_json_atomic(runs_file, runs, indent=1)
        except OSError as e:
            print("Error: cannot write runs file %s: %s" % (runs_file, e), file=sys.stderr)
            runs_file = None
            code = 1
    # A state file must not point at a runs file that was not written.
    if args.state_file and code == 0:
        try:
            write_state(args.state_file, series, trend, runs_file)
        except (state.StateError, OSError) as e:
            print("Error: %s" % e, file=sys.stderr)
            code = 1

    if args.format == "json":
        print(json.dumps({"series": series_summary(series), "trend": dict(trend, runs_file=runs_file)}, indent=2))
    else:
        print_table(series, trend)
    return code


if __name__ == "__main__":
    sys.exit(main())
