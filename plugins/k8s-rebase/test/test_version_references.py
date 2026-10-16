#!/usr/bin/env python3
"""Offline OCP image-reference checks with real Phase 3 control flow."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
SOURCE = (PLUGIN / "scripts/k8s-rebase.sh").read_text()
PHASE = SOURCE.split('NEW_GO_VERSION=$(grep "^go "', 1)[1].split(
    "# Reconcile ENVTEST_K8S_VERSION", 1)[0]
PHASE = 'NEW_GO_VERSION=$(grep "^go "' + PHASE
AUTOFIX_SOURCE = (PLUGIN / "scripts/k8s-rebase-autofix.sh").read_text()
GO_AUTOFIX = 'fix_go_version() {' + AUTOFIX_SOURCE.split('fix_go_version() {', 1)[1].split(
    '\nfix_lint_version() {', 1)[0]
CONFIG_ROOT = ("https://raw.githubusercontent.com/openshift/release/master/"
               "ci-operator/config/openshift/example/openshift-example-")
REGISTRY = "https://registry.ci.openshift.org"
CI_TAG = "rhel-9-release-golang-1.26-openshift-5.1"
BUILDER_TAG = "rhel-9-golang-1.26-openshift-5.1"


class VersionReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k8s-version-refs-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.old_go = "1.25.0"
        self.bin = self.repo / "bin"
        self.bin.mkdir()
        (self.repo / "go.mod").write_text("module example.invalid/test\ngo 1.26.0\n")
        (self.repo / ".ci-operator.yaml").write_text(
            "build_root_image:\n  name: release\n  namespace: openshift\n"
            "  tag: rhel-9-release-golang-1.25-openshift-5.0\n")
        (self.repo / "Dockerfile").write_text(
            "FROM registry.ci.openshift.org/ocp/builder:"
            "rhel-9-golang-1.25-openshift-5.0 AS builder\n"
            "FROM registry.ci.openshift.org/ocp/5.0:base-rhel9\n")
        (self.repo / "Dockerfile.rhel7").write_text(
            "FROM registry.ci.openshift.org/ocp/builder:"
            "rhel-7-golang-1.19-openshift-4.12\n")
        self.stub("git", "import sys\nassert sys.argv[1:] == ['remote', 'get-url', 'origin']\n"
                  "print('https://github.com/openshift/example.git')\n")
        self.stub("curl", """import json, os, sys
from pathlib import Path
root = Path(os.environ['TEST_ROOT'])
url = sys.argv[-1]
with (root / 'requests').open('a') as log:
    log.write(url + '\\n')
rc, body = json.loads(os.environ['TEST_RESPONSES']).get(url, [22, ''])
sys.stdout.write(body)
sys.exit(rc)
""")
        self.responses = {CONFIG_ROOT + "master.yaml": [0, self.config("5.1")]}
        for repository, tag in (("openshift/release", CI_TAG),
                                ("ocp/builder", BUILDER_TAG), ("ocp/5.1", "base-rhel9")):
            self.responses[REGISTRY + "/openshift/token?service=registry.ci.openshift.org&"
                           f"scope=repository:{repository}:pull"] = [0, '{"token":"anonymous-test"}']
            self.responses[REGISTRY + f"/v2/{repository}/manifests/{tag}"] = [0, ""]

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env python3\n" + body)
        path.chmod(0o755)

    @staticmethod
    def config(latest, initial="5.0"):
        return (f'releases:\n  initial:\n    integration:\n      name: "{initial}"\n'
                f'      namespace: ocp\n  latest:\n    integration:\n      name: "{latest}"\n'
                '      namespace: ocp\n')

    def run_phase(self):
        env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                   TEST_ROOT=str(self.repo), TEST_RESPONSES=json.dumps(self.responses),
                   BASH_ENV="", ENV="")
        body = (f'set -euo pipefail\nPRIMARY_GOMOD=go.mod\nOLD_GO_VERSION={self.old_go}\n'
                'OPENSHIFT_BRANCH=release-5.1\nCHANGED_FILES=\n'
                'info() { echo ":: $*" >&2; }\n' + PHASE +
                'printf "CHANGED_FILES:\\n%s" "$CHANGED_FILES"\n')
        result = subprocess.run(["bash", "-c", body], cwd=self.repo, env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def files(self):
        return {name: (self.repo / name).read_text()
                for name in (".ci-operator.yaml", "Dockerfile", "Dockerfile.rhel7")}

    def run_go_autofix(self):
        # Run the real Step 3 writer after Step 1, without builds or commits.
        result = subprocess.run(["bash", "-c", 'set -uo pipefail\nPRIMARY_GOMOD=go.mod\n' +
                                 GO_AUTOFIX + '\nfix_go_version\n'], cwd=self.repo,
                                env=dict(os.environ, BASH_ENV="", ENV=""),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def requests(self):
        path = self.repo / "requests"
        return path.read_text() if path.exists() else ""

    def test_go_floor_increase_updates_verified_builders_and_retains_os_base(self):
        old_legacy = self.files()["Dockerfile.rhel7"]
        for name in ("Dockerfile.openshift", "Dockerfile.microshift"):
            (self.repo / name).write_text(self.files()["Dockerfile"])
        result = self.run_phase()
        self.assertIn(CI_TAG, self.files()[".ci-operator.yaml"])
        self.assertIn(BUILDER_TAG, self.files()["Dockerfile"])
        self.assertIn("/ocp/5.0:base-rhel9", self.files()["Dockerfile"])
        self.assertEqual(self.files()["Dockerfile.rhel7"], old_legacy)
        for name in ("Dockerfile.openshift", "Dockerfile.microshift"):
            content = (self.repo / name).read_text()
            self.assertIn(BUILDER_TAG, content)
            self.assertIn("/ocp/5.0:base-rhel9", content)
        self.assertIn(".ci-operator.yaml", result.stdout)
        self.assertIn("Dockerfile", result.stdout)
        self.assertNotIn("anonymous-test", result.stdout + result.stderr)

    def test_same_go_rebase_retains_supported_builder_and_base_streams(self):
        self.old_go = "1.26.0"
        for name in (".ci-operator.yaml", "Dockerfile"):
            path = self.repo / name
            path.write_text(path.read_text().replace("golang-1.25", "golang-1.26"))
        before = self.files()
        self.run_phase()
        self.assertEqual(self.files(), before)
        self.assertEqual(self.requests(), "")

    def test_generic_go_image_updates_still_work(self):
        path = self.repo / "Dockerfile.build"
        path.write_text("FROM golang:1.25 AS builder\n")
        self.run_phase()
        self.assertEqual(path.read_text(), "FROM golang:1.26 AS builder\n")

    def test_generic_image_catchup_preserves_unverified_ocp_coordinates(self):
        path = self.repo / "Dockerfile.build"
        protected = "FROM registry.ci.openshift.org/ci/golang:1.25 AS ocp-builder\n"
        path.write_text(protected + "FROM golang:1.24 AS upstream-builder\n")
        self.run_phase()
        self.assertEqual(path.read_text(), protected + "FROM golang:1.26 AS upstream-builder\n")

    def test_step3_preserves_step1_image_decisions_and_updates_ordinary_refs(self):
        self.responses = {}
        before = self.files()
        self.run_phase()
        self.assertEqual(self.files(), before)
        # A stale ordinary reference can survive an interrupted earlier phase.
        generic = self.repo / "Dockerfile.upstream"
        generic.write_text("FROM golang:1.25 AS upstream\n")
        makefile = self.repo / "Makefile"
        makefile.write_text("GO_VERSION ?= 1.25\n")
        self.run_go_autofix()
        self.assertEqual(self.files(), before)
        self.assertEqual(generic.read_text(), "FROM golang:1.26 AS upstream\n")
        self.assertEqual(makefile.read_text(), "GO_VERSION ?= 1.26\n")

    def test_indirect_ocp_go_versions_stay_protected_through_both_steps(self):
        self.responses = {}
        protected = {}
        for variable, assignment in (("GOLANG_VERSION", "ARG GOLANG_VERSION=1.25"),
                                     ("GOVERSION", 'ARG GOVERSION="1.25"')):
            path = self.repo / ("Dockerfile." + variable)
            contents = (assignment + "\nFROM registry.ci.openshift.org/ocp/builder:"
                        "rhel-9-golang-${" + variable + "}-openshift-5.0\n")
            path.write_text(contents)
            protected[path] = contents
        generic = self.repo / "Dockerfile.upstream"
        generic.write_text("ARG GOLANG_VERSION=1.25\nFROM golang:${GOLANG_VERSION}\n")
        self.run_phase()
        for path, contents in protected.items():
            self.assertEqual(path.read_text(), contents)
        self.run_go_autofix()
        for path, contents in protected.items():
            self.assertEqual(path.read_text(), contents)
        self.assertEqual(generic.read_text(),
                         "ARG GOLANG_VERSION=1.26\nFROM golang:${GOLANG_VERSION}\n")

    def test_build_arg_suppliers_cannot_override_a_protected_image_default(self):
        self.responses = {}
        files = {
            "Dockerfile.ocp": ("ARG GOLANG_VERSION=1.25\nFROM registry.ci.openshift.org/ocp/builder:"
                               "rhel-9-golang-${GOLANG_VERSION}-openshift-5.0\n"),
            "Makefile": ("GO_VERSION ?= 1.25\nbuild:\n\tpodman build --build-arg "
                         "GOLANG_VERSION=$(GO_VERSION) -f Dockerfile.ocp .\n"),
            ".github/workflows/docker.yml": (
                'name: image\non: push\nenv:\n  GO_VERSION: "1.25"\njobs:\n  image:\n'
                '    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/setup-go@v5\n'
                '        with:\n          go-version: 1.25\n'
                '      - run: docker build --build-arg GOLANG_VERSION=${GO_VERSION} -f Dockerfile.ocp .\n'),
        }
        for name, contents in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        self.run_phase()
        for name, contents in files.items():
            with self.subTest(step=1, path=name):
                self.assertEqual((self.repo / name).read_text(), contents)
        self.run_go_autofix()
        for name, contents in files.items():
            with self.subTest(step=3, path=name):
                self.assertEqual((self.repo / name).read_text(), contents)

    def test_unavailable_or_newer_ci_stream_retains_all_refs(self):
        for config in (None, self.config("5.2", initial="5.1")):
            with self.subTest(config=config):
                self.responses.pop(CONFIG_ROOT + "master.yaml", None)
                if config is not None:
                    self.responses[CONFIG_ROOT + "master.yaml"] = [0, config]
                before = self.files()
                result = self.run_phase()
                self.assertEqual(self.files(), before)
                self.assertIn("existing OCP image refs retained", result.stderr)
                self.assertNotIn("/openshift/token", self.requests())

    def test_target_branch_can_confirm_stream_ahead_of_default_config(self):
        self.responses[CONFIG_ROOT + "release-5.1.yaml"] = [0, self.config("5.1")]
        self.responses[CONFIG_ROOT + "master.yaml"] = [0, self.config("5.2")]
        self.run_phase()
        self.assertIn(CI_TAG, self.files()[".ci-operator.yaml"])
        self.assertNotIn(CONFIG_ROOT + "master.yaml", self.requests())
        self.assertNotIn("openshift-5.2", "".join(self.files().values()))

    def test_unavailable_images_retain_their_original_refs(self):
        for url in list(self.responses):
            if "/manifests/" in url:
                self.responses[url] = [22, ""]
        before = self.files()
        result = self.run_phase()
        self.assertEqual(self.files(), before)
        self.assertIn("unavailable or unverifiable", result.stderr)
        self.assertEqual(result.stdout, "CHANGED_FILES:\n")

    def test_unverifiable_token_never_certifies_an_image(self):
        for url in list(self.responses):
            if "/openshift/token" in url:
                self.responses[url] = [0, '{"token":null}']
        before = self.files()
        self.run_phase()
        self.assertEqual(self.files(), before)
        self.assertNotIn("/manifests/", self.requests())

    def test_builder_tag_configs_and_quoted_image_fields(self):
        self.responses[CONFIG_ROOT + "master.yaml"] = [0, "build_root:\n  tag: " + CI_TAG + "\n"]
        path = self.repo / ".ci-operator.yaml"
        path.write_text(path.read_text().replace("name: release", 'name: "release"')
                        .replace("namespace: openshift", "namespace: 'openshift'"))
        self.run_phase()
        self.assertIn(CI_TAG, self.files()[".ci-operator.yaml"])

    def test_digest_pinned_images_require_explicit_review(self):
        path = self.repo / "Dockerfile"
        path.write_text(path.read_text().replace(" AS builder", "@sha256:" + "a" * 64 + " AS builder"))
        result = self.run_phase()
        self.assertIn("golang-1.25-openshift-5.0@sha256:", path.read_text())
        self.assertIn("digest-pinned image needs explicit digest review", result.stderr)

    def test_verified_short_image_does_not_rewrite_unavailable_longer_tags(self):
        path = self.repo / "Dockerfile"
        old_image = "registry.ci.openshift.org/ocp/builder:" + BUILDER_TAG.replace("5.1", "5.0").replace("1.26", "1.25")
        new_image = "registry.ci.openshift.org/ocp/builder:" + BUILDER_TAG
        unrelated = (f'FROM {old_image}-extra AS unavailable\n'
                     f'LABEL example="prefix{old_image}-suffix"\n'
                     f'RUN echo "https://{old_image}"\n')
        path.write_text(f"FROM {old_image} AS verified\n" + unrelated)
        self.run_phase()
        self.assertEqual(path.read_text(), f"FROM {new_image} AS verified\n" + unrelated)
        self.assertIn("/manifests/" + BUILDER_TAG + "-extra", self.requests())

    def test_ci_rewrite_only_changes_exact_build_root_tag_value(self):
        path = self.repo / ".ci-operator.yaml"
        old_tag = CI_TAG.replace("5.1", "5.0").replace("1.26", "1.25")
        for quote in ("", "'", '"'):
            with self.subTest(quote=quote):
                prefix = "build_root_image:\n  name: release\n  namespace: openshift\n"
                suffix = (f" # retain {old_tag} in comment\n  note: {old_tag}\n"
                          f"other_image:\n  tag: {old_tag}-extra\n  original: {old_tag}\n")
                path.write_text(prefix + f"  tag: {quote}{old_tag}{quote}" + suffix)
                self.run_phase()
                self.assertEqual(path.read_text(), prefix + f"  tag: {quote}{CI_TAG}{quote}" + suffix)


if __name__ == "__main__":
    unittest.main(verbosity=2)
