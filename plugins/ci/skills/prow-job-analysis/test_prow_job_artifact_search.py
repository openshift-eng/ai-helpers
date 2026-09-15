#!/usr/bin/env python3
"""Tests for prow_job_artifact_search.parse_prow_url."""
import unittest

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

    def test_legacy_bucket_remaps_to_public(self):
        url = f"https://prow.ci.openshift.org/view/gs/test-platform-results/{PATH}"
        bucket, path = parse_prow_url(url)
        self.assertEqual(bucket, PUBLIC)
        self.assertEqual(path, PATH)

    def test_archive_bucket_is_preserved(self):
        url = f"https://prow.ci.openshift.org/view/gs/prow-artifact-archive/{PATH}"
        bucket, path = parse_prow_url(url)
        self.assertEqual(bucket, "prow-artifact-archive")
        self.assertEqual(path, PATH)


if __name__ == "__main__":
    unittest.main()
