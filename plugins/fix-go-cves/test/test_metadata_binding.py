#!/usr/bin/env python3
"""Offline real-Go controls for internal metadata ownership and native binding."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


@unittest.skipUnless(all(shutil.which(x) for x in ("go", "git", "bash", "jq", "timeout")),
                     "Go, Git, Bash, jq and timeout are required")
class MetadataBinding(unittest.TestCase):
    def setUp(self):
        scratch = PLUGIN.parents[1] / ".work" / "fix-go-cves-metadata-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {**os.environ, "GOENV": "off", "GOWORK": "off", "GOFLAGS": "",
                    "GOTOOLCHAIN": "local", "GOPROXY": "off", "GOSUMDB": "off",
                    "GOPRIVATE": "", "GONOPROXY": "none", "GOEXPERIMENT": ",",
                    "GOMODCACHE": str(self.root / "cache"),
                    "GIT_CEILING_DIRECTORIES": str(self.root)}
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.run_cmd(["git", "init", "-q"])
        self.run_cmd(["git", "config", "user.name", "Test"])
        self.run_cmd(["git", "config", "user.email", "test@example.invalid"])
        (self.repo / "go.mod").write_text("module example.invalid/target\n\ngo 1.24.0\n")
        self.commit()
        self.base = self.run_cmd(["git", "rev-parse", "HEAD"]).stdout.strip()
        self.state = self.root / "state.env"
        self.state.write_text(f"REPO={str(self.repo)!r}\nBRANCH=main\nBUILD_GO_VERSION=unknown\nHAS_VENDOR=false\n")
        self.outside = self.root / "outside module.mod"
        self.outside.write_text("module example.invalid/outside\n\ngo 1.24.0\n")
        self.outside_bytes = self.outside.read_bytes()

    def run_cmd(self, args, *, env=None, check=True, cwd=None):
        result = subprocess.run(args, cwd=cwd or self.repo,
                                env={**self.env, **(env or {})}, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def commit(self):
        self.run_cmd(["git", "add", "-A"])
        self.run_cmd(["git", "commit", "-qm", "fixture"])

    def shell(self, command, *args, env=None, check=True):
        return self.run_cmd(["bash", "-c", 'source "$1/lib.sh"; shift; ' + command,
                             "bash", str(SCRIPTS), *map(str, args)], env=env, check=check)

    def stdlib(self, env=None, check=True):
        return self.run_cmd(["bash", str(SCRIPTS / "fix-stdlib.sh"), str(self.state),
                             "1.24.1", "", "CVE-TEST"], env=env, check=check)

    def test_stdlib_binds_absolute_relative_and_stored_alternates(self):
        (self.root / "outside.mod").write_bytes(self.outside_bytes)
        stored = self.root / "goenv"
        stored.write_text(f"GOFLAGS='-modfile={self.outside}'\n")
        variants = [{"GOFLAGS": f"'-modfile={self.outside}'"},
                    {"GOFLAGS": "-modfile=../outside.mod"},
                    {"GOENV": str(stored)}]
        for env in variants:
            with self.subTest(env=env):
                self.run_cmd(["git", "reset", "--hard", "-q", self.base])
                self.stdlib(env)
                self.assertIn("toolchain go1.24.1", (self.repo / "go.mod").read_text())
                self.assertEqual(self.outside.read_bytes(), self.outside_bytes)
                self.assertEqual((self.root / "outside.mod").read_bytes(), self.outside_bytes)
                self.assertEqual(self.run_cmd(["git", "status", "--porcelain"]).stdout, "")

    def test_overlay_and_alias_do_not_change_internal_reads(self):
        overlay = self.root / "overlay.json"
        overlay.write_text(json.dumps({"Replace": {str(self.repo / "go.mod"): str(self.outside)}}))
        alias = self.root / "alias.mod"
        alias.symlink_to(self.repo / "go.mod")
        flags = f"-modfile={alias} -overlay={overlay} -tags=example"
        result = self.shell('module_go . list -m -mod=readonly -json', env={"GOFLAGS": flags})
        module = json.loads(result.stdout)
        self.assertEqual(module["Path"], "example.invalid/target")
        self.assertEqual(Path(module["GoMod"]), self.repo / "go.mod")
        self.stdlib({"GOFLAGS": flags})
        self.assertIn("toolchain go1.24.1", (self.repo / "go.mod").read_text())
        self.assertEqual(self.outside.read_bytes(), self.outside_bytes)
        self.assertFalse((self.root / "alias.sum").exists())

    def test_sum_link_and_module_parent_escape_are_rejected(self):
        (self.repo / "go.sum").symlink_to(self.outside)
        result = self.stdlib(check=False)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertNotIn("toolchain", (self.repo / "go.mod").read_text())
        self.assertEqual(self.outside.read_bytes(), self.outside_bytes)
        (self.repo / "go.sum").unlink()
        nested = self.repo / "tools"
        nested.mkdir()
        (nested / "go.mod").write_text("module example.invalid/tools\n\ngo 1.24.0\n")
        self.commit()
        shutil.rmtree(nested)
        nested.symlink_to(self.root, target_is_directory=True)
        (self.root / "go.mod").write_bytes(self.outside_bytes)
        result = self.stdlib(check=False)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual((self.root / "go.mod").read_bytes(), self.outside_bytes)
        # Locate/audit paths share the same state-loading ownership boundary.
        result = self.run_cmd(["bash", str(SCRIPTS / "locate.sh"), str(self.state),
                               "example.invalid/dep"], check=False)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("linked module path", result.stdout)
        self.assertEqual((self.root / "go.mod").read_bytes(), self.outside_bytes)

    def test_mutable_metadata_hardlinks_are_rejected(self):
        for name in ("go.mod", "go.sum", "go.work", "go.work.sum"):
            with self.subTest(name=name):
                repo = self.root / ("hardlink-" + name)
                shutil.copytree(self.repo, repo)
                if name.startswith("go.work"):
                    (repo / "go.work").write_text("go 1.24.0\n\nuse .\n")
                contents = (repo / name).read_bytes() if (repo / name).exists() else b"sum fixture\n"
                outside = self.root / ("outside-" + name)
                outside.write_bytes(contents)
                (repo / name).unlink(missing_ok=True)
                os.link(outside, repo / name)
                self.run_cmd(["git", "add", "-A"], cwd=repo)
                self.run_cmd(["git", "commit", "--allow-empty", "-qm", "shared metadata"], cwd=repo)
                state = self.root / (name + ".env")
                state.write_text(f"REPO={str(repo)!r}\nBRANCH=main\nBUILD_GO_VERSION=unknown\n")
                result = self.run_cmd(["bash", str(SCRIPTS / "fix-stdlib.sh"), str(state),
                                       "1.24.1", "", "CVE-TEST"], check=False)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("one link", result.stdout)
                self.assertEqual(outside.read_bytes(), contents)
                self.assertEqual((repo / name).read_bytes(), contents)

    def test_workspace_outside_member_is_rejected_without_writes(self):
        outside_repo = self.root / "outside"
        outside_repo.mkdir()
        (outside_repo / "go.mod").write_bytes(self.outside_bytes)
        (self.repo / "go.work").write_text("go 1.24.0\n\nuse (\n .\n ../outside\n)\n")
        self.commit()
        before = self.run_cmd(["git", "rev-parse", "HEAD"]).stdout
        result = self.run_cmd(["bash", str(SCRIPTS / "fix-package.sh"), str(self.state),
                               "example.invalid/dep", "1.0.1", "CVE-TEST"], check=False)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("outside the checkout", result.stdout)
        self.assertEqual(self.run_cmd(["git", "rev-parse", "HEAD"]).stdout, before)
        self.assertEqual(self.run_cmd(["git", "status", "--porcelain"]).stdout, "")
        self.assertEqual((outside_repo / "go.mod").read_bytes(), self.outside_bytes)

    def package_fixture(self):
        proxy = self.root / "proxy" / "example.invalid" / "dep" / "@v"
        proxy.mkdir(parents=True)
        for version in ("v1.0.0", "v1.0.1"):
            mod = "module example.invalid/dep\n\ngo 1.24.0\n"
            (proxy / f"{version}.mod").write_text(mod)
            (proxy / f"{version}.info").write_text(json.dumps({"Version": version, "Time": "2026-01-01T00:00:00Z"}))
            with zipfile.ZipFile(proxy / f"{version}.zip", "w") as archive:
                archive.writestr(f"example.invalid/dep@{version}/go.mod", mod)
                archive.writestr(f"example.invalid/dep@{version}/dep.go", f'package dep\nconst Value = "{version}"\n')
        (proxy / "list").write_text("v1.0.0\nv1.0.1\n")
        self.env["GOPROXY"] = (self.root / "proxy").as_uri()
        (self.repo / ".gitignore").write_text("/output\n")
        (self.repo / "main.go").write_text('package main\nimport "example.invalid/dep"\nfunc main() { println(dep.Value) }\n')
        with (self.repo / "go.mod").open("a") as file:
            file.write("\nrequire example.invalid/dep v1.0.0\n")
        self.run_cmd(["go", "mod", "tidy"])
        self.run_cmd(["go", "mod", "vendor"])
        self.commit()
        with self.state.open("a") as file:
            file.write("HAS_VENDOR=true\nBUILD_CMD='go build -mod=vendor -o output . '\n")

    def test_real_package_binding_vendor_and_rollback(self):
        self.package_fixture()
        base = self.run_cmd(["git", "rev-parse", "HEAD"]).stdout.strip()
        hostile = f"'-modfile={self.outside}'"
        # Native build retains caller flags, so an invalid caller-selected build
        # fails and all internal dependency/vendor changes roll back.
        result = self.run_cmd(["bash", str(SCRIPTS / "fix-package.sh"), str(self.state),
                               "example.invalid/dep", "1.0.1", "CVE-TEST"],
                              env={"GOFLAGS": hostile}, check=False)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.outside.read_bytes(), self.outside_bytes)
        self.assertEqual(self.run_cmd(["git", "rev-parse", "HEAD"]).stdout.strip(), base)
        self.assertEqual(self.run_cmd(["git", "status", "--porcelain"]).stdout, "")
        # The same genuine workflow succeeds with ordinary caller flags.
        self.run_cmd(["bash", str(SCRIPTS / "fix-package.sh"), str(self.state),
                      "example.invalid/dep", "1.0.1", "CVE-TEST"])
        self.assertIn("v1.0.1", (self.repo / "go.mod").read_text())
        self.assertEqual(self.run_cmd([str(self.repo / "output")]).stdout.strip(), "v1.0.1")
        self.assertEqual(self.outside.read_bytes(), self.outside_bytes)
        self.assertEqual(self.run_cmd(["git", "status", "--porcelain"]).stdout, "")

    def test_package_capture_preserves_command_and_logger_statuses(self):
        self.package_fixture()
        base = self.run_cmd(["git", "rev-parse", "HEAD"]).stdout.strip()
        tools = self.root / "capture-tools"
        tools.mkdir()
        tee, go = shutil.which("tee"), shutil.which("go")
        (tools / "tee").write_text(
            "#!/usr/bin/env python3\nimport subprocess,sys\n"
            "data=sys.stdin.buffer.read()\n"
            f"result=subprocess.run([{tee!r},*sys.argv[1:]],input=data)\n"
            "sys.exit(19 if b'CAPTURE_TEST' in data else result.returncode)\n")
        (tools / "tee").chmod(0o755)
        for stage in ("get", "build"):
            for child in (0, 2, 124):
                with self.subTest(stage=stage, child=child):
                    self.run_cmd(["git", "reset", "--hard", "-q", base])
                    if stage == "get":
                        (tools / "go").write_text(
                            "#!/usr/bin/env python3\nimport os,sys\n"
                            f"if sys.argv[3:4] == ['get']:\n print('CAPTURE_TEST');sys.exit({child})\n"
                            f"os.execv({go!r},[{go!r},*sys.argv[1:]])\n")
                        (tools / "go").chmod(0o755)
                    else:
                        (tools / "go").unlink(missing_ok=True)
                        with self.state.open("a") as file:
                            file.write(f"BUILD_CMD=\"printf 'CAPTURE_TEST\\n'; exit {child}\"\n")
                    result = self.run_cmd(["bash", str(SCRIPTS / "fix-package.sh"), str(self.state),
                                           "example.invalid/dep", "1.0.1", "CVE-TEST"],
                                          env={"PATH": str(tools) + os.pathsep + self.env["PATH"]}, check=False)
                    self.assertEqual(result.returncode, 5 if child == 124 else 2, result.stdout)
                    self.assertIn(f"command exited {child}; tee exited 19", result.stdout)
                    self.assertIn("Cannot capture", result.stdout)
                    self.assertNotIn("FIXED:", result.stdout)
                    self.assertEqual(self.run_cmd(["git", "rev-parse", "HEAD"]).stdout.strip(), base)
                    self.assertEqual(self.run_cmd(["git", "status", "--porcelain"]).stdout, "")


if __name__ == "__main__":
    unittest.main()
