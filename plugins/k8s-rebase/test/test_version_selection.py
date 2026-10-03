#!/usr/bin/env python3
"""Offline Step 1 selection checks: real parsers, stubbed proxy, no rebase."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
SOURCE = (PLUGIN / "scripts/k8s-rebase.sh").read_text()
PACKAGES = ("client-go", "api", "library-go", "build-machinery-go")
VERSION = "v0.0.0-20260904224155-42fb550ea02a"


def function(name):
    return name + "() {\n" + SOURCE.split(name + "() {\n", 1)[1].split("\n}\n", 1)[0] + "\n}\n"


class VersionSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k8s-version-selection-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        self.gomod = self.repo / "go.mod"
        self.gomod.write_text("module example.invalid/fixture\ngo 1.23.0\nrequire (\n"
                             " k8s.io/api v0.34.1\n k8s.io/apimachinery v0.34.1\n)\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        GOTOOLCHAIN="local", GOWORK="off", GOPROXY="off", GOSUMDB="off",
                        TEST_REAL_GO=shutil.which("go") or "", TEST_ROOT=str(self.root),
                        BASH_ENV="", ENV="", GOFLAGS="")
        self.assertTrue(self.env["TEST_REAL_GO"], "Go is required for read-only go.mod parsing")
        self.stub("curl", '''import json, os, sys
from pathlib import Path
url = sys.argv[-1]
with (Path(os.environ["TEST_ROOT"]) / "requests").open("a") as log:
    log.write(url + "\\n")
rc, body = json.loads(os.environ["TEST_PROXY"]).get(url, [22, ""])
sys.stdout.write(body)
sys.exit(rc)
''')
        self.stub("go", '''import os, sys
from pathlib import Path
if sys.argv[1:] != ["mod", "edit", "-json", "/dev/stdin"]:
    sys.exit("Unexpected Go operation: " + repr(sys.argv[1:]))
with (Path(os.environ["TEST_ROOT"]) / "go-calls").open("a") as log:
    log.write("read-only parse\\n")
os.execv(os.environ["TEST_REAL_GO"], [os.environ["TEST_REAL_GO"], *sys.argv[1:]])
''')
        # The script's automatic Go image has Go and Perl, not necessarily jq.
        # Make every case exercise that same dependency constraint.
        self.stub("jq", 'raise SystemExit("Unexpected jq dependency")\n')
        self.responses = {}

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env python3\n" + body)
        path.chmod(0o755)

    def response(self, package, suffix, body, rc=0):
        self.responses[f"https://proxy.golang.org/github.com/openshift/{package}/@v/{suffix}"] = [rc, body]

    def module(self, package="api", requirements="require k8s.io/api v0.35.1\n"):
        return f"module github.com/openshift/{package}\ngo 1.23.0\n{requirements}"

    def run_shell(self, body, minor=35):
        env = dict(self.env, TEST_PROXY=json.dumps(self.responses))
        prefix = (f"set -euo pipefail\nK8S_MINOR={minor}\nK8S_PATCH=3\nOLD_MINOR=34\n"
                  f"API_VERSION=v0.{minor}.3\nCR_VERSION=v0.23.1\nKUBE_OPENAPI_VERSION=\n"
                  "info() { echo \":: $*\" >&2; }\n")
        before = self.gomod.read_bytes()
        result = subprocess.run(["bash", "-c", prefix + body], cwd=self.repo, env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(self.gomod.read_bytes(), before)
        self.assertFalse((self.repo / "go.sum").exists())
        return result

    def validate(self, module, minor=35, package="api", rc=0):
        self.response(package, VERSION + ".mod", module, rc)
        return self.run_shell(function("_validate_openshift_k8s_minor") +
                              f'version=$(_validate_openshift_k8s_minor "github.com/openshift/{package}" "{VERSION}")\n'
                              'printf "%s" "$version"\n', minor)

    def selection(self, minor=35, invoke_module=False):
        # Execute the real top-level assignments under errexit, not only functions
        # in conditionals (which suppress Bash's errexit within the function).
        block = SOURCE.split("# Discover openshift/* versions", 1)[1].split(
            "# Discover the kube-openapi version", 1)[0]
        call = 'commands=$(derive_go_gets "go.mod")\nprintf "%s\\n" "$commands"\n'
        if invoke_module:
            support = function("cleanup_hook")
            support += next(line for line in SOURCE.splitlines() if line.startswith("die() {")) + "\n"
            support += next(line for line in SOURCE.splitlines() if line.startswith("trap ")) + "\n"
            call = support + function("rebase_module") + 'banner() { :; }\nrebase_module module\necho continued\n'
        return self.run_shell("# Discover openshift/* versions" + block + function("derive_go_gets") + call, minor)

    def test_matching_minors_and_require_formats(self):
        for minor in (35, 36):
            for requirements in (f"require k8s.io/api v0.{minor}.1\n",
                                 f"require (\n\tk8s.io/api v0.{minor}.1 // indirect\n)\n"):
                with self.subTest(minor=minor, requirements=requirements):
                    result = self.validate(self.module(requirements=requirements), minor)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, VERSION)

    def test_mismatching_core_requirements_are_rejected(self):
        for package in ("api", "apimachinery", "client-go"):
            for requirements in (f"require k8s.io/{package} v0.36.2\n",
                                 f"require (\n k8s.io/{package} v0.36.2\n)\n"):
                with self.subTest(package=package, requirements=requirements):
                    result = self.validate(self.module(requirements=requirements))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("WARNING:", result.stderr)

    def test_mixed_minors_are_rejected(self):
        result = self.validate(self.module(requirements="require (\n k8s.io/api v0.35.1\n"
                                          " k8s.io/client-go v0.36.2\n)\n"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_no_core_requirement_is_distinct_from_unreadable_metadata(self):
        result = self.validate(self.module(requirements="require example.invalid/other v1.2.3\n"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, VERSION)
        for module, rc in (("", 22), (self.module(), 22), ("", 0), ("not go.mod", 0),
                           ("module example.invalid/wrong\n", 0),
                           (self.module(requirements="require (\n k8s.io/api\n"), 0)):
            with self.subTest(module=module, rc=rc):
                result = self.validate(module, rc=rc)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("WARNING:", result.stderr)

    def test_parser_failure_does_not_certify_a_version(self):
        valid_json = json.dumps({"Module": {"Path": "github.com/openshift/api"}, "Require": []})
        for body in ('raise SystemExit(19)', 'print("{}")',
                     f'print({valid_json!r}); raise SystemExit(19)'):
            with self.subTest(body=body):
                self.stub("go", body)
                result = self.validate(self.module())
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("WARNING:", result.stderr)

    def test_unverifiable_core_versions_are_rejected(self):
        for version in ("main", "v0.35.0-alpha.1", "v1.35.1", "v0.0.0"):
            with self.subTest(version=version):
                result = self.validate(self.module(requirements=f"require k8s.io/api {version}\n"))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_json_spacing_and_invalid_proxy_responses(self):
        for body in (json.dumps({"Version": VERSION}), json.dumps({"Version": VERSION}, indent=2),
                     json.dumps({"Version": VERSION}).replace("v0", r"\u00760", 1)):
            self.response("api", "release-4.22.info", body)
            result = self.run_shell('OPENSHIFT_BRANCH=release-4.22\n' + function("_resolve_openshift_version") +
                                    'version=$(_resolve_openshift_version github.com/openshift/api)\nprintf "%s" "$version"')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, VERSION)
        for body, rc in (("", 22), ("{", 0), ("{}", 0), ('{"Version":null}', 0),
                         (json.dumps({"Version": VERSION}).replace("v0", r"v\u0030", 1), 0),
                         (r'{"Version":"v0.1\u00300.0"}', 0),
                         (json.dumps({"Version": VERSION + "\n"}), 0),
                         (json.dumps({"Version": VERSION + "\0"}), 0),
                         (json.dumps({"Version": VERSION}) + " trailing", 0),
                         ('{"Version":42}', 0), ('{"Version":"v0.0.1; false"}', 0),
                         (json.dumps({"Version": VERSION}), 22)):
            with self.subTest(body=body, rc=rc):
                self.response("api", "release-4.22.info", body, rc)
                result = self.run_shell('OPENSHIFT_BRANCH=release-4.22\n' + function("_resolve_openshift_version") +
                                        'version=$(_resolve_openshift_version github.com/openshift/api)\nprintf "%s" "$version"')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_all_openshift_packages_use_checked_branch_versions(self):
        for minor, branch in ((35, "release-4.22"), (36, "release-5.0")):
            with self.subTest(minor=minor):
                self.gomod.write_text("module example.invalid/fixture\nrequire (\n k8s.io/api v0.34.1\n" +
                                      "".join(f" github.com/openshift/{p} v0.0.1\n" for p in PACKAGES) + ")\n")
                for package in PACKAGES:
                    self.response(package, branch + ".info", json.dumps({"Version": VERSION}))
                    self.response(package, VERSION + ".mod", self.module(package, f"require k8s.io/api v0.{minor}.1\n"))
                result = self.selection(minor)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), [f"go get k8s.io/api@v0.{minor}.3"] +
                                 [f"go get github.com/openshift/{p}@{VERSION}" for p in PACKAGES])

    def test_unresolved_required_packages_stop_without_fallback_commands(self):
        for package in PACKAGES:
            for failure in ("no branch", "wrong minor", "no module"):
                with self.subTest(package=package, failure=failure):
                    self.responses.clear()
                    self.gomod.write_text("module example.invalid/fixture\nrequire (\n k8s.io/api v0.34.1\n"
                                          f" github.com/openshift/{package} v0.0.1\n)\n")
                    if failure != "no branch":
                        self.response(package, "release-4.22.info", json.dumps({"Version": VERSION}))
                    if failure == "wrong minor":
                        self.response(package, VERSION + ".mod", self.module(package, "require k8s.io/api v0.36.2\n"))
                    result = self.selection()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("ERROR:", result.stderr)
                    self.assertNotIn("will use @latest", result.stderr)

    def test_no_openshift_dependency_does_not_need_optional_metadata(self):
        result = self.selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["go get k8s.io/api@v0.35.3",
                                                     "go get k8s.io/apimachinery@v0.35.3"])
        self.assertFalse((self.root / "go-calls").exists())

    def test_only_actual_openshift_requirements_need_a_version(self):
        for declaration in ("module github.com/openshift/api\n",
                            "module example.invalid/fixture\n// See github.com/openshift/api\n",
                            "module example.invalid/fixture\nreplace (\n github.com/openshift/api v0.0.1 => ../api\n)\n",
                            "module example.invalid/fixture\nrequire github.com/openshift/api-extra v0.0.1\n"):
            with self.subTest(declaration=declaration):
                self.gomod.write_text(declaration + "require (\n k8s.io/api v0.34.1\n)\n")
                result = self.selection()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), ["go get k8s.io/api@v0.35.3"])

    def test_selection_failure_restores_hooks_before_go_updates(self):
        # Isolate Git before running the real cleanup helper from a subdirectory.
        self.env = {key: value for key, value in self.env.items() if not key.startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "-c", "init.templateDir=", "init", "-q", str(self.repo)],
                       env=self.env, check=True, capture_output=True)
        hooks = self.repo / ".git/hooks"
        hooks.mkdir(exist_ok=True)
        hook = hooks / "pre-push"
        backup = hooks / "pre-push.bak.k8s-rebase"
        original = "#!/bin/sh\n# fixture user hook\nexit 0\n"
        module = self.repo / "module"
        module.mkdir()
        contents = self.gomod.read_text() + "require github.com/openshift/library-go v0.0.1\n"
        (module / "go.mod").write_text(contents)
        self.env.update(REPO_ROOT=str(self.repo), REBASE_TMP=str(self.repo / ".rebase-tmp"))
        for failure in ("unresolved version", "parser failure"):
            if failure == "parser failure":
                self.stub("go", "raise SystemExit(19)\n")
            for has_original in (False, True):
                with self.subTest(failure=failure, has_original=has_original):
                    hook.write_text("#!/bin/sh\n# k8s-rebase guard\nexit 1\n")
                    hook.chmod(0o755)
                    backup.unlink(missing_ok=True)
                    if has_original:
                        backup.write_text(original)
                        backup.chmod(0o751)
                    result = self.selection(invoke_module=True)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("ERROR: no verified" if failure == "unresolved version" else
                                  "ERROR: cannot read requirements", result.stderr)
                    self.assertNotIn("Unexpected Go operation", result.stderr)
                    self.assertNotIn("continued", result.stdout)
                    self.assertEqual((module / "go.mod").read_text(), contents)
                    self.assertEqual(sorted(p.name for p in module.iterdir()), ["go.mod"])
                    if has_original:
                        self.assertEqual(hook.read_text(), original)
                        self.assertEqual(hook.stat().st_mode & 0o777, 0o751)
                    else:
                        self.assertFalse(hook.exists())
                    self.assertFalse(backup.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
