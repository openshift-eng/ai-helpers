#!/usr/bin/env python3
"""Collect a frozen, bounded Sippy payload/job snapshot. Standard library only."""

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SIPPY = "https://sippy.dptools.openshift.org"
UTC = dt.timezone.utc
ROLES = {"Blocking": "BLOCKING", "Informing": "INFORMING"}
OUTCOMES = {"Succeeded": "SUCCEEDED", "Failed": "FAILED", "Aborted": "ABORTED", "Running": "RUNNING"}
PROW_PATH = re.compile(
    r"^/view/gs/(?P<bucket>test-platform-results(?:-public)?)/"
    r"(?P<path>(?:logs/[^/]+|pr-logs/pull/(?:batch/[^/]+|[^/]+/[^/]+/\d+/[^/]+))/"
    r"(?P<id>\d{10,}))/?$"
)


class CollectionError(Exception):
    """A visible collection or validation error."""


def now():
    return dt.datetime.now(UTC)


def stamp(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_utc(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be ISO 8601 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise argparse.ArgumentTypeError("must specify UTC with Z or +00:00")
    return parsed.astimezone(UTC)


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def rate(value):
    value = float(value)
    if value < 0 or value > 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return value


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + "\n")


def filter_value(items):
    return json.dumps({"items": items, "linkOperator": "and"}, separators=(",", ":"))


def endpoint(path, **params):
    clean = {key: value for key, value in params.items() if value is not None}
    return SIPPY + path + "?" + urllib.parse.urlencode(clean)


def tag_url(release, architecture, stream, start, end, limit):
    items = [
        {"columnField": "architecture", "operatorValue": "equals", "value": architecture},
        {"columnField": "stream", "operatorValue": "equals", "value": stream},
        {"columnField": "release_time", "operatorValue": ">=", "value": stamp(start)},
        {"columnField": "release_time", "operatorValue": "<=", "value": stamp(end)},
    ]
    return endpoint("/api/releases/tags", release=release, filter=filter_value(items),
                    sortField="release_time", sort="desc", limit=limit)


def jobs_url(release, tag):
    items = [{"columnField": "release_tag", "operatorValue": "equals", "value": tag}]
    # This endpoint returns one array. Do not invent page parameters or apply the UI page size.
    return endpoint("/api/releases/job_runs", release=release, filter=filter_value(items),
                    sortField="kind", sort="asc")


class Client:
    def __init__(self, raw_dir, max_bytes=64 * 1024 * 1024, max_requests=200,
                 timeout=30, retries=3, opener=urllib.request.urlopen):
        self.raw_dir = Path(raw_dir)
        self.max_bytes = max_bytes
        self.max_requests = max_requests
        self.timeout = timeout
        self.retries = retries
        self.opener = opener
        self.bytes = 0
        self.requests = 0
        self.provenance = []

    def get(self, url, label):
        for attempt in range(self.retries + 1):
            if self.requests >= self.max_requests:
                raise CollectionError("request limit reached")
            self.requests += 1
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "payload-informing-analysis/1"})
                with self.opener(request, timeout=self.timeout) as response:
                    body = response.read(self.max_bytes - self.bytes + 1)
                if self.bytes + len(body) > self.max_bytes:
                    raise CollectionError("response byte limit reached")
                self.bytes += len(body)
                path = self.raw_dir / ("%04d-%s.json" % (self.requests, label))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
                record = {"url": url, "retrieved_at": stamp(now()), "bytes": len(body),
                          "sha256": sha256(body), "path": str(path)}
                self.provenance.append(record)
                try:
                    return json.loads(body)
                except (UnicodeError, ValueError) as exc:
                    raise CollectionError("invalid JSON from " + url) from exc
            except urllib.error.HTTPError as exc:
                exc.close()
                if exc.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise CollectionError("HTTP %s from %s" % (exc.code, url)) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt == self.retries:
                    raise CollectionError("request failed for %s: %s" % (url, exc)) from exc
            time.sleep(min(2 ** attempt, 8))
        raise AssertionError("unreachable")


def require_array(value, source):
    if not isinstance(value, list):
        raise CollectionError(source + " must return a JSON array")
    return value


def parse_prow_url(url):
    parsed = urllib.parse.urlsplit(url or "")
    if parsed.scheme != "https" or parsed.netloc != "prow.ci.openshift.org" or parsed.query or parsed.fragment:
        return None, None, None
    match = PROW_PATH.match(parsed.path)
    if not match:
        return None, None, None
    path = match.group("path")
    parts = path.split("/")
    return match.group("id"), parts[-2], match.group("bucket")


def normalize_association(row, payload, population_role):
    raw_id = row.get("name")
    prow_id, provisional_job, bucket = parse_prow_url(row.get("url"))
    if prow_id is None and isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool):
        candidate = str(raw_id)
        prow_id = candidate if candidate.isdecimal() else None
    role = ROLES.get(row.get("kind"), "UNKNOWN")
    outcome = OUTCOMES.get(row.get("state"), "OTHER")
    route = {"from": row.get("upgrades_from") or None, "to": row.get("upgrades_to") or None,
             "upgrade": bool(row.get("upgrade"))}
    return {
        "schema_version": 1,
        "payload_id": str(payload.get("id")),
        "payload_tag": payload.get("release_tag"),
        "release": payload.get("release"),
        "architecture": payload.get("architecture"),
        "stream": payload.get("stream"),
        "population_role": population_role,
        "association_id": str(row.get("id")) if row.get("id") is not None else None,
        "raw_alias": row.get("job_name"),
        "raw_role": row.get("kind"),
        "normalized_role": role,
        "raw_state": row.get("state"),
        "normalized_outcome": outcome,
        "prow_run_id": prow_id,
        "prow_url": row.get("url") or None,
        "prow_bucket": bucket,
        "actual_prow_job": None,
        "provisional_prow_job": provisional_job,
        "identity_state": "PROVISIONAL_URL" if provisional_job else "UNRESOLVED",
        "transition_time": row.get("transition_time") or None,
        "retries": row.get("retries") if isinstance(row.get("retries"), int) else None,
        "upgrade_route": route,
        "labels": row.get("labels") if isinstance(row.get("labels"), list) else [],
        "raw": row,
    }


def payload_record(tag, rows, population_role, inventory_complete=True):
    counts = {"blocking": {}, "informing": {}, "unknown_role": {}}
    for row in rows:
        group = "blocking" if row.get("kind") == "Blocking" else "informing" if row.get("kind") == "Informing" else "unknown_role"
        state = row.get("state") or "<missing>"
        counts[group][state] = counts[group].get(state, 0) + 1
    return {
        "schema_version": 1,
        "id": str(tag.get("id")),
        "tag": tag.get("release_tag"),
        "release": tag.get("release"),
        "architecture": tag.get("architecture"),
        "stream": tag.get("stream"),
        "population_role": population_role,
        "release_time": tag.get("release_time"),
        "phase": tag.get("phase"),
        "forced": bool(tag.get("forced")),
        "previous_release_tag": tag.get("previous_release_tag") or None,
        "kubernetes_version": tag.get("kubernetes_version") or None,
        "current_os_version": tag.get("current_os_version") or None,
        "previous_os_version": tag.get("previous_os_version") or None,
        "outcome_counts": counts,
        "job_row_count": len(rows),
        "inventory_complete": bool(inventory_complete),
        "eligibility": "UNREVIEWED",
        "reason_codes": [],
        "evidence": [],
        "raw": tag,
    }


def prelim_healthy(payload, threshold):
    blockers = payload["outcome_counts"]["blocking"]
    succeeded, failed = blockers.get("Succeeded", 0), blockers.get("Failed", 0)
    terminal = succeeded + failed
    nonterminal = sum(blockers.values()) - terminal
    return (payload["inventory_complete"] and terminal > 0 and nonterminal == 0
            and succeeded / terminal >= threshold and payload.get("phase") not in ("Pending", "Ready"))


def release_names(value):
    if not isinstance(value, dict) or not isinstance(value.get("releases"), list):
        raise CollectionError("/api/releases response lacks releases array")
    return [item for item in value["releases"] if isinstance(item, str) and re.fullmatch(r"\d+\.\d+", item)]


def previous_release(current, names):
    if current not in names:
        raise CollectionError("selected release is absent from /api/releases metadata")
    index = names.index(current)
    if index + 1 >= len(names):
        raise CollectionError("selected release has no verified predecessor")
    return names[index + 1]


def collect_population(client, release, architecture, stream, start, end, limit, role):
    tags = require_array(client.get(tag_url(release, architecture, stream, start, end, limit), role + "-tags"),
                         "/api/releases/tags")
    # Exact post-filtering protects against ignored or changed upstream filter semantics.
    scoped = []
    for tag in tags:
        if (tag.get("release") != release or tag.get("architecture") != architecture
                or tag.get("stream") != stream or not tag.get("release_tag")):
            continue
        try:
            released = parse_utc(tag.get("release_time"))
        except argparse.ArgumentTypeError as exc:
            raise CollectionError("tag has invalid release_time: " + str(tag.get("release_tag"))) from exc
        if start <= released <= end:
            scoped.append(tag)
    tags = scoped
    payloads, associations = [], []
    for index, tag in enumerate(tags[:limit]):
        rows = require_array(client.get(jobs_url(release, tag["release_tag"]), "%s-jobs-%03d" % (role, index)),
                             "/api/releases/job_runs")
        payload = payload_record(tag, rows, role)
        payloads.append(payload)
        associations.extend(normalize_association(row, tag, role) for row in rows)
    return payloads, associations, len(tags) >= limit


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release")
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--stream", required=True)
    parser.add_argument("--history-release", default="auto-previous")
    parser.add_argument("--lookback-days", type=positive, default=14)
    parser.add_argument("--start", type=parse_utc)
    parser.add_argument("--end", type=parse_utc)
    parser.add_argument("--healthy-payloads", type=positive, default=10)
    parser.add_argument("--max-payloads-scan", type=positive, default=50)
    parser.add_argument("--min-healthy-payloads", type=positive, default=3)
    parser.add_argument("--min-job-runs", type=positive, default=5)
    parser.add_argument("--min-job-payloads", type=positive, default=3)
    parser.add_argument("--min-blocker-pass-rate", type=rate, default=.90)
    parser.add_argument("--poor-job-pass-rate", type=rate, default=.50)
    parser.add_argument("--max-recommendations", type=positive, default=10)
    parser.add_argument("--max-candidates", type=positive, default=100)
    parser.add_argument("--time-budget-minutes", type=positive, default=120)
    parser.add_argument("--workspace")
    parser.add_argument("--max-response-bytes", type=positive, default=64 * 1024 * 1024)
    parser.add_argument("--max-requests", type=positive, default=200)
    parser.add_argument("--timeout-seconds", type=positive, default=30)
    parser.add_argument("--retries", type=int, choices=range(0, 6), default=3)
    parser.add_argument("--resume", action="store_true", help="reuse a completed matching frozen workspace")
    return parser


def validate_args(parser, args, collected_at):
    if (args.start or args.end) and args.lookback_days != 14:
        parser.error("--start/--end cannot be combined with --lookback-days")
    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be supplied together")
    end = args.end or collected_at
    start = args.start or end - dt.timedelta(days=args.lookback_days)
    if start >= end:
        parser.error("--start must precede --end")
    if args.min_healthy_payloads > args.healthy_payloads:
        parser.error("--min-healthy-payloads cannot exceed --healthy-payloads")
    if args.min_job_payloads > args.healthy_payloads:
        parser.error("--min-job-payloads cannot exceed --healthy-payloads")
    return start, end


def run(args, client=None, collected_at=None):
    collected_at = collected_at or now()
    start, end = validate_args(build_parser(), args, collected_at)
    workspace = Path(args.workspace).expanduser() if args.workspace else (
        Path.home() / "tmp" / "analyze-payload-informing-jobs" /
        collected_at.strftime("%Y%m%dT%H%M%SZ"))
    if (workspace / "manifest.json").exists():
        if not args.resume:
            raise CollectionError("workspace already contains a frozen analysis; choose a fresh workspace or use --resume")
        manifest = json.loads((workspace / "manifest.json").read_text())
        effective = manifest.get("effective_inputs", {})
        for key in ("release", "architecture", "stream"):
            if effective.get(key) != getattr(args, key):
                raise CollectionError("resume scope does not match frozen " + key)
        frozen = manifest.get("current_window", {})
        if args.start and (frozen.get("start") != stamp(start) or frozen.get("end") != stamp(end)):
            raise CollectionError("resume window does not match frozen window")
        for record in manifest.get("provenance", []):
            path = Path(record.get("path", ""))
            if not path.is_file() or sha256(path.read_bytes()) != record.get("sha256"):
                raise CollectionError("cached response is missing or changed: " + str(path))
        payloads = json.loads((workspace / "payloads.json").read_text()).get("payloads", [])
        associations = json.loads((workspace / "associations.json").read_text()).get("associations", [])
        return workspace, manifest, payloads, associations
    workspace.mkdir(parents=True, exist_ok=True)
    client = client or Client(workspace / "raw", args.max_response_bytes, args.max_requests,
                              args.timeout_seconds, args.retries)
    current_payloads, current_associations, current_scan_limit = collect_population(
        client, args.release, args.architecture, args.stream, start, end,
        args.max_payloads_scan, "current")
    healthy_now = sum(prelim_healthy(item, args.min_blocker_pass_rate) for item in current_payloads)
    history = {"requested": args.history_release, "triggered": False, "release": None,
               "window": None, "reason": None, "anchored": False}
    historical_payloads, historical_associations = [], []
    historical_scan_limit = False
    if (healthy_now < args.min_healthy_payloads and args.history_release != "none"
            and not current_scan_limit):
        history["triggered"] = True
        history["reason"] = "current release has %d preliminarily healthy payloads; minimum is %d" % (
            healthy_now, args.min_healthy_payloads)
        chosen = args.history_release
        if chosen == "auto-previous":
            releases = client.get(SIPPY + "/api/releases", "releases")
            chosen = previous_release(args.release, release_names(releases))
        if chosen == args.release:
            raise CollectionError("history release must differ from current release")
        history["release"] = chosen
        remaining_capacity = max(1, args.max_payloads_scan - len(current_payloads))
        historical_payloads, historical_associations, historical_scan_limit = collect_population(
            client, chosen, args.architecture, args.stream, start, end,
            remaining_capacity, "previous-release-history")
        history_start, history_end = start, end
        if not historical_payloads:
            probe_start = dt.datetime(1970, 1, 1, tzinfo=UTC)
            probe, _, _ = collect_population(client, chosen, args.architecture, args.stream,
                                              probe_start, end, 1, "history-window-probe")
            if probe:
                history_end = parse_utc(probe[0]["release_time"])
                history_start = history_end - (end - start)
                historical_payloads, historical_associations, historical_scan_limit = collect_population(
                    client, chosen, args.architecture, args.stream, history_start, history_end,
                    remaining_capacity, "previous-release-history")
                history["anchored"] = True
        history["window"] = {"start": stamp(history_start), "end": stamp(history_end)}
    elif healthy_now < args.min_healthy_payloads and current_scan_limit:
        history["reason"] = "payload scan limit was exhausted before fallback capacity was available"

    payloads = current_payloads + historical_payloads
    associations = current_associations + historical_associations
    effective = {
        "release": args.release, "architecture": args.architecture, "stream": args.stream,
        "history_release": args.history_release, "lookback_days": args.lookback_days,
        "healthy_payloads": args.healthy_payloads, "max_payloads_scan": args.max_payloads_scan,
        "min_healthy_payloads": args.min_healthy_payloads, "min_job_runs": args.min_job_runs,
        "min_job_payloads": args.min_job_payloads, "min_blocker_pass_rate": args.min_blocker_pass_rate,
        "poor_job_pass_rate": args.poor_job_pass_rate,
        "max_recommendations": args.max_recommendations, "max_candidates": args.max_candidates,
        "time_budget_minutes": args.time_budget_minutes,
    }
    scope_seed = json.dumps({"inputs": effective, "window": [stamp(start), stamp(end)]}, sort_keys=True).encode()
    manifest = {
        "schema_version": 1, "analysis_id": sha256(scope_seed)[:20], "stage": "COLLECTED",
        "collected_at": stamp(collected_at), "effective_inputs": effective,
        "current_window": {"start": stamp(start), "end": stamp(end)},
        "history": history, "selection_version": 0,
        "counts": {"payloads_inspected": len(payloads), "current_payloads": len(current_payloads),
                   "historical_payloads": len(historical_payloads), "associations": len(associations)},
        "limits": {"payload_scan_limit_hit": current_scan_limit or historical_scan_limit, "requests": client.requests,
                   "bytes": client.bytes, "max_requests": args.max_requests,
                   "max_response_bytes": args.max_response_bytes},
        "complete": not (current_scan_limit or historical_scan_limit),
        "missing_evidence": (["payload scan bound reached; population is bounded"]
                             if current_scan_limit or historical_scan_limit else []),
        "provenance": client.provenance,
    }
    write_json(workspace / "payloads.json", {"schema_version": 1, "payloads": payloads})
    write_json(workspace / "associations.json", {"schema_version": 1, "associations": associations})
    write_json(workspace / "manifest.json", manifest)
    return workspace, manifest, payloads, associations


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        workspace, manifest, _, _ = run(args)
        print(json.dumps({"workspace": str(workspace), "analysis_id": manifest["analysis_id"],
                          "counts": manifest["counts"], "complete": manifest["complete"]}, indent=2))
        return 0
    except (CollectionError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "complete": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
