#!/usr/bin/env python3
"""Bounded, stdlib-only public Prow artifact access; stdout is always JSON."""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BUCKET = "test-platform-results"
RUN = re.compile(r"(?:logs/[^/]+/\d{10,}|pr-logs/pull/batch/[^/]+/\d{10,}|pr-logs/pull/[^/]+/\d+/[^/]+/\d{10,})")
HOSTS = {
    "prow.ci.openshift.org": "/view/gs/",
    "storage.googleapis.com": "/",
    "gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com": "/gcs/",
}


class ArtifactError(Exception):
    pass


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(value, allow_empty=False):
    if not value and allow_empty:
        return ""
    if (not value or value.startswith("/") or "\\" in value
            or any(ord(c) < 32 for c in value)
            or any(p in (".", "..", "") for p in value.rstrip("/").split("/"))):
        raise ArtifactError("Expected a non-traversing relative object/prefix")
    return value


def parse_run_url(url, allow_artifact=False):
    parsed = urllib.parse.urlsplit(url)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ArtifactError("Run URL must not contain credentials, query or fragment")
    if parsed.scheme == "gs" and parsed.netloc == BUCKET:
        path = parsed.path.lstrip("/")
    elif parsed.scheme == "https" and parsed.netloc in HOSTS:
        prefix = HOSTS[parsed.netloc] + BUCKET + "/"
        if not parsed.path.startswith(prefix):
            raise ArtifactError("URL is not in the public Prow results bucket")
        path = parsed.path[len(prefix):]
    else:
        raise ArtifactError("Unsupported public Prow/GCS run URL")
    path = urllib.parse.unquote(path).rstrip("/")
    relative(path)
    match = RUN.match(path)
    if not match or (match.end() != len(path) and not (allow_artifact and path[match.end():].startswith("/"))):
        raise ArtifactError("Expected logs/JOB/BUILD_ID, pr-logs/pull/ORG_REPO/PR/JOB/BUILD_ID, or pr-logs/pull/batch/JOB/BUILD_ID")
    return match.group(0)


def object_url(run, obj):
    relative(obj)
    return "https://storage.googleapis.com/" + BUCKET + "/" + urllib.parse.quote(run + "/" + obj, safe="/")


class Budget:
    def __init__(self, maximum):
        self.maximum = maximum
        self.used = 0
        self.exhausted = False

    def charge(self, amount):
        if self.exhausted:
            raise ArtifactError("Byte limit already exhausted")
        if self.used + amount > self.maximum:
            self.exhausted = True
            raise ArtifactError("Byte limit reached; increase --max-bytes deliberately or narrow --prefix")
        self.used += amount


class Client:
    """Serial requests. Budget includes metadata, listings, cache reads and retry bytes."""
    def __init__(self, run, scratch, maximum=16 * 1024 * 1024, retries=3,
                 opener=urllib.request.urlopen, sleeper=time.sleep, refresh=False):
        self.run = run
        self.refresh = refresh
        self.cache = Path(scratch).expanduser() / "cache" / digest(run.encode())
        self.budget = Budget(maximum)
        self.retries = retries
        self.opener = opener
        self.sleeper = sleeper

    def request(self, url):
        if self.budget.exhausted:
            raise ArtifactError("Byte limit already exhausted")
        for attempt in range(self.retries + 1):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "ci-reliability-artifacts/1"})
                with self.opener(request, timeout=30) as response:
                    chunks = []
                    while True:
                        chunk = response.read(min(65536, self.budget.maximum - self.budget.used + 1))
                        if not chunk:
                            return b"".join(chunks)
                        self.budget.charge(len(chunk))
                        chunks.append(chunk)
            except urllib.error.HTTPError as exc:
                exc.close()
                if exc.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise ArtifactError("HTTP %s fetching %s" % (exc.code, url)) from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                if attempt == self.retries:
                    raise ArtifactError("Network failure fetching %s: %s" % (url, exc)) from exc
            self.sleeper(min(2 ** attempt, 8))
        raise AssertionError("unreachable")

    def fetch(self, obj):
        relative(obj)
        key = digest(obj.encode())
        data_path = self.cache / (key + ".data")
        meta_path = self.cache / (key + ".json")
        url = object_url(self.run, obj)
        if not self.refresh and data_path.exists() and meta_path.exists():
            try:
                if meta_path.stat().st_size > 65536:
                    raise ValueError("Oversized cache sidecar")
                meta = json.loads(meta_path.read_text())
                size = data_path.stat().st_size
                if size > self.budget.maximum - self.budget.used:
                    raise ArtifactError("Cached artifact exceeds remaining byte limit")
                self.budget.charge(size)
                data = data_path.read_bytes()
                if meta.get("source_url") == url and meta.get("sha256") == digest(data) and meta.get("bytes") == size:
                    return data, dict(meta, cache_hit=True, cache_path=str(data_path))
            except (ValueError, OSError):
                pass
        data = self.request(url)
        meta = {"source_url": url, "object": obj, "run": self.run,
                "sha256": digest(data), "bytes": len(data), "fetched_at": utcnow()}
        self.cache.mkdir(parents=True, exist_ok=True)
        # No shared filenames across artifacts; serial CLI IO avoids a worker race.
        pending = data_path.with_suffix(".pending")
        pending.write_bytes(data)
        pending.replace(data_path)
        pending_meta = meta_path.with_suffix(".pending-json")
        pending_meta.write_text(json.dumps(meta, indent=2) + "\n")
        pending_meta.replace(meta_path)
        return data, dict(meta, cache_hit=False, cache_path=str(data_path))

    def list(self, prefix="", max_objects=200):
        relative(prefix, allow_empty=True)
        bucket_prefix = self.run + "/" + prefix
        objects, pages, token, tokens = [], [], None, set()
        truncated = False
        while True:
            query = {"prefix": bucket_prefix, "maxResults": min(1000, max_objects - len(objects) + 1),
                     "fields": "items(name,size,generation,md5Hash),nextPageToken"}
            if token:
                query["pageToken"] = token
            url = "https://storage.googleapis.com/storage/v1/b/" + BUCKET + "/o?" + urllib.parse.urlencode(query)
            raw = self.request(url)
            try:
                result = json.loads(raw)
            except ValueError as exc:
                raise ArtifactError("Invalid GCS listing JSON") from exc
            pages.append({"source_url": url, "sha256": digest(raw), "bytes": len(raw), "fetched_at": utcnow()})
            for item in result.get("items", []):
                name = item.get("name", "")
                if not name.startswith(bucket_prefix):
                    raise ArtifactError("GCS returned an object outside requested prefix")
                if len(objects) == max_objects:
                    truncated = True
                    break
                obj = name[len(self.run) + 1:]
                relative(obj)
                objects.append(dict(item, object=obj))
            token = result.get("nextPageToken")
            if truncated or (token and len(objects) >= max_objects):
                truncated = True
                break
            if not token:
                break
            if len(pages) >= min(max_objects + 1, 100):
                truncated = True
                break
            if token in tokens:
                raise ArtifactError("Repeated GCS pagination token")
            tokens.add(token)
        return {"objects": objects, "truncated": truncated, "pages": pages,
                "unresolved": ["Object/page limit reached; listing is incomplete"] if truncated else []}


def local_tag(node):
    return node.tag.rsplit("}", 1)[-1]


def first_child(node, tag):
    return next((child for child in node if local_tag(child) == tag), None)


def suite_reports(data, path):
    root = ET.fromstring(data)
    reports = []
    for suite in root.iter():
        if local_tag(suite) != "testsuite":
            continue
        errors = [{"kind": local_tag(child), "message": child.get("message", ""),
                   "text": "".join(child.itertext())} for child in suite
                  if local_tag(child) in ("error", "failure")]
        reports.append({"path": path, "suite": suite.get("name", ""),
                        "declared_counts": {k: suite.get(k) for k in ("tests", "failures", "errors", "skipped")},
                        "suite_errors": errors})
    return reports


def junit_attempts(data, path):
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ArtifactError("Invalid JUnit XML in %s: %s" % (path, exc)) from exc
    attempts = []

    def walk(node, suites):
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "testsuite":
            suites = suites + [node.get("name", "")]
        if tag == "testcase":
            property_node = first_child(node, "properties")
            properties = {p.get("name"): p.get("value", p.text or "")
                          for p in (list(property_node) if property_node is not None else [])
                          if local_tag(p) == "property"}
            failure = first_child(node, "failure")
            error = first_child(node, "error")
            skipped = first_child(node, "skipped")
            failure_nodes = [x for x in (failure, error) if x is not None]
            outcome = "skipped" if skipped is not None else "failure" if failure_nodes else "success"
            attempts.append({"path": path, "suite": suites, "classname": node.get("classname", ""),
                             "name": node.get("name", ""), "outcome": outcome,
                             "lifecycle": node.get("lifecycle", properties.get("lifecycle", "unknown")),
                             "source_image": node.get("source-image", properties.get("source-image", "")),
                             "source_binary": node.get("source-binary", properties.get("source-binary", "")),
                             "time": node.get("time"), "start_time": node.get("start-time"),
                             "end_time": node.get("end-time"), "properties": properties,
                             "failure_text": "\n".join("".join(x.itertext()) or x.get("message", "") for x in failure_nodes),
                             "skip_reason": (skipped.text or skipped.get("message", "")) if skipped is not None else None})
        for child in node:
            if child.tag.rsplit("}", 1)[-1] in ("testsuites", "testsuite", "testcase"):
                walk(child, suites)
    walk(root, [])
    return attempts


def summarize_junit(attempts):
    groups = {}
    for attempt in attempts:
        # Do not merge independent step directories or distinguish retries by filename alone.
        key = (str(Path(attempt["path"]).parent), tuple(attempt["suite"]), attempt["classname"],
               attempt["name"], attempt["source_image"], attempt["source_binary"])
        groups.setdefault(key, []).append(attempt)
    cases = []
    for group in groups.values():
        outcomes = {a["outcome"] for a in group if a["outcome"] != "skipped"}
        lifecycle_values = sorted({a["lifecycle"] for a in group})
        lifecycle = lifecycle_values[0] if len(lifecycle_values) == 1 else "conflicting"
        if not outcomes:
            classification = "skipped_only"
        elif outcomes == {"failure", "success"}:
            classification = "mixed_success_failure"
        elif outcomes == {"failure"}:
            classification = "failure_only"
        else:
            classification = "success_only"
        cases.append({"name": group[0]["name"], "classname": group[0]["classname"],
                      "suite": group[0]["suite"], "lifecycle": lifecycle,
                      "lifecycle_values": lifecycle_values, "classification": classification,
                      "blocking_failure": classification == "failure_only" and lifecycle == "blocking",
                      "informing_failure": classification == "failure_only" and lifecycle == "informing",
                      "policy_review_required": classification == "mixed_success_failure" or
                          (classification == "failure_only" and lifecycle not in ("blocking", "informing")),
                      "attempts": group})
    return {"cases": cases, "attempt_count": len(attempts),
            "evaluated_cases": sum(c["classification"] != "skipped_only" for c in cases),
            "skipped_attempts": sum(a["outcome"] == "skipped" for a in attempts),
            "blocking_failure_cases": sum(c["blocking_failure"] for c in cases),
            "informing_failure_cases": sum(c["informing_failure"] for c in cases),
            "unresolved": ["Mixed outcomes may be retries or repeated executions; verify runner policy. Unknown lifecycle is not inferred from failure."]}


def recorded_children(text, parent_run, source_name, max_objects=200):
    source_sha = digest(text.encode())
    strings = []

    def walk(value, pointer):
        if isinstance(value, str):
            strings.append((pointer, value))
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, pointer + "/" + str(key).replace("~", "~0").replace("/", "~1"))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, pointer + "/" + str(index))
    try:
        walk(json.loads(text), "")
    except ValueError:
        strings = [("line:" + str(i), line) for i, line in enumerate(text.splitlines(), 1)]
    edges, unresolved = {}, []
    reference_count, truncated = 0, False
    for location, value in strings:
        if truncated:
            break
        for match in re.finditer(r"(?:https://|gs://)[^\s<>\"']+", value):
            url = match.group(0).rstrip(".,);]}")
            if BUCKET not in url and "prow.ci.openshift.org" not in url:
                continue
            if reference_count >= max_objects:
                truncated = True
                break
            reference_count += 1
            evidence = {"source": source_name, "source_sha256": source_sha,
                        "location": location, "offset": match.start(), "recorded_url": url}
            try:
                run = parse_run_url(url, allow_artifact=True)
            except ArtifactError as exc:
                unresolved.append(dict(evidence, reason=str(exc)))
                continue
            if run == parent_run:
                continue
            edges.setdefault(run, []).append(evidence)
    if truncated:
        unresolved.append({"reason": "Recorded reference limit reached; extraction incomplete"})
    return {"truncated": truncated, "child_candidates": [{"run": run, "url": "https://prow.ci.openshift.org/view/gs/" + BUCKET + "/" + run,
                                  "relationship": "recorded_reference_requires_parent_validation", "evidence": proof}
                                 for run, proof in sorted(edges.items())],
            "unresolved": unresolved + [{"reason": "References alone do not prove aggregate membership or completeness; compare the aggregate report's explicit attempt list."}],
            "missing_edges": "unknown; no child URLs or IDs synthesized"}


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "fetch", "junit", "children"))
    parser.add_argument("run_url")
    parser.add_argument("object", nargs="?", help="relative object for fetch")
    parser.add_argument("--prefix", default="", help="relative listing prefix; narrow to a test step")
    parser.add_argument("--scratch", default="~/tmp/ci-reliability")
    parser.add_argument("--max-objects", type=positive, default=200)
    parser.add_argument("--max-bytes", type=positive, default=16 * 1024 * 1024)
    parser.add_argument("--retries", type=int, choices=range(0, 6), default=3)
    parser.add_argument("--refresh", action="store_true", help="bypass cached objects and refresh provenance")
    parser.add_argument("--output", help="explicit curated fetch destination; refuses differing existing file")
    parser.add_argument("--input", help="bounded local recorded aggregate log/JSON for children")
    args = parser.parse_args(argv)
    try:
        run = parse_run_url(args.run_url)
        client = Client(run, args.scratch, args.max_bytes, args.retries, refresh=args.refresh)
        raw_meta, provenance = client.fetch("prowjob.json")
        try:
            meta = json.loads(raw_meta)
        except ValueError as exc:
            raise ArtifactError("Invalid prowjob.json") from exc
        result = {"run": run, "metadata": {"job": meta.get("spec", {}).get("job"),
                  "type": meta.get("spec", {}).get("type"), "refs": meta.get("spec", {}).get("refs"),
                  "extra_refs": meta.get("spec", {}).get("extra_refs"), "status": meta.get("status"),
                  "annotations": meta.get("metadata", {}).get("annotations", {})}, "metadata_provenance": provenance}
        if args.command == "fetch":
            if not args.object:
                raise ArtifactError("fetch requires a relative object")
            data, proof = client.fetch(args.object)
            if args.output:
                destination = Path(args.output).expanduser()
                if destination.exists() and (destination.stat().st_size != len(data) or digest(destination.read_bytes()) != proof["sha256"]):
                    raise ArtifactError("Refusing to overwrite differing curated output")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                destination.with_name(destination.name + ".provenance.json").write_text(json.dumps(proof, indent=2) + "\n")
                proof["output"] = str(destination)
            result["artifact"] = proof
        elif args.command in ("list", "junit"):
            listing = client.list(args.prefix, args.max_objects)
            result["listing"] = listing
            if args.command == "junit":
                attempts, artifacts, failures, suites = [], [], [], []
                for item in listing["objects"]:
                    obj = item["object"]
                    if not obj.lower().endswith(".xml") or "junit" not in obj.lower():
                        continue
                    try:
                        data, proof = client.fetch(obj)
                        attempts.extend(junit_attempts(data, obj))
                        suites.extend(suite_reports(data, obj))
                        artifacts.append(proof)
                    except ArtifactError as exc:
                        failures.append({"object": obj, "error": str(exc)})
                        if client.budget.exhausted or client.budget.used >= client.budget.maximum:
                            break
                result["junit"] = dict(summarize_junit(attempts), artifacts=artifacts, unavailable=failures, suite_reports=suites,
                                       complete=not listing["truncated"] and not failures)
                if any(suite["suite_errors"] for suite in suites):
                    result["junit"]["unresolved"].append("Suite-level errors require separate gate-policy review; they are not testcase counts")
                if not artifacts:
                    result["junit"]["complete"] = False
                    result["junit"]["unresolved"].append("No JUnit artifacts parsed; narrow or correct prefix, do not infer passing tests")
        else:
            if not args.input:
                raise ArtifactError("children requires --input containing recorded URLs")
            input_path = Path(args.input).expanduser()
            size = input_path.stat().st_size
            client.budget.charge(size)
            result["children"] = recorded_children(input_path.read_text(), run, str(input_path), args.max_objects)
        result["bytes_used"] = client.budget.used
        print(json.dumps(result, indent=2))
        return 0
    except (ArtifactError, OSError, UnicodeError) as exc:
        print(json.dumps({"error": str(exc), "complete": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
