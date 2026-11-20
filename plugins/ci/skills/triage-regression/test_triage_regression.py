#!/usr/bin/env python3
"""Tests for triage_regression payload building."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import triage_regression as tr  # noqa: E402


class TestResolvedForwarding(unittest.TestCase):

    def test_resolved_time_uses_offset_not_z(self):
        mgr = tr.TriageManager([33639], "token", "https://redhat.atlassian.net/browse/OCPBUGS-1",
                               "product", None, 456)
        mgr._resolved = {"Time": "2026-10-07T18:07:00Z", "Valid": True}
        mgr._resolution_reason = "jira-progression"
        payload = mgr._build_payload()
        self.assertEqual(payload["resolved"]["Time"], "2026-10-07T18:07:00+00:00")
        self.assertIs(payload["resolved"]["Valid"], True)
        self.assertEqual(payload["resolution_reason"], "jira-progression")

    def test_resolved_none_passthrough(self):
        mgr = tr.TriageManager([33639], "token", "https://redhat.atlassian.net/browse/OCPBUGS-1",
                               "product", None, 456)
        mgr._resolved = None
        payload = mgr._build_payload()
        self.assertNotIn("resolved", payload)
        self.assertIsNone(tr.normalize_resolved(None))

    def test_normalize_leaves_offset_form_alone(self):
        original = {"Time": "2026-10-07T18:07:00+00:00", "Valid": True}
        result = tr.normalize_resolved(original)
        self.assertEqual(result, original)
        self.assertIsNot(result, original)


SCRIPTS = os.path.join(HERE, "..", "..", "scripts")
sys.path.insert(0, SCRIPTS)
import release_target  # noqa: E402
import test_release_target as fx  # noqa: E402  (synthetic Jira fixtures)

import json  # noqa: E402
import io  # noqa: E402
from unittest import mock  # noqa: E402

SIPPY_RELEASES = {101: "4.30", 102: "4.30", 201: "4.31"}
CLOSED_NEWER_PARENT = fx.issue("SYNTH-110", "4.31.0", status="Closed")      # no clone for 4.30
UNTARGETED = fx.issue("SYNTH-120", None)
AMBIGUOUS = [fx.issue("SYNTH-130", "4.31.0", links=[fx.link("Cloners", "in", "SYNTH-131"), fx.link("Cloners", "in", "SYNTH-132")]),
             fx.issue("SYNTH-131", "4.30.z"), fx.issue("SYNTH-132", "4.30.0")]
INCOMPLETE = fx.issue("SYNTH-140", "4.31.0", links=[fx.link("Cloners", "in", "SYNTH-141")])   # SYNTH-141 unreadable


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestReleaseGateConsumerPath(unittest.TestCase):
    """End to end through TriageManager: the release gate runs before any Sippy write."""

    def setUp(self):
        self.sent = []
        jira = fx.store(fx.PARENT, fx.CLONE, fx.BLOCKED, CLOSED_NEWER_PARENT, UNTARGETED, INCOMPLETE, *AMBIGUOUS)

        def fake_get_json(url, headers=None):
            rid = int(url.rstrip("/").rsplit("/", 1)[-1])
            return {"release": SIPPY_RELEASES[rid]}
        self.patches = [mock.patch.object(release_target, "jira_fetcher", lambda auth=None: jira),
                        mock.patch.object(release_target, "_get_json", fake_get_json)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def urlopen(self, existing=None):
        def fake(req, timeout=None):
            self.sent.append((req.get_method(), req.full_url, req.data))
            if req.get_method() == "GET":
                return _Resp(json.dumps(existing).encode())
            body = json.loads(req.data)
            return _Resp(json.dumps(dict(body, id=777)).encode())
        return mock.patch.object(tr.urllib.request, "urlopen", fake)

    def manager(self, ids, key, triage_id=None):
        return tr.TriageManager(ids, "token", "https://example.atlassian.net/browse/" + key if key else None,
                                "product", "d", triage_id, release_gate=tr.default_release_gate)

    def test_wrong_release_target_is_refused_before_any_write(self):
        with self.urlopen():
            res = self.manager([101, 102], "SYNTH-100").create()
        self.assertFalse(res["success"])
        self.assertEqual(self.sent, [])
        self.assertEqual(res["release_check"]["releases"]["4.30"]["target"], "SYNTH-200")
        self.assertIn("nothing was sent", res["error"])

    def test_closed_newer_release_parent_without_clone_is_refused_with_zero_http(self):
        with self.urlopen():
            res = self.manager([101, 102], "SYNTH-110").create()
        self.assertFalse(res["success"])
        self.assertEqual(self.sent, [])                       # no Sippy call at all
        d = res["release_check"]["releases"]["4.30"]
        self.assertEqual((d["decision"], d["target"], d["complete"]), ("no-matching-clone", None, True))

    def test_candidate_without_target_version_is_refused_with_zero_http(self):
        with self.urlopen():
            res = self.manager([101], "SYNTH-120").create()
        self.assertFalse(res["success"])
        self.assertEqual(self.sent, [])
        self.assertEqual(res["release_check"]["releases"]["4.30"]["decision"], "unknown")

    def test_ambiguous_or_incomplete_family_is_refused_with_zero_http(self):
        for key, decision in (("SYNTH-130", "ambiguous"), ("SYNTH-140", "unknown")):
            with self.urlopen():
                res = self.manager([101], key).create()
            self.assertFalse(res["success"], key)
            self.assertEqual(self.sent, [], key)
            self.assertEqual(res["release_check"]["releases"]["4.30"]["decision"], decision)

    def test_suggested_clone_is_written_only_after_revalidation_as_candidate(self):
        with self.urlopen():
            refused = self.manager([101], "SYNTH-100").create()
        suggested = refused["release_check"]["releases"]["4.30"]["target"]
        self.assertEqual((refused["success"], suggested, self.sent), (False, "SYNTH-200", []))   # nothing rerouted
        with self.urlopen():
            res = self.manager([101], suggested).create()        # caller supplies the clone; gate re-runs
        self.assertTrue(res["success"], res.get("error"))
        self.assertEqual(res["release_check"]["releases"]["4.30"]["decision"], "self")
        method, _, body = self.sent[0]
        self.assertEqual((method, json.loads(body)["url"]), ("POST", "https://example.atlassian.net/browse/SYNTH-200"))

    def test_matching_release_target_is_written_with_evidence(self):
        with self.urlopen():
            res = self.manager([101, 102], "SYNTH-200").create()
        self.assertTrue(res["success"], res.get("error"))
        self.assertEqual([m for m, _, _ in self.sent], ["POST"])
        self.assertTrue(res["release_check"]["allowed"])
        self.assertEqual(res["release_check"]["releases"]["4.30"]["decision"], "self")

    def test_update_checks_only_added_regressions_against_existing_url(self):
        existing = {"id": 5, "url": "https://example.atlassian.net/browse/SYNTH-100", "type": "product",
                    "description": "", "regressions": [{"id": 201}]}
        with self.urlopen(existing):
            res = self.manager([101], None, triage_id=5).update()
        self.assertFalse(res["success"])
        self.assertEqual([m for m, _, _ in self.sent], ["GET"])      # no PUT
        self.assertEqual(sorted(res["release_check"]["regression_releases"]), ["101"])
        self.sent.clear()
        with self.urlopen(existing):
            res = self.manager([201], None, triage_id=5).update()
        self.assertTrue(res["success"], res.get("error"))
        self.assertEqual([m for m, _, _ in self.sent], ["GET", "PUT"])

    def test_gate_errors_fail_closed(self):
        mgr = tr.TriageManager([101], "token", "https://example.atlassian.net/browse/SYNTH-200", "product",
                               release_gate=lambda url, ids: 1 / 0)
        with self.urlopen():
            res = mgr.create()
        self.assertFalse(res["success"])
        self.assertEqual(self.sent, [])

    def test_without_gate_behaviour_is_unchanged(self):
        mgr = tr.TriageManager([101], "token", "https://example.atlassian.net/browse/SYNTH-100", "product")
        with self.urlopen():
            res = mgr.create()
        self.assertTrue(res["success"])
        self.assertNotIn("release_check", res)

    def test_cli_flag_enables_gate(self):
        argv = ["triage_regression.py", "101", "--token", "t", "--url",
                "https://example.atlassian.net/browse/SYNTH-100", "--type", "product", "--require-release-target"]
        with self.urlopen(), mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", new=io.StringIO()) as out:
            rc = tr.main()
        self.assertEqual(rc, 1)
        self.assertEqual(self.sent, [])
        self.assertFalse(json.loads(out.getvalue())["success"])


if __name__ == '__main__':
    unittest.main()
