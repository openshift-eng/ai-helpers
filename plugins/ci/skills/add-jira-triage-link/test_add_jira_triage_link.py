#!/usr/bin/env python3
"""Tests for the add-jira-triage-link release gate (synthetic data, no network)."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))

import add_jira_triage_link as al  # noqa: E402
import test_release_target as fx  # noqa: E402  (synthetic Jira fixtures)

RELEASES = {101: "4.30", 201: "4.31"}


def triage(key, ids):
    return {"id": 9, "url": "https://example.atlassian.net/browse/" + key, "regressions": [{"id": i} for i in ids]}


def checker():
    jira = fx.store(fx.PARENT, fx.CLONE)
    return lambda key, ids: al.release_target.check_regressions(key, ids, fetch=jira,
                                                                fetch_regression=lambda rid: {"release": RELEASES[rid]})


class TestReleaseGate(unittest.TestCase):

    def gate(self, t):
        return lambda key, tid: al.check_triage_release(key, tid, fetch_triage=lambda _: t, check=checker())

    def test_refused_gate_writes_nothing(self):
        with mock.patch.object(al, "_add_triage_link") as write:
            res = al.add_triage_link("SYNTH-100", 9, auth=None, release_gate=self.gate(triage("SYNTH-100", [101])))
        write.assert_not_called()
        self.assertFalse(res["success"])
        self.assertEqual(res["release_check"]["releases"]["4.30"]["target"], "SYNTH-200")

    def test_triage_pointing_elsewhere_is_refused(self):
        rec = al.check_triage_release("SYNTH-200", 9, fetch_triage=lambda _: triage("SYNTH-100", [101]), check=checker())
        self.assertFalse(rec["allowed"])
        self.assertIn("points at SYNTH-100", rec["reasons"][0])

    def test_unreadable_triage_is_refused(self):
        rec = al.check_triage_release("SYNTH-200", 9, fetch_triage=lambda _: 1 / 0)
        self.assertFalse(rec["allowed"])

    def test_matching_target_is_written_with_evidence(self):
        with mock.patch.object(al, "_add_triage_link", return_value={"success": True, "issue_key": "SYNTH-200"}) as write:
            res = al.add_triage_link("SYNTH-200", 9, auth=None, release_gate=self.gate(triage("SYNTH-200", [101])))
        write.assert_called_once()
        self.assertTrue(res["success"])
        self.assertTrue(res["release_check"]["allowed"])

    def test_no_gate_keeps_existing_behaviour(self):
        with mock.patch.object(al, "_add_triage_link", return_value={"success": True}) as write:
            res = al.add_triage_link("SYNTH-100", 9, auth=None)
        write.assert_called_once()
        self.assertNotIn("release_check", res)


if __name__ == "__main__":
    unittest.main()
