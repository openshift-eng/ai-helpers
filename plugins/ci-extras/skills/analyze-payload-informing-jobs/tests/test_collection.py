import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "collect_payload_jobs.py"
SPEC = importlib.util.spec_from_file_location("collect_payload_jobs", SCRIPT)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def tag(identifier, name, phase="Accepted", when="2026-10-02T05:22:46Z", release="5.1"):
    return {"id": identifier, "release_tag": name, "release": release, "stream": "nightly",
            "architecture": "amd64", "phase": phase, "forced": False, "release_time": when,
            "kubernetes_version": "1.36.4", "current_os_version": "10.2", "previous_os_version": "10.1"}


def job(index, kind="Informing", state="Succeeded", payload_id="147634", alias=None, duplicate_run=None):
    run = str(duplicate_run or (2105892780260724700 + index))
    alias = alias or "job-%02d" % index
    return {"id": 1780000 + index, "ReleaseTagID": payload_id, "name": int(run), "job_name": alias,
            "kind": kind, "state": state, "transition_time": "2026-10-02T09:08:43Z", "retries": 0,
            "url": "https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/periodic-%s/%s" % (alias, run),
            "upgrades_from": "", "upgrades_to": "", "upgrade": False, "labels": []}


def rows(block_pass, block_fail, info_pass, info_fail, payload_id):
    result, index = [], 0
    for kind, state, count in (("Blocking", "Succeeded", block_pass), ("Blocking", "Failed", block_fail),
                               ("Informing", "Succeeded", info_pass), ("Informing", "Failed", info_fail)):
        for _ in range(count):
            result.append(job(index, kind, state, payload_id))
            index += 1
    return result


class FakeClient:
    def __init__(self, tags_by_release, jobs_by_tag, releases=None):
        self.tags_by_release = tags_by_release
        self.jobs_by_tag = jobs_by_tag
        self.releases = releases or ["5.1", "5.0"]
        self.requests = 0
        self.bytes = 0
        self.provenance = []

    def get(self, url, label):
        self.requests += 1
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/releases":
            value = {"releases": self.releases}
        elif parsed.path.endswith("/tags"):
            value = self.tags_by_release.get(query["release"][0], [])
        else:
            model = json.loads(query["filter"][0])
            payload = next(item["value"] for item in model["items"] if item["columnField"] == "release_tag")
            value = self.jobs_by_tag[payload]
        raw = json.dumps(value).encode()
        self.bytes += len(raw)
        self.provenance.append({"url": url, "path": label, "bytes": len(raw), "sha256": collector.sha256(raw),
                                "retrieved_at": "2026-10-06T00:00:00Z"})
        return value


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def __call__(self, request, timeout):
        self.urls.append(request.full_url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return io.BytesIO(response)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = Path(self.temp.name)
        sleeper = mock.patch.object(collector.time, "sleep")
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def client(self, responses, **kwargs):
        http = FakeHTTP(responses)
        return collector.Client(self.raw, opener=http, **kwargs), http

    def http_error(self, code):
        return urllib.error.HTTPError("https://example.invalid", code, "fixture error", {}, None)

    def test_retryable_http_succeeds_with_retained_provenance(self):
        body = b'[{"id": 123}]'
        for code in (429, 500, 502, 503, 504):
            with self.subTest(code=code):
                self.sleep.reset_mock()
                client, http = self.client([self.http_error(code), body])
                self.assertEqual([{"id": 123}], client.get("https://example.invalid", "tags"))
                self.assertEqual(2, client.requests)
                self.assertEqual(["https://example.invalid"] * 2, http.urls)
                self.sleep.assert_called_once_with(1)
                self.assertEqual(len(body), client.bytes)
                self.assertEqual(1, len(client.provenance))
                proof = client.provenance[0]
                self.assertEqual("https://example.invalid", proof["url"])
                self.assertEqual(collector.sha256(body), proof["sha256"])
                self.assertEqual(body, Path(proof["path"]).read_bytes())

    def test_nonretryable_http_error_fails_immediately(self):
        client, http = self.client([self.http_error(404), b"[]"])
        with self.assertRaisesRegex(collector.CollectionError, "HTTP 404"):
            client.get("https://example.invalid", "tags")
        self.assertEqual(1, client.requests)
        self.assertEqual(1, len(http.urls))
        self.sleep.assert_not_called()
        self.assertEqual([], client.provenance)

    def test_response_byte_limit_does_not_retain_partial_body(self):
        client, http = self.client([b"123456"], max_bytes=5)
        with self.assertRaisesRegex(collector.CollectionError, "response byte limit reached"):
            client.get("https://example.invalid", "tags")
        self.assertEqual(1, len(http.urls))
        self.assertEqual([], list(self.raw.iterdir()))
        self.assertEqual([], client.provenance)
        self.sleep.assert_not_called()

    def test_byte_limit_is_shared_across_responses(self):
        client, http = self.client([b"[]", b"[]"], max_bytes=3)
        self.assertEqual([], client.get("https://example.invalid/first", "first"))
        with self.assertRaisesRegex(collector.CollectionError, "response byte limit reached"):
            client.get("https://example.invalid/second", "second")
        self.assertEqual(2, len(http.urls))
        self.assertEqual(2, client.bytes)
        self.assertEqual(1, len(client.provenance))
        self.assertEqual(["0001-first.json"], [path.name for path in self.raw.iterdir()])

    def test_request_limit_stops_retry_before_another_request(self):
        client, http = self.client([self.http_error(503), b"[]"], max_requests=1)
        with self.assertRaisesRegex(collector.CollectionError, "request limit reached"):
            client.get("https://example.invalid", "tags")
        self.assertEqual(1, client.requests)
        self.assertEqual(1, len(http.urls))
        self.assertEqual([], client.provenance)

    def test_retry_exhaustion_uses_exponential_backoff(self):
        client, http = self.client([self.http_error(503) for _ in range(3)], retries=2)
        with self.assertRaisesRegex(collector.CollectionError, "HTTP 503"):
            client.get("https://example.invalid", "tags")
        self.assertEqual(3, client.requests)
        self.assertEqual(3, len(http.urls))
        self.assertEqual([mock.call(1), mock.call(2)], self.sleep.call_args_list)
        self.assertEqual([], client.provenance)

    def test_invalid_json_is_rejected_without_retry_and_retained_for_diagnosis(self):
        client, http = self.client([b"not JSON", b"[]"])
        with self.assertRaisesRegex(collector.CollectionError, "invalid JSON"):
            client.get("https://example.invalid", "tags")
        self.assertEqual(1, client.requests)
        self.assertEqual(1, len(http.urls))
        self.sleep.assert_not_called()
        self.assertEqual(b"not JSON", Path(client.provenance[0]["path"]).read_bytes())


def options(workspace, history="none", minimum="1"):
    return collector.build_parser().parse_args([
        "5.1", "--architecture", "amd64", "--stream", "nightly", "--history-release", history,
        "--start", "2026-09-22T00:00:00Z", "--end", "2026-10-06T00:00:00Z",
        "--min-healthy-payloads", minimum, "--workspace", str(workspace),
    ])


class CollectionTests(unittest.TestCase):
    def test_exploration_defaults_and_explicit_candidate_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            args = options(Path(directory) / "run")
            collector.validate_args(collector.build_parser(), args, datetime(2026, 10, 6, tzinfo=timezone.utc))
            self.assertEqual(100, args.max_candidates)
            self.assertEqual(10, args.max_recommendations)
            args = collector.build_parser().parse_args([
                "5.1", "--architecture", "amd64", "--stream", "nightly", "--max-candidates", "5",
            ])
            collector.validate_args(collector.build_parser(), args, datetime(2026, 10, 6, tzinfo=timezone.utc))
            self.assertEqual(5, args.max_candidates)

    def test_supplied_payload_invariants_collect_all_84_rows(self):
        healthy = tag(147634, "5.1.0-0.nightly-2026-10-02-052246")
        latest = tag(147823, "5.1.0-0.nightly-2026-10-05-164628", "Rejected", "2026-10-05T16:46:28Z")
        jobs = {healthy["release_tag"]: rows(16, 0, 42, 26, "147634"),
                latest["release_tag"]: rows(6, 10, 22, 46, "147823")}
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "run"
            _, manifest, payloads, associations = collector.run(
                options(workspace), FakeClient({"5.1": [latest, healthy]}, jobs),
                datetime(2026, 10, 6, tzinfo=timezone.utc))
            self.assertEqual(168, len(associations))
            self.assertEqual([84, 84], [item["job_row_count"] for item in payloads])
            self.assertEqual("2105892780260724700", associations[0]["prow_run_id"])
            self.assertTrue(all(item["prow_bucket"] == "test-platform-results-public" for item in associations))
            self.assertTrue(manifest["complete"])
            self.assertEqual(100, manifest["effective_inputs"]["max_candidates"])
            self.assertEqual(10, manifest["effective_inputs"]["max_recommendations"])

    def test_unknown_role_and_state_remain_visible(self):
        payload = tag(1, "payload")
        raw = job(1, "Async", "Mystery", "1")
        association = collector.normalize_association(raw, payload, "current")
        self.assertEqual("UNKNOWN", association["normalized_role"])
        self.assertEqual("OTHER", association["normalized_outcome"])

    def test_scan_limit_remains_visible_after_post_filtering(self):
        valid = tag(1, "valid")
        for excluded in (dict(tag(2, "wrong-scope"), architecture="arm64"),
                         tag(2, "outside-window", when="2026-09-01T00:00:00Z")):
            with self.subTest(excluded=excluded["release_tag"]), tempfile.TemporaryDirectory() as directory:
                args = options(Path(directory) / "run")
                args.max_payloads_scan = 2
                client = FakeClient({"5.1": [valid, excluded]}, {"valid": rows(1, 0, 0, 1, "1")})
                _, manifest, payloads, _ = collector.run(args, client, datetime(2026, 10, 6, tzinfo=timezone.utc))
                self.assertEqual(["valid"], [item["tag"] for item in payloads])
                self.assertEqual(2, client.requests)
                self.assertTrue(manifest["limits"]["payload_scan_limit_hit"])
                self.assertFalse(manifest["complete"])
                self.assertIn("payload scan bound reached; population is bounded", manifest["missing_evidence"])

    def test_auto_previous_uses_verified_release_order(self):
        current = tag(1, "current")
        previous = tag(2, "previous", release="5.0")
        current_jobs = rows(1, 1, 1, 0, "1")
        previous_jobs = rows(2, 0, 1, 0, "2")
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient({"5.1": [current], "5.0": [previous]},
                                {"current": current_jobs, "previous": previous_jobs}, ["5.1", "5.0", "4.19"])
            _, manifest, payloads, _ = collector.run(options(Path(directory) / "run", "auto-previous", "2"), client,
                                                       datetime(2026, 10, 6, tzinfo=timezone.utc))
            self.assertTrue(manifest["history"]["triggered"])
            self.assertEqual("5.0", manifest["history"]["release"])
            self.assertEqual("previous-release-history", payloads[-1]["population_role"])

    def test_supplied_fixture_summary_is_pinned(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/supplied-live-summary.json").read_text())
        self.assertEqual([84, 84], [item["job_rows"] for item in fixture["payloads"]])
        self.assertEqual(16, fixture["payloads"][1]["blocking"]["Succeeded"])


if __name__ == "__main__":
    unittest.main()
