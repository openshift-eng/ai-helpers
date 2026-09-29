#!/usr/bin/env python3
"""Tests for provider-neutral and legacy reply signature detection."""

import unittest
from unittest.mock import patch

from check_replied import check_issue_comment, check_review_comment, is_bot_reply


class TestIsBotReply(unittest.TestCase):
    def test_provider_neutral_signature(self):
        self.assertTrue(is_bot_reply("some-bot", "---\n*AI-assisted response*"))

    def test_legacy_claude_code_signature(self):
        self.assertTrue(
            is_bot_reply(
                "some-bot", "---\n*AI-assisted response via Claude Code*"
            )
        )

    def test_unrelated_comment(self):
        self.assertFalse(is_bot_reply("some-user", "Looks good to me."))


class TestMissingCommentsAreNotSafe(unittest.TestCase):
    @patch("check_replied.run_gh", return_value=[])
    def test_issue_comment_empty_list(self, _run_gh):
        result = check_issue_comment("openshift", "release", 1, "99")
        self.assertFalse(result["safe_to_reply"])
        self.assertEqual(result["reason"], "no_comments_found")

    @patch("check_replied.run_gh")
    def test_issue_comment_id_missing(self, run_gh):
        run_gh.return_value = [
            {"id": 1, "created_at": "t", "user": {"login": "a"}, "body": "x"}
        ]
        result = check_issue_comment("openshift", "release", 1, "99")
        self.assertFalse(result["safe_to_reply"])
        self.assertEqual(result["reason"], "comment_not_found")

    @patch("check_replied.run_gh", return_value=[])
    def test_review_comment_empty_list(self, _run_gh):
        result = check_review_comment("openshift", "release", 1, "99")
        self.assertFalse(result["safe_to_reply"])
        self.assertEqual(result["reason"], "no_comments_found")

    @patch("check_replied.run_gh")
    def test_review_comment_id_missing(self, run_gh):
        run_gh.return_value = [
            {"id": 1, "user": {"login": "a"}, "body": "x", "in_reply_to_id": None}
        ]
        result = check_review_comment("openshift", "release", 1, "99")
        self.assertFalse(result["safe_to_reply"])
        self.assertEqual(result["reason"], "comment_not_found")


if __name__ == "__main__":
    unittest.main()
