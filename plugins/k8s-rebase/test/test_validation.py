#!/usr/bin/env python3
"""Offline execution checks for discovery, module routing, and full coverage."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
VALIDATOR = PLUGIN / "scripts/k8s-rebase-validate.sh"


class ValidationTests(unittest.TestCase):
    def setUp(self):
        scratch = PLUGIN.parents[1] / ".work/k8s-validation-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith(("GIT_", "BASH_FUNC_", "KUBE_FEATURE_")):
                del self.env[key]
        real_go = shutil.which("go")
        self.assertTrue(real_go, "Go is required for real fixture test execution")
        self.env.update(PATH=f"{self.bin}:{os.environ['PATH']}", REAL_GO=real_go,
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        BASH_ENV="", ENV="", GOTOOLCHAIN="local", GOWORK="off",
                        GOPROXY="off", GOSUMDB="off", GOFLAGS="-p=2", GOMAXPROCS="2",
                        K8S_REBASE_IN_CONTAINER="", TEST_ROOT=str(self.root))
        self.run_cmd("git", "init", "-q", "-b", "main", check=True)
        self.run_cmd("git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                     "commit", "-q", "--allow-empty", "-m", "Baseline", check=True)
        self.run_cmd("git", "checkout", "-q", "-b", "rebase", check=True)
        self.stub("go", '''import json, os, sys
from pathlib import Path
with (Path(os.environ["TEST_ROOT"]) / "go-calls.jsonl").open("a") as log:
    log.write(json.dumps({"cwd": os.getcwd(), "argv": sys.argv[1:]}) + "\\n")
if sys.argv[1:] == ["env", "GOVERSION"] and os.getenv("FAKE_GOVERSION"):
    print(os.environ["FAKE_GOVERSION"])
else:
    os.execv(os.environ["REAL_GO"], [os.environ["REAL_GO"], *sys.argv[1:]])
''')

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env python3\n" + body)
        path.chmod(0o755)

    def run_cmd(self, *args, check=False, cwd=None, env=None):
        return subprocess.run(args, cwd=cwd or self.repo, env=env or self.env,
                              capture_output=True, text=True, check=check, timeout=60)

    def module(self, directory=".", version="1.23.0", vendor=False):
        path = self.repo / directory
        path.mkdir(parents=True, exist_ok=True)
        (path / "go.mod").write_text(f"module example.invalid/fixture\ngo {version}\n")
        if vendor:
            (path / "vendor").mkdir()
            (path / "vendor/modules.txt").write_text("")
        return path

    def package(self, module, package, label, fail=False, gate=""):
        path = module / package
        path.mkdir(parents=True, exist_ok=True)
        (path / "reach_test.go").write_text('''package fixture
import ("os"; "testing")
func TestReachability(t *testing.T) {
 t.Log(LABEL)
 if GATE != "" && os.Getenv("KUBE_FEATURE_Fixture") != GATE { t.Fatal("wrong feature gate") }
 if FAIL { t.Fatal("intentional failure") }
}
'''.replace("LABEL", json.dumps(label)).replace("GATE", json.dumps(gate))
                .replace("FAIL", "true" if fail else "false"))

    def write_test_script(self, module, roots=(), gate=""):
        hack = module / "hack"
        hack.mkdir(exist_ok=True)
        text = "#!/bin/bash\nroot_pkgs=(\n"
        text += "".join(f' "example.invalid/fixture/{p}"\n' for p in roots) + ")\n"
        if gate:
            text += f"export KUBE_FEATURE_Fixture={gate}\n"
        (hack / "test-go.sh").write_text(text)

    def validate(self, *args, cwd=None):
        return self.run_cmd("bash", str(VALIDATOR), "--test-only", *args, cwd=cwd)

    def logs(self):
        return sorted((self.repo / ".rebase-tmp").glob("test-only-*"))

    def go_calls(self):
        path = self.root / "go-calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_quick_runs_build_target_instead_of_dependency_update_default(self):
        self.module()
        (self.repo / 'fixture.go').write_text('package fixture\n')
        (self.repo / 'Makefile').write_text(
            'deps-update:\n\ttouch deps-updated\n'
            'build:\n\tgo build ./...\n\ttouch binary-built\n')
        result = self.run_cmd('bash', str(VALIDATOR), '--quick')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.repo / 'binary-built').exists())
        self.assertFalse((self.repo / 'deps-updated').exists())

    def test_build_target_failure_is_not_hidden_by_successful_default_and_vet(self):
        self.module()
        (self.repo / 'fixture.go').write_text('package fixture\n')
        (self.repo / 'Makefile').write_text('help:\n\t@echo usage\nbuild:\n\t@echo link failed\n\t@exit 1\n')
        result = self.run_cmd('bash', str(VALIDATOR), '--quick')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('link failed', (self.repo / '.rebase-tmp/root-build.log').read_text())
        self.assertNotIn('All validation passes', result.stdout)

    def test_command_evidence_keeps_actual_revision_exit_and_prior_output(self):
        self.module()
        (self.repo / 'fixture.go').write_text('package fixture\n')
        makefile = self.repo / 'Makefile'
        makefile.write_text('build:\n\t@echo first-attempt\n\t@exit 7\n')
        first_sha = self.run_cmd('git', 'rev-parse', 'HEAD', check=True).stdout.strip()
        first = self.run_cmd('bash', str(VALIDATOR), '--quick')
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        records = list((self.repo / '.rebase-tmp').glob('validation-*/command.txt'))
        failed = [p for p in records if 'COMMAND: make -C . build' in p.read_text()]
        self.assertEqual(len(failed), 1)
        record = failed[0]
        original = (record.read_bytes(), record.with_name('output.log').read_bytes())
        self.assertIn(f'HEAD: {first_sha}\n', record.read_text())
        self.assertIn(f'HEAD_AFTER: {first_sha}\n', record.read_text())
        self.assertIn('Makefile', record.with_name('worktree-before.txt').read_text())
        self.assertIn('Makefile', record.with_name('worktree-after.txt').read_text())
        self.assertIn('EXIT_STATUS: 2\n', record.read_text())  # make propagates recipe failure as 2
        self.assertIn(b'first-attempt', original[1])
        makefile.write_text('build:\n\t@echo second-attempt\n')
        self.run_cmd('git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
                     'commit', '-q', '--allow-empty', '-m', 'Follow-up', check=True)
        second = self.run_cmd('bash', str(VALIDATOR), '--quick')
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual((record.read_bytes(), record.with_name('output.log').read_bytes()), original)
        second_sha = self.run_cmd('git', 'rev-parse', 'HEAD', check=True).stdout.strip()
        latest = [p for p in (self.repo / '.rebase-tmp').glob('validation-*/command.txt')
                  if 'COMMAND: make -C . build' in p.read_text() and p != record]
        self.assertEqual(len(latest), 1)
        self.assertIn(f'HEAD: {second_sha}\n', latest[0].read_text())
        self.assertIn('EXIT_STATUS: 0\n', latest[0].read_text())
        self.assertIn('second-attempt', latest[0].with_name('output.log').read_text())

    def test_legacy_primary_module_and_prefixed_packages(self):
        primary = self.module("go-controller", vendor=True)
        root = self.module()
        self.package(primary, "pkg/safe", "primary executed", gate="primary")
        self.package(root, "pkg/safe", "wrong root", fail=True)
        self.write_test_script(primary, gate="primary")
        for package in ("./pkg/safe", "./go-controller/pkg/safe"):
            with self.subTest(package=package):
                before = set(self.logs())
                result = self.validate(package, "-v")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("primary executed", (set(self.logs()) - before).pop().read_text())
        calls = [c for c in self.go_calls() if c["argv"][0] == "test"]
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c["cwd"] == str(primary) and "-mod=vendor" in c["argv"] for c in calls))

    def test_explicit_secondary_module_and_argument_boundaries(self):
        primary = self.module("go-controller")
        secondary = self.module("test/unit tests")
        self.package(primary, "pkg/shared", "wrong primary", fail=True)
        self.package(secondary, "pkg/shared", "secondary executed", gate="fallback")
        self.write_test_script(primary, roots=("pkg/shared",), gate="fallback")
        regex = "^TestReachability$|^not a test$"
        result = self.validate("--module", "test/unit tests", "./pkg/shared", "-run", regex, "-v",
                               cwd=secondary)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("secondary executed", self.logs()[0].read_text())
        call = next(c for c in self.go_calls() if c["argv"][0] == "test")
        self.assertEqual(call["cwd"], str(secondary))
        self.assertIn(regex, call["argv"])

    def test_root_module_can_be_selected_when_go_controller_exists(self):
        primary = self.module("go-controller")
        root = self.module()
        self.package(primary, "pkg/shared", "wrong primary", fail=True)
        self.package(root, "pkg/shared", "root executed")
        result = self.validate("--module", ".", "./pkg/shared", "-v")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("root executed", self.logs()[0].read_text())

    def test_exact_privileged_exclusion_preserves_unlisted_children(self):
        module = self.module()
        self.package(module, "pkg/node", "privileged test must not execute", fail=True)
        self.package(module, "pkg/node/util", "child executed", gate="local")
        self.write_test_script(module, roots=("pkg/node",), gate="local")
        for packages in (("./pkg/node/util",), ("./pkg/node", "./pkg/node/util"),
                         ("./pkg/node/...",), ("./...",)):
            with self.subTest(packages=packages):
                before = set(self.logs())
                result = self.validate(*packages, "-v")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                log = (set(self.logs()) - before).pop().read_text()
                self.assertIn("child executed", log)
                self.assertNotIn("privileged test must not execute", log)

    def test_all_privileged_is_explicit_skip_with_independent_log(self):
        module = self.module()
        self.package(module, "pkg/node", "must not execute", fail=True)
        self.write_test_script(module, roots=("pkg/node",))
        result = self.validate("./pkg/node", "-v")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SKIP", result.stdout)
        self.assertNotIn("PASS", result.stdout)
        self.assertIn("no tests ran", self.logs()[0].read_text())
        self.assertFalse(any(c["argv"][0] == "test" for c in self.go_calls()))

    def test_failed_or_empty_wildcard_expansion_is_not_pass(self):
        module = self.module()
        self.write_test_script(module, roots=("pkg/node",))
        for pattern in ("./missing/...", "not-a-package/..."):
            with self.subTest(pattern=pattern):
                before = set(self.logs())
                result = self.validate(pattern)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("PASS", result.stdout)
                self.assertTrue((set(self.logs()) - before).pop().read_text())
        self.assertFalse(any(c["argv"][0] == "test" for c in self.go_calls()))

    def test_discovery_retains_modules_and_prunes_nested_module_packages(self):
        root = self.module()
        nested = self.module("test/unit tests")
        self.package(root, "pkg/node", "root excluded")
        self.package(root, "pkg/node/util", "root child")
        self.package(nested, "pkg/node", "nested allowed")
        self.write_test_script(root, roots=("pkg/node",))
        for excluded in (".rebase-tmp", "vendor", ".claude", ".git"):
            self.package(root, f"{excluded}/retained", "not repository tests")
            artifact = self.module(f"{excluded}/synthetic-module")
            self.package(artifact, "pkg/fixture", "not a repository module")
        instructions = (PLUGIN / "skills/k8s-rebase/steps/step4-verification.md").read_text()
        discovery = instructions.split("First, discover test packages:\n\n```bash\n", 1)[1].split("\n```", 1)[0]
        result = self.run_cmd("bash", "-ec", discovery)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["=== . ===", "./pkg/node/util",
                                                     "=== ./test/unit tests ===", "./pkg/node"])

    def test_quick_ignores_retained_evidence_modules(self):
        self.module()
        (self.repo / "fixture.go").write_text("package fixture\n")
        for excluded in (".rebase-tmp", "vendor", ".claude", ".git"):
            artifact = self.module(f"{excluded}/synthetic-module")
            (artifact / "broken.go").write_text("this retained fixture must not compile\n")
        result = self.run_cmd("bash", str(VALIDATOR), "--quick")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.go_calls())
        self.assertTrue(all(call["cwd"] == str(self.repo) for call in self.go_calls()))

    def test_invalid_module_fails_before_running_tests(self):
        self.module()
        (self.repo / "empty").mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "go.mod").write_text("module example.invalid/outside\ngo 1.23.0\n")
        (self.repo / "escape").symlink_to(outside, target_is_directory=True)
        for args in (("--module",), ("--module", "--bad", "."), ("--module", "empty", "."),
                     ("--module", "missing", "."), ("--module", "../outside", "."),
                     ("--module", "escape", "."), ("--module", str(outside), ".")):
            with self.subTest(args=args):
                result = self.validate(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ERROR:", result.stdout + result.stderr)
        self.assertFalse(any(c["argv"][0] == "test" for c in self.go_calls()))

    def test_container_uses_selected_module_version_and_preserves_argv(self):
        for key in ("K8S_REBASE_CONTAINER_MEMORY", "K8S_REBASE_CONTAINER_MEMORY_SWAP",
                    "K8S_REBASE_CONTAINER_CPUS", "TMPDIR"):
            self.env.pop(key, None)
        self.module("go-controller", version="1.23.0")
        self.module("test/unit tests", version="1.25.0")
        self.env["FAKE_GOVERSION"] = "go1.23.0"
        self.stub("podman", '''import json, os, sys
from pathlib import Path
(Path(os.environ["TEST_ROOT"]) / "container.json").write_text(json.dumps(sys.argv[1:]))
''')
        args = ("--module", "test/unit tests", "./pkg/safe", "-run", "name with spaces")
        result = self.validate(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        argv = json.loads((self.root / "container.json").read_text())
        self.assertIn("docker.io/library/golang:1.25.0", argv)
        for flag in ("--memory", "--memory-swap", "--cpus", "TMPDIR=/task-tmp"):
            self.assertNotIn(flag, argv)
        self.assertIn("--userns=keep-id", argv)
        self.assertNotIn("--privileged", argv)
        self.assertEqual(argv[argv.index("--test-only") + 1:], list(args))

    def test_full_on_nonroot_current_go_requests_privileged_container(self):
        self.module()
        self.env["FAKE_GOVERSION"] = "go1.99.0"
        self.env.update(GOMAXPROCS="1", GOFLAGS="-p=1 -mod=readonly",
                        GOMEMLIMIT="1GiB", K8S_REBASE_CONTAINER_MEMORY="2g",
                        K8S_REBASE_CONTAINER_MEMORY_SWAP="2g",
                        K8S_REBASE_CONTAINER_CPUS="1.5", TMPDIR=str(self.root / "temporary path with spaces"),
                        VALIDATION_TIMEOUT="10m", LINT_TIMEOUT="12m",
                        GOCACHE=str(self.root / "cache with spaces"))
        Path(self.env["TMPDIR"]).mkdir()
        self.stub("id", 'print("1000")\n')
        self.stub("podman", '''import json, os, sys
from pathlib import Path
(Path(os.environ["TEST_ROOT"]) / "container.json").write_text(json.dumps(sys.argv[1:]))
sys.exit(125)
''')
        result = self.run_cmd("bash", str(VALIDATOR), "--full")
        self.assertEqual(result.returncode, 125, result.stdout + result.stderr)
        argv = json.loads((self.root / "container.json").read_text())
        self.assertIn("--privileged", argv)
        self.assertNotIn("--userns=keep-id", argv)
        self.assertEqual(argv[-1], "--full")
        self.assertIn("GOMAXPROCS=1", argv)
        self.assertIn("GOFLAGS=-p=1 -mod=readonly", argv)
        self.assertIn("GOMEMLIMIT=1GiB", argv)
        self.assertIn("VALIDATION_TIMEOUT=10m", argv)
        self.assertIn("LINT_TIMEOUT=12m", argv)
        self.assertEqual(argv[argv.index("--memory") + 1], "2g")
        self.assertIn("--memory-swap", argv)
        self.assertEqual(argv[argv.index("--memory-swap") + 1], "2g")
        self.assertIn("--cpus", argv)
        self.assertEqual(argv[argv.index("--cpus") + 1], "1.5")
        self.assertIn(f"{self.env['TMPDIR']}:/task-tmp", argv)
        self.assertIn("TMPDIR=/task-tmp", argv)
        self.assertIn(f"GOCACHE={self.env['GOCACHE']}", argv)
        self.assertIn(f"{self.env['GOCACHE']}:{self.env['GOCACHE']}", argv)
        self.assertNotIn("All validation passes", result.stdout)
        self.assertFalse(any(c["argv"][0] == "test" for c in self.go_calls()))

    def test_container_rejects_missing_configured_tmpdir_before_launch(self):
        self.module()
        self.env.update(FAKE_GOVERSION="go1.99.0", TMPDIR=str(self.root / "missing scratch"))
        self.stub("id", 'print("1000")\n')
        self.stub("podman", 'raise SystemExit("container must not be launched")\n')
        result = self.run_cmd("bash", str(VALIDATOR), "--full")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("TMPDIR must be an existing directory", result.stderr)
        self.assertNotIn("container must not be launched", result.stderr)

    def test_full_without_root_or_runtime_records_unresolved_coverage(self):
        module = self.module()
        self.package(module, "pkg/node", "must not execute", fail=True)
        self.write_test_script(module, roots=("pkg/node", "pkg/stale"))
        self.stub("id", 'print("1000")\n')
        # Limit PATH to the tools used by validation, excluding both runtimes.
        # No daemon is contacted even when the host has podman/docker installed.
        for tool in ("bash", "git", "mkdir", "grep", "sed", "awk", "find", "sort",
                     "head", "cut", "timeout", "tail", "cat", "wc", "chmod", "tr",
                     "tee", "python3", "dirname", "basename", "mktemp", "cp"):
            (self.bin / tool).symlink_to(shutil.which(tool))
        self.env["PATH"] = str(self.bin)
        result = self.run_cmd("bash", str(VALIDATOR), "--full")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("All validation passes", result.stdout)
        summary = (self.repo / ".rebase-tmp/summary.txt").read_text()
        self.assertIn("INCONCLUSIVE PRIVILEGED TESTS", summary)
        self.assertIn("pkg/node", summary)
        self.assertNotIn("pkg/stale", summary)
        self.assertIn("Skipping stale: pkg/stale", result.stdout)
        calls = [c for c in self.go_calls() if c["argv"][0] == "test"]
        self.assertTrue(calls)
        self.assertTrue(all("-run=^$" in c["argv"] for c in calls))

    def test_full_nonroot_container_does_not_report_privileged_pass(self):
        module = self.module()
        self.package(module, "pkg/node", "must not execute", fail=True)
        self.write_test_script(module, roots=("pkg/node",))
        self.env["K8S_REBASE_IN_CONTAINER"] = "1"
        self.stub("id", 'print("1000")\n')
        self.stub("jq", 'raise SystemExit("unexpected jq invocation")\n')
        result = self.run_cmd("bash", str(VALIDATOR), "--full")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("INCONCLUSIVE PRIVILEGED TESTS", result.stdout)
        self.assertNotIn("All validation passes", result.stdout)

    def test_full_root_path_executes_tests_and_preserves_failure(self):
        module = self.module()
        self.write_test_script(module, roots=("pkg/node",), gate="full")
        # Simulate only the shell's UID branch; the real Go fixture is harmless
        # and runs under the invoking user's actual UID without host changes.
        self.env["K8S_REBASE_IN_CONTAINER"] = "1"
        self.stub("id", 'print("0")\n')
        self.stub("sudo", 'raise SystemExit("unexpected sudo invocation")\n')
        self.stub("jq", 'raise SystemExit("unexpected jq invocation")\n')
        marker = self.root / "full-test-executed"
        for fail in (False, True):
            with self.subTest(fail=fail):
                marker.unlink(missing_ok=True)
                self.package(module, "pkg/node", "full test body executed", fail=fail, gate="full")
                source = module / "pkg/node/reach_test.go"
                source.write_text(source.read_text().replace(
                    ' t.Log(', f' if err := os.WriteFile({json.dumps(str(marker))}, []byte("executed"), 0600); err != nil {{ t.Fatal(err) }}\n t.Log('))
                result = self.run_cmd("bash", str(VALIDATOR), "--full")
                self.assertEqual(result.returncode, int(fail), result.stdout + result.stderr)
                self.assertEqual(marker.read_text(), "executed")
                log = (self.repo / ".rebase-tmp/priv-node.log").read_text()
                if fail:
                    self.assertIn("intentional failure", log)
                    self.assertIn("PRIVILEGED TEST FAILURE", result.stdout)
                else:
                    self.assertIn("All validation passes", result.stdout)

    def test_parallel_pass_and_failure_keep_separate_logs_and_shared_summary(self):
        module = self.module()
        self.package(module, "pkg/pass", "pass executed")
        self.package(module, "pkg/fail", "failure executed", fail=True)
        tmp = self.repo / ".rebase-tmp"
        tmp.mkdir()
        summary = tmp / "summary.txt"
        summary.write_text("previous full validation evidence\n")
        with ThreadPoolExecutor(max_workers=2) as pool:
            passed = pool.submit(self.validate, "./pkg/pass", "-v")
            failed = pool.submit(self.validate, "./pkg/fail", "-v")
            self.assertEqual(passed.result().returncode, 0)
            self.assertEqual(failed.result().returncode, 1)
        self.assertEqual(len(self.logs()), 2)
        content = "".join(p.read_text() for p in self.logs())
        self.assertIn("pass executed", content)
        self.assertIn("failure executed", content)
        self.assertIn("intentional failure", content)
        self.assertEqual(summary.read_text(), "previous full validation evidence\n")


if __name__ == "__main__":
    unittest.main()
