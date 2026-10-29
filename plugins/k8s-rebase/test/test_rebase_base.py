#!/usr/bin/env python3
"""Rebase baseline and import-repair scope checks using real Git histories."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
HELPER = PLUGIN / "scripts/resolve-rebase-base.sh"
AUTOFIX = (PLUGIN / "scripts/k8s-rebase-autofix.sh").read_text()
IMPORTS = "fix_imports() {" + AUTOFIX.split("fix_imports() {", 1)[1].split(
    "\nfix_bounding_dirs() {", 1)[0]
REBASE = (PLUGIN / "scripts/k8s-rebase.sh").read_text()
BRANCH = REBASE.split("# Ensure default branch is current with remote\n", 1)[1].split(
    "# ── Derivation function", 1)[0]


class RebaseBaseTests(unittest.TestCase):
    def setUp(self):
        work = PLUGIN.parents[1] / ".work/rebase-base-tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=work)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith(("GIT_", "BASH_FUNC_")):
                del self.env[key]
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        BASH_ENV="", ENV="")
        self.git("init", "-q", "-b", "release-5.1")
        self.git("config", "user.name", "Baseline Fixture")
        self.git("config", "user.email", "baseline@example.invalid")
        (self.repo / ".git/info/exclude").write_text(".rebase-tmp/\n")
        self.write("go.mod", "module example.invalid/fixture\ngo 1.26.0\n")
        self.write("active.go", "package fixture\nvar    Active = 1\n")
        self.initial = self.commit("initial")
        self.record = self.repo / ".rebase-tmp/base-commit"
        self.record.parent.mkdir()
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        shutil.copyfile(HELPER, self.scripts / HELPER.name)

    def run_cmd(self, *args, check=True, cwd=None):
        return subprocess.run(args, cwd=cwd or self.repo, env=self.env, text=True,
                              capture_output=True, check=check, timeout=20)

    def git(self, *args, check=True):
        return self.run_cmd("git", *args, check=check)

    def write(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message, "--allow-empty")
        return self.git("rev-parse", "HEAD").stdout.strip()

    def resolve(self, tip=None, check=True):
        args = ["bash", str(HELPER), str(self.repo)]
        if tip is not None:
            args.append(tip)
        return self.run_cmd(*args, check=check)

    def remote_default(self, commit):
        self.git("update-ref", "refs/remotes/origin/release-5.1", commit)
        self.git("symbolic-ref", "refs/remotes/origin/HEAD",
                 "refs/remotes/origin/release-5.1")

    def record_base(self, commit):
        self.record.write_text(commit + "\n")

    def install_formatters(self):
        binary = self.root / "bin"
        binary.mkdir()
        self.format_log = self.root / "formatters.jsonl"
        formatter = """#!/usr/bin/env python3
import json, os, pathlib, sys
with open(os.environ['FORMAT_LOG'], 'a') as out:
    out.write(json.dumps({'tool': pathlib.Path(sys.argv[0]).name, 'args': sys.argv[1:]}) + '\\n')
if pathlib.Path(sys.argv[0]).name == 'goimports':
    path = pathlib.Path(sys.argv[-1])
    path.write_text(path.read_text().replace('var    ', 'var '))
"""
        for tool in ("goimports", "gci"):
            path = binary / tool
            path.write_text(formatter)
            path.chmod(0o755)
        self.env.update(PATH=str(binary) + os.pathsep + self.env["PATH"],
                        FORMAT_LOG=str(self.format_log))

    def import_fix(self, check=True):
        wrapper = self.scripts / "import-test.sh"
        wrapper.write_text('''#!/bin/bash
set -uo pipefail
REPO_ROOT=$1
PRIMARY_GOMOD=go.mod
''' + IMPORTS + "\nfix_imports\n")
        return self.run_cmd("bash", str(wrapper), str(self.repo), check=check)

    def branch_creation(self, check=True):
        wrapper = self.scripts / "branch-test.sh"
        wrapper.write_text('''#!/bin/bash
set -euo pipefail
REPO_ROOT=$1
REBASE_TMP="$REPO_ROOT/.rebase-tmp"
K8S_MAJOR_MINOR=1.37
info() { printf ':: %s\\n' "$*" >&2; }
die() { printf 'ERROR: %s\\n' "$*" >&2; exit 1; }
''' + BRANCH)
        return self.run_cmd("bash", str(wrapper), str(self.repo), check=check)

    def crd_evidence(self):
        result = self.run_cmd("bash", str(PLUGIN / "gates/step3-autofix/crd-validation.sh"),
                              str(self.repo))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return (self.repo / ".rebase-tmp/gates/step3-crd-validation.evidence").read_text()

    def test_crd_yaml_and_yml_with_spaces_are_compared_and_vendor_excluded(self):
        crd = "kind: CustomResourceDefinition\nspec:\n  minimum: 0\n"
        for name in ("deployments/schema with spaces.yml", "deployments/other.yaml",
                     "vendor/ignored.yml", "nested/vendor/ignored.yaml"):
            self.write(name, crd)
        base = self.commit("CRD baseline")
        self.record_base(base)
        self.write("deployments/schema with spaces.yml", crd.replace("minimum: 0", "minimum: -1"))
        self.write("deployments/new schema.yml", crd)
        candidate = self.commit("CRD candidate")
        evidence = self.crd_evidence()
        self.assertIn(f"HEAD: {candidate}", evidence)
        self.assertIn("deployments/schema with spaces.yml CHANGED-VALIDATION: 1", evidence)
        self.assertIn("deployments/other.yaml IDENTICAL", evidence)
        self.assertIn("deployments/new schema.yml ALL-NEW", evidence)
        self.assertIn("NEW_ISSUES=2", evidence)
        self.assertNotIn("vendor/ignored", evidence)
        self.assertNotIn("SKIP", evidence)

    def test_no_crds_skips_despite_vendor_crd_and_regular_yml(self):
        self.write("vendor/ignored.yml", "kind: CustomResourceDefinition\n")
        self.write("deployments/ordinary manifest.yml", "kind: Deployment\n")
        self.commit("No owned CRDs")
        self.record_base(self.initial)
        self.assertIn("SKIP: no CRD files found", self.crd_evidence())

    def test_recorded_commit_wins_when_remote_default_moves(self):
        self.record_base(self.initial)
        self.remote_default(self.initial)
        self.git("switch", "-qc", "bump1.37")
        self.write("active.go", "package fixture\nvar    Active = 2\n")
        tip = self.commit("rebase")
        self.remote_default(tip)
        result = self.resolve()
        self.assertEqual(result.stdout, self.initial + "\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.resolve(self.initial).stdout, self.initial + "\n")

    def test_release_default_without_master_or_main(self):
        self.remote_default(self.initial)
        self.git("switch", "-qc", "bump1.37")
        self.commit("rebase")
        self.assertEqual(self.resolve().stdout, self.initial + "\n")
        for name in ("master", "main"):
            self.assertNotEqual(self.git("show-ref", "--verify", "refs/heads/" + name,
                                        check=False).returncode, 0)

    def test_release_tracking_branch_without_origin_head(self):
        self.git("remote", "add", "origin", str(self.root / "not-contacted"))
        self.git("update-ref", "refs/remotes/origin/release-5.1", self.initial)
        self.git("switch", "-qc", "bump1.37")
        self.git("branch", "--set-upstream-to", "origin/release-5.1")
        self.commit("local work")
        self.assertEqual(self.resolve().stdout, self.initial + "\n")

    def test_tracking_published_rebase_branch_requires_verified_record(self):
        self.git("remote", "add", "origin", str(self.root / "not-contacted"))
        self.remote_default(self.initial)
        self.git("switch", "-qc", "bump1.37")
        tip = self.commit("rebase")
        self.git("update-ref", "refs/remotes/origin/bump1.37", tip)
        self.git("branch", "--set-upstream-to", "origin/bump1.37")
        result = self.resolve(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('does not identify its starting commit', result.stderr)
        self.record_base(self.initial)
        self.assertEqual(self.resolve().stdout, self.initial + '\n')

    def test_release_tracking_branch_precedes_different_remote_default(self):
        self.git("remote", "add", "origin", str(self.root / "not-contacted"))
        self.git("update-ref", "refs/remotes/origin/main", self.initial)
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        self.write("historical.go", "package fixture\nvar Historical = 1\n")
        base = self.commit("unrelated release work")
        self.git("update-ref", "refs/remotes/origin/release-5.1", base)
        self.git("switch", "-qc", "bump1.37")
        self.git("branch", "--set-upstream-to", "origin/release-5.1")
        self.write("active.go", "package fixture\nvar Active = 2\n")
        self.commit("rebase")
        self.assertEqual(self.resolve().stdout, base + "\n")
        self.assertEqual(self.git("diff", "--name-only", base + "..HEAD").stdout, "active.go\n")

    def test_gate_diff_and_history_examples_stop_on_invalid_record(self):
        self.record.write_text("invalid baseline\n")
        self.env["PLUGIN_ROOT"] = str(PLUGIN)
        scope = (PLUGIN / 'gates/step2-compilation/diff-scope.md').read_text()
        maintainer = (PLUGIN / 'gates/step4-verification/maintainer-review.md').read_text()
        examples = [scope.split('`')[1]]
        examples.extend(line.strip() for line in maintainer.splitlines()
                        if line.startswith('  BASE=') and ('git log ' in line or 'git diff ' in line))
        self.assertEqual(len(examples), 3)
        for command in examples:
            with self.subTest(command=command):
                result = self.run_cmd('bash', '-c', command, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ERROR:', result.stderr)
                self.assertEqual(result.stdout, '')

    def test_default_remote_precedes_legacy_master(self):
        self.git("branch", "master", self.initial)
        base = self.commit("release advances")
        self.remote_default(base)
        self.git("switch", "-qc", "bump1.37")
        self.commit("rebase")
        self.assertEqual(self.resolve().stdout, base + "\n")

    def test_legacy_main_is_used_when_no_default_metadata_exists(self):
        self.git("branch", "main", self.initial)
        self.commit("rebase")
        self.assertEqual(self.resolve().stdout, self.initial + "\n")

    def test_invalid_record_never_falls_back_to_valid_remote(self):
        self.remote_default(self.initial)
        for invalid in ("HEAD\n", self.initial[:12] + "\n", "", "f" * 40 + "\n",
                        self.initial + "\n" + self.initial + "\n"):
            with self.subTest(record=invalid):
                self.record.write_text(invalid)
                result = self.resolve(check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("ERROR: Cannot resolve rebase baseline:", result.stderr)
                self.assertEqual(self.record.read_text(), invalid)

    def test_recorded_commit_must_be_ancestor_of_requested_tip(self):
        later = self.commit("later")
        self.record_base(later)
        self.remote_default(self.initial)
        result = self.resolve(self.initial, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not an ancestor", result.stderr)
        self.assertEqual(self.resolve().stdout, later + "\n")
        self.assertNotEqual(self.resolve("not-a-tip", check=False).returncode, 0)

    def test_unrelated_record_is_rejected(self):
        orphan = self.git("commit-tree", "HEAD^{tree}", "-m", "unrelated root").stdout.strip()
        self.record_base(orphan)
        self.remote_default(self.initial)
        result = self.resolve(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not an ancestor", result.stderr)
        self.assertEqual(self.record.read_text(), orphan + "\n")

    def test_no_arbitrary_history_fallback_or_formatting(self):
        for index in range(12):
            self.commit(f"history {index}")
        self.write("active.go", "package fixture\nvar    Active = 2\n")
        self.install_formatters()
        before = (self.repo / "active.go").read_bytes()
        result = self.import_fix(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no recorded baseline or usable default/tracking branch", result.stderr)
        self.assertFalse(self.format_log.exists())
        self.assertEqual((self.repo / "active.go").read_bytes(), before)

    def test_imports_ignore_historical_files_and_handle_filenames_safely(self):
        historical = "package fixture\nvar    Historical = 1\n"
        for index in range(9):
            self.commit(f"history {index}")
        self.write("historical.go", historical)
        self.commit("unformatted file before rebase")
        self.write("removed.go", "package fixture\n")
        base = self.commit("starting release")
        self.record_base(base)
        self.git("switch", "-qc", "bump1.37")
        self.write("active.go", "package fixture\nvar    Active = 2\n")
        self.commit("committed rebase change")
        self.assertIn("historical.go", self.git("diff", "--name-only", "HEAD~10").stdout)
        unusual = "nested dir/file with\na newline.go"
        self.write(unusual, "package fixture\nvar    Added = 1\n")
        self.write("vendor/dep/ignored.go", "package dep\nvar    Vendor = 1\n")
        self.write("nested/vendor/dep/ignored.go", "package dep\nvar    Nested = 1\n")
        self.write("nested/zz_generated.deepcopy.go", "package fixture\nvar    Generated = 1\n")
        self.git("add", "-A")
        (self.repo / "removed.go").unlink()
        self.write(".golangci.yml", "linters:\n  gci:\n    sections:\n      - standard\n      - default\n")
        self.install_formatters()
        self.import_fix()
        calls = [json.loads(line) for line in self.format_log.read_text().splitlines()]
        wanted = {str(self.repo / "active.go"), str(self.repo / unusual)}
        for tool in ("goimports", "gci"):
            self.assertEqual({call["args"][-1] for call in calls if call["tool"] == tool}, wanted)
        self.assertEqual((self.repo / "historical.go").read_text(), historical)
        self.assertIn("var Added", (self.repo / unusual).read_text())
        self.assertIn("var    Vendor", (self.repo / "vendor/dep/ignored.go").read_text())

    def test_imports_use_release_default_without_record(self):
        self.write("historical.go", "package fixture\nvar    Historical = 1\n")
        base = self.commit("starting release")
        self.remote_default(base)
        self.git("switch", "-qc", "bump1.37")
        self.write("active.go", "package fixture\nvar    Active = 2\n")
        self.commit("rebase")
        self.install_formatters()
        self.import_fix()
        calls = [json.loads(line) for line in self.format_log.read_text().splitlines()]
        self.assertEqual([call["args"][-1] for call in calls], [str(self.repo / "active.go")])
        self.assertIn("var    Historical", (self.repo / "historical.go").read_text())

    def test_step1_records_after_default_fast_forward(self):
        origin = self.root / "origin.git"
        self.run_cmd("git", "clone", "--bare", "-q", str(self.repo), str(origin))
        for key, value in (("user.name", "Baseline Fixture"),
                           ("user.email", "baseline@example.invalid")):
            self.run_cmd("git", "-C", str(origin), "config", key, value)
        newer = self.run_cmd("git", "-C", str(origin), "commit-tree", "HEAD^{tree}",
                             "-p", self.initial, "-m", "upstream advance").stdout.strip()
        self.run_cmd("git", "-C", str(origin), "update-ref", "refs/heads/release-5.1", newer)
        self.git("remote", "add", "origin", str(origin))
        self.remote_default(self.initial)
        self.branch_creation()
        self.assertEqual(self.record.read_text(), newer + "\n")
        self.assertEqual(self.git("branch", "--show-current").stdout.strip(), "bump1.37")
        self.assertEqual(self.resolve().stdout, newer + "\n")
        start = self.repo / ".rebase-tmp/start-branch"
        self.assertEqual(start.read_text(), "release-5.1\n")

    def test_step1_records_pr_start_branch_for_detached_and_resumed_runs(self):
        start = self.repo / ".rebase-tmp/start-branch"
        self.git("checkout", "-q", "--detach")
        self.branch_creation()
        # Detached starts fall back to the default branch.
        self.assertEqual(start.read_text(), "main\n")
        start.write_text("release-5.1\n")
        self.git("checkout", "-q", "release-5.1")
        self.git("branch", "-q", "-D", "bump1.37")
        self.git("checkout", "-q", "-b", "other-work")
        self.branch_creation()
        self.assertEqual(start.read_text(), "release-5.1\n")

    def test_step1_preserves_existing_compatible_record(self):
        self.record_base(self.initial)
        self.commit("already recorded work")
        self.branch_creation()
        self.assertEqual(self.record.read_text(), self.initial + "\n")

    def test_step1_rejects_incompatible_record_before_branch_creation(self):
        original = "HEAD\n"
        self.record.write_text(original)
        result = self.branch_creation(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Existing rebase baseline is invalid", result.stderr)
        self.assertEqual(self.record.read_text(), original)
        self.assertEqual(self.git("branch", "--show-current").stdout.strip(), "release-5.1")

    def test_signalled_script_exits_instead_of_resuming_without_push_guard(self):
        lines = REBASE.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("cleanup_hook() {"))
        end = max(i for i, line in enumerate(lines[:60]) if line.startswith("trap "))
        setup = "\n".join(lines[start:end + 1])
        hook = self.repo / ".git/hooks/pre-push"
        for name, sig, code in (("TERM", signal.SIGTERM, 143), ("INT", signal.SIGINT, 130)):
            with self.subTest(signal=name):
                hook.parent.mkdir(exist_ok=True)
                hook.write_text("#!/bin/sh\n# k8s-rebase push guard\n")
                marker = self.repo / "continued"
                marker.unlink(missing_ok=True)
                script = ("set -euo pipefail\n" + setup +
                          '\nsleep 1\ntouch continued\n')
                proc = subprocess.Popen(["bash", "-c", script], cwd=self.repo, env=self.env,
                                        text=True, stderr=subprocess.PIPE,
                                        start_new_session=True)
                time.sleep(0.3)
                os.kill(proc.pid, sig)
                _, stderr = proc.communicate(timeout=10)
                self.assertEqual(proc.returncode, code, stderr)
                self.assertFalse(marker.exists(), "script resumed after the signal")
                self.assertFalse(hook.exists())
                self.assertIn("ERROR:", stderr)
                self.assertNotIn("crashed", stderr)


if __name__ == "__main__":
    unittest.main()
