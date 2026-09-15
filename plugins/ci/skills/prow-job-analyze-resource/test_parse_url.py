#!/usr/bin/env python3
"""Tests for parse_url.parse_prowjob_url."""
import unittest

from parse_url import parse_prowjob_url


PUBLIC = "test-platform-results-public"
PATH = (
    "pr-logs/pull/30393/pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn/"
    "1978913325970362368"
)


class ParseProwjobURLTest(unittest.TestCase):
    def test_gcsweb_public_url(self):
        url = (
            "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/"
            f"{PUBLIC}/{PATH}/"
        )
        got = parse_prowjob_url(url)
        self.assertEqual(got["bucket"], PUBLIC)
        self.assertEqual(got["bucket_path"], PATH)
        self.assertEqual(got["gcs_base_path"], f"gs://{PUBLIC}/{PATH}/")
        self.assertEqual(got["build_id"], "1978913325970362368")

    def test_prow_gs_public_url(self):
        url = f"https://prow.ci.openshift.org/view/gs/{PUBLIC}/{PATH}"
        got = parse_prowjob_url(url)
        self.assertEqual(got["bucket"], PUBLIC)
        self.assertEqual(got["gcs_base_path"], f"gs://{PUBLIC}/{PATH}/")

    def test_legacy_bucket_remaps_to_public(self):
        url = (
            "https://prow.ci.openshift.org/view/gs/test-platform-results/"
            f"{PATH}"
        )
        got = parse_prowjob_url(url)
        self.assertEqual(got["bucket"], PUBLIC)
        self.assertEqual(got["bucket_path"], PATH)
        self.assertEqual(got["gcs_base_path"], f"gs://{PUBLIC}/{PATH}/")
        self.assertNotIn("gs://test-platform-results/", got["gcs_base_path"])

    def test_rejects_url_without_gs_or_gcs(self):
        with self.assertRaises(ValueError) as ctx:
            parse_prowjob_url("https://example.com/logs/job/1234567890")
        self.assertIn("/gs/<bucket>/", str(ctx.exception))
        self.assertIn("/gcs/<bucket>/", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
