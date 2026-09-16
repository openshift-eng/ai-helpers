#!/usr/bin/env python3
"""Tests for remapping the legacy GCS bucket in payload-snapshot."""

import importlib.util
import os
import unittest
from unittest.mock import patch


_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "payload_snapshot_gcs_remap", os.path.join(_HERE, "payload_snapshot.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _load_module()

JOB_PATH = (
    "logs/periodic-ci-openshift-release-master-okd-scos-4.20-e2e-aws-ovn-techpreview/"
    "1964725888612306944"
)
PUBLIC = "test-platform-results-public"
LEGACY = "test-platform-results"
ARCHIVE = "prow-artifact-archive"


class RemapLegacyGCSBucketTest(unittest.TestCase):
    def test_legacy_bucket_remaps_to_public(self):
        self.assertEqual(
            ps._remap_legacy_gcs_bucket(f"{LEGACY}/{JOB_PATH}"),
            f"{PUBLIC}/{JOB_PATH}",
        )

    def test_public_bucket_is_unchanged(self):
        path = f"{PUBLIC}/{JOB_PATH}"
        self.assertEqual(ps._remap_legacy_gcs_bucket(path), path)

    def test_archive_bucket_is_preserved(self):
        path = f"{ARCHIVE}/{JOB_PATH}"
        self.assertEqual(ps._remap_legacy_gcs_bucket(path), path)

    def test_bare_legacy_bucket_remaps(self):
        self.assertEqual(ps._remap_legacy_gcs_bucket(LEGACY), PUBLIC)


class ProwURLToGCSBucketPathTest(unittest.TestCase):
    def test_legacy_prow_url_remaps(self):
        url = f"https://prow.ci.openshift.org/view/gs/{LEGACY}/{JOB_PATH}"
        self.assertEqual(
            ps._prow_url_to_gcs_bucket_path(url),
            f"{PUBLIC}/{JOB_PATH}",
        )

    def test_public_prow_url_is_unchanged(self):
        url = f"https://prow.ci.openshift.org/view/gs/{PUBLIC}/{JOB_PATH}"
        self.assertEqual(
            ps._prow_url_to_gcs_bucket_path(url),
            f"{PUBLIC}/{JOB_PATH}",
        )

    def test_archive_prow_url_is_preserved(self):
        url = f"https://prow.ci.openshift.org/view/gs/{ARCHIVE}/{JOB_PATH}"
        self.assertEqual(
            ps._prow_url_to_gcs_bucket_path(url),
            f"{ARCHIVE}/{JOB_PATH}",
        )

    def test_empty_or_non_prow_url_returns_none(self):
        self.assertIsNone(ps._prow_url_to_gcs_bucket_path(""))
        self.assertIsNone(
            ps._prow_url_to_gcs_bucket_path("https://example.com/job")
        )


class ResolveProwStateTest(unittest.TestCase):
    def test_legacy_url_fetches_public_prowjob_json(self):
        captured = {}

        def fake_fetch(url, timeout=10):
            captured["url"] = url
            return {"status": {"state": "success"}}

        rc = ps.ReleaseController()
        with patch.object(ps, "try_fetch_json", side_effect=fake_fetch):
            state = rc.resolve_prow_state(
                f"https://prow.ci.openshift.org/view/gs/{LEGACY}/{JOB_PATH}"
            )

        self.assertEqual(state, "Succeeded")
        self.assertEqual(
            captured["url"],
            f"{ps.GCSWEB_BASE}/{PUBLIC}/{JOB_PATH}/prowjob.json",
        )
        self.assertNotIn(f"/{LEGACY}/", captured["url"])

    def test_archive_url_keeps_archive_bucket(self):
        captured = {}

        def fake_fetch(url, timeout=10):
            captured["url"] = url
            return {"status": {"state": "failure"}}

        rc = ps.ReleaseController()
        with patch.object(ps, "try_fetch_json", side_effect=fake_fetch):
            state = rc.resolve_prow_state(
                f"https://prow.ci.openshift.org/view/gs/{ARCHIVE}/{JOB_PATH}"
            )

        self.assertEqual(state, "Failed")
        self.assertEqual(
            captured["url"],
            f"{ps.GCSWEB_BASE}/{ARCHIVE}/{JOB_PATH}/prowjob.json",
        )


if __name__ == "__main__":
    unittest.main()
