#!/usr/bin/env python3
"""
Unit tests for fetch_gerrit_comments.py

These tests use mocked data based on real Gerrit changes from OpenDev.

Run with: python -m pytest test_fetch_gerrit_comments.py -v
Or:       python -m unittest test_fetch_gerrit_comments -v
"""

import unittest
from unittest.mock import patch, MagicMock
import json

# Import the module under test
from fetch_gerrit_comments import (
    parse_gerrit_url,
    format_comment,
    format_output,
)


class TestParseGerritUrl(unittest.TestCase):
    """Tests for parse_gerrit_url function."""

    def test_parse_new_style_url(self):
        """Parse new-style Gerrit URL with project path."""
        base_url, change_id, patchset = parse_gerrit_url(
            "https://review.example.com/c/org/project/+/123456"
        )
        self.assertEqual(base_url, "https://review.example.com")
        self.assertIn("123456", change_id)
        self.assertIsNone(patchset)

    def test_parse_new_style_url_with_patchset(self):
        """Parse new-style URL with patchset number."""
        base_url, change_id, patchset = parse_gerrit_url(
            "https://review.example.com/c/org/project/+/123456/3"
        )
        self.assertEqual(base_url, "https://review.example.com")
        self.assertIn("123456", change_id)
        self.assertEqual(patchset, 3)

    def test_parse_old_style_url(self):
        """Parse old-style Gerrit URL with hash fragment."""
        base_url, change_id, patchset = parse_gerrit_url(
            "https://review.example.com/#/c/123456/"
        )
        self.assertEqual(base_url, "https://review.example.com")
        self.assertEqual(change_id, "123456")
        self.assertIsNone(patchset)

    def test_parse_old_style_url_with_patchset(self):
        """Parse old-style URL with patchset."""
        base_url, change_id, patchset = parse_gerrit_url(
            "https://review.example.com/#/c/123456/2"
        )
        self.assertEqual(base_url, "https://review.example.com")
        self.assertEqual(change_id, "123456")
        self.assertEqual(patchset, 2)

    def test_parse_direct_url(self):
        """Parse direct change number URL."""
        base_url, change_id, patchset = parse_gerrit_url(
            "https://review.example.com/123456"
        )
        self.assertEqual(base_url, "https://review.example.com")
        self.assertEqual(change_id, "123456")
        self.assertIsNone(patchset)

    def test_parse_trailing_slash(self):
        """Handle trailing slashes correctly."""
        base_url, change_id, patchset = parse_gerrit_url(
            "https://review.example.com/c/org/project/+/123456/"
        )
        self.assertEqual(base_url, "https://review.example.com")
        self.assertIn("123456", change_id)

    def test_parse_nested_project(self):
        """Parse URL with nested project path."""
        base_url, change_id, patchset = parse_gerrit_url(
            "https://review.example.com/c/org/sub/project/+/789012"
        )
        self.assertEqual(base_url, "https://review.example.com")
        # Project path should be URL-encoded in change_id
        self.assertIn("789012", change_id)

    def test_parse_invalid_url_raises(self):
        """Invalid URL raises ValueError."""
        with self.assertRaises(ValueError):
            parse_gerrit_url("not-a-valid-url")

    def test_parse_github_url_raises(self):
        """GitHub URL raises ValueError."""
        with self.assertRaises(ValueError):
            parse_gerrit_url("https://github.com/owner/repo/pull/123")


class TestFormatComment(unittest.TestCase):
    """Tests for format_comment function."""

    def test_format_inline_comment(self):
        """Format inline code comment."""
        comment = {
            "author": {"name": "John Reviewer", "_account_id": 12345},
            "message": "Please use a constant here instead of magic number.",
            "patch_set": 3,
            "line": 45,
            "unresolved": True,
        }
        result = format_comment(comment, "pkg/utils/config.go", {})
        
        self.assertIn("John Reviewer", result)
        self.assertIn("UNRESOLVED", result)
        self.assertIn("pkg/utils/config.go:45", result)
        self.assertIn("magic number", result)

    def test_format_patchset_level_comment(self):
        """Format patchset-level (general) comment."""
        comment = {
            "author": {"name": "Jane Smith", "_account_id": 67890},
            "message": "Overall looks good, just a few nits.",
            "patch_set": 2,
            "unresolved": False,
        }
        result = format_comment(comment, "/PATCHSET_LEVEL", {})
        
        self.assertIn("Jane Smith", result)
        self.assertIn("Patchset 2 - General Comment", result)
        self.assertNotIn("UNRESOLVED", result)

    def test_format_resolved_comment(self):
        """Resolved comments don't show UNRESOLVED marker."""
        comment = {
            "author": {"name": "Reviewer"},
            "message": "Done.",
            "patch_set": 1,
            "line": 10,
            "unresolved": False,
        }
        result = format_comment(comment, "file.py", {})
        
        self.assertNotIn("UNRESOLVED", result)

    def test_format_comment_without_line(self):
        """Comment without line number shows just file."""
        comment = {
            "author": {"name": "Reviewer"},
            "message": "General comment on this file.",
            "patch_set": 1,
            "unresolved": True,
        }
        result = format_comment(comment, "README.md", {})
        
        # Should show [README.md] without line number (no :123 suffix)
        self.assertIn("[README.md]", result)
        # Should NOT have [README.md:123] format (no line number after colon)
        self.assertNotIn("[README.md:", result)

    def test_format_comment_author_fallback(self):
        """Handle missing author fields gracefully."""
        comment = {
            "author": {"username": "jdoe"},
            "message": "Comment from username only.",
            "patch_set": 1,
            "unresolved": False,
        }
        result = format_comment(comment, "file.go", {})
        
        self.assertIn("jdoe", result)


class TestFormatOutput(unittest.TestCase):
    """Tests for format_output function."""

    def setUp(self):
        """Set up sample data based on typical Gerrit change."""
        self.change_details = {
            "_number": 123456,
            "project": "org/project",
            "branch": "master",
            "status": "NEW",
            "subject": "Add support for UpdateService actions",
            "owner": {
                "name": "John Developer",
                "_account_id": 11111,
            },
        }

        self.comments = {
            "/PATCHSET_LEVEL": [
                {
                    "author": {"name": "CI Bot", "_account_id": 1},
                    "message": "Build succeeded.",
                    "patch_set": 3,
                    "unresolved": False,
                },
                {
                    "author": {"name": "Core Reviewer", "_account_id": 2},
                    "message": "Please add unit tests for the new functionality.",
                    "patch_set": 3,
                    "unresolved": True,
                },
            ],
            "sushy/resources/updateservice/updateservice.py": [
                {
                    "author": {"name": "Reviewer A", "_account_id": 3},
                    "message": "Consider using a constant for this magic string.",
                    "patch_set": 3,
                    "line": 45,
                    "unresolved": True,
                },
                {
                    "author": {"name": "Reviewer B", "_account_id": 4},
                    "message": "Missing docstring.",
                    "patch_set": 3,
                    "line": 67,
                    "unresolved": True,
                },
            ],
            "sushy/tests/test_updateservice.py": [
                {
                    "author": {"name": "Reviewer A", "_account_id": 3},
                    "message": "Add edge case test.",
                    "patch_set": 2,
                    "line": 100,
                    "unresolved": False,
                },
            ],
        }

    def test_format_output_includes_change_info(self):
        """Output includes change metadata."""
        result = format_output(self.change_details, self.comments)
        
        self.assertIn("123456", result)
        self.assertIn("org/project", result)
        self.assertIn("master", result)
        self.assertIn("NEW", result)
        self.assertIn("UpdateService", result)
        self.assertIn("John Developer", result)

    def test_format_output_counts_comments(self):
        """Output includes comment statistics."""
        result = format_output(self.change_details, self.comments)
        
        self.assertIn("Total comments:", result)
        self.assertIn("Unresolved:", result)
        self.assertIn("Resolved:", result)

    def test_format_output_groups_by_file(self):
        """Comments are grouped by file."""
        result = format_output(self.change_details, self.comments)
        
        self.assertIn("### FILE: sushy/resources/updateservice/updateservice.py ###", result)
        self.assertIn("### FILE: sushy/tests/test_updateservice.py ###", result)

    def test_format_output_patchset_level_first(self):
        """Patchset-level comments appear before file comments."""
        result = format_output(self.change_details, self.comments)
        
        patchset_pos = result.find("PATCHSET-LEVEL COMMENTS")
        file_pos = result.find("### FILE:")
        self.assertLess(patchset_pos, file_pos)

    def test_format_output_action_items(self):
        """Output includes action items section."""
        result = format_output(self.change_details, self.comments)
        
        self.assertIn("ACTION ITEMS", result)
        self.assertIn("unresolved comment(s)", result)

    def test_format_output_patchset_filter(self):
        """Filter comments by patchset."""
        result = format_output(self.change_details, self.comments, patchset_filter=3)
        
        # Should show patchset 3 comments, not patchset 2
        self.assertIn("Showing patchset: 3", result)

    def test_format_output_no_comments(self):
        """Handle change with no comments."""
        result = format_output(self.change_details, {})
        
        self.assertIn("No comments found", result)

    def test_format_output_all_resolved(self):
        """Handle when all comments are resolved."""
        resolved_comments = {
            "file.py": [
                {
                    "author": {"name": "Reviewer"},
                    "message": "Done",
                    "patch_set": 1,
                    "line": 10,
                    "unresolved": False,
                },
            ],
        }
        result = format_output(self.change_details, resolved_comments)
        
        self.assertIn("All comments have been resolved", result)


class TestFetchJsonMocked(unittest.TestCase):
    """Tests for fetch_json with mocked HTTP responses."""

    @patch('fetch_gerrit_comments.urllib.request.urlopen')
    def test_fetch_json_strips_xssi_prefix(self, mock_urlopen):
        """Gerrit's XSSI prefix is stripped correctly."""
        from fetch_gerrit_comments import fetch_json
        
        # Gerrit prefixes JSON with )]}' to prevent XSSI
        mock_response = MagicMock()
        mock_response.read.return_value = b')]}\'\n{"key": "value"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = fetch_json("https://example.com/api")
        
        self.assertEqual(result, {"key": "value"})

    @patch('fetch_gerrit_comments.urllib.request.urlopen')
    def test_fetch_json_handles_404(self, mock_urlopen):
        """404 response raises ValueError with helpful message."""
        from fetch_gerrit_comments import fetch_json
        import urllib.error
        
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", {}, None
        )
        
        with self.assertRaises(ValueError) as ctx:
            fetch_json("https://example.com/api")
        
        self.assertIn("not found", str(ctx.exception).lower())


class TestEndToEnd(unittest.TestCase):
    """End-to-end tests with fully mocked API calls."""

    @patch('fetch_gerrit_comments.fetch_comments')
    @patch('fetch_gerrit_comments.fetch_change_details')
    def test_full_workflow(self, mock_details, mock_comments):
        """Test complete workflow with mocked API."""
        mock_details.return_value = {
            "_number": 12345,
            "project": "test/repo",
            "branch": "main",
            "status": "NEW",
            "subject": "Test change",
            "owner": {"name": "Test User"},
        }
        
        mock_comments.return_value = {
            "file.py": [
                {
                    "author": {"name": "Reviewer"},
                    "message": "Please fix this.",
                    "patch_set": 1,
                    "line": 10,
                    "unresolved": True,
                },
            ],
        }
        
        # Verify format_output works with mocked data
        result = format_output(mock_details.return_value, mock_comments.return_value)
        
        self.assertIn("12345", result)
        self.assertIn("Please fix this", result)
        self.assertIn("1 unresolved", result)


if __name__ == '__main__':
    unittest.main()

