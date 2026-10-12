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


if __name__ == '__main__':
    unittest.main()
