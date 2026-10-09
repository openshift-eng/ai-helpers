#!/usr/bin/env python3
"""Tests for prow_job_artifact_search URL parsing and fetch windows."""
import unittest
from unittest import mock

import prow_job_artifact_search as pjas
from prow_job_artifact_search import parse_prow_url


PUBLIC = "test-platform-results-public"
PATH = "logs/periodic-ci-example/1856789012345678848"


class ParseProwURLTest(unittest.TestCase):
    def test_public_prow_url(self):
        url = f"https://prow.ci.openshift.org/view/gs/{PUBLIC}/{PATH}"
        bucket, path = parse_prow_url(url)
        self.assertEqual(bucket, PUBLIC)
        self.assertEqual(path, PATH)

    def test_public_gcsweb_url(self):
        url = (
            "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/"
            f"{PUBLIC}/{PATH}"
        )
        bucket, path = parse_prow_url(url)
        self.assertEqual(bucket, PUBLIC)
        self.assertEqual(path, PATH)

    def test_url_bucket_is_preserved(self):
        url = f"https://prow.ci.openshift.org/view/gs/test-platform-results/{PATH}"
        bucket, path = parse_prow_url(url)
        self.assertEqual(bucket, "test-platform-results")
        self.assertEqual(path, PATH)

    def test_archive_bucket_is_preserved(self):
        url = f"https://prow.ci.openshift.org/view/gs/prow-artifact-archive/{PATH}"
        bucket, path = parse_prow_url(url)
        self.assertEqual(bucket, "prow-artifact-archive")
        self.assertEqual(path, PATH)

    def test_arbitrary_bucket_is_preserved(self):
        url = f"https://prow.ci.openshift.org/view/gs/origin-ci-test/{PATH}"
        bucket, path = parse_prow_url(url)
        self.assertEqual(bucket, "origin-ci-test")
        self.assertEqual(path, PATH)

    def test_gs_uri_bucket_is_preserved(self):
        bucket, path = parse_prow_url(f"gs://test-platform-results/{PATH}")
        self.assertEqual(bucket, "test-platform-results")
        self.assertEqual(path, PATH)

    def test_rejects_missing_path(self):
        with self.assertRaises(ValueError):
            parse_prow_url(
                "https://prow.ci.openshift.org/view/gs/test-platform-results-public/"
            )


class FakeResponse:
    def __init__(self, body, status=200, headers=None):
        self._body = body
        self.status = status
        self.headers = headers or {}

    def read(self, n=-1):
        return self._body if n is None or n < 0 else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FetchWindowTest(unittest.TestCase):
    BODY = b"0123456789"

    def test_select_window_head_and_tail(self):
        self.assertEqual(pjas._select_window(self.BODY, 4), b"0123")
        self.assertEqual(pjas._select_window(self.BODY, 4, tail=True), b"6789")
        self.assertEqual(pjas._select_window(self.BODY, 0, tail=True), b"")

    def test_tail_uses_partial_content_response(self):
        resp = FakeResponse(b"6789", status=206, headers={"Content-Range": "bytes 6-9/10"})
        with mock.patch("urllib.request.urlopen", return_value=resp) as urlopen:
            size, truncated, content = pjas._http_fetch("b", "o", 4, tail=True)
        self.assertEqual(urlopen.call_args[0][0].get_header("Range"), "bytes=-4")
        self.assertEqual((size, truncated, content), (10, True, "6789"))

    def test_tail_falls_back_when_range_ignored(self):
        resp = FakeResponse(self.BODY, status=200, headers={"Content-Length": "10"})
        with mock.patch("urllib.request.urlopen", return_value=resp):
            self.assertEqual(pjas._http_fetch("b", "o", 4, tail=True), (10, True, "6789"))

    def test_head_fetch_unchanged(self):
        resp = FakeResponse(self.BODY, status=200, headers={"Content-Length": "10"})
        with mock.patch("urllib.request.urlopen", return_value=resp) as urlopen:
            self.assertEqual(pjas._http_fetch("b", "o", 4), (10, True, "0123"))
        self.assertIsNone(urlopen.call_args[0][0].get_header("Range"))


if __name__ == "__main__":
    unittest.main()
