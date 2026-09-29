#!/usr/bin/env python3
"""Collect a bounded, auditable Sippy run inventory. Python standard library only."""
import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

SIPPY = "https://sippy.dptools.openshift.org/api/jobs/runs"
UTC = dt.timezone.utc


class CollectionError(Exception):
    """An acquisition or validation failure that must remain visible."""


class BudgetExceeded(CollectionError):
    pass


def utc(value):
    """Require explicit UTC, rather than interpreting a local or naive timestamp."""
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp must be ISO 8601 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("timestamp must specify UTC (Z or +00:00)")
    return parsed.astimezone(UTC)


def stamp(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run_id(value):
    # Do not round Prow's 64-bit IDs through float or a JavaScript number.
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("run ID must be an integer or decimal string")
    value = str(value)
    if not value.isdecimal():
        raise ValueError("run ID must be decimal")
    return value


class Client:
    """One shared network budget, including retries and blocking metadata."""
    def __init__(self, scratch, max_bytes, max_requests, timeout, seconds, retries=3):
        self.scratch = scratch
        self.max_bytes = max_bytes
        self.max_requests = max_requests
        self.timeout = timeout
        self.deadline = time.monotonic() + seconds
        self.retries = retries
        self.bytes = 0
        self.requests = 0
        self.records = []

    def get(self, url):
        for attempt in range(self.retries + 1):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or self.requests >= self.max_requests or self.bytes >= self.max_bytes:
                raise BudgetExceeded("download time, request, or byte budget exhausted")
            self.requests += 1
            request = urllib.request.Request(url, headers={"User-Agent": "ci-reliability/1"})
            try:
                with urllib.request.urlopen(request, timeout=min(self.timeout, remaining)) as response:
                    chunks = []
                    while True:
                        if time.monotonic() >= self.deadline:
                            raise BudgetExceeded("download time budget exhausted")
                        available = self.max_bytes - self.bytes
                        if available <= 0:
                            raise BudgetExceeded("download byte budget exhausted")
                        chunk = response.read(min(65536, available))
                        if not chunk:
                            break
                        self.bytes += len(chunk)
                        chunks.append(chunk)
                    body = b"".join(chunks)
                path = self.scratch / ("response-%05d.json" % self.requests)
                path.write_bytes(body)
                self.records.append({"url": url, "path": str(path), "bytes": len(body),
                                     "sha256": hashlib.sha256(body).hexdigest(),
                                     "fetched_at": stamp(dt.datetime.now(UTC))})
                try:
                    return json.loads(body)
                except (ValueError, UnicodeError) as exc:
                    raise CollectionError("invalid JSON response from " + url) from exc
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise CollectionError("HTTP %s from %s" % (exc.code, url)) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt == self.retries:
                    raise CollectionError("request failed for %s: %s" % (url, exc)) from exc
            delay = min(2 ** attempt, max(0, self.deadline - time.monotonic()))
            time.sleep(delay)
        raise CollectionError("request retries exhausted")


def attempt_key(url):
    """Only accept actual Prow attempt URLs, not guessed job name prefixes."""
    parsed = urllib.parse.urlparse(url or "")
    if parsed.scheme != "https" or parsed.hostname != "prow.ci.openshift.org":
        return None
    parts = parsed.path.rstrip("/").split("/")
    if len(parts) < 7 or parts[1:4] != ["view", "gs", "test-platform-results"]:
        return None
    try:
        return run_id(parts[-1]), urllib.parse.unquote(parts[-2])
    except ValueError:
        return None


class BlockingProof:
    """Admit exact RC blocking attempt references; never infer from job names."""
    def __init__(self, client, snapshots=(), evidence=None):
        self.client = client
        self.attempts = {}
        self.payloads = {}
        for directory in snapshots:
            if not pathlib.Path(directory).is_dir():
                raise ValueError("blocking snapshot directory does not exist: " + str(directory))
            for path in sorted(pathlib.Path(directory).glob("*.json")):
                self.load(path)
        if evidence:
            self.load(pathlib.Path(evidence))

    def load(self, path):
        value = json.loads(path.read_text())
        # A raw RC detail document, or source-preserving archived documents.
        documents = value.get("snapshots", [value]) if isinstance(value, dict) else value
        if not isinstance(documents, list):
            raise ValueError("blocking evidence must be RC detail JSON or a snapshots list")
        for document in documents:
            if not isinstance(document, dict):
                raise ValueError("blocking evidence entries must be JSON objects")
            detail = document.get("document", document)
            if not isinstance(detail, dict):
                raise ValueError("archived RC document must be an object")
            if "results" in detail:
                self.ingest(detail, document.get("source_url", str(path)))
            elif "tags" not in detail:
                raise ValueError("blocking evidence lacks RC results.blockingJobs: " + str(path))

    def ingest(self, detail, source):
        if not isinstance(detail, dict) or not isinstance(detail.get("results"), dict):
            raise CollectionError("invalid RC detail results")
        results = detail["results"]
        for category, blocking in (("blockingJobs", True), ("informingJobs", False)):
            jobs = results.get(category, {})
            if not isinstance(jobs, dict):
                raise CollectionError("invalid RC " + category)
            for verification, result in jobs.items():
                if not isinstance(result, dict):
                    raise CollectionError("invalid RC verification result")
                previous = result.get("previousAttemptURLs") or []
                if not isinstance(previous, list):
                    raise CollectionError("invalid RC previousAttemptURLs")
                urls = [result.get("url")] + previous
                for url in urls:
                    key = attempt_key(url)
                    if key is None:
                        continue
                    proof = {"kind": "release_controller_attempt", "blocking": blocking,
                             "verification_name": verification, "payload": detail.get("name"),
                             "source": source, "attempt_url": url}
                    if key in self.attempts and self.attempts[key]["blocking"] != blocking:
                        raise CollectionError("conflicting RC blocking evidence for " + key[0])
                    self.attempts[key] = proof

    def check(self, row):
        key = row["run_id"], row["job"]
        if key in self.attempts:
            return self.attempts[key]
        if attempt_key(row["url"]) != key:
            raise CollectionError("cannot verify malformed or mismatched Prow URL")
        metadata_url = "https://storage.googleapis.com/" + urllib.parse.urlparse(row["url"]).path.removeprefix("/view/gs/").rstrip("/") + "/prowjob.json"
        metadata = self.client.get(metadata_url)
        if not isinstance(metadata, dict) or not isinstance(metadata.get("spec"), dict):
            raise CollectionError("invalid Prow metadata")
        if metadata.get("spec", {}).get("job") != row["job"]:
            raise CollectionError("Prow metadata job differs from Sippy job")
        status_id = metadata.get("status", {}).get("build_id")
        if status_id is not None and run_id(status_id) != row["run_id"]:
            raise CollectionError("Prow metadata ID differs from Sippy ID")
        annotations = metadata.get("metadata", {}).get("annotations", {})
        if not isinstance(annotations, dict):
            raise CollectionError("invalid Prow annotations")
        payload = annotations.get("release.openshift.io/tag")
        if not payload:
            return {"blocking": False, "kind": "no_payload_annotation", "source": metadata_url}
        match = re.fullmatch(r"(.+)-(\d{4}-\d{2}-\d{2}-\d{6})", payload)
        if not match:
            raise CollectionError("payload stream cannot be derived; provide archived RC detail")
        stream = match.group(1)
        arch = annotations.get("release.openshift.io/architecture", "amd64")
        if arch not in ("amd64", "arm64", "ppc64le", "s390x", "multi"):
            raise CollectionError("unsupported release-controller architecture " + str(arch))
        if stream.endswith("-multi"):
            arch = "multi"
        rc_url = "https://%s.ocp.releases.ci.openshift.org/api/v1/releasestream/%s/release/%s" % (
            arch, urllib.parse.quote(stream, safe=""), urllib.parse.quote(payload, safe=""))
        if rc_url not in self.payloads:
            try:
                detail = self.client.get(rc_url)
                if not isinstance(detail, dict) or detail.get("name") != payload:
                    raise CollectionError("RC detail payload name mismatch")
                self.ingest(detail, rc_url)
                self.payloads[rc_url] = None
            except CollectionError as exc:
                self.payloads[rc_url] = str(exc)
                raise
        if self.payloads[rc_url]:
            raise CollectionError(self.payloads[rc_url])
        if key not in self.attempts:
            raise CollectionError("attempt absent from retained RC blocking/informing results; archive required")
        return dict(self.attempts[key], metadata_source=metadata_url)


def normalize(raw, release):
    return {"run_id": run_id(raw["id"]), "job": raw["job"], "url": raw.get("url") or raw.get("test_grid_url") or "",
            "timestamp": stamp(utc(raw["timestamp"])), "result": raw.get("overall_result"),
            "source_releases": [release], "raw": raw}


def matches(row, args):
    return (not args.job or row["job"] in args.job) and all(
        part in row["job"] for part in args.job_contains) and all(
        variant in (row["raw"].get("variants") or []) for variant in args.variant)


def collect(args, client, start, end):
    releases = (["Presubmits"] if args.scope == "presubmits" else
                [args.release] if args.scope in ("release", "blocking") else [args.release, "Presubmits"])
    releases = list(dict.fromkeys(releases))
    manifest = {"schema_version": 1, "started_at": stamp(dt.datetime.now(UTC)), "start_inclusive": stamp(start),
                "end_exclusive": stamp(end), "requested_release": args.release, "scope": args.scope,
                "source_releases": releases, "filters": {"job": args.job, "job_contains": args.job_contains,
                "variant": args.variant}, "sources": {}, "errors": [], "incomplete_reasons": [],
                "blocking_unverified": [], "complete": False}
    rows = {}
    proof = BlockingProof(client, args.blocking_snapshot, args.blocking_evidence) if args.scope == "blocking" else None
    stop = False
    for release in releases:
        stats = {"pages": [], "api_unique_runs": 0, "duplicate_rows": 0, "outside_window": 0,
                 "filtered_out": 0, "nonblocking": 0, "complete": False}
        manifest["sources"][release] = stats
        seen = set()
        totals = set()
        ended = False
        previous_page = None
        for page in range(args.max_pages):
            filters = {"items": [{"columnField": "timestamp", "operatorValue": ">=", "value": stamp(start)},
                                  {"columnField": "timestamp", "operatorValue": "<=", "value": stamp(end)}],
                       "linkOperator": "and"}
            query = {"release": release, "filter": json.dumps(filters), "sortField": "id", "sort": "asc",
                     "perPage": args.per_page, "page": page}
            url = SIPPY + "?" + urllib.parse.urlencode(query)
            try:
                data = client.get(url)
                if not isinstance(data, dict):
                    raise CollectionError("Sippy response must be an object")
                got = data.get("rows")
                if not isinstance(got, list) or type(data.get("total_rows")) is not int or data["total_rows"] < 0:
                    raise CollectionError("Sippy response must contain rows list and integer total_rows")
                totals.add(data["total_rows"])
                page_ids = tuple(run_id(raw["id"]) for raw in got)
                if page_ids and page_ids == previous_page:
                    raise CollectionError("Sippy repeated a page; pagination is not complete")
                previous_page = page_ids
                stats["pages"].append({"page": page, "rows": len(got), "total_rows": data["total_rows"], "url": url})
                for raw in got:
                    rid = run_id(raw["id"])
                    stats["duplicate_rows"] += rid in seen
                    seen.add(rid)
                    row = normalize(raw, release)
                    if not start <= utc(row["timestamp"]) < end:
                        stats["outside_window"] += 1
                        continue
                    if not matches(row, args):
                        stats["filtered_out"] += 1
                        continue
                    if proof:
                        try:
                            verdict = proof.check(row)
                        except BudgetExceeded:
                            raise
                        except (CollectionError, KeyError, ValueError, TypeError) as exc:
                            manifest["blocking_unverified"].append({"run_id": rid, "job": row["job"], "reason": str(exc)})
                            continue
                        if not verdict["blocking"]:
                            stats["nonblocking"] += 1
                            continue
                        row["blocking_evidence"] = verdict
                    if rid in rows:
                        old = rows[rid]
                        if old["job"] != row["job"]:
                            raise CollectionError("same run ID has conflicting job names")
                        if release not in old["source_releases"]:
                            old["source_releases"].append(release)
                            old.setdefault("additional_raw", {})[release] = raw
                        continue
                    if len(rows) >= args.max_runs:
                        manifest["incomplete_reasons"].append("max-runs limit reached")
                        stop = True
                        break
                    rows[rid] = row
                if stop:
                    break
                if len(got) < args.per_page:
                    ended = True
                    break
            except (CollectionError, KeyError, ValueError, TypeError) as exc:
                manifest["errors"].append({"release": release, "page": page, "url": url, "error": str(exc)})
                if isinstance(exc, BudgetExceeded):
                    stop = True
                break
        stats["api_unique_runs"] = len(seen)
        stats["reported_totals"] = sorted(totals)
        stats["complete"] = ended and len(totals) == 1 and len(seen) == next(iter(totals))
        if not stats["complete"]:
            manifest["incomplete_reasons"].append("%s inventory not proven complete (page limit, acquisition error, total drift, or missing IDs)" % release)
        if stop:
            break
    if len(manifest["sources"]) < len(releases):
        manifest["incomplete_reasons"].append("one or more requested release sources not fetched")
    if manifest["blocking_unverified"]:
        manifest["incomplete_reasons"].append("blocking membership unverified for some candidates")
    manifest["complete"] = not manifest["errors"] and not manifest["incomplete_reasons"]
    manifest["selected_runs"] = len(rows)
    manifest["result_counts"] = dict(collections.Counter(str(row["result"]) for row in rows.values()))
    manifest["completed_at"] = stamp(dt.datetime.now(UTC))
    return sorted(rows.values(), key=lambda row: (row["timestamp"], row["run_id"])), manifest


def write_outputs(output, rows, manifest):
    corpus = output / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    with (corpus / "runs.jsonl").open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    greens = collections.defaultdict(lambda: collections.defaultdict(list))
    failures = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        if row["result"] == "R":
            continue
        group = greens if row["result"] == "S" else failures
        for test in set(row["raw"].get("failed_test_names") or []):
            group[row["job"]][test].append(row["run_id"])
    controls = [{"job": job, "test": test, "failed_run_ids": ids, "successful_run_ids": greens[job][test]}
                for job, tests in failures.items() for test, ids in tests.items() if test in greens[job]]
    write_json(corpus / "same_job_green_controls.json", controls)
    write_json(output / "manifest.json", manifest)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release", required=True, help="Sippy release (required even with --scope presubmits)")
    p.add_argument("--hours", type=float, help="look back this many hours from one frozen UTC end; default 24")
    p.add_argument("--start", help="inclusive ISO 8601 UTC; requires --end, incompatible with --hours")
    p.add_argument("--end", help="exclusive ISO 8601 UTC; requires --start")
    p.add_argument("--scope", choices=("all", "release", "presubmits", "blocking"), default="all")
    p.add_argument("--job", action="append", default=[], help="exact name; repeated values are OR")
    p.add_argument("--job-contains", action="append", default=[], help="substring; repeated values are AND")
    p.add_argument("--variant", action="append", default=[], help="exact Sippy variant, e.g. Platform:aws; repeated values are AND")
    p.add_argument("--output", type=pathlib.Path, required=True)
    p.add_argument("--scratch-dir", type=pathlib.Path, default=pathlib.Path.home() / "tmp" / "ci-reliability")
    p.add_argument("--max-runs", type=int, default=10000)
    p.add_argument("--per-page", type=int, default=500)
    p.add_argument("--max-pages", type=int, default=100, help="maximum pages per release source")
    p.add_argument("--max-download-mb", type=float, default=256)
    p.add_argument("--max-requests", type=int, default=1000, help="includes retries and metadata")
    p.add_argument("--max-seconds", type=float, default=1800)
    p.add_argument("--timeout", type=float, default=60, help="maximum seconds per network operation")
    p.add_argument("--blocking-snapshot", action="append", default=[], metavar="DIR", help="directory of raw RC detail JSON snapshots")
    p.add_argument("--blocking-evidence", metavar="JSON", help="raw RC detail document or archived snapshots list")
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if bool(args.start) != bool(args.end) or (args.start and args.hours is not None):
        p.error("use --start and --end together, or --hours, not both")
    try:
        end = utc(args.end) if args.end else dt.datetime.now(UTC)
        start = utc(args.start) if args.start else end - dt.timedelta(hours=args.hours if args.hours is not None else 24)
        if start >= end:
            raise ValueError("start must precede end")
    except (ValueError, OverflowError) as exc:
        p.error(str(exc))
    for name in ("max_runs", "per_page", "max_pages", "max_download_mb", "max_requests", "max_seconds", "timeout"):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
            p.error("--" + name.replace("_", "-") + " must be positive")
    if args.per_page > 10000:
        p.error("--per-page must not exceed 10000")
    args.scratch_dir = args.scratch_dir.expanduser()
    args.output = args.output.expanduser()
    if args.scratch_dir.resolve().is_relative_to(pathlib.Path("/tmp")):
        p.error("--scratch-dir must be outside /tmp; use ~/tmp/ci-reliability or another persistent scratch parent")
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="runs-", dir=args.scratch_dir))
    client = Client(scratch, int(args.max_download_mb * 1024 * 1024), args.max_requests, args.timeout, args.max_seconds)
    try:
        rows, manifest = collect(args, client, start, end)
    except (CollectionError, OSError, ValueError) as exc:
        rows, manifest = [], {"schema_version": 1, "complete": False, "start_inclusive": stamp(start),
                              "end_exclusive": stamp(end), "errors": [{"error": str(exc)}],
                              "incomplete_reasons": ["collector initialization failed"]}
    manifest["scratch_dir"] = str(scratch)
    manifest["downloads"] = client.records
    manifest["budgets"] = {"max_runs": args.max_runs, "max_pages_per_source": args.max_pages,
                           "max_download_bytes": client.max_bytes, "downloaded_bytes": client.bytes,
                           "max_requests": args.max_requests, "requests": client.requests,
                           "max_seconds": args.max_seconds, "timeout_seconds": args.timeout}
    manifest["limitations"] = ["Completeness is relative to Sippy's observed inventory; ingestion lag and mutable statuses remain possible.",
                              "Successful runs may contain informing failures. Green controls are exposure checks, not causal proof.",
                              "Blocking scope includes only exact RC attempt references; absent or garbage-collected evidence remains unresolved.",
                              "Aggregator parents and component jobs overlap; expand parents before estimating independent failure impact."]
    write_outputs(args.output, rows, manifest)
    print(json.dumps({"runs": len(rows), "complete": manifest["complete"], "manifest": str(args.output / "manifest.json")}))
    return 0 if manifest["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
