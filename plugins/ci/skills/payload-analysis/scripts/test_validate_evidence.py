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
        evidence = self.root / "payload-evidence" / "job"
        evidence.mkdir(parents=True)
        (evidence / "build-log.txt").write_text(
            "starting test\nwaiting for operator\nreconcile failed: unsupported gateway mode\nretrying reconcile\ntest timed out\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_document(self, proof=None):
        if proof is None:
            proof = {
                "type": "log",
                "artifact": "payload-evidence/job/build-log.txt",
                "artifact_url": "https://example.invalid/build-log.txt",
                "lines": [3, 4],
                "note": "The failing operation emits the error and immediately retries.",
            }
        data = {
            "payload_tag": "4.22.0-0.nightly-example",
            "jobs": [
                {
                    "job_name": "periodic-ci-example",
                    "causal_chain": [
                        {
                            "question": "Why did this job fail?",
                            "answer": "The test timed out after gateway reconciliation failed.",
                            "proof": [proof],
                        }
                    ],
                }
            ],
        }
        path = self.root / "payload-evidence.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_document_hydrates_exact_lines(self):
        errors, markdown = validate_and_render(self._write_document(), self.root)
        self.assertEqual([], errors)
        self.assertIn("3 | reconcile failed: unsupported gateway mode", markdown)
        self.assertIn("4 | retrying reconcile", markdown)
        self.assertNotIn("5 | test timed out", markdown)

    def test_rejects_out_of_range_lines(self):
        path = self._write_document(
            {
                "type": "log",
                "artifact": "payload-evidence/job/build-log.txt",
                "lines": [4, 99],
                "note": "Invalid range",
            }
        )
        errors, _ = validate_and_render(path, self.root)
        self.assertTrue(any("exceed artifact length" in error for error in errors))

    def test_rejects_path_escape(self):
        outside = self.root.parent / "outside-evidence.txt"
        outside.write_text("secret\n", encoding="utf-8")
        self.addCleanup(outside.unlink)
        path = self._write_document(
            {
                "type": "log",
                "artifact": "../outside-evidence.txt",
                "lines": [1, 1],
                "note": "Must not be readable",
            }
        )
        errors, _ = validate_and_render(path, self.root)
        self.assertTrue(any("escapes evidence root" in error for error in errors))

    def test_requires_proof_for_every_link(self):
        path = self._write_document()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["jobs"][0]["causal_chain"][0]["proof"] = []
        path.write_text(json.dumps(data), encoding="utf-8")
        errors, _ = validate_and_render(path, self.root)
        self.assertTrue(any("proof must be a non-empty array" in error for error in errors))

    def test_requires_every_expected_failed_job(self):
        path = self._write_document()
        errors, _ = validate_and_render(
            path, self.root, {"periodic-ci-example", "periodic-ci-missing"}
        )
        self.assertTrue(any("periodic-ci-missing" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
