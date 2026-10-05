"""Find Prow job runs with disruption from Grafana dashboard parameters.

Takes Grafana disruption dashboard URL parameters (platform, backend,
upgrade type, etc.), queries Sippy for matching runs, enriches them with
actual disruption seconds from BigQuery, and outputs a candidate table.

Usage:
    python3 find_disruption_runs.py --grafana-url <url>
    python3 find_disruption_runs.py --alert-text <pasted alert>
    python3 find_disruption_runs.py --release 5.0 --platform gcp --backend host-to-host-new-connections --upgrade-type micro --architecture amd64 --topology ha --network ovn

Output formats:
    --format table   (default) Human-readable table with disruption status
    --format json    Machine-readable JSON array
"""
import argparse
import itertools
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SIPPY_BASE = "https://sippy.dptools.openshift.org/api/jobs/runs"
SIPPY_DISRUPTION_URL = "https://sippy.dptools.openshift.org/api/jobs/runs/disruption"

# Sippy ignores offset/page, so the window is walked with a timestamp cursor.
# A single page is not the candidate set — scoring happens after the scan.
PAGE_SIZE = 500
MAX_SCANNED_RUNS = 5000
DISRUPTION_BATCH_SIZE = 100
DEFAULT_SINCE_HOURS = 720
# DisruptionRegression* compares the last 3 days to the previous GA.
ALERT_LOOKBACK_DAYS = "3"
_CONNECTION_SUFFIXES = ("-new-connections", "-reused-connections")

GRAFANA_TO_VARIANT = {
    "platform": "Platform",
    "architectures": "Architecture",
    "topologies": "Topology",
    "networks": "Network",
    "upgrade_type": "Upgrade",
    "featureset": "FeatureSet",
    "ipmode": "NetworkStack",
    "os": "OS",
}

# Chart thresholds and regression context. Not Sippy job filters.
GRAFANA_DISPLAY_ONLY = {
    "percentile", "lookback", "min_disruption_regression",
    "min_disruption_job_list", "min_relevance", "orgId",
    "compare_release", "releaseStatus", "release_status",
}

# Run-level series labels. Same job can be Y on one run and N on the next.
RUN_LEVEL_FILTERS = {"master_nodes_updated"}

# Alert label -> grafana param. The annotation link omits feature_set and os.
ALERT_LABEL_TO_GRAFANA = {
    "platform": "platform",
    "backend": "backend",
    "upgrade_type": "upgrade_type",
    "master_nodes_updated": "master_nodes_updated",
    "architecture": "architectures",
    "topology": "topologies",
    "network": "networks",
    "release": "releases",
    "delta": "percentile",
    "feature_set": "featureset",
    "os": "os",
    "compare_release": "compare_release",
}

_LABEL_LINE = re.compile(
    r"^(?:[\s\-*•·]+)?([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$"
)


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
    return _normalize_grafana_keys(result)


def _normalize_grafana_keys(result):
    """Collapse alert-style names onto the dashboard var names."""
    alias = result.pop("feature_set", None)
    if alias and not result.get("featureset"):
        result["featureset"] = alias
    return result


def parse_alert_labels(text):
    """Pull `key: value` labels and an optional `link:` annotation out of alert text."""
    labels = {}
    link = None
    for line in (text or "").splitlines():
        match = _LABEL_LINE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if not value:
            continue
        if key.lower() == "link" and value.startswith("http"):
            link = value
            continue
        labels[key] = value
    return labels, link


def _overlay_alert_labels(params, labels):
    """Fill grafana params the link left empty. A value already on the link wins."""
    for alert_key, gkey in ALERT_LABEL_TO_GRAFANA.items():
        value = (labels.get(alert_key) or "").strip()
        if not value:
            continue
        existing = params.get(gkey)
        if existing is None or str(existing).strip() == "":
            params[gkey] = value
    return params


def grafana_params_from_inputs(grafana_url=None, alert_text=None):
    """Build the shared filter set from a dashboard URL, alert text, or both.

    An explicit URL is the base. Otherwise a `link:` annotation in the alert is
    the base. Alert labels fill keys that base omitted (`feature_set`, `os`,
    and any other series label the link does not set). With neither URL nor
    link, the window is the 3-day regression lookback.
    """
    labels, link = parse_alert_labels(alert_text) if alert_text else ({}, None)
    if grafana_url:
        params = parse_grafana_url(grafana_url)
    elif link:
        params = parse_grafana_url(link)
    elif alert_text:
        params = {"_dashboard_name": "(alert)", "lookback": ALERT_LOOKBACK_DAYS}
    else:
        return {}
    if labels:
        _overlay_alert_labels(params, labels)
    return params


def parse_backend(backend_value):
    """Parse backend name into base name and connection type.

    Examples:
        host-to-host-new-connections -> (host-to-host, new)
        cache-kube-api-reused-connections -> (cache-kube-api, reused)
        oauth-api -> (oauth-api, None)
    """
    for suffix, conn in (("-new-connections", "new"), ("-reused-connections", "reused")):
        if backend_value.endswith(suffix):
            return backend_value[: -len(suffix)], conn
    return backend_value, None


def split_backends(value):
    """Split a comma-joined backend list into exact selector strings."""
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def expand_backend_selectors(selectors):
    """Return the exact backend names a selector or list of selectors scores.

    A name that already ends in -new-connections or -reused-connections matches
    only itself. A bare base name matches only those two connection variants.
    Derived probes (localhost, http1/http2, service-network, internal-lb) and
    cache-* backends match only when their exact name was requested.
    """
    if isinstance(selectors, str):
        selectors = [selectors]
    names = set()
    for selector in selectors or []:
        if not selector:
            continue
        if selector.endswith(_CONNECTION_SUFFIXES):
            names.add(selector)
        else:
            for suffix in _CONNECTION_SUFFIXES:
                names.add(selector + suffix)
    return names


def selector_bases(selectors):
    """Base names implied by selectors, for disruption test-failure names.

    Failed tests record `disruption/kube-api`, not the full connection backend.
    """
    if isinstance(selectors, str):
        selectors = [selectors]
    bases = set()
    for selector in selectors or []:
        if not selector:
            continue
        base, _conn = parse_backend(selector)
        bases.add(base)
    return bases


def _is_all_sentinel(value):
    """True when a Grafana value means 'all', not a Sippy variant.

    `All` and `$__all` match zero Sippy rows (there is no FeatureSet:All).
    A list that includes either sentinel is also unfiltered.
    """
    parts = [part.strip() for part in str(value).split(",") if part.strip()]
    if not parts:
        return False
    return any(part == "$__all" or part.lower() == "all" for part in parts)


def concrete_variant_values(raw):
    """Return concrete variant values, or None when the field should not be filtered."""
    if raw is None or str(raw).strip() == "":
        return None
    if _is_all_sentinel(raw):
        return None
    parts = [part.strip() for part in str(raw).split(",") if part.strip()]
    return parts or None


def resolve_window_start(since_hours, lookback_days, now=None):
    """Choose the start of the Sippy `timestamp >` window.

    An explicit --since-hours is a rolling hour count and wins over the
    dashboard. Otherwise var-lookback=N is N calendar days: UTC midnight of
    `now` minus N days, so lookback 7 on 2026-10-05 includes 2026-09-28.
    With neither, the window is the last DEFAULT_SINCE_HOURS hours.
    """
    now = now or datetime.now(timezone.utc)
    if since_hours is not None:
        return now - timedelta(hours=float(since_hours))
    if lookback_days is not None and str(lookback_days).strip() != "":
        try:
            days = int(float(lookback_days))
        except (TypeError, ValueError):
            days = None
        if days is not None and days >= 0:
            midnight = now.astimezone(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0)
            return midnight - timedelta(days=days)
    return now - timedelta(hours=DEFAULT_SINCE_HOURS)


def _parse_timestamp(value):
    """Parse a Sippy `timestamp` value to a timezone-aware UTC datetime.

    Accepts an RFC 3339 string (e.g. "2026-08-14T00:01:05Z") or a numeric
    epoch-milliseconds value. Booleans are not treated as numeric and fall
    through to the sentinel. Any UTC offset in a string is normalized to UTC,
    and a string carrying no timezone is interpreted as UTC, so the returned
    datetime is always UTC. Anything else — None, empty, unparseable, or a
    non-finite or out-of-range numeric (infinity, NaN, or a magnitude too large
    for the platform) — returns the epoch (1970-01-01 UTC) as a safe sentinel so
    the dedup arithmetic and sorting below keep working instead of raising.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _rfc3339(dt):
    """Format a timezone-aware datetime as RFC 3339 UTC for Sippy filters."""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_sippy_filter(variants, since, until=None):
    """Build Sippy filter dict from variant key-value pairs.

    `since` and `until`, when set, are datetimes. Sippy's `timestamp` column
    is a timestamptz, so they are formatted to RFC 3339 UTC strings here.
    `until` is an exclusive cursor (`timestamp <`) used to page older runs.
    """
    items = []
    for key, value in variants.items():
        items.append(
            {"columnField": "variants", "operatorValue": "has entry", "value": "%s:%s" % (key, value)}
        )
    if since is not None:
        items.append(
            {"columnField": "timestamp", "operatorValue": ">", "value": _rfc3339(since)}
        )
    if until is not None:
        items.append(
            {"columnField": "timestamp", "operatorValue": "<", "value": _rfc3339(until)}
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


def fetch_runs_in_window(release, variants, since, page_size=PAGE_SIZE, max_runs=MAX_SCANNED_RUNS):
    """Page Sippy newest-first until the window start or a short page.

    Sippy ignores offset and page. The next page is `timestamp <` the oldest
    row of the previous page. Rows are deduped by prow_id. Returns
    (rows, truncated).
    """
    seen = set()
    rows = []
    until = None
    truncated = False
    while True:
        remaining = max_runs - len(rows)
        if remaining <= 0:
            truncated = True
            break
        request_limit = min(page_size, remaining)
        filter_dict = build_sippy_filter(variants, since, until)
        batch = fetch_runs(release, filter_dict, request_limit)
        if not batch:
            break
        oldest = None
        for row in batch:
            ts = _parse_timestamp(row.get("timestamp", ""))
            if oldest is None or ts < oldest:
                oldest = ts
            pid = str(row.get("prow_id", ""))
            if pid and pid not in seen:
                seen.add(pid)
                rows.append(row)
                if len(rows) >= max_runs:
                    truncated = True
                    break
        if truncated or len(batch) < request_limit:
            break
        if oldest is None or oldest <= since:
            break
        if until is not None and oldest >= until:
            break
        until = oldest
    return rows, truncated


def collect_runs(release, variants, since, max_runs):
    """Fetch every matching run in the window, across multi-value variant combos.

    Multi-value variants are queried separately (Sippy matches one value per
    filter), then merged, deduped, and capped at max_runs newest-first.
    """
    multi_keys = [(key, value.split(",")) for key, value in variants.items() if "," in value]
    if not multi_keys:
        return fetch_runs_in_window(release, variants, since, max_runs=max_runs)

    keys = [key for key, _values in multi_keys]
    value_lists = [values for _key, values in multi_keys]
    variant_combos = [dict(zip(keys, combo)) for combo in itertools.product(*value_lists)]
    max_combos = 20
    if len(variant_combos) > max_combos:
        print("Error: %d variant combinations exceeds limit of %d" % (
            len(variant_combos), max_combos), file=sys.stderr)
        sys.exit(1)

    seen = set()
    rows = []
    truncated = False
    for combo in variant_combos:
        query_variants = dict(variants, **combo)
        batch, batch_truncated = fetch_runs_in_window(
            release, query_variants, since, max_runs=max_runs)
        truncated = truncated or batch_truncated
        for row in batch:
            pid = str(row.get("prow_id", ""))
            if pid and pid not in seen:
                seen.add(pid)
                rows.append(row)
    rows.sort(key=lambda row: _parse_timestamp(row.get("timestamp", "")), reverse=True)
    if len(rows) > max_runs:
        rows = rows[:max_runs]
        truncated = True
    return rows, truncated


def _fetch_disruption_batch(prow_ids):
    """Query one batch of prow IDs. Returns the raw rows list, or None on failure.

    The backend_name query param is a substring filter and is intentionally
    not sent: `kube-api` also returns localhost, http, and cache derivatives.
    Callers keep only the exact selected names.
    """
    params = {"job_run_names": ",".join(str(pid) for pid in prow_ids)}
    url = "%s?%s" % (SIPPY_DISRUPTION_URL, urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print("Warning: could not fetch disruption data: %s" % e, file=sys.stderr)
        return None
    try:
        data = json.loads(body)
    except (ValueError, json.JSONDecodeError):
        print("Warning: invalid JSON from disruption API", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print("Warning: unexpected response type from disruption API", file=sys.stderr)
        return None
    return data.get("rows") or []


def fetch_disruption_data(prow_ids):
    """Query Sippy disruption endpoint for per-run disruption seconds.

    Returns dict keyed by prow_id -> list of {backend_name, disruption_seconds}.
    IDs are requested in batches. Every backend the API returns is kept;
    exact-name filtering happens in filter_disruption_data.
    """
    if not prow_ids:
        return {}
    lookup = {}
    ids = [str(pid) for pid in prow_ids]
    for start in range(0, len(ids), DISRUPTION_BATCH_SIZE):
        rows = _fetch_disruption_batch(ids[start:start + DISRUPTION_BATCH_SIZE])
        if rows is None:
            continue
        for row in rows:
            pid = str(row.get("job_run_name", ""))
            if pid not in lookup:
                lookup[pid] = []
            entry = {
                "backend_name": row.get("backend_name", ""),
                "disruption_seconds": row.get("disruption_seconds", 0),
            }
            if "master_nodes_updated" in row:
                entry["master_nodes_updated"] = row.get("master_nodes_updated") or ""
            lookup[pid].append(entry)
    return lookup


def disruption_api_has_master_field(disruption_data):
    """True when any returned row included master_nodes_updated."""
    for entries in (disruption_data or {}).values():
        for entry in entries or []:
            if "master_nodes_updated" in entry:
                return True
    return False


def master_nodes_filter_value(raw):
    """Return Y or N when runs should be filtered, else None.

    All / $__all / empty means the series is not limited to one value.
    """
    if raw is None or str(raw).strip() == "":
        return None
    if _is_all_sentinel(raw):
        print("Warning: master_nodes_updated=%s is an All sentinel, not applied as a run filter" % (
            raw), file=sys.stderr)
        return None
    value = str(raw).strip().upper()
    if value in ("Y", "N"):
        return value
    print("Warning: master_nodes_updated '%s' is not Y or N; not applied as a run filter" % (
        raw), file=sys.stderr)
    return None


def apply_master_nodes_filter(rows, disruption_data, wanted, field_present):
    """Keep runs whose selected-backend rows match wanted (Y or N).

    wanted is None when no filter applies. When a filter is set and the API
    response did not include the field, return no rows rather than the
    unfiltered set. A run with no selected-backend row cannot be classified
    and is dropped.
    """
    if wanted is None:
        return rows
    if not field_present:
        print(
            "Warning: master_nodes_updated=%s was requested, but the disruption API "
            "response did not include that field. Those runs were not kept." % wanted,
            file=sys.stderr,
        )
        return []
    kept = []
    for row in rows:
        pid = str(row.get("prow_id", ""))
        matched = False
        for entry in disruption_data.get(pid) or []:
            value = entry.get("master_nodes_updated")
            if value is None:
                continue
            if str(value).strip().upper() == wanted:
                matched = True
                break
        if matched:
            kept.append(row)
    print("Kept %d of %d runs with master_nodes_updated=%s." % (
        len(kept), len(rows), wanted), file=sys.stderr)
    return kept


def filter_disruption_data(disruption_data, selectors):
    """Keep only entries whose backend_name is an exact selected name."""
    allowed = expand_backend_selectors(selectors)
    filtered = {}
    for pid, entries in (disruption_data or {}).items():
        kept = [entry for entry in entries if entry.get("backend_name") in allowed]
        if kept:
            filtered[pid] = kept
    return filtered


def disruption_peak(disruption_entries, selectors):
    """Return (seconds, backend_name) for the highest exact selected match.

    seconds is None when there is no disruption data for the run. It is 0,
    with backend_name None, when data exists but no selected backend matches.
    """
    allowed = expand_backend_selectors(selectors)
    if not disruption_entries:
        return None, None
    best_secs = None
    best_name = None
    for entry in disruption_entries:
        if entry.get("backend_name") not in allowed:
            continue
        secs = entry.get("disruption_seconds", 0)
        if best_secs is None or secs > best_secs:
            best_secs = secs
            best_name = entry.get("backend_name")
    if best_secs is None:
        return 0, None
    return best_secs, best_name


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
            "timestamp": _parse_timestamp(row.get("timestamp", "")),
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
    # from a job that has disrupted runs in the pool but is not in that set is not useful.
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


def format_timestamp(ts):
    """Reformat an RFC 3339 timestamp to a shorter display form (YYYY-MM-DD HH:MM).

    A missing timestamp — None or an empty string — returns an empty string
    rather than a 1970 epoch date, since callers pass "" when the timestamp is
    absent. A numeric 0 is a valid epoch-ms value and formats normally.
    """
    if ts is None or ts == "":
        return ""
    return _parse_timestamp(ts).strftime("%Y-%m-%d %H:%M")


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
        if val and not _is_all_sentinel(val):
            filters.append("%s=%s" % (variant_key, val))
    masters = grafana_params.get("master_nodes_updated")
    if masters and not _is_all_sentinel(masters):
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
                             "lookback is %s days." % ALERT_LOOKBACK_DAYS)

    parser.add_argument("--release", help="OpenShift release (e.g., 5.0)")
    parser.add_argument("--platform", help="Platform (e.g., gcp, aws, azure)")
    parser.add_argument("--backend", help="Disruption backend (e.g., host-to-host-new-connections)")
    parser.add_argument("--upgrade-type", help="Upgrade type (e.g., micro, minor, none)")
    parser.add_argument("--architecture", help="Architecture (e.g., amd64, arm64)")
    parser.add_argument("--topology", help="Topology (e.g., ha, single)")
    parser.add_argument("--network", help="Network (e.g., ovn, sdn)")

    parser.add_argument("--since-hours", type=float, default=None,
                        help="Lookback window in hours. Overrides var-lookback. "
                             "Default when the URL has no lookback: %d (30 days)." % DEFAULT_SINCE_HOURS)
    parser.add_argument("--limit", type=int, default=None,
                        help="Max runs to scan (default: the full window, capped at %d)" % MAX_SCANNED_RUNS)
    parser.add_argument("--format", choices=["table", "json"], default="table",
                        help="Output format (default: table)")
    parser.add_argument("--disruption-only", action="store_true",
                        help="Only show runs with disruption > 0 for the selected backends")
    parser.add_argument("--auto-select", type=int, default=None, metavar="N",
                        help="Auto-select N representative runs for diverse coverage")
    args = parser.parse_args(argv)

    grafana_params = grafana_params_from_inputs(args.grafana_url, args.alert_text)

    release = args.release or grafana_params.get("releases")
    backend = args.backend or grafana_params.get("backend")

    if not release:
        print("Error: --release is required (or provide --grafana-url with var-releases, "
              "or --alert-text with a release label)", file=sys.stderr)
        sys.exit(1)
    if not backend:
        print("Error: --backend is required (or provide --grafana-url with var-backend, "
              "or --alert-text with a backend label)", file=sys.stderr)
        sys.exit(1)
    if "," in release:
        print("Error: multiple releases not supported (got '%s'). Use a single release." % release, file=sys.stderr)
        sys.exit(1)

    selectors = split_backends(backend)
    if not selectors:
        print("Error: --backend is required (or provide --grafana-url with var-backend, "
              "or --alert-text with a backend label)", file=sys.stderr)
        sys.exit(1)

    cli_overrides = {
        "platform": args.platform,
        "upgrade_type": args.upgrade_type,
        "architectures": args.architecture,
        "topologies": args.topology,
        "networks": args.network,
    }

    variants = {}
    for gkey, variant_key in GRAFANA_TO_VARIANT.items():
        raw = cli_overrides.get(gkey) or grafana_params.get(gkey)
        if raw and _is_all_sentinel(raw):
            print("Warning: Grafana parameter '%s=%s' is an All sentinel, not applied as a Sippy filter" % (
                gkey, raw), file=sys.stderr)
            continue
        values = concrete_variant_values(raw)
        if values:
            variants[variant_key] = ",".join(values)

    known_keys = (
        set(GRAFANA_TO_VARIANT) | GRAFANA_DISPLAY_ONLY | RUN_LEVEL_FILTERS
        | {"releases", "backend", "_dashboard_name"}
    )
    for gkey in grafana_params:
        if gkey not in known_keys:
            print("Warning: Grafana parameter '%s' not mapped to a Sippy filter, ignoring" % gkey, file=sys.stderr)

    lookback = grafana_params.get("lookback")
    if lookback and args.since_hours is None:
        try:
            int(float(lookback))
        except (TypeError, ValueError):
            print("Warning: var-lookback '%s' is not a number of days; using %d hours" % (
                lookback, DEFAULT_SINCE_HOURS), file=sys.stderr)
            lookback = None
    since = resolve_window_start(args.since_hours, lookback if args.since_hours is None else None)

    max_runs = args.limit if args.limit is not None else MAX_SCANNED_RUNS
    rows, truncated = collect_runs(release, variants, since, max_runs)

    if not rows:
        filters_desc = ", ".join("%s:%s" % (k, v) for k, v in variants.items())
        print("No runs found for release=%s with variants [%s] since %s." % (
            release, filters_desc, _rfc3339(since)), file=sys.stderr)
        print("Try widening --since-hours or relaxing filters.", file=sys.stderr)
        sys.exit(0)

    scanned_count = len(rows)
    prow_ids = [str(r["prow_id"]) for r in rows if r.get("prow_id")]
    raw_disruption = fetch_disruption_data(prow_ids)
    master_wanted = master_nodes_filter_value(grafana_params.get("master_nodes_updated"))
    field_present = disruption_api_has_master_field(raw_disruption)
    disruption_data = filter_disruption_data(raw_disruption, selectors)
    if master_wanted:
        rows = apply_master_nodes_filter(rows, disruption_data, master_wanted, field_present)
        if not rows:
            print("No runs matched master_nodes_updated=%s in %d scanned runs." % (
                master_wanted, scanned_count), file=sys.stderr)
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
        _parse_timestamp(row.get("timestamp", "")),
    ), reverse=True)

    if args.disruption_only and not display:
        print("No runs with disruption > 0 for %s in %d runs since %s." % (
            _backend_label(selectors), scanned_count, _rfc3339(since)), file=sys.stderr)
        print("Re-run without --disruption-only to see all runs.", file=sys.stderr)
        sys.exit(0)

    selected_indices = None
    if selected_ids:
        selected_indices = [i for i, row in enumerate(display) if str(row.get("prow_id", "")) in selected_ids]

    if args.format == "json":
        print("Scanned %d runs since %s." % (scanned_count, _rfc3339(since)), file=sys.stderr)
        if truncated:
            print("Warning: stopped after %d runs; the lookback window was not fully scanned." % scanned_count,
                  file=sys.stderr)
        print_json(display, selectors, disruption_data, selected_indices)
    else:
        print_table(display, grafana_params, selectors, disruption_data, selected_indices,
                    scanned_count=scanned_count, window_start=since, truncated=truncated)


if __name__ == "__main__":
    main()
