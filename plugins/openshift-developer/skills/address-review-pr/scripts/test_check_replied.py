#!/usr/bin/env python3
"""Tests for provider-neutral and legacy reply signature detection."""

import unittest

from check_replied import is_bot_reply


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


if __name__ == "__main__":
    unittest.main()
