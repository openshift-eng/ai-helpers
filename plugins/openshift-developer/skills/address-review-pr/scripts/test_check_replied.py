#!/usr/bin/env python3
"""Tests for review reply detection and deduplication."""

import contextlib
import io
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from check_replied import (
    check_issue_comment,
    check_review,
    check_review_comment,
    is_bot_reply,
    main,
    paginated_items,
)


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

    def test_configured_agent_matches_unsigned_user_form(self):
        self.assertTrue(is_bot_reply("Review-Agent", "Done.", "review-agent[bot]"))


class TestMissingCommentsAreNotSafe(unittest.TestCase):
    @patch("check_replied.run_gh", return_value=[])
    def test_issue_comment_empty_list(self, _run_gh):
        result = check_issue_comment("openshift", "release", 1, "99")
        self.assertFalse(result["safe_to_reply"])
        self.assertEqual(result["reason"], "no_comments_found")

    @patch("check_replied.run_gh")
    def test_issue_comment_id_missing(self, run_gh):
        run_gh.return_value = [[
            {"id": 1, "created_at": "t", "user": {"login": "a"}, "body": "x"}
        ]]
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
        run_gh.return_value = [[
            {"id": 1, "user": {"login": "a"}, "body": "x", "in_reply_to_id": None}
        ]]
        result = check_review_comment("openshift", "release", 1, "99")
        self.assertFalse(result["safe_to_reply"])
        self.assertEqual(result["reason"], "comment_not_found")


class TestPaginatedItems(unittest.TestCase):
    @patch("check_replied.subprocess.run")
    def test_multiple_single_and_empty_pages(self, run):
        cases = (
            ('[[{"id":1}],[{"id":2}]]', [{"id": 1}, {"id": 2}]),
            ('[[{"id":1}]]', [{"id": 1}]),
            ('[[]]', []),
        )
        for stdout, expected in cases:
            with self.subTest(stdout=stdout):
                run.return_value = subprocess.CompletedProcess([], 0, stdout, "")
                self.assertEqual(paginated_items("endpoint"), expected)
        self.assertIn("--paginate", run.call_args.args[0])
        self.assertIn("--slurp", run.call_args.args[0])


class TestIssueCommentPagination(unittest.TestCase):
    @patch("check_replied.run_gh")
    def test_later_conversation_page_deduplicates_comment(self, run_gh):
        run_gh.return_value = [
            [
                {"id": 100, "created_at": "2026-10-19T12:00:00Z", "user": {"login": "reviewer"}, "body": "Please fix this"},
            ],
            [
                {"id": 101, "created_at": "2026-10-19T12:01:00Z", "user": {"login": "review-agent"}, "body": "Done.\n\n---\n*AI-assisted response*"},
            ],
        ]

        result = check_issue_comment("openshift", "release", 1, "100")

        self.assertFalse(result["safe_to_reply"])
        self.assertEqual(result["reason"], "bot_replied_after")


class TestInlineReplyDeduplication(unittest.TestCase):
    @patch("check_replied.run_gh")
    def test_reply_to_root_handles_child_target(self, run_gh):
        run_gh.return_value = [
            [
                {"id": 4313941703, "created_at": "2026-10-19T12:43:32Z", "user": {"login": "reviewer"}, "body": "First point"},
                {"id": 4313946225, "in_reply_to_id": 4313941703, "created_at": "2026-10-19T12:44:02Z", "user": {"login": "reviewer"}, "body": "And this follow-up"},
            ],
            [
                {"id": 4314161323, "in_reply_to_id": 4313941703, "created_at": "2026-10-19T13:06:36Z", "user": {"login": "review-agent"}, "body": "Done.\n\n---\n*AI-assisted response*"},
            ],
        ]

        result = check_review_comment("openshift", "release", 1, "4313946225")

        self.assertFalse(result["safe_to_reply"])
        self.assertEqual(result["reason"], "bot_already_replied")
        self.assertEqual(result["existing_reply"]["created_at"], "2026-10-19T13:06:36Z")

    @patch("check_replied.run_gh")
    def test_human_followup_after_bot_reply_is_safe(self, run_gh):
        run_gh.return_value = [[
            {"id": 100, "created_at": "2026-10-19T12:00:00Z", "user": {"login": "reviewer"}, "body": "First point"},
            {"id": 101, "in_reply_to_id": 100, "created_at": "2026-10-19T12:01:00Z", "user": {"login": "review-agent"}, "body": "Done.\n\n---\n*AI-assisted response*"},
            {"id": 102, "in_reply_to_id": 100, "created_at": "2026-10-19T12:02:00Z", "user": {"login": "reviewer"}, "body": "There is still a problem"},
        ]]

        result = check_review_comment("openshift", "release", 1, "102")

        self.assertTrue(result["safe_to_reply"])
        self.assertEqual(result["reason"], "no_bot_reply_found")


class TestReviewReplyDeduplication(unittest.TestCase):
    @patch("check_replied.run_gh")
    def test_later_inline_reply_deduplicates_review(self, run_gh):
        run_gh.side_effect = [
            {"id": 200, "submitted_at": "2026-10-19T12:00:00Z"},
            [[]],
            [[], [{"id": 300, "created_at": "2026-10-19T12:01:00Z", "user": {"login": "review-agent"}, "body": "Done.\n\n---\n*AI-assisted response*"}]],
        ]

        result = check_review("openshift", "release", 1, "200")

        self.assertFalse(result["safe_to_reply"])
        self.assertEqual(result["reason"], "bot_replied_after")

    @patch("check_replied.run_gh")
    def test_new_review_after_existing_replies_is_safe(self, run_gh):
        run_gh.side_effect = [
            {"id": 200, "submitted_at": "2026-10-19T12:02:00Z"},
            [[{"id": 300, "created_at": "2026-10-19T12:01:00Z", "user": {"login": "review-agent"}, "body": "Done.\n\n---\n*AI-assisted response*"}]],
            [[]],
        ]

        result = check_review("openshift", "release", 1, "200")

        self.assertTrue(result["safe_to_reply"])
        self.assertEqual(result["reason"], "no_bot_reply_after")

    @patch("check_replied.run_gh")
    def test_cli_uses_authenticated_login_for_unsigned_reply(self, run_gh):
        run_gh.side_effect = [
            {"login": "review-agent[bot]"},
            {"id": 200, "submitted_at": "2026-10-19T12:00:00Z"},
            [[]],
            [[{"id": 300, "created_at": "2026-10-19T12:01:00Z", "user": {"login": "review-agent"}, "body": "Done."}]],
        ]

        argv = [
            "check_replied.py", "openshift", "release", "1", "200",
            "--type", "review",
        ]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_context:
                main()

        self.assertEqual(exit_context.exception.code, 1)

    @patch("check_replied.run_gh", side_effect=RuntimeError("identity unavailable"))
    def test_cli_identity_lookup_failure_is_an_error(self, _run_gh):
        argv = [
            "check_replied.py", "openshift", "release", "1", "200",
            "--type", "review",
        ]
        stdout = io.StringIO()
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as exit_context:
                main()

        self.assertEqual(exit_context.exception.code, 2)
        self.assertEqual(json.loads(stdout.getvalue())["reason"], "error_fallback")

if __name__ == "__main__":
    unittest.main()
