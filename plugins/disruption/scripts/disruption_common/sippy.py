"""Fetch job runs and per-run disruption seconds from the public Sippy API.

Sippy ignores offset/page, so a window is walked newest-first with a
timestamp cursor. Disruption seconds come from BigQuery through Sippy's
disruption endpoint and lag job completion by up to about four hours.

The disruption endpoint allows 25 requests per rolling hour, shared by every
client, and answers HTTP 429 beyond that without a Retry-After header. A
rejected request does not count against the limit, and a repeated URL is
served from a one-hour response cache without counting.
"""
import email.utils
import http.client
import itertools
import json
import numbers
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .state import write_json_atomic

SIPPY_BASE = "https://sippy.dptools.openshift.org/api/jobs/runs"
SIPPY_DISRUPTION_URL = "https://sippy.dptools.openshift.org/api/jobs/runs/disruption"

PAGE_SIZE = 500
# 500 comma-separated build IDs make a URL of about 10 KB, which Sippy accepts
# (checked 2026-11-10). Larger batches spend fewer of the 25 hourly requests.
DISRUPTION_BATCH_SIZE = 500
MAX_VARIANT_COMBOS = 20
# Total seconds one disruption fetch may sleep on HTTP 429, across all batches.
RATE_LIMIT_MAX_WAIT = 90
RATE_LIMIT_FIRST_DELAY = 15
# Request too large: split the batch in half and try each half.
_SPLIT_STATUSES = (413, 414, 431)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class SippyError(RuntimeError):
    """Sippy could not be reached or returned something unusable.

    `status` is the HTTP status when Sippy answered with an error, and
    `retry_after` the delay in seconds its headers asked for, if any.
    """

    def __init__(self, message, status=None, retry_after=None):
        """Keep the HTTP status and Retry-After seconds, when Sippy sent them."""
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def parse_timestamp(value):
    """Parse a Sippy `timestamp` value to a timezone-aware UTC datetime.

    Accepts an RFC 3339 string (e.g. "2026-08-14T00:01:05Z") or a numeric
    epoch-milliseconds value. Booleans are not treated as numeric. A string
    with no timezone is read as UTC. Anything unparseable returns the epoch
    as a sentinel so sorting and arithmetic keep working. A trailing `Z` is
    rewritten to `+00:00` because fromisoformat only accepts it from 3.11.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return _EPOCH
    if isinstance(value, str) and value:
        try:
            text = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return _EPOCH
    return _EPOCH


def rfc3339(dt):
    """Format a timezone-aware datetime as RFC 3339 UTC for Sippy filters."""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_sippy_filter(variants, since, until=None):
    """Build a Sippy filter dict from variant key-value pairs.

    `since` and `until`, when set, are datetimes. `until` is an exclusive
    cursor (`timestamp <`) used to page older runs.
    """
    items = []
    for key, value in variants.items():
        items.append(
            {"columnField": "variants", "operatorValue": "has entry", "value": "%s:%s" % (key, value)}
        )
    if since is not None:
        items.append({"columnField": "timestamp", "operatorValue": ">", "value": rfc3339(since)})
    if until is not None:
        items.append({"columnField": "timestamp", "operatorValue": "<", "value": rfc3339(until)})
    return {"items": items, "linkOperator": "and"}


def _retry_after_seconds(headers, now=None):
    """Seconds to wait from Retry-After or a rate-limit reset header, or None.

    Retry-After may be seconds or an HTTP date. A reset header above 1e9 is
    read as an epoch time, anything smaller as a delay. Sippy sends neither
    today; they are honored in case it starts to.
    """
    if headers is None:
        return None
    now = time.time() if now is None else now
    value = (headers.get("Retry-After") or "").strip()
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            pass
        try:
            when = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            when = None
        if when is not None:
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return max(0.0, when.timestamp() - now)
    for name in ("RateLimit-Reset", "X-RateLimit-Reset"):
        try:
            seconds = float(headers.get(name))
        except (TypeError, ValueError):
            continue
        if seconds > 1e9:
            seconds -= now
        return max(0.0, seconds)
    return None


def _get_json(url, what):
    """Fetch and decode JSON from url. Raises SippyError naming what was being fetched."""
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace").strip()
        except (OSError, ValueError):
            detail = "<unable to read response body>"
        raise SippyError("HTTP %d from %s: %s" % (e.code, what, detail), status=e.code,
                         retry_after=_retry_after_seconds(e.headers)) from e
    except urllib.error.URLError as e:
        raise SippyError("failed to connect to %s: %s" % (what, e.reason)) from e
    except (OSError, http.client.HTTPException) as e:
        # Read timeouts and truncated bodies, which urlopen does not wrap in URLError.
        raise SippyError("failed to read from %s: %s" % (what, str(e) or type(e).__name__)) from e
    except UnicodeDecodeError as e:
        raise SippyError("response from %s is not UTF-8" % what) from e
    try:
        data = json.loads(body)
    except ValueError as e:
        raise SippyError("invalid JSON from %s" % what) from e
    if not isinstance(data, dict):
        raise SippyError("unexpected response type from %s" % what)
    return data


def _rows(data, what):
    """The `rows` list of a Sippy reply, keeping only object rows."""
    rows = data.get("rows")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise SippyError("unexpected rows type from %s" % what)
    return [row for row in rows if isinstance(row, dict)]


def fetch_runs(release, filter_dict, limit):
    """Query Sippy /api/jobs/runs newest-first and return rows."""
    params = {
        "release": release,
        "filter": json.dumps(filter_dict),
        "limit": str(limit),
        "sortField": "timestamp",
        "sort": "desc",
    }
    url = "%s?%s" % (SIPPY_BASE, urllib.parse.urlencode(params))
    return _rows(_get_json(url, "Sippy runs API"), "Sippy runs API")


def _just_before(timestamp):
    """A timestamp strictly earlier than `timestamp`, still after any older instant."""
    return timestamp - timedelta(microseconds=1)


def _room(rows, max_runs):
    """How many more rows fit under max_runs, or None when there is no limit."""
    return None if max_runs is None else max_runs - len(rows)


def _take_unseen(batch, seen, rows, max_runs):
    """Append unseen rows. Returns (oldest timestamp, truncated)."""
    oldest = None
    truncated = False
    for row in batch:
        ts = parse_timestamp(row.get("timestamp", ""))
        if oldest is None or ts < oldest:
            oldest = ts
        if max_runs is not None and len(rows) >= max_runs:
            truncated = True
            break
        pid = str(row.get("prow_id", ""))
        if pid and pid not in seen:
            seen.add(pid)
            rows.append(row)
            if max_runs is not None and len(rows) >= max_runs:
                truncated = True
                break
    return oldest, truncated


def _fetch_timestamp_ties(release, variants, since, oldest, upper, max_runs, seen, rows, page_size):
    """Fetch runs that share `oldest` and did not fit on the page that ended there.

    Sippy has no offset, so `timestamp < oldest` alone would drop the rest of
    that tie. This asks for `oldest` inclusive up to the next newer timestamp.
    With a run budget, one request uses the remaining budget. Without one, the
    limit doubles until Sippy returns a short page (the whole tie). A full page
    with no unseen runs means Sippy will not return more, so the result is
    reported as truncated. Returns True when the scan is truncated.
    """
    lower = _just_before(oldest)
    if since is not None and lower < since:
        lower = since
    tie_filter = build_sippy_filter(variants, lower, upper)
    room = _room(rows, max_runs)
    if room is not None:
        if room <= 0:
            return True
        batch = fetch_runs(release, tie_filter, room)
        if not batch:
            return False
        _oldest, truncated = _take_unseen(batch, seen, rows, max_runs)
        return truncated

    limit = page_size
    while True:
        batch = fetch_runs(release, tie_filter, limit)
        count_before = len(rows)
        _take_unseen(batch, seen, rows, None)
        if len(batch) < limit:
            return False
        if len(rows) == count_before:
            return True
        limit *= 2


def fetch_runs_in_window(release, variants, since, page_size=PAGE_SIZE, max_runs=None, progress=None):
    """Page Sippy newest-first until the window start or a short page.

    max_runs=None scans the whole window. `progress`, when set, is called
    with (runs so far, oldest timestamp so far) after each page. Rows are
    deduped by prow_id. Returns (rows, truncated).
    """
    seen = set()
    rows = []
    until = None
    truncated = False
    while True:
        room = _room(rows, max_runs)
        if room is not None and room <= 0:
            truncated = True
            break
        request_limit = page_size if room is None else min(page_size, room)
        batch = fetch_runs(release, build_sippy_filter(variants, since, until), request_limit)
        if not batch:
            break
        oldest, truncated = _take_unseen(batch, seen, rows, max_runs)
        if progress:
            progress(len(rows), oldest)
        if truncated or len(batch) < request_limit:
            break
        if oldest is None or oldest <= since:
            break
        if until is not None and oldest >= until:
            break
        newer = [ts for ts in (parse_timestamp(row.get("timestamp", "")) for row in batch) if ts > oldest]
        upper = min(newer) if newer else until
        if _fetch_timestamp_ties(release, variants, since, oldest, upper, max_runs, seen, rows, page_size):
            truncated = True
            break
        until = oldest
    return rows, truncated


def collect_runs(release, variants, since, max_runs=None, progress=None):
    """Fetch every matching run in the window, across multi-value variant combos.

    Sippy matches one value per filter, so multi-value variants are queried
    separately, merged, deduped, and sorted newest-first.
    """
    multi_keys = [(key, value.split(",")) for key, value in variants.items() if "," in value]
    if not multi_keys:
        return fetch_runs_in_window(release, variants, since, max_runs=max_runs, progress=progress)

    keys = [key for key, _values in multi_keys]
    combos = [dict(zip(keys, combo)) for combo in itertools.product(*[v for _k, v in multi_keys])]
    if len(combos) > MAX_VARIANT_COMBOS:
        raise SippyError("%d variant combinations exceeds limit of %d" % (len(combos), MAX_VARIANT_COMBOS))

    seen = set()
    rows = []
    truncated = False
    failures = []
    for combo in combos:
        try:
            batch, batch_truncated = fetch_runs_in_window(
                release, dict(variants, **combo), since, max_runs=max_runs, progress=progress)
        except SippyError as e:
            failures.append("%s: %s" % (", ".join("%s=%s" % kv for kv in combo.items()), e))
            continue
        truncated = truncated or batch_truncated
        for row in batch:
            pid = str(row.get("prow_id", ""))
            if pid and pid not in seen:
                seen.add(pid)
                rows.append(row)
    if failures:
        # Partial results would skew the series toward the combinations that worked.
        raise SippyError("%d of %d variant combinations failed: %s" % (
            len(failures), len(combos), "; ".join(failures)))
    rows.sort(key=lambda row: parse_timestamp(row.get("timestamp", "")), reverse=True)
    if max_runs is not None and len(rows) > max_runs:
        rows = rows[:max_runs]
        truncated = True
    return rows, truncated


def _fetch_disruption_batch(prow_ids):
    """Query one batch of prow IDs. Returns the raw rows list; raises SippyError.

    The backend_name query param is a substring filter and is intentionally
    not sent: `kube-api` also returns localhost, http, and cache derivatives.
    Callers keep only the exact selected names. Commas are left unescaped to
    keep the URL short.
    """
    params = {"job_run_names": ",".join(str(pid) for pid in prow_ids)}
    url = "%s?%s" % (SIPPY_DISRUPTION_URL, urllib.parse.urlencode(params, safe=","))
    return _rows(_get_json(url, "Sippy disruption API"), "Sippy disruption API")


class _WaitBudget:
    """Seconds left to sleep on rate limits during one disruption fetch."""

    def __init__(self, seconds, sleep):
        """Track the seconds left to spend waiting on rate limits."""
        self.remaining = max(0.0, float(seconds))
        self.sleep = sleep


def _rate_limit_delay(error, attempt, budget):
    """Seconds to sleep before retrying a 429, or None when the budget cannot cover it.

    A delay the server asked for must fit whole; sleeping part of it would
    only earn another 429. A computed backoff is trimmed to what is left.
    """
    if error.retry_after is not None:
        delay = max(1.0, error.retry_after)
        return delay if delay <= budget.remaining else None
    delay = min(RATE_LIMIT_FIRST_DELAY * 2 ** attempt, budget.remaining)
    return delay if delay >= 1 else None


def _fetch_batch_rows(prow_ids, budget, failed):
    """Rows for one batch, retrying HTTP 429 within the budget.

    A request too large for the server is split in half. IDs that still
    fail are appended to `failed`, and the rows that did arrive are returned.
    """
    attempt = 0
    while True:
        try:
            return _fetch_disruption_batch(prow_ids)
        except SippyError as e:
            if e.status in _SPLIT_STATUSES and len(prow_ids) > 1:
                half = len(prow_ids) // 2
                return (_fetch_batch_rows(prow_ids[:half], budget, failed)
                        + _fetch_batch_rows(prow_ids[half:], budget, failed))
            delay = _rate_limit_delay(e, attempt, budget) if e.status == 429 else None
            if delay is None:
                print("Warning: could not fetch disruption data for %d run(s): %s" % (len(prow_ids), e),
                      file=sys.stderr)
                failed.extend(prow_ids)
                return []
            print("  Sippy disruption API rate limit (HTTP 429); retrying in %ds (%ds of wait budget left)"
                  % (delay, budget.remaining), file=sys.stderr)
            budget.sleep(delay)
            budget.remaining -= delay
            attempt += 1


def _seconds(value):
    """Disruption seconds as a number, or None when the value is missing or not numeric."""
    if isinstance(value, bool):
        return None
    if isinstance(value, numbers.Real):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _entry(row):
    """One backend's disruption for a run, or None when its seconds are not usable."""
    seconds = _seconds(row.get("disruption_seconds"))
    if seconds is None:
        return None
    entry = {
        "backend_name": row.get("backend_name", ""),
        "disruption_seconds": seconds,
        "release_tag": row.get("release_tag") or "",
        "job_name": row.get("job_name") or "",
    }
    if "master_nodes_updated" in row:
        entry["master_nodes_updated"] = row.get("master_nodes_updated") or ""
    return entry


def _load_cache(path):
    """The disruption cache at path, or {} when it is missing or unreadable."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        print("Warning: ignoring unreadable disruption cache %s" % path, file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(path, cache):
    """Write the cache atomically. Returns False, after a warning, when it cannot."""
    try:
        write_json_atomic(path, cache)
    except OSError as e:
        print("Warning: could not write disruption cache %s: %s" % (path, e), file=sys.stderr)
        return False
    return True


def fetch_disruption_data_with_failures(prow_ids, cache_path=None, progress=None,
                                        max_wait=RATE_LIMIT_MAX_WAIT, sleep=time.sleep):
    """Like fetch_disruption_data, but also return the IDs the API failed for.

    Returns (lookup, failed). `failed` lists the prow IDs whose batch still
    failed after retries (rate limit, HTTP or connection error); they are
    not in `lookup`, but they are not known to lack data either. An HTTP 429
    is retried with backoff, honoring Retry-After or a rate-limit reset
    header when present, while the total sleep stays within `max_wait`
    seconds. `sleep` is injectable for tests. With `cache_path`, the cache is
    rewritten after every batch that returned rows, so a run that stops
    early or loses batches keeps what it fetched and a rerun asks only for
    the rest.
    """
    if not prow_ids:
        return {}, []
    ids = [str(pid) for pid in prow_ids]
    cache = _load_cache(cache_path)
    lookup = {pid: cache[pid] for pid in ids if cache.get(pid)}
    missing = [pid for pid in ids if pid not in lookup]
    budget = _WaitBudget(max_wait, sleep)
    failed = []
    cache_writable = bool(cache_path)
    for start in range(0, len(missing), DISRUPTION_BATCH_SIZE):
        batch = missing[start:start + DISRUPTION_BATCH_SIZE]
        fetched = {}
        for row in _fetch_batch_rows(batch, budget, failed):
            entry = _entry(row)
            if entry is not None:
                fetched.setdefault(str(row.get("job_run_name", "")), []).append(entry)
        wanted = set(batch)
        fetched = {pid: entries for pid, entries in fetched.items() if pid in wanted}
        lookup.update(fetched)
        if cache_writable and fetched:
            cache.update(fetched)
            cache_writable = _save_cache(cache_path, cache)
        if progress:
            progress(len(ids) - len(missing) + min(start + DISRUPTION_BATCH_SIZE, len(missing)), len(ids))
    return lookup, failed


def fetch_disruption_data(prow_ids, cache_path=None, progress=None, max_wait=RATE_LIMIT_MAX_WAIT,
                          sleep=time.sleep, failed=None):
    """Query Sippy for per-run disruption seconds.

    Returns dict prow_id -> list of {backend_name, disruption_seconds,
    release_tag, job_name, [master_nodes_updated]}. Every backend the API
    returns with numeric seconds is kept; exact-name filtering is the
    caller's job. With
    `cache_path`, runs that already have rows are read from and written to
    that JSON file. Runs with no rows are not cached, because BigQuery may
    not have them yet. `progress`, when set, is called with (done, total).
    Runs the API failed for are absent from the result. Pass a list as
    `failed` to have their IDs appended, so they can be told apart from runs
    with no data.
    """
    lookup, lost = fetch_disruption_data_with_failures(
        prow_ids, cache_path=cache_path, progress=progress, max_wait=max_wait, sleep=sleep)
    if failed is not None:
        failed.extend(lost)
    return lookup
