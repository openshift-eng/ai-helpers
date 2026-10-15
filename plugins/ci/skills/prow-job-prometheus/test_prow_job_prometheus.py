#!/usr/bin/env python3
"""Tests for load_snapshot.py and promql.py."""
import io
import os
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import load_snapshot  # noqa: E402
import promql  # noqa: E402

RUN = "logs/periodic-ci-openshift-release-main-ci-5.1-e2e-aws-ovn-techpreview/2109982696762511360"


class TestParseRunPath(unittest.TestCase):
    def test_url_forms(self):
        for url in [
            f"https://prow.ci.openshift.org/view/gs/test-platform-results-public/{RUN}",
            f"https://gcs.ci.openshift.org/gcs/test-platform-results-public/{RUN}/artifacts/e2e-aws-ovn-techpreview/gather-extra/",
            f"https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results-public/{RUN}/",
            f"gs://test-platform-results-public/{RUN}",
            f"https://prow.ci.openshift.org/view/gs/test-platform-results/{RUN}",
        ]:
            with self.subTest(url=url):
                self.assertEqual(load_snapshot.parse_run_path(url), RUN)

    def test_pr_logs(self):
        path = "pr-logs/pull/openshift_origin/31759/pull-ci-openshift-origin-main-e2e-aws/2110000000000000000"
        url = f"https://prow.ci.openshift.org/view/gs/test-platform-results-public/{path}"
        self.assertEqual(load_snapshot.parse_run_path(url), path)

    def test_rejects_other_urls(self):
        with self.assertRaises(ValueError):
            load_snapshot.parse_run_path("https://example.com/foo")


class TestChooseStep(unittest.TestCase):
    def test_choose_step(self):
        found = {"e2e-aws": "a/", "e2e-aws-upgrade": "b/"}
        self.assertEqual(load_snapshot.choose_step({"e2e-aws": "a/"}, None), "e2e-aws")
        self.assertEqual(load_snapshot.choose_step(found, "e2e-aws-upgrade"), "e2e-aws-upgrade")
        with self.assertRaises(ValueError):
            load_snapshot.choose_step(found, None)
        with self.assertRaises(ValueError):
            load_snapshot.choose_step({}, None)


class TestSafeExtract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _tar(self, members):
        path = os.path.join(self.tmp.name, "t.tar.gz")
        with tarfile.open(path, "w:gz") as tf:
            for name, data in members:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        return path

    def test_extracts_files(self):
        out = os.path.join(self.tmp.name, "out")
        load_snapshot.safe_extract(self._tar([("wal/00000000", b"abc"), ("chunks_head/000001", b"x")]), out)
        with open(os.path.join(out, "wal", "00000000"), "rb") as f:
            self.assertEqual(f.read(), b"abc")

    def test_rejects_traversal(self):
        for name in ["../evil", "/abs/evil"]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    load_snapshot.safe_extract(self._tar([(name, b"x")]), os.path.join(self.tmp.name, "out"))


class TestFormat(unittest.TestCase):
    def test_format_range(self):
        result = [
            {"metric": {"instance": "a"}, "values": [[0, "1"], [60, "2"]]},
            {"metric": {"instance": "b"}, "values": [[60, "5"]]},
        ]
        out = promql.format_range(result, "instance").splitlines()
        self.assertEqual(out[0].split(), ["time", "b", "a"])  # ordered by peak value
        self.assertEqual(out[1].split(), ["00:00:00", "-", "1"])
        self.assertEqual(out[2].split(), ["00:01:00", "5", "2"])

    def test_format_instant(self):
        result = [{"metric": {"job": "etcd"}, "value": [0, "1"]}, {"metric": {"job": "apiserver"}, "value": [0, "3"]}]
        self.assertEqual(promql.format_instant(result, "job").splitlines()[0].split(), ["3", "apiserver"])


if __name__ == "__main__":
    unittest.main()
