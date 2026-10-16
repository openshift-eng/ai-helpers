#!/usr/bin/env python3

import json
from pathlib import Path
import tempfile
import unittest

from validate_evidence import validate_and_render


class ValidateEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        (artifacts / "trace.txt").write_text(
            "request starts\ncache hit revision=old\nresponse revision=old\nrequest ends\n",
            encoding="utf-8",
        )
        (artifacts / "verification.txt").write_text(
            "update revision=new\ninvalidate cache key=item-7\nread revision=new\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def _proof(self, artifact="artifacts/trace.txt", lines=None):
        return {
            "type": "trace",
            "artifact": artifact,
            "lines": lines or [2, 3],
            "note": "The same request reads the old revision from the cache.",
        }

    def _document(self):
        return {
            "schema_version": "1.0",
            "investigation": {
                "question": "Why is the read stale?",
                "scope": "development instance, request item-7",
                "status": "supported",
            },
            "chains": [
                {
                    "id": "cache",
                    "hypothesis": "The read is served by a stale cache entry.",
                    "status": "supported",
                    "links": [
                        {
                            "question": "What served the old revision?",
                            "answer": "The cache served it.",
                            "proof": [self._proof()],
                        }
                    ],
                }
            ],
            "conclusion": {
                "answer": "The cache served a stale entry.",
                "chain_ids": ["cache"],
                "verification": [
                    {
                        "method": "counterfactual",
                        "claim": "Invalidation makes the next read return the new revision.",
                        "proof": [
                            {
                                "type": "test",
                                "artifact": "artifacts/verification.txt",
                                "lines": [2, 3],
                                "note": "The controlled run invalidates the key and reads the new revision.",
                            }
                        ],
                    }
                ],
                "limitations": [],
            },
        }

    def _write(self, data=None):
        path = self.root / "evidence.json"
        path.write_text(json.dumps(data or self._document()), encoding="utf-8")
        return path

    def test_valid_document_hydrates_only_exact_lines(self):
        errors, markdown = validate_and_render(self._write(), self.root)
        self.assertEqual([], errors)
        self.assertIn("2 | cache hit revision=old", markdown)
        self.assertIn("3 | response revision=old", markdown)
        self.assertNotIn("4 | request ends", markdown)
        self.assertIn("invalidate cache key=item-7", markdown)

    def test_rejects_out_of_range_lines(self):
        data = self._document()
        data["chains"][0]["links"][0]["proof"][0]["lines"] = [3, 99]
        errors, _ = validate_and_render(self._write(data), self.root)
        self.assertTrue(any("exceed artifact length" in error for error in errors))

    def test_rejects_path_escape(self):
        data = self._document()
        data["chains"][0]["links"][0]["proof"][0]["artifact"] = "../outside.txt"
        errors, _ = validate_and_render(self._write(data), self.root)
        self.assertTrue(any("escapes evidence root" in error for error in errors))

    def test_requires_proof_for_every_link(self):
        data = self._document()
        data["chains"][0]["links"][0]["proof"] = []
        errors, _ = validate_and_render(self._write(data), self.root)
        self.assertTrue(any("proof must be a non-empty array" in error for error in errors))

    def test_rejects_unknown_conclusion_chain(self):
        data = self._document()
        data["conclusion"]["chain_ids"] = ["missing"]
        errors, _ = validate_and_render(self._write(data), self.root)
        self.assertTrue(any("unknown chain" in error for error in errors))

    def test_supported_result_requires_independent_verification(self):
        data = self._document()
        data["conclusion"]["verification"] = []
        errors, _ = validate_and_render(self._write(data), self.root)
        self.assertTrue(any("requires at least one verification" in error for error in errors))

    def test_supported_conclusion_must_reference_supported_chain(self):
        data = self._document()
        data["chains"].append(
            {
                "id": "alternative",
                "hypothesis": "The database returned the old revision.",
                "status": "ruled_out",
                "links": [
                    {
                        "question": "What revision did the database return?",
                        "answer": "It returned the new revision.",
                        "proof": [self._proof()],
                    }
                ],
            }
        )
        data["conclusion"]["chain_ids"] = ["alternative"]
        errors, _ = validate_and_render(self._write(data), self.root)
        self.assertTrue(any("reference at least one supported chain" in error for error in errors))

    def test_inconclusive_result_requires_limitation(self):
        data = self._document()
        data["investigation"]["status"] = "inconclusive"
        data["chains"][0]["status"] = "inconclusive"
        data["conclusion"]["verification"] = []
        errors, _ = validate_and_render(self._write(data), self.root)
        self.assertTrue(any("requires at least one limitation" in error for error in errors))

    def test_inconclusive_result_without_verification_is_valid(self):
        data = self._document()
        data["investigation"]["status"] = "inconclusive"
        data["chains"][0]["status"] = "inconclusive"
        data["conclusion"]["verification"] = []
        data["conclusion"]["limitations"] = [
            "The trace does not identify who populated the cache entry."
        ]
        errors, markdown = validate_and_render(self._write(data), self.root)
        self.assertEqual([], errors)
        self.assertIn("No independent verification recorded.", markdown)

    def test_inconclusive_result_without_any_evidence_is_valid(self):
        data = self._document()
        data["investigation"]["status"] = "inconclusive"
        data["chains"] = []
        data["conclusion"]["chain_ids"] = []
        data["conclusion"]["verification"] = []
        data["conclusion"]["limitations"] = [
            "No logs, source, or reproduction environment were available."
        ]
        errors, markdown = validate_and_render(self._write(data), self.root)
        self.assertEqual([], errors)
        self.assertIn("No evidence chains recorded.", markdown)

    def test_rejects_unsafe_artifact_url(self):
        data = self._document()
        data["chains"][0]["links"][0]["proof"][0]["artifact_url"] = (
            "javascript:alert(1)"
        )
        errors, _ = validate_and_render(self._write(data), self.root)
        self.assertTrue(any("http or https URL" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
