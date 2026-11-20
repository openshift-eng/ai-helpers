#!/usr/bin/env python3
"""Tests for fetch_jira_issue field selection and parsing (synthetic data, no network)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fetch_jira_issue as fji  # noqa: E402

LEGACY_KEYS = {"key", "url", "summary", "description", "status", "resolution", "priority", "assignee", "reporter",
               "components", "labels", "fix_versions", "created", "updated", "comment_count", "comments",
               "linked_prs", "progress"}


def fetcher():
    f = fji.JiraIssueFetcher.__new__(fji.JiraIssueFetcher)
    f.jira_key = "SYNTH-1"
    return f


class TestFields(unittest.TestCase):

    def test_requests_release_routing_fields(self):
        for name in ("issuelinks", "versions", "fixVersions", fji.release_target.TARGET_VERSION_FIELD):
            self.assertIn(name, fji.JiraIssueFetcher.FIELDS)

    def test_parse_preserves_links_and_versions(self):
        raw = {"key": "SYNTH-1", "fields": {
            "summary": "s", "status": {"name": "ON_QA"}, "fixVersions": [{"name": "4.31.0"}],
            "versions": [{"name": "4.31"}], fji.release_target.TARGET_VERSION_FIELD: [{"name": "4.30.z"}],
            "issuelinks": [{"type": {"name": "Cloners", "inward": "is cloned by", "outward": "clones"},
                            "outwardIssue": {"key": "SYNTH-0"}}],
            "comment": {"comments": []}}}
        out = fetcher().parse(raw)
        self.assertTrue(LEGACY_KEYS <= set(out))
        self.assertEqual(out["fix_versions"], ["4.31.0"])
        self.assertEqual(out["affects_versions"], ["4.31"])
        self.assertEqual(out["target_versions"], ["4.30.z"])
        self.assertEqual(out["target_releases"], ["4.30"])
        self.assertEqual(out["links"], [{"type": "Cloners", "direction": "outward", "relation": "clones", "key": "SYNTH-0"}])
        self.assertIn("Target Version: 4.30.z", fji.format_summary(out))

    def test_parse_legacy_response_without_new_fields(self):
        out = fetcher().parse({"key": "SYNTH-1", "fields": {"summary": "s", "comment": {"comments": []}}})
        self.assertTrue(LEGACY_KEYS <= set(out))
        self.assertEqual((out["links"], out["target_versions"], out["affects_versions"]), ([], [], []))


if __name__ == "__main__":
    unittest.main()
