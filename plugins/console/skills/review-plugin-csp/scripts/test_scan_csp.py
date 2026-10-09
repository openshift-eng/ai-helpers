#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Developer tests; the scanner itself requires neither Python nor npm."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("scan-csp.sh")
BASH = shutil.which("bash")


@unittest.skipUnless(BASH and shutil.which("rg"), "Bash and ripgrep are required")
class ScanCSPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="console-csp-scan-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def fixture(self, files):
        for name, content in files.items():
            file = self.root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content, encoding="utf-8")
        return self.root

    def run_scan(self, *arguments, directory=None, env=None):
        command = [BASH, str(SCRIPT), str(directory or self.root), *arguments]
        result = subprocess.run(command, capture_output=True, text=True, env=env, cwd=tempfile.gettempdir(), timeout=30)
        candidates = [line.split("\t") for line in result.stdout.splitlines() if line.startswith("candidate\t")]
        summaries = [line.split("\t", 1)[1] for line in result.stdout.splitlines() if line.startswith("summary\t")]
        summary = dict(field.split("=", 1) for field in summaries[0].split()) if summaries else {}
        return result, candidates, summary

    def test_evaluation_forms_have_locations(self):
        examples = {
            "direct.js": 'eval("1");',
            "indirect.mjs": '(0, eval)("1");',
            "alias.cjs": 'const evaluate = window.eval; evaluate("1");',
            "constructor.js": 'new Function("return 1");',
            "bare.js": 'Function("return 1");',
            "timer.js": 'setTimeout("run()", 1); window.setInterval(`run()`, 1);',
        }
        self.fixture(examples)
        result, candidates, summary = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(int(summary["candidates_total"]), 7)
        self.assertEqual({row[1] for row in candidates}, {"eval-reference", "function-constructor", "string-timer"})
        self.assertTrue(all(len(row) == 6 and row[3] == "1" and int(row[4]) > 0 for row in candidates))

    def test_style_script_worker_and_connection_candidates(self):
        self.fixture({"bundle.js": 'document.createElement("style"); document.createElement(\'script\'); new Worker("a"); new SharedWorker("b"); navigator.serviceWorker.register("c"); fetch("/api"); new WebSocket("wss://example.test");'})
        result, candidates, _ = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({row[1] for row in candidates}, {"inline-style", "script-element", "worker", "service-worker", "connection"})

    def test_innerhtml_blob_and_cdn_candidates(self):
        self.fixture({"bundle.js": 'el.innerHTML = "<script>alert(1)</script>"; var url = URL.createObjectURL(blob); var src = "https://cdn.jsdelivr.net/npm/monaco";'})
        result, candidates, _ = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({row[1] for row in candidates}, {"innerHTML-assignment", "blob-url", "cdn-reference"})

    def test_comments_and_strings_are_explicitly_only_candidates(self):
        self.fixture({"bundle.js": '// eval("comment")\nconst text = "new Function(fake)";'})
        result, candidates, _ = self.run_scan()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(candidates), 2)
        self.assertIn("not JavaScript validation or a CSP verdict", result.stdout)

    def test_no_matches_is_successful_search_not_compliance(self):
        self.fixture({"bundle.js": 'const value = 1; setTimeout(() => value, 1);'})
        result, candidates, summary = self.run_scan()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(candidates, [])
        self.assertEqual(summary["candidates_total"], "0")
        self.assertIn("status\tcomplete-text-search", result.stdout)

    def test_maps_and_dependency_directories_are_excluded(self):
        self.fixture({"bundle.js": 'const value = 1;', "bundle.js.map": 'eval("map")', "node_modules/dep.js": 'eval("dep");', ".git/ignored.js": 'eval("git");'})
        result, candidates, summary = self.run_scan()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(candidates, [])
        self.assertEqual(summary["files_selected"], "1")

    def test_hidden_and_gitignored_bundles_are_not_silently_omitted(self):
        self.fixture({".gitignore": "*\n", ".hidden.js": 'eval("1");'})
        result, candidates, summary = self.run_scan()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(summary["files_selected"], "1")
        self.assertEqual(len(candidates), 1)

    def test_minified_output_is_bounded_and_omissions_are_counted(self):
        self.fixture({"bundle.js": 'const text = "' + "x" * 100000 + '";' + 'eval("1");' * 10})
        result, candidates, summary = self.run_scan("--max-findings", "2")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(summary["candidates_total"], "10")
        self.assertEqual(summary["candidates_omitted"], "8")
        self.assertLess(len(result.stdout), 3000)

    def test_output_order_is_deterministic(self):
        self.fixture({"z.js": 'eval("1");', "a.js": 'eval("2");'})
        first, _, _ = self.run_scan()
        second, _, _ = self.run_scan()
        self.assertEqual(first.stdout, second.stdout)

    def test_special_characters_in_paths_do_not_corrupt_records(self):
        self.fixture({"space:tab\tquote'\n.js": 'eval("1");', "unicode-č.js": 'eval("2");'})
        result, candidates, summary = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["candidates_total"], "2")
        self.assertTrue(all(len(row) == 6 for row in candidates))

    def test_ripgrep_configuration_cannot_execute_a_preprocessor(self):
        self.fixture({"bundle.js": 'eval("1");'})
        marker = self.root / "executed"
        preprocessor = self.root / "preprocessor.sh"
        preprocessor.write_text(f"#!/bin/sh\ntouch '{marker}'\ncat\n", encoding="utf-8")
        preprocessor.chmod(0o755)
        config = self.root / "rg-config"
        config.write_text(f"--pre={preprocessor}\n--glob=!*\n", encoding="utf-8")
        environment = dict(os.environ, RIPGREP_CONFIG_PATH=str(config))
        result, candidates, _ = self.run_scan(env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(candidates), 1)
        self.assertFalse(marker.exists())

    def test_bundle_is_not_executed_or_changed(self):
        source = 'throw new Error("do not run"); eval("1");'
        self.fixture({"bundle.js": source})
        result, _, _ = self.run_scan()
        self.assertEqual(result.returncode, 0)
        self.assertEqual((self.root / "bundle.js").read_text(), source)

    def test_large_files_produce_incomplete_status(self):
        self.fixture({"bundle.js": 'eval("1");'})
        result, candidates, summary = self.run_scan("--max-file-bytes", "5")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(candidates, [])
        self.assertEqual(summary["files_skipped"], "1")
        self.assertIn("file-too-large", result.stdout)
        self.assertIn("status\tincomplete", result.stdout)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can read chmod-000 files")
    def test_unreadable_files_produce_incomplete_status(self):
        self.fixture({"blocked.js": 'eval("1");'})
        file = self.root / "blocked.js"
        file.chmod(0)
        try:
            result, _, _ = self.run_scan()
            self.assertEqual(result.returncode, 2)
            self.assertIn("unreadable-file", result.stdout)
        finally:
            file.chmod(0o600)

    def test_symlinks_outside_the_directory_are_not_followed(self):
        self.fixture({"dist/bundle.js": "const value = 1;", "external.js": 'eval("1");'})
        (self.root / "dist/link.js").symlink_to(self.root / "external.js")
        result, candidates, summary = self.run_scan(directory=self.root / "dist")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(candidates, [])
        self.assertEqual(summary["files_selected"], "1")

    def test_empty_and_missing_directories_are_not_clean_scans(self):
        for directory in [self.root, self.root / "missing"]:
            with self.subTest(directory=directory):
                result, _, _ = self.run_scan(directory=directory)
                self.assertEqual(result.returncode, 2)

    def test_invalid_options_are_rejected(self):
        self.fixture({"bundle.js": "const value = 1;"})
        for arguments in [("--max-findings", "0"), ("--max-file-bytes", "bad"), ("--unknown",)]:
            with self.subTest(arguments=arguments):
                result, _, _ = self.run_scan(*arguments)
                self.assertEqual(result.returncode, 2)

    def test_missing_ripgrep_is_reported_without_installation(self):
        self.fixture({"bundle.js": "const value = 1;"})
        result, _, _ = self.run_scan(env=dict(os.environ, PATH=""))
        self.assertEqual(result.returncode, 2)
        self.assertIn("Required command is missing: rg", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
