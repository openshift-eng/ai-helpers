#!/usr/bin/env python3
"""Declaration coverage and failure behavior for the read-only AST inventory."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("go"), "Go compiler unavailable")
class DeprecationScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="deprecation-tool-")
        cls.addClassCleanup(cls.build.cleanup)
        cls.binary = Path(cls.build.name) / "deprecation-scan"
        environment = dict(os.environ, GO111MODULE="off", GOWORK="off", GOFLAGS="-p=1")
        subprocess.run(["go", "build", "-o", str(cls.binary),
                        str(PLUGIN / "scripts/deprecation-scan.go")],
                       env=environment, capture_output=True, text=True, check=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="deprecation-input-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = self.root / "module with spaces"
        self.dependency = self.module / "vendor/example.invalid/lib"
        self.dependency.mkdir(parents=True)
        (self.module / "go.mod").write_text("module example.invalid/app\n")
        (self.module / "app.go").write_text("package app\n")

    def scan(self, *dependencies):
        return subprocess.run([str(self.binary), str(self.module),
                               *(str(p) for p in dependencies or [self.dependency])],
                              capture_output=True, text=True)

    def test_long_comments_methods_grouped_specs_and_fields(self):
        (self.dependency / "lib.go").write_text("""package lib
// DEPRECATED: use New.
// A long explanation.
// Additional detail.
func Old() {}
type Receiver struct {
    // Deprecated: use Better.
    Field int
    Trailing int // DEPRECATED: use Better.
}
// DEPRECATED: use NewMethod.
func (*Receiver) Method() {}
const (
    // DEPRECATED: use NewConstant.
    Constant = 1
)
// Deprecated: use NewVariables.
var (
    First, Second int
)
type Interface interface {
    // DEPRECATED: use Other.
    InterfaceMethod()
}
// DEPRECATED: this unattached comment requires manual review.
""")
        (self.module / "app.go").write_text("""package app
var Field = 1
func use() { Old(); value.Method(); _ = Constant }
""")
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        declarations = {d["Name"]: d for d in data["Declarations"] if d["Name"]}
        self.assertEqual(set(declarations), {"Old", "Field", "Trailing", "Method",
                                           "Constant", "First", "Second", "InterfaceMethod"})
        self.assertEqual(declarations["Method"]["Receiver"], "*Receiver")
        self.assertIn("Additional detail.", declarations["Old"]["Doc"])
        self.assertTrue(any(d["Kind"] == "unbound-comment" for d in data["Declarations"]))
        # Identical identifiers remain candidates; the tool cannot certify bindings.
        self.assertEqual({u["Name"] for u in data["Candidates"]},
                         {"Field", "Old", "Method", "Constant"})
        self.assertEqual(data["DependencyFiles"], 1)
        self.assertEqual(data["SourceFiles"], 1)

    def test_nested_modules_and_vendor_are_not_consumer_source(self):
        (self.dependency / "lib.go").write_text("package lib\n// Deprecated: use New.\nfunc Old() {}\n")
        (self.module / "app.go").write_text("package app\nfunc use() { Old() }\n")
        nested = self.module / "nested"
        nested.mkdir()
        (nested / "go.mod").write_text("module example.invalid/nested\n")
        (nested / "invalid.go").write_text("invalid Go source")
        hidden = self.module / ".cache"
        hidden.mkdir()
        (hidden / "invalid.go").write_text("invalid Go source")
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["SourceFiles"], 1)
        self.assertEqual(len(data["Candidates"]), 1)
        self.assertEqual(data["Candidates"][0]["File"], str(self.module / "app.go"))

    def test_multiple_dependency_roots_are_fully_scanned(self):
        (self.dependency / "lib.go").write_text("package lib\n// Deprecated: use New.\nfunc Old() {}\n")
        other = self.root / "resolved dependency"
        other.mkdir()
        (other / "other.go").write_text("package other\n// DEPRECATED: use Better.\ntype Older int\n")
        result = self.scan(self.dependency, other)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["DependencyFiles"], 2)
        self.assertEqual({d["Name"] for d in data["Declarations"]}, {"Old", "Older"})

    def test_unreadable_empty_or_invalid_input_never_publishes_partial_inventory(self):
        empty = self.root / "empty"
        empty.mkdir()
        for dependency in (empty, self.root / "missing"):
            with self.subTest(dependency=dependency):
                result = self.scan(dependency)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
        (self.dependency / "valid.go").write_text("package lib\n// Deprecated: use New.\nfunc Old() {}\n")
        for invalid in (self.dependency / "broken.go", self.module / "broken.go"):
            with self.subTest(invalid=invalid):
                invalid.write_text("invalid Go source")
                result = self.scan()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                invalid.unlink()

    def test_orchestrator_retains_full_inventory_and_failed_attempts_without_verdict(self):
        (self.dependency / "lib.go").write_text("package lib\n// Deprecated: use New.\nfunc Old() {}\n")
        plugin = self.root / "isolated plugin"
        scripts = plugin / "scripts"
        scripts.mkdir(parents=True)
        for name in ("k8s-rebase-orchestrator.sh", "gate-script-lib.sh",
                     "resolve-rebase-base.sh", "deprecation-scan.go"):
            shutil.copy2(PLUGIN / "scripts" / name, scripts / name)
        gates = plugin / "gates/step3-autofix"
        gates.mkdir(parents=True)
        for suffix in ("md", "sh"):
            shutil.copy2(PLUGIN / f"gates/step3-autofix/deprecated-calls.{suffix}",
                         gates / f"deprecated-calls.{suffix}")
        environment = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_CONFIG_NOSYSTEM="1", GOFLAGS="-p=1")
        for key in list(environment):
            if key.startswith("GIT_") and key not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"):
                del environment[key]
        def git(*arguments):
            return subprocess.check_output(["git", "-C", str(self.module), *arguments],
                                           env=environment, text=True).strip()
        git("init", "-q", "-b", "main")
        git("config", "user.name", "Test")
        git("config", "user.email", "test@example.invalid")
        git("add", ".")
        git("commit", "-qm", "base")
        scratch = self.module / ".rebase-tmp"
        scratch.mkdir()
        (scratch / "base-commit").write_text(git("rev-parse", "HEAD") + "\n")
        (scratch / "state.json").write_text(json.dumps({"current_step": 3, "version": "1.37.1"}))
        command = ["bash", str(scripts / "k8s-rebase-orchestrator.sh"),
                   "gates", str(self.module), "3"]
        completed = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("PENDING: deprecated-calls", completed.stdout)
        evidence = scratch / "gates/step3-deprecated-calls.evidence"
        original = evidence.read_text()
        self.assertIn("INVENTORY_EXIT: 0", original)
        inventories = list(scratch.glob("deprecation-inventory-*/module-*/inventory.json"))
        self.assertEqual(len(inventories), 1)
        inventory_bytes = inventories[0].read_bytes()
        self.assertEqual(json.loads(inventory_bytes)["Declarations"][0]["Name"], "Old")
        self.assertFalse(evidence.with_suffix(".report").exists())
        # A later parser failure is explicit and never overwrites prior raw output.
        (self.dependency / "broken.go").write_text("invalid Go")
        failed = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("INVENTORY_EXIT: 1", evidence.read_text())
        self.assertIn("0 module inventories collected; 1 incomplete", evidence.read_text())
        self.assertEqual(inventories[0].read_bytes(), inventory_bytes)
        self.assertFalse(evidence.with_suffix(".report").exists())
        # Partial stdout from failed module discovery cannot become complete coverage.
        binaries = self.root / "fake commands"
        binaries.mkdir()
        real_find = shutil.which("find")
        fake_find = binaries / "find"
        fake_find.write_text("#!/bin/bash\n"
                             "if [[ $1 == . ]]; then echo ./go.mod; exit 9; fi\n"
                             f"exec {shlex.quote(real_find)} \"$@\"\n")
        fake_find.chmod(0o755)
        environment["PATH"] = str(binaries) + os.pathsep + environment["PATH"]
        discovery = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertEqual(discovery.returncode, 1)
        self.assertIn("MODULE_DISCOVERY_EXIT: 9", evidence.read_text())
        self.assertIn("INCOMPLETE: module discovery failed", evidence.read_text())
        self.assertNotIn("INVENTORY_EXIT:", evidence.read_text())
        fake_find.unlink()
        (self.dependency / "broken.go").unlink()
        # Moving HEAD during an otherwise successful collection invalidates evidence.
        initial = git("rev-parse", "HEAD")
        real_go = shutil.which("go")
        fake_go = binaries / "go"
        fake_go.write_text("#!/bin/bash\n"
                           "git -C \"$SCAN_TEST_REPO\" commit --allow-empty -qm movement || exit\n"
                           f"exec {shlex.quote(real_go)} \"$@\"\n")
        fake_go.chmod(0o755)
        environment["SCAN_TEST_REPO"] = str(self.module)
        movement = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertEqual(movement.returncode, 1)
        self.assertIn("INVENTORY_EXIT: 0", evidence.read_text())
        self.assertIn("INCOMPLETE: revision changed", evidence.read_text())
        self.assertIn(f"SCAN_HEAD: {initial}", evidence.read_text())
        self.assertNotEqual(initial, git("rev-parse", "HEAD"))
        self.assertEqual(inventories[0].read_bytes(), inventory_bytes)
        self.assertFalse(evidence.with_suffix(".report").exists())


if __name__ == "__main__":
    unittest.main()
