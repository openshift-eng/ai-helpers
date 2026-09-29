#!/usr/bin/env python3
"""Offline contract tests; no external services or third-party packages required."""
import contextlib
import io
import json
import pathlib
import tempfile
import unittest
import urllib.parse
from unittest import mock

import collect_runs as collector

START = "2026-09-01T00:00:00Z"
END = "2026-09-02T00:00:00Z"
BIG = 2096338379691003904


def row(identifier, result="F", job="periodic-example", timestamp=START, tests=None, variants=None):
    return {"id": identifier, "job": job, "timestamp": timestamp, "overall_result": result,
            "url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/%s/%s" % (job, identifier),
            "failed_test_names": tests, "variants": variants or []}


def args(*extra):
    return collector.parser().parse_args(["--release", "5.1", "--output", "unused", "--per-page", "2", *extra])


class FakeClient:
    def __init__(self, pages=None, urls=None):
        self.pages = pages or {}
        self.urls = urls or {}
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        if url.startswith(collector.SIPPY + "?"):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            value = self.pages[(query["release"][0], int(query["page"][0]))]
        else:
            value = self.urls[url]
        if isinstance(value, Exception):
            raise value
        return value


def page(rows, total=None):
    return {"rows": rows, "total_rows": len(rows) if total is None else total}


def run(options, client):
    return collector.collect(options, client, collector.utc(START), collector.utc(END))


class CollectionTests(unittest.TestCase):
    def test_default_collects_release_and_presubmits_all_results_and_exact_ids(self):
        first = row(BIG, "S")
        client = FakeClient({("5.1", 0): page([first, row(BIG + 1, "R")], 3),
                             ("5.1", 1): page([row(BIG + 2, "A")], 3),
                             ("Presubmits", 0): page([dict(first, pull_request_sha="abc")])})
        rows, manifest = run(args(), client)
        self.assertTrue(manifest["complete"])
        self.assertEqual([str(BIG + i) for i in range(3)], [r["run_id"] for r in rows])
        self.assertEqual(["5.1", "Presubmits"], rows[0]["source_releases"])
        self.assertEqual("abc", rows[0]["additional_raw"]["Presubmits"]["pull_request_sha"])
        self.assertEqual({"S", "R", "A"}, {r["result"] for r in rows})
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(client.calls[0]).query)
        filters = json.loads(query["filter"][0])
        self.assertEqual([">=", "<="], [v["operatorValue"] for v in filters["items"]])
        self.assertEqual("and", filters["linkOperator"])

    def test_client_enforces_half_open_bounds(self):
        data = [row(BIG, timestamp="2026-08-31T23:59:59Z"), row(BIG + 1), row(BIG + 2, timestamp=END)]
        rows, manifest = run(args("--scope", "release", "--per-page", "10"), FakeClient({("5.1", 0): page(data)}))
        self.assertTrue(manifest["complete"])
        self.assertEqual([str(BIG + 1)], [r["run_id"] for r in rows])
        self.assertEqual(2, manifest["sources"]["5.1"]["outside_window"])

    def test_exact_jobs_or_substrings_and_variants_and(self):
        data = [row(i, job=job, variants=variants) for i, job, variants in [
            (1, "aws-upgrade-a", ["Platform:aws", "Architecture:amd64"]),
            (2, "aws-upgrade-b", ["Platform:aws", "Architecture:amd64"]),
            (3, "aws-upgrade-c", ["Platform:aws", "Architecture:amd64"]),
            (4, "aws-upgrade-b", ["Platform:aws"]),
            (5, "gcp-upgrade-a", ["Platform:gcp", "Architecture:amd64"])]]
        options = args("--scope", "release", "--per-page", "10", "--job", "aws-upgrade-a", "--job", "aws-upgrade-b",
                       "--job-contains", "aws", "--job-contains", "upgrade", "--variant", "Platform:aws",
                       "--variant", "Architecture:amd64")
        rows, manifest = run(options, FakeClient({("5.1", 0): page(data)}))
        self.assertEqual(["1", "2"], [r["run_id"] for r in rows])
        self.assertTrue(manifest["complete"])

    def test_duplicate_pages_do_not_create_fake_completeness(self):
        repeated = page([row(1), row(2)], 4)
        rows, manifest = run(args("--scope", "release"), FakeClient({("5.1", 0): repeated, ("5.1", 1): repeated}))
        self.assertFalse(manifest["complete"])
        self.assertEqual(2, len(rows))
        self.assertIn("repeated a page", manifest["errors"][0]["error"])

    def test_overlapping_pages_deduplicate_and_report_total_drift(self):
        client = FakeClient({("5.1", 0): page([row(1), row(2)], 4),
                             ("5.1", 1): page([row(2), row(3)], 3), ("5.1", 2): page([], 3)})
        rows, manifest = run(args("--scope", "release"), client)
        self.assertEqual(3, len(rows))
        self.assertEqual(1, manifest["sources"]["5.1"]["duplicate_rows"])
        self.assertFalse(manifest["complete"])

    def test_cap_is_explicit_and_keeps_partial_rows(self):
        rows, manifest = run(args("--max-runs", "1"), FakeClient({("5.1", 0): page([row(1), row(2)])}))
        self.assertEqual(1, len(rows))
        self.assertFalse(manifest["complete"])
        self.assertIn("max-runs limit reached", manifest["incomplete_reasons"])
        self.assertIn("one or more requested release sources not fetched", manifest["incomplete_reasons"])

    def test_late_request_failure_retains_earlier_rows(self):
        client = FakeClient({("5.1", 0): page([row(1), row(2)], 3),
                             ("5.1", 1): collector.CollectionError("HTTP 503")})
        rows, manifest = run(args("--scope", "release"), client)
        self.assertEqual(2, len(rows))
        self.assertFalse(manifest["complete"])
        self.assertIn("503", manifest["errors"][0]["error"])

    def test_page_budget_and_reported_missing_ids_are_partial(self):
        for options, data in [(args("--scope", "release", "--max-pages", "1"), page([row(1), row(2)], 3)),
                              (args("--scope", "release"), page([row(1)], 3))]:
            _, manifest = run(options, FakeClient({("5.1", 0): data}))
            self.assertFalse(manifest["complete"])

    def test_rejects_lossy_float_ids_and_naive_times(self):
        with self.assertRaises(ValueError):
            collector.run_id(float(BIG))
        with self.assertRaises(ValueError):
            collector.utc("2026-09-01T00:00:00")
        with self.assertRaises(ValueError):
            collector.utc("2026-09-01T01:00:00+01:00")

    def test_green_controls_retain_failure_in_success_and_do_not_drop_running(self):
        data = [row(1, "S", tests=["informing"]), row(2, "F", tests=["informing", "blocking"]), row(3, "R")]
        rows, manifest = run(args("--scope", "release", "--per-page", "10"), FakeClient({("5.1", 0): page(data)}))
        with temporary() as directory:
            collector.write_outputs(pathlib.Path(directory), rows, manifest)
            controls = json.loads((pathlib.Path(directory) / "corpus/same_job_green_controls.json").read_text())
            self.assertEqual(["1"], controls[0]["successful_run_ids"])
            self.assertEqual(["2"], controls[0]["failed_run_ids"])
            self.assertEqual(3, len((pathlib.Path(directory) / "corpus/runs.jsonl").read_text().splitlines()))


class BlockingTests(unittest.TestCase):
    def test_snapshot_requires_exact_attempt_and_honors_previous_attempts(self):
        first, previous, informing = row(BIG), row(BIG + 1), row(BIG + 2)
        detail = {"name": "payload", "results": {"blockingJobs": {"verify": {"url": first["url"],
                     "previousAttemptURLs": [previous["url"]]}}, "informingJobs": {"inform": {"url": informing["url"]}}}}
        with temporary() as directory:
            path = pathlib.Path(directory) / "payload.json"
            collector.write_json(path, detail)
            options = args("--scope", "blocking", "--per-page", "10", "--blocking-snapshot", directory)
            rows, manifest = run(options, FakeClient({("5.1", 0): page([first, previous, informing])}))
            self.assertTrue(manifest["complete"])
            self.assertEqual([str(BIG), str(BIG + 1)], [r["run_id"] for r in rows])
            self.assertTrue(all(r["blocking_evidence"]["blocking"] for r in rows))

    def test_live_metadata_and_rc_exact_attempt_proof(self):
        raw = row(BIG)
        payload = "5.1.0-0.nightly-2026-09-01-000000"
        metadata_url = raw["url"].replace("https://prow.ci.openshift.org/view/gs/", "https://storage.googleapis.com/") + "/prowjob.json"
        rc_url = "https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/5.1.0-0.nightly/release/" + payload
        metadata = {"spec": {"job": raw["job"]}, "status": {"build_id": str(BIG)}, "metadata": {"annotations": {
                    "release.openshift.io/tag": payload, "release.openshift.io/architecture": "amd64"}}}
        client = FakeClient({("5.1", 0): page([raw])}, {metadata_url: metadata, rc_url: {
            "name": payload, "results": {"blockingJobs": {"gate": {"url": raw["url"]}}}}})
        rows, manifest = run(args("--scope", "blocking"), client)
        self.assertTrue(manifest["complete"])
        self.assertEqual("gate", rows[0]["blocking_evidence"]["verification_name"])
        self.assertEqual(3, len(client.calls))

    def test_verify_annotation_or_name_never_proves_blocking(self):
        raw = row(BIG, job="aggregated-payload-blocking-looking-name")
        payload = "5.1.0-0.nightly-2026-09-01-000000"
        metadata_url = raw["url"].replace("https://prow.ci.openshift.org/view/gs/", "https://storage.googleapis.com/") + "/prowjob.json"
        rc_url = "https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/5.1.0-0.nightly/release/" + payload
        metadata = {"spec": {"job": raw["job"]}, "metadata": {"annotations": {
            "release.openshift.io/tag": payload, "release.openshift.io/verify": "true"}}}
        client = FakeClient({("5.1", 0): page([raw])}, {metadata_url: metadata, rc_url: {"name": payload, "results": {}}})
        rows, manifest = run(args("--scope", "blocking"), client)
        self.assertEqual([], rows)
        self.assertFalse(manifest["complete"])
        self.assertEqual(str(BIG), manifest["blocking_unverified"][0]["run_id"])

    def test_metadata_job_mismatch_fails_closed(self):
        raw = row(BIG)
        metadata_url = raw["url"].replace("https://prow.ci.openshift.org/view/gs/", "https://storage.googleapis.com/") + "/prowjob.json"
        client = FakeClient({("5.1", 0): page([raw])}, {metadata_url: {"spec": {"job": "different"}}})
        rows, manifest = run(args("--scope", "blocking"), client)
        self.assertFalse(manifest["complete"])
        self.assertEqual([], rows)

    def test_archive_with_source_provenance(self):
        raw = row(1)
        with temporary() as directory:
            path = pathlib.Path(directory) / "archive.json"
            collector.write_json(path, {"snapshots": [{"source_url": "https://amd64.ocp.releases.ci.openshift.org/api/v1/example",
                "document": {"name": "payload", "results": {"blockingJobs": {"gate": {"url": raw["url"]}}}}}]})
            proof = collector.BlockingProof(FakeClient(), evidence=str(path)).check(collector.normalize(raw, "5.1"))
            self.assertTrue(proof["source"].startswith("https://"))


class BudgetTests(unittest.TestCase):
    def test_download_byte_budget_stops_before_exceeding_limit(self):
        with temporary() as directory, mock.patch("urllib.request.urlopen", return_value=io.BytesIO(b"1234567890")):
            client = collector.Client(pathlib.Path(directory), 5, 10, 1, 10)
            with self.assertRaises(collector.BudgetExceeded):
                client.get("https://example.invalid/data")
            self.assertEqual(5, client.bytes)

    def test_request_budget_is_shared(self):
        with temporary() as directory:
            client = collector.Client(pathlib.Path(directory), 100, 1, 1, 10)
            with mock.patch("urllib.request.urlopen", return_value=io.BytesIO(b"{}")):
                self.assertEqual({}, client.get("https://example.invalid/data"))
            with self.assertRaises(collector.BudgetExceeded):
                client.get("https://example.invalid/next")
            self.assertEqual(1, client.requests)
            self.assertEqual(1, len(client.records))
            self.assertTrue(pathlib.Path(client.records[0]["path"]).exists())

    def test_default_cli_freezes_exact_24_hour_window(self):
        with temporary() as directory:
            output = pathlib.Path(directory) / "output"
            with mock.patch.object(collector, "collect", return_value=([], {"complete": True})) as collect_mock, contextlib.redirect_stdout(io.StringIO()):
                result = collector.main(["--release", "5.1", "--output", str(output), "--scratch-dir", directory])
                options, _, start, end = collect_mock.call_args.args
                self.assertEqual("all", options.scope)
                self.assertEqual(24 * 3600, (end - start).total_seconds())
                self.assertEqual(0, result)
                self.assertTrue((output / "manifest.json").exists())

    def test_cli_rejects_mixed_window_without_any_network(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            collector.main(["--release", "5.1", "--output", "unused", "--hours", "24", "--start", START, "--end", END])
        self.assertEqual(2, exc.exception.code)


def temporary():
    # Tests follow the same scratch policy as collection; never default to /tmp.
    root = pathlib.Path.home() / "tmp" / "ci-reliability-tests"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


if __name__ == "__main__":
    unittest.main()
