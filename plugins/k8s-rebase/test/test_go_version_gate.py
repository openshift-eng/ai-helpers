#!/usr/bin/env python3
"""Offline Go-version gate attribution checks against real Git baselines."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
GATE = PLUGIN / "gates/step4-verification/go-version-check.sh"


class GoVersionGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k8s-go-version-gate-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo with spaces"
        self.repo.mkdir()
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith(("GIT_", "BASH_FUNC_")):
                del self.env[key]
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        BASH_ENV="", ENV="")
        self.run_cmd("git", "init", "-q", "-b", "main")
        self.run_cmd("git", "config", "user.name", "Gate Fixture")
        self.run_cmd("git", "config", "user.email", "gate@example.invalid")

    def run_cmd(self, *args):
        return subprocess.run(args, cwd=self.repo, env=self.env, text=True,
                              capture_output=True, check=True, timeout=20)

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def module(self, version="1.26.0", dependency="0.36.2", path="go.mod"):
        self.write(path, f"module example.invalid/fixture\ngo {version}\n"
                   f"require k8s.io/api v{dependency}\n")

    def commit(self, message):
        self.run_cmd("git", "add", ".")
        self.run_cmd("git", "commit", "-qm", message)

    def start_rebase(self):
        self.commit("baseline")
        self.run_cmd("git", "switch", "-qc", "rebase")

    def evidence(self, expected_issues):
        self.commit("rebase change")
        before = self.run_cmd("git", "diff", "HEAD").stdout
        result = self.run_cmd("bash", str(GATE), str(self.repo))
        self.assertIn("PENDING: step4-go-version-check", result.stdout)
        directory = self.repo / ".rebase-tmp/gates"
        self.assertFalse((directory / "step4-go-version-check.crash").exists())
        self.assertFalse((directory / "step4-go-version-check.report").exists())
        evidence = (directory / "step4-go-version-check.evidence").read_text()
        head = self.run_cmd("git", "rev-parse", "HEAD").stdout.strip()
        self.assertTrue(evidence.startswith(f"HEAD: {head}\n"))
        self.assertIn(f"SUMMARY: {expected_issues} Go version issues\n", evidence)
        self.assertEqual(self.run_cmd("git", "diff", "HEAD").stdout, before)
        return evidence

    def test_same_go_dependency_bump_preserves_existing_mismatches(self):
        self.module()
        self.module("1.25.0", path="nested/go.mod")
        self.write("Dockerfile", "FROM golang:1.25 AS build\n")
        self.write("Makefile", "GO_VERSION := 1.25\n")
        self.write(".github/workflows/build.yml", "go-version: '1.25'\n")
        self.start_rebase()
        self.module(dependency="0.37.0")
        self.module("1.25.0", dependency="0.37.0", path="nested/go.mod")
        # Moving the lines or editing their comments does not change Go refs.
        self.write("Dockerfile", "# Kubernetes 1.37\nFROM golang:1.25 AS build # updated comment\n")
        self.write("Makefile", "GO_VERSION := 1.25 # Kubernetes 1.37\n")
        self.write(".github/workflows/build.yml", "name: Kubernetes 1.37\ngo-version: '1.25'\n")
        evidence = self.evidence(0)
        self.assertIn("INFO PRE-EXISTING: inconsistent go directives unchanged", evidence)
        self.assertIn("base go directive: 1.26.0", evidence)
        self.assertNotIn("NEW MISMATCH:", evidence)

    def test_real_go_bump_invalidates_previously_valid_untouched_refs(self):
        self.module("1.25.0")
        self.write("Dockerfile", "FROM golang:1.25\n")
        self.write("Dockerfile.legacy", "FROM golang:1.24\n")
        self.write("Makefile", "GOLANG_VERSION ?= 1.25\n")
        self.write(".github/workflows/build.yml", "go-version: '1.25'\n")
        self.start_rebase()
        self.module("1.26.0", dependency="0.37.0")
        evidence = self.evidence(3)
        self.assertIn("INFO PRE-EXISTING: ./Dockerfile.legacy", evidence)
        self.assertIn("NEW MISMATCH: ./Dockerfile:1:FROM golang:1.25", evidence)
        self.assertIn("base go directive: 1.25.0", evidence)

    def test_newly_changed_stale_ref_fails_without_go_bump(self):
        self.module()
        self.write("Dockerfile", "FROM golang:1.26\n")
        self.start_rebase()
        self.module(dependency="0.37.0")
        self.write("Dockerfile", "FROM golang:1.25\n")
        self.assertIn("NEW MISMATCH: ./Dockerfile:1:FROM golang:1.25", self.evidence(1))

    def test_new_stale_occurrence_does_not_inherit_existing_status(self):
        self.module()
        self.write("Dockerfile", "FROM golang:1.25 AS old\n")
        self.start_rebase()
        self.module(dependency="0.37.0")
        self.write("Dockerfile", "FROM golang:1.25 AS old\nFROM golang:1.25 AS added\n")
        evidence = self.evidence(1)
        self.assertIn("INFO PRE-EXISTING: ./Dockerfile:1:", evidence)
        self.assertIn("NEW MISMATCH: ./Dockerfile:2:", evidence)

    def test_partial_go_directive_bump_introduces_module_inconsistency(self):
        self.module("1.25.0")
        self.module("1.25.0", path="nested/go.mod")
        self.start_rebase()
        self.module("1.26.0", dependency="0.37.0")
        self.assertIn("NEW MISMATCH: inconsistent go directives", self.evidence(1))

    def test_matching_and_newer_workflow_versions_do_not_fail(self):
        self.module()
        self.write(".github/workflows/build.yml", "go-version: '1.26'\n")
        self.start_rebase()
        self.module(dependency="0.37.0")
        self.write(".github/workflows/newer.yml", "go-version: '1.27'\n")
        self.assertNotIn("NEW MISMATCH:", self.evidence(0))

    def test_symbolic_build_argument_is_not_a_literal_version_mismatch(self):
        self.module()
        self.write("Makefile", "GOLANG_VERSION ?= 1.26\nimage:\n"
                   "\tdocker build --build-arg GOLANG_VERSION=$(GOLANG_VERSION) .\n")
        self.start_rebase()
        self.module(dependency="0.37.0")
        self.assertNotIn("NEW MISMATCH:", self.evidence(0))

    def test_nested_primary_module_uses_its_actual_base_directive(self):
        self.module("1.25.0", path="go-controller/go.mod")
        self.write("Dockerfile", "FROM golang:1.25\n")
        self.start_rebase()
        self.module("1.26.0", dependency="0.37.0", path="go-controller/go.mod")
        self.assertIn("NEW MISMATCH: ./Dockerfile:1:", self.evidence(1))

    def test_new_stale_matrix_entry_after_current_entry_is_detected(self):
        self.module()
        self.write(".github/workflows/build.yml", "go-version: [1.26]\n")
        self.start_rebase()
        self.module(dependency="0.37.0")
        self.write(".github/workflows/build.yml", "go-version: [1.26, 1.25]\n")
        self.assertIn("Go 1.25; go.mod requires 1.26.0", self.evidence(1))

    def test_real_go_bump_checks_every_matrix_entry(self):
        self.module("1.25.0")
        self.write(".github/workflows/build.yml", "go-version: [1.26, 1.25]\n")
        self.start_rebase()
        self.module("1.26.0", dependency="0.37.0")
        self.assertIn("Go 1.25; go.mod requires 1.26.0", self.evidence(1))

    def test_existing_stale_later_matrix_entry_remains_pre_existing(self):
        self.module()
        self.write(".github/workflows/build.yml", "go-version: [1.26, 1.25]\n")
        self.start_rebase()
        self.module(dependency="0.37.0")
        self.assertIn("INFO PRE-EXISTING:", self.evidence(0))

    def test_added_duplicate_matrix_entry_does_not_borrow_baseline_occurrence(self):
        self.module()
        self.write(".github/workflows/build.yml", "go-version: [1.26, 1.25]\n")
        self.start_rebase()
        self.module(dependency="0.37.0")
        self.write(".github/workflows/build.yml", "go-version: [1.26, 1.25, 1.25]\n")
        evidence = self.evidence(1)
        self.assertIn("INFO PRE-EXISTING:", evidence)
        self.assertIn("NEW MISMATCH:", evidence)

    def test_nested_module_bump_invalidates_its_previously_valid_ref(self):
        self.module()
        self.module("1.25.0", path="nested/go.mod")
        self.write("nested/Dockerfile", "FROM golang:1.25\n")
        self.start_rebase()
        self.module("1.26.0", dependency="0.37.0", path="nested/go.mod")
        evidence = self.evidence(1)
        self.assertIn("NEW MISMATCH: ./nested/Dockerfile:1:", evidence)
        self.assertIn("nested/go.mod requires 1.26.0", evidence)
        self.assertNotIn("INFO PRE-EXISTING:", evidence)

    def test_nested_module_bump_preserves_its_existing_ref_debt(self):
        self.module()
        self.module("1.25.0", path="nested/go.mod")
        self.write("nested/Dockerfile", "FROM golang:1.24\n")
        self.start_rebase()
        self.module("1.26.0", dependency="0.37.0", path="nested/go.mod")
        evidence = self.evidence(0)
        self.assertIn("already mismatched nested/go.mod go 1.25.0 on base", evidence)


if __name__ == "__main__":
    unittest.main(verbosity=2)
