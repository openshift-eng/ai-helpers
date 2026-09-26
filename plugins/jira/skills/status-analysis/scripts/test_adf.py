#!/usr/bin/env python3
"""Tests for ADF rendering used by status-analysis helper scripts."""

import unittest

from adf import adf_to_text


class AdfToTextTests(unittest.TestCase):
    def test_renders_nested_status_summary(self) -> None:
        document = {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "bulletList",
                "content": [{
                    "type": "listItem",
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Color Status: Green"}],
                    }],
                }],
            }],
        }

        self.assertIn("Color Status: Green", adf_to_text(document))

    def test_preserves_legacy_text_values(self) -> None:
        self.assertEqual(adf_to_text("Color Status: Yellow"), "Color Status: Yellow")


if __name__ == "__main__":
    unittest.main()
