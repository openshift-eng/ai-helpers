#!/usr/bin/env python3
"""
Unit tests for fetch_github_comments.py

These tests use mocked data based on example PR structure.

Run with: python -m pytest test_fetch_github_comments.py -v
Or:       python -m unittest test_fetch_github_comments -v
"""

import unittest
from unittest.mock import patch, MagicMock

# Import the module under test
from fetch_github_comments import (
    parse_github_url,
    is_bot_author,
    is_outdated_comment,
    format_comment,
    format_output,
)


class TestParseGitHubUrl(unittest.TestCase):
    """Tests for parse_github_url function."""

    def test_parse_full_url(self):
        """Parse standard GitHub PR URL."""
        owner, repo, pr_num = parse_github_url(
            "https://github.com/example-org/example-repo/pull/123"
        )
        self.assertEqual(owner, "example-org")
        self.assertEqual(repo, "example-repo")
        self.assertEqual(pr_num, 123)

    def test_parse_url_without_https(self):
        """Parse URL without https:// prefix."""
        owner, repo, pr_num = parse_github_url(
            "github.com/example-org/example-repo/pull/456"
        )
        self.assertEqual(owner, "example-org")
        self.assertEqual(repo, "example-repo")
        self.assertEqual(pr_num, 456)

    def test_parse_short_format(self):
        """Parse owner/repo#number format."""
        owner, repo, pr_num = parse_github_url("example-org/example-repo#123")
        self.assertEqual(owner, "example-org")
        self.assertEqual(repo, "example-repo")
        self.assertEqual(pr_num, 123)

    def test_parse_invalid_url_raises(self):
        """Invalid URL raises ValueError."""
        with self.assertRaises(ValueError):
            parse_github_url("not-a-valid-url")

    def test_parse_invalid_format_raises(self):
        """Invalid format raises ValueError."""
        with self.assertRaises(ValueError):
            parse_github_url("https://gitlab.com/owner/repo/merge_requests/123")


class TestIsBotAuthor(unittest.TestCase):
    """Tests for is_bot_author function."""

    def test_openshift_ci_robot(self):
        """Detect openshift-ci-robot as bot."""
        self.assertTrue(is_bot_author("openshift-ci-robot"))

    def test_project_bot(self):
        """Detect project-specific bots."""
        self.assertTrue(is_bot_author("metal3-io-bot"))
        self.assertTrue(is_bot_author("some-project-bot[bot]"))

    def test_dependabot(self):
        """Detect dependabot as bot."""
        self.assertTrue(is_bot_author("dependabot[bot]"))
        self.assertTrue(is_bot_author("dependabot"))

    def test_github_actions(self):
        """Detect github-actions as bot."""
        self.assertTrue(is_bot_author("github-actions[bot]"))
        self.assertTrue(is_bot_author("github-actions"))

    def test_codecov(self):
        """Detect codecov as bot."""
        self.assertTrue(is_bot_author("codecov[bot]"))

    def test_renovate(self):
        """Detect renovate as bot."""
        self.assertTrue(is_bot_author("renovate[bot]"))

    def test_human_user(self):
        """Human users are not bots."""
        self.assertFalse(is_bot_author("mabulgu"))
        self.assertFalse(is_bot_author("tuminoid"))
        self.assertFalse(is_bot_author("dtantsur"))

    def test_copilot_not_filtered(self):
        """Copilot is not in the bot list (useful review comments)."""
        # Note: Copilot provides code review, so we don't filter it
        self.assertFalse(is_bot_author("Copilot"))


class TestIsOutdatedComment(unittest.TestCase):
    """Tests for is_outdated_comment function."""

    def test_current_comment(self):
        """Comment with line number is current."""
        comment = {
            "type": "review_comment",
            "line": 45,
            "original_line": 45,
        }
        self.assertFalse(is_outdated_comment(comment))

    def test_outdated_comment(self):
        """Comment with null line but original_line is outdated."""
        comment = {
            "type": "review_comment",
            "line": None,
            "original_line": 10,
        }
        self.assertTrue(is_outdated_comment(comment))

    def test_issue_comment_not_outdated(self):
        """Issue comments are never outdated."""
        comment = {
            "type": "issue_comment",
            "line": None,
        }
        self.assertFalse(is_outdated_comment(comment))

    def test_review_not_outdated(self):
        """Reviews are never outdated."""
        comment = {
            "type": "review",
            "line": None,
        }
        self.assertFalse(is_outdated_comment(comment))


class TestFormatComment(unittest.TestCase):
    """Tests for format_comment function."""

    def test_format_review_comment(self):
        """Format inline review comment."""
        comment = {
            "type": "review_comment",
            "author": "tuminoid",
            "body": "LOL bot being in 2024.",
            "path": "internal/controller/metal3.io/image_auth_validator_test.go",
            "line": 10,
            "created_at": "2025-12-05T10:00:00Z",
        }
        result = format_comment(comment)
        self.assertIn("tuminoid", result)
        self.assertIn("LOL bot being in 2024.", result)
        self.assertIn("image_auth_validator_test.go:10", result)

    def test_format_outdated_comment_hidden(self):
        """Outdated comments return None by default."""
        comment = {
            "type": "review_comment",
            "author": "reviewer",
            "body": "Old comment",
            "path": "file.go",
            "line": None,
            "original_line": 5,
            "created_at": "2025-01-01T00:00:00Z",
        }
        result = format_comment(comment, show_outdated=False)
        self.assertIsNone(result)

    def test_format_outdated_comment_shown(self):
        """Outdated comments shown when requested."""
        comment = {
            "type": "review_comment",
            "author": "reviewer",
            "body": "Old comment",
            "path": "file.go",
            "line": None,
            "original_line": 5,
            "created_at": "2025-01-01T00:00:00Z",
        }
        result = format_comment(comment, show_outdated=True)
        self.assertIsNotNone(result)
        self.assertIn("OUTDATED", result)

    def test_format_review(self):
        """Format review submission."""
        comment = {
            "type": "review",
            "author": "dtantsur",
            "body": "Please address the comments.",
            "state": "CHANGES_REQUESTED",
            "submitted_at": "2025-12-05T11:00:00Z",
        }
        result = format_comment(comment)
        self.assertIn("dtantsur", result)
        self.assertIn("CHANGES_REQUESTED", result)

    def test_format_issue_comment(self):
        """Format PR conversation comment."""
        comment = {
            "type": "issue_comment",
            "author": "mabulgu",
            "body": "Thanks for the review!",
            "created_at": "2025-12-05T12:00:00Z",
        }
        result = format_comment(comment)
        self.assertIn("mabulgu", result)
        self.assertIn("PR Comment", result)

    def test_format_empty_body_returns_none(self):
        """Empty body returns None (except for reviews)."""
        comment = {
            "type": "issue_comment",
            "author": "user",
            "body": "",
            "created_at": "2025-01-01T00:00:00Z",
        }
        result = format_comment(comment)
        self.assertIsNone(result)


class TestFormatOutput(unittest.TestCase):
    """Tests for format_output function."""

    def setUp(self):
        """Set up sample data based on example PR structure."""
        self.pr_details = {
            "number": 123,
            "title": "Example pull request title",
            "state": "open",
            "user": "example-user",
            "head": "feature/example-branch",
            "base": "main",
            "html_url": "https://github.com/example-org/example-repo/pull/123",
        }

        self.issue_comments = [
            {
                "id": 1,
                "author": "github-actions[bot]",
                "body": "This PR is NOT APPROVED...",
                "created_at": "2025-10-22T10:52:00Z",
                "type": "issue_comment",
            },
        ]

        self.reviews = [
            {
                "id": 100,
                "author": "tuminoid",
                "body": "",
                "state": "COMMENTED",
                "submitted_at": "2025-12-05T10:00:00Z",
                "type": "review",
            },
        ]

        self.review_comments = [
            {
                "id": 200,
                "author": "Copilot",
                "body": "The scheme check is case-sensitive...",
                "path": "pkg/secretutils/dockerconfig.go",
                "line": 45,
                "original_line": 45,
                "created_at": "2025-12-05T10:30:00Z",
                "type": "review_comment",
            },
            {
                "id": 201,
                "author": "Copilot",
                "body": "Missing strings import...",
                "path": "pkg/secretutils/dockerconfig.go",
                "line": 10,
                "original_line": 10,
                "created_at": "2025-12-05T10:31:00Z",
                "type": "review_comment",
            },
            {
                "id": 202,
                "author": "tuminoid",
                "body": "LOL bot being in 2024.",
                "path": "internal/controller/metal3.io/image_auth_validator_test.go",
                "line": None,
                "original_line": 10,
                "created_at": "2025-12-05T10:32:00Z",
                "type": "review_comment",
            },
        ]

    def test_format_output_includes_pr_info(self):
        """Output includes PR metadata."""
        result = format_output(
            self.pr_details,
            self.issue_comments,
            self.reviews,
            self.review_comments,
        )
        self.assertIn("#123", result)
        self.assertIn("Example pull request title", result)
        self.assertIn("example-user", result)

    def test_format_output_filters_bots(self):
        """Bot comments are filtered by default."""
        result = format_output(
            self.pr_details,
            self.issue_comments,
            self.reviews,
            self.review_comments,
            filter_bots=True,
        )
        self.assertIn("Filtered bot comments: 1", result)
        self.assertNotIn("NOT APPROVED", result)

    def test_format_output_includes_bots(self):
        """Bot comments included when filter_bots=False."""
        result = format_output(
            self.pr_details,
            self.issue_comments,
            self.reviews,
            self.review_comments,
            filter_bots=False,
        )
        self.assertIn("NOT APPROVED", result)

    def test_format_output_filters_outdated(self):
        """Outdated comments are filtered by default."""
        result = format_output(
            self.pr_details,
            self.issue_comments,
            self.reviews,
            self.review_comments,
            filter_outdated=True,
        )
        self.assertIn("Filtered outdated comments: 1", result)

    def test_format_output_groups_by_file(self):
        """Comments are grouped by file."""
        result = format_output(
            self.pr_details,
            [],
            [],
            self.review_comments,
            filter_bots=False,
            filter_outdated=False,
        )
        self.assertIn("### FILE: pkg/secretutils/dockerconfig.go ###", result)
        self.assertIn("### FILE: internal/controller/metal3.io/image_auth_validator_test.go ###", result)

    def test_format_output_action_items(self):
        """Output includes action items section."""
        result = format_output(
            self.pr_details,
            [],
            [],
            self.review_comments[:2],  # Only current comments
        )
        self.assertIn("ACTION ITEMS", result)
        self.assertIn("inline comment(s)", result)

    def test_format_output_no_comments(self):
        """Handle PR with no comments."""
        result = format_output(
            self.pr_details,
            [],
            [],
            [],
        )
        self.assertIn("No comments found", result)


class TestIntegration(unittest.TestCase):
    """Integration tests with mocked gh CLI calls."""

    @patch('fetch_github_comments.run_gh_command')
    def test_fetch_with_mocked_gh(self, mock_gh):
        """Test full flow with mocked gh CLI."""
        # This test verifies the integration works
        # We mock run_gh_command to return sample data
        import json

        pr_json = json.dumps({
            "number": 123,
            "title": "Test PR",
            "state": "open",
            "user": "testuser",
            "head": "feature",
            "base": "main",
            "html_url": "https://github.com/test/repo/pull/123"
        })

        mock_gh.return_value = (pr_json, 0)

        # Import and call the function
        from fetch_github_comments import fetch_pr_details
        result = fetch_pr_details("test", "repo", 123)

        self.assertEqual(result["number"], 123)
        self.assertEqual(result["title"], "Test PR")


if __name__ == '__main__':
    unittest.main()

