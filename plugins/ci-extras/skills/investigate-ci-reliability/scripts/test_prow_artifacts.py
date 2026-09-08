"""Offline tests. Temporary data goes under ~/tmp, never system /tmp."""
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

spec = importlib.util.spec_from_file_location("prow_artifacts", Path(__file__).with_name("prow_artifacts.py"))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
RUN = "logs/a-job/2093824069861380096"


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def __call__(self, request, timeout):
        self.urls.append(request.full_url)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(value)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        base = Path.home() / "tmp" / "ci-reliability-tests"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)

    def client(self, responses, **kwargs):
        http = FakeHTTP(responses)
        return p.Client(RUN, self.temp.name, opener=http, sleeper=lambda _: None, **kwargs), http

    def test_url_validation_and_artifact_boundary(self):
        valid = "https://prow.ci.openshift.org/view/gs/test-platform-results/" + RUN
        self.assertEqual(p.parse_run_url(valid), RUN)
        self.assertEqual(p.parse_run_url("gs://test-platform-results/" + RUN), RUN)
        for bad in (valid + "/build-log.txt", valid + "?x=1", valid.replace("prow.ci.openshift.org", "evil.example"),
                    valid.replace("a-job", "%2e%2e"), valid.replace("a-job", "a/../b"), valid.replace("https:", "http:")):
            with self.assertRaises(p.ArtifactError, msg=bad):
                p.parse_run_url(bad)
        for obj in ("/absolute", "../secret", "a/../secret", "a//b", "a\\b"):
            with self.assertRaises(p.ArtifactError):
                p.object_url(RUN, obj)

    def test_tide_batch_run_and_recorded_child(self):
        batch = "pr-logs/pull/batch/pull-ci-Azure-ARO-HCP-main-config-change-detection/2093003352324444160"
        url = "https://prow.ci.openshift.org/view/gs/test-platform-results/" + batch
        self.assertEqual(p.parse_run_url(url), batch)
        self.assertEqual(p.parse_run_url("gs://test-platform-results/" + batch), batch)
        children = p.recorded_children(json.dumps({"children": [url + "/build-log.txt"]}), RUN, "batch.json")
        self.assertEqual(children["child_candidates"][0]["run"], batch)
        self.assertEqual(children["child_candidates"][0]["evidence"][0]["location"], "/children/0")
        for bad in (url + "/extra", url.replace("/batch/", "/batch/../"), url.replace("2093003352324444160", "123")):
            with self.assertRaises(p.ArtifactError):
                p.parse_run_url(bad)

    def test_pagination_and_object_cap_are_explicit(self):
        a = {"items": [{"name": RUN + "/artifacts/a", "size": "2"}], "nextPageToken": "next"}
        b = {"items": [{"name": RUN + "/artifacts/b", "size": "2"}, {"name": RUN + "/artifacts/c", "size": "2"}]}
        client, http = self.client([json.dumps(x).encode() for x in (a, b)])
        result = client.list("artifacts/", max_objects=2)
        self.assertEqual([x["object"] for x in result["objects"]], ["artifacts/a", "artifacts/b"])
        self.assertTrue(result["truncated"])
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(http.urls[1]).query)["pageToken"], ["next"])
        self.assertTrue(all(page["sha256"] for page in result["pages"]))

    def test_out_of_prefix_listing_rejected(self):
        client, _ = self.client([json.dumps({"items": [{"name": "logs/other/1234567890/x"}]}).encode()])
        with self.assertRaises(p.ArtifactError):
            client.list("artifacts/")

    def test_byte_limit_stops_body_and_does_not_cache_partial(self):
        client, http = self.client([b"123456"], maximum=5)
        with self.assertRaises(p.ArtifactError):
            client.fetch("build-log.txt")
        self.assertEqual(len(http.urls), 1)
        with self.assertRaises(p.ArtifactError):
            client.fetch("another-object")
        self.assertEqual(len(http.urls), 1)
        self.assertFalse(list(Path(self.temp.name).rglob("*.data")))

    def test_cache_digest_revalidation_and_provenance(self):
        client, http = self.client([b"original", b"updated!"])
        first, proof = client.fetch("build-log.txt")
        second, cached = client.fetch("build-log.txt")
        self.assertEqual(first, second)
        self.assertTrue(cached["cache_hit"])
        self.assertEqual(len(http.urls), 1)
        Path(proof["cache_path"]).write_bytes(b"tampered")
        third, new = client.fetch("build-log.txt")
        self.assertEqual(third, b"updated!")
        self.assertEqual(new["sha256"], p.digest(third))
        self.assertFalse(new["cache_hit"])

    def test_retryable_http_and_nonretryable_404(self):
        unavailable = urllib.error.HTTPError("https://storage.googleapis.com/x", 503, "unavailable", {}, None)
        client, http = self.client([unavailable, b"ok"])
        self.assertEqual(client.fetch("x")[0], b"ok")
        self.assertEqual(len(http.urls), 2)
        missing = urllib.error.HTTPError("https://storage.googleapis.com/x", 404, "missing", {}, None)
        client, http = self.client([missing, b"unexpected"])
        with self.assertRaises(p.ArtifactError):
            client.fetch("not-found")
        self.assertEqual(len(http.urls), 1)

    def test_junit_retries_lifecycle_skips_and_identity(self):
        xml = b'''<testsuites><testsuite name="suite"><testcase name="retry" classname="C" lifecycle="blocking"><failure>first</failure></testcase><testcase name="retry" classname="C" lifecycle="blocking"/><testcase name="info"><properties><property name="lifecycle" value="informing"/></properties><failure>noise</failure></testcase><testcase name="unknown"><error>boom</error></testcase><testcase name="skip"><skipped>not supported</skipped></testcase><testcase name="red" lifecycle="blocking"><failure>red</failure></testcase></testsuite></testsuites>'''
        attempts = p.junit_attempts(xml, "artifacts/step/junit.xml")
        result = p.summarize_junit(attempts)
        by_name = {c["name"]: c for c in result["cases"]}
        self.assertEqual(by_name["retry"]["classification"], "mixed_success_failure")
        self.assertTrue(by_name["retry"]["policy_review_required"])
        self.assertFalse(by_name["unknown"]["blocking_failure"])
        self.assertEqual(result["evaluated_cases"], 4)
        self.assertEqual(result["blocking_failure_cases"], 1)
        self.assertEqual(result["informing_failure_cases"], 1)
        self.assertEqual(by_name["retry"]["classname"], "C")
        self.assertEqual(by_name["retry"]["suite"], ["suite"])
        # Same name in another step is not a retry of the first step.
        other = p.junit_attempts(b'<testsuite name="suite"><testcase name="red" lifecycle="blocking"/></testsuite>', "artifacts/other/junit.xml")
        self.assertEqual(len(p.summarize_junit(attempts + other)["cases"]), 6)

    def test_namespaced_xml_and_suite_error_are_preserved(self):
        xml = b'<testsuite xmlns="urn:junit" name="setup" tests="1" errors="1"><error message="runner died">stack</error><testcase name="case"><properties><property name="lifecycle" value="informing"/></properties><failure>detail</failure></testcase></testsuite>'
        attempts = p.junit_attempts(xml, "junit.xml")
        self.assertEqual(attempts[0]["lifecycle"], "informing")
        self.assertEqual(attempts[0]["failure_text"], "detail")
        report = p.suite_reports(xml, "junit.xml")[0]
        self.assertEqual(report["suite_errors"][0]["message"], "runner died")
        self.assertEqual(report["declared_counts"]["errors"], "1")

    def test_children_only_recorded_urls_keep_missing_edges_unknown(self):
        child = "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/child/2093824069861380097"
        text = json.dumps({"attempts": [{"url": child}, {"url": child + "/build-log.txt"}], "missing_id": "2093824069861380098"})
        result = p.recorded_children(text, RUN, "aggregate.json")
        self.assertEqual(len(result["child_candidates"]), 1)
        self.assertEqual(len(result["child_candidates"][0]["evidence"]), 2)
        self.assertEqual(result["child_candidates"][0]["evidence"][0]["location"], "/attempts/0/url")
        self.assertIn("unknown", result["missing_edges"])
        self.assertNotIn("2093824069861380098", json.dumps(result))
        capped = p.recorded_children(text, RUN, "aggregate.json", max_objects=1)
        self.assertTrue(capped["truncated"])
        self.assertEqual(len(capped["child_candidates"][0]["evidence"]), 1)


if __name__ == "__main__":
    unittest.main()
