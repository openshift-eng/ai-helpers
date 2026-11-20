#!/usr/bin/env python3
"""Tests for backport_note: the "no clone" note is only rendered from a complete no-matching-clone check."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "scripts"))

import backport_note as bn  # noqa: E402
import test_release_target as fx  # noqa: E402  (synthetic Jira fixtures)

RELEASES = {101: "4.30", 201: "4.31"}


def checker(*issues):
    jira = fx.store(*issues)
    return lambda key, ids: bn.release_target.check_regressions(key, ids, fetch=jira,
                                                                fetch_regression=lambda rid: {"release": RELEASES[rid]})


class FakeJira:
    def __init__(self, comments=(), total=None):
        self.calls, self.comments = [], list(comments)
        self.total = len(self.comments) if total is None else total

    def __call__(self, method, path, data=None):
        self.calls.append((method, path))
        if method == "GET":
            return {"total": self.total, "comments": self.comments}
        return {"id": "42", "created": "2026-01-01T00:00:00.000+0000"}


class TestBackportNote(unittest.TestCase):

    def run_note(self, issue, ids, *issues, jira=None, post=True):
        jira = jira or FakeJira()
        res = bn.backport_note(issue, ids, "4.31", "org/repo#1", "https://example.com/pr/1", post=post,
                               check=checker(*issues), request=jira)
        return res, jira

    def test_refused_when_a_matching_clone_exists(self):
        res, jira = self.run_note("SYNTH-100", [101], fx.PARENT, fx.CLONE)
        self.assertEqual(res["status"], "refused")
        self.assertEqual(jira.calls, [])

    def test_refused_when_lookup_incomplete(self):
        res, jira = self.run_note("SYNTH-100", [101], fx.PARENT)          # clone unreadable
        self.assertEqual(res["status"], "refused")
        self.assertEqual(jira.calls, [])

    def test_refused_for_the_release_target_itself(self):
        res, jira = self.run_note("SYNTH-200", [101], fx.PARENT, fx.CLONE)   # decision "self", not a backport gap
        self.assertEqual(res["status"], "refused")

    def test_posts_with_evidence_after_complete_search(self):
        parent = fx.issue("SYNTH-110", "4.31.0", status="Closed")
        res, jira = self.run_note("SYNTH-110", [101], parent)
        self.assertEqual(res["status"], "posted")
        self.assertEqual([m for m, _ in jira.calls], ["GET", "POST"])
        self.assertIn("no issue in this bug's clone family (1 checked", res["text"])
        self.assertIn("Target Version 4.30", res["text"])

    def test_dry_run_and_dedupe(self):
        parent = fx.issue("SYNTH-110", "4.31.0", status="Closed")
        res, jira = self.run_note("SYNTH-110", [101], parent, post=False)
        self.assertEqual((res["status"], jira.calls), ("dry-run", []))
        body, _ = bn.render(["4.30"], "4.31", "org/repo#1", None, {"family": [], "checked_at": "t"})
        res, jira = self.run_note("SYNTH-110", [101], parent, jira=FakeJira([{"body": body}]))
        self.assertEqual(res["status"], "skipped")
        res, jira = self.run_note("SYNTH-110", [101], parent, jira=FakeJira([], total=500))
        self.assertEqual(res["status"], "refused")
        self.assertEqual([m for m, _ in jira.calls], ["GET"])


if __name__ == "__main__":
    unittest.main()
