#!/usr/bin/env python3
"""Tests for is_slash_command_only.py"""

import unittest

from is_slash_command_only import is_slash_command_only


class IsSlashCommandOnlyTest(unittest.TestCase):
    def test_single_commands(self):
        for body in ("/lgtm", "/hold", "/override", "/approve", "/retest"):
            with self.subTest(body=body):
                self.assertTrue(is_slash_command_only(body))

    def test_commands_with_args(self):
        self.assertTrue(is_slash_command_only("/lgtm cancel"))
        self.assertTrue(is_slash_command_only("/test e2e-aws"))
        self.assertTrue(is_slash_command_only("/override ci/prow/lint"))
        self.assertTrue(is_slash_command_only("/pipeline required"))
        self.assertTrue(is_slash_command_only("/cc @someone"))

    def test_multiple_command_lines(self):
        self.assertTrue(is_slash_command_only("/hold\n/lgtm"))
        self.assertTrue(is_slash_command_only("  /hold  \n\n/lgtm cancel\n"))

    def test_html_comment_only_commands(self):
        self.assertTrue(is_slash_command_only("<!-- metadata -->\n/lgtm"))

    def test_empty_is_not_review_work(self):
        self.assertTrue(is_slash_command_only(""))
        self.assertTrue(is_slash_command_only("   \n  "))
        self.assertTrue(is_slash_command_only("<!-- only a comment -->"))

    def test_mixed_prose_is_kept(self):
        self.assertFalse(is_slash_command_only("Please rename this helper.\n\n/lgtm"))
        self.assertFalse(is_slash_command_only("/lgtm\n\nPlease rename this helper."))
        self.assertFalse(is_slash_command_only("LGTM"))
        self.assertFalse(is_slash_command_only("looks good, /lgtm later"))

    def test_path_or_url_not_a_command(self):
        self.assertFalse(is_slash_command_only("/usr/bin/env"))
        self.assertFalse(is_slash_command_only("see /tmp/foo"))


if __name__ == "__main__":
    unittest.main()
