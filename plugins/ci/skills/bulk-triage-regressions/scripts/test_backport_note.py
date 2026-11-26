#!/usr/bin/env python3
"""Tests for backport_note: backport-candidate evidence only from a complete no-matching-clone check; never writes."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "scripts"))

import backport_note as bn  # noqa: E402
import test_release_target as fx  # noqa: E402  (synthetic Jira fixtures)

RELEASES = {101: "4.30", 201: "4.31"}
CLOSED_NEWER_PARENT = fx.issue("SYNTH-110", "4.31.0", status="Closed")


def checker(*issues):
    jira = fx.store(*issues)
    return lambda key, ids: bn.release_target.check_regressions(key, ids, fetch=jira,
                                                                fetch_regression=lambda rid: {"release": RELEASES[rid]})


class TestBackportNote(unittest.TestCase):

    def run_note(self, issue, ids, *issues):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network write attempted")):
            return bn.backport_note(issue, ids, "4.31", "org/repo#1", "c-1", check=checker(*issues))

    def test_refused_when_a_matching_clone_exists(self):
        self.assertEqual(self.run_note("SYNTH-100", [101], fx.PARENT, fx.CLONE)["status"], "refused")

    def test_refused_when_lookup_incomplete(self):
        self.assertEqual(self.run_note("SYNTH-100", [101], fx.PARENT)["status"], "refused")   # clone unreadable

    def test_refused_for_the_release_target_itself(self):
        self.assertEqual(self.run_note("SYNTH-200", [101], fx.PARENT, fx.CLONE)["status"], "refused")

    def test_refused_without_target_version(self):
        self.assertEqual(self.run_note("SYNTH-120", [101], fx.issue("SYNTH-120", None))["status"], "refused")

    def test_complete_no_clone_yields_evidence_not_a_write(self):
        res = self.run_note("SYNTH-110", [101], CLOSED_NEWER_PARENT)
        self.assertEqual(res["status"], "candidate")
        entry = res["backport_candidates"][0]
        self.assertEqual((entry["this_release"], entry["clone_exists"], entry["fixed_in"]["key"]),
                         ("4.30", False, "SYNTH-110"))
        self.assertFalse(entry["release_check"]["allowed"])          # evidence, never authorization
        self.assertEqual(bn.release_target.validate_record(entry["release_check"], issue="SYNTH-110",
                                                           releases=["4.30"], purpose="no-clone"), [])
        self.assertIn("stay untriaged", res["draft"])
        self.assertFalse(hasattr(bn, "_request"))                     # no Jira write path exists


if __name__ == "__main__":
    unittest.main()
