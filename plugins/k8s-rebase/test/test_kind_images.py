#!/usr/bin/env python3
"""KIND image reconciliation against controlled registry responses."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
SOURCE = (PLUGIN / "scripts/k8s-rebase-autofix.sh").read_text()
FUNCTION = "fix_kind_image() {" + SOURCE.split("fix_kind_image() {", 1)[1].split(
    "\nfix_kind_version() {", 1)[0]
MECHANICAL = (PLUGIN / "scripts/k8s-rebase.sh").read_text().split(
    'NEW_K8S_FULL="${K8S_FULL}"', 1)[1].split('NEW_GO_VERSION=$(grep "^go "', 1)[0]


class KindImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k8s-kind-images-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.bin = self.repo / "bin"
        self.bin.mkdir()
        (self.repo / "go.mod").write_text(
            "module example.invalid/test\ngo 1.26.0\nrequire k8s.io/api v0.37.1\n")
        self.tags = ["v1.37.0"]
        self.listing = []
        curl = self.bin / "curl"
        curl.write_text("""#!/usr/bin/env python3
import json, os, sys
url = sys.argv[-1]
if '?' in url:
    print(json.dumps({'results': [{'name': t} for t in json.loads(os.environ['TEST_LISTING'])]}))
    sys.exit(0)
sys.exit(0 if url.rsplit('/', 1)[-1] in json.loads(os.environ['TEST_TAGS']) else 22)
""")
        curl.chmod(0o755)

    def run_fix(self):
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                   TEST_TAGS=json.dumps(self.tags), TEST_LISTING=json.dumps(self.listing))
        return subprocess.run(
            ["bash", "-c", 'set -uo pipefail\nPRIMARY_GOMOD=go.mod\n' + FUNCTION +
             '\nfix_kind_image\n'], cwd=self.repo, env=env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)

    def run_mechanical(self):
        subprocess.run(["bash", "-c", '''set -uo pipefail
info() { :; }
K8S_MAJOR=1 OLD_MINOR=36 K8S_MAJOR_MINOR=1.37 NEW_K8S_FULL=v1.37.1
''' + MECHANICAL], cwd=self.repo, check=True, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_available_patch_reconciles_current_and_previous_minor_only(self):
        path = self.repo / "cluster.yaml"
        path.write_text("""target: kindest/node:v1.37.1
previous: kindest/node:v1.36.4
upgrade-source: kindest/node:v1.35.9
legacy: kindest/node:v1.27.3
future: kindest/node:v1.38.0
""")
        self.run_fix()
        self.assertEqual(path.read_text(), """target: kindest/node:v1.37.0
previous: kindest/node:v1.37.0
upgrade-source: kindest/node:v1.35.9
legacy: kindest/node:v1.27.3
future: kindest/node:v1.38.0
""")

    def test_unverified_registry_does_not_invent_previous_patch(self):
        self.tags = []
        path = self.repo / "kind-common.sh"
        original = 'KIND_IMAGE=kindest/node\nK8S_VERSION=v1.37.1\nold=kindest/node:v1.36.4\n'
        path.write_text(original)
        result = self.run_fix()
        self.assertEqual(path.read_text(), original)
        self.assertIn("unverified", result.stdout.lower())

    def test_digest_prerelease_and_extended_tags_need_explicit_review(self):
        path = self.repo / "cluster.yaml"
        original = ("pinned: kindest/node:v1.36.4@sha256:" + "a" * 64 + "\n"
                    "custom: kindest/node:v1.36.4-extra\n"
                    "preview: kindest/node:v1.37.1-rc.1\n")
        path.write_text(original)
        self.run_fix()
        self.assertEqual(path.read_text(), original)

    def test_kind_variable_reconciles_patch_without_changing_envtest(self):
        path = self.repo / "kind-common.sh"
        path.write_text('KIND_IMAGE=kindest/node\nK8S_VERSION=${K8S_VERSION:-v1.37.1}\n'
                        'kind create cluster --image "${KIND_IMAGE}:${K8S_VERSION}"\n')
        envtest = self.repo / "Makefile"
        envtest.write_text('ENVTEST_K8S_VERSION = v1.37.1\n')
        self.run_fix()
        self.assertIn('K8S_VERSION=${K8S_VERSION:-v1.37.0}', path.read_text())
        self.assertEqual(envtest.read_text(), 'ENVTEST_K8S_VERSION = v1.37.1\n')

    def test_kubectl_variable_is_not_a_kind_image_pin(self):
        path = self.repo / "Makefile"
        path.write_text('K8S_VERSION ?= v1.37.1\nurl=https://dl.k8s.io/$(K8S_VERSION)/bin/linux/amd64/kubectl\n')
        (self.repo / "cluster.yaml").write_text('image: kindest/node:v1.37.1\n')
        self.run_fix()
        self.assertIn('K8S_VERSION ?= v1.37.1', path.read_text())

    def test_listing_parses_json_and_excludes_other_minors_and_prereleases(self):
        self.tags = []
        self.listing = ["v1.37.0", "v1.38.0", "v1.37.2-rc.0", "v1.370.0"]
        path = self.repo / "cluster.yaml"
        path.write_text('image: kindest/node:v1.37.1\n')
        self.run_fix()
        self.assertEqual(path.read_text(), 'image: kindest/node:v1.37.0\n')

    def test_mechanical_pass_defers_kind_images_and_their_digests(self):
        path = self.repo / "cluster.yaml"
        original = 'image: kindest/node:v1.36.4@sha256:' + "a" * 64 + '\n'
        path.write_text(original)
        (self.repo / "Makefile").write_text('K8S_VERSION ?= v1.36.2\n')
        self.run_mechanical()
        self.assertEqual(path.read_text(), original)
        self.assertIn('K8S_VERSION ?= v1.37.1', (self.repo / "Makefile").read_text())

    def test_upgrade_source_roles_stay_at_source_version(self):
        path = self.repo / "upgrade.yaml"
        path.write_text('SOURCE_IMAGE: kindest/node:v1.36.2\nTARGET_IMAGE: kindest/node:v1.36.4\n')
        self.run_mechanical()
        self.run_fix()
        self.assertEqual(path.read_text(),
                         'SOURCE_IMAGE: kindest/node:v1.36.2\nTARGET_IMAGE: kindest/node:v1.37.0\n')

    def test_private_registry_requires_its_own_verification(self):
        path = self.repo / "cluster.yaml"
        original = 'image: registry.example.invalid/kindest/node:v1.36.2\n'
        path.write_text(original)
        self.run_mechanical()
        self.run_fix()
        self.assertEqual(path.read_text(), original)

    def test_private_registry_variable_is_not_verified_by_docker_hub(self):
        path = self.repo / 'kind-common.sh'
        original = ('KIND_IMAGE=registry.example.invalid/kindest/node\n'
                    'K8S_VERSION=v1.36.2\n'
                    'kind create cluster --image "${KIND_IMAGE}:${K8S_VERSION}"\n')
        path.write_text(original)
        self.run_mechanical()
        self.run_fix()
        self.assertEqual(path.read_text(), original)

    def test_same_file_kind_and_kubectl_are_separate_consumers(self):
        path = self.repo / "mixed.sh"
        path.write_text('K8S_VERSION=v1.36.2\n'
                        'curl "https://dl.k8s.io/${K8S_VERSION}/bin/linux/amd64/kubectl"\n'
                        'kind create cluster --image kindest/node:v1.36.2\n')
        self.run_mechanical()
        self.run_fix()
        self.assertIn('K8S_VERSION=v1.37.1\n', path.read_text())
        self.assertIn('--image kindest/node:v1.37.0', path.read_text())

    def test_direct_workflow_consumer_uses_fallback_but_kubectl_keeps_target(self):
        (self.repo / 'kind-common.sh').write_text(
            'KIND_IMAGE=kindest/node\nK8S_VERSION=v1.36.2\n'
            'kind create cluster --image "${KIND_IMAGE}:${K8S_VERSION}"\n')
        (self.repo / 'kind.yaml').write_text('K8S_VERSION: v1.36.2\nsteps:\n  - run: ./kind-common.sh\n')
        client = self.repo / 'kubectl.yaml'
        client.write_text('K8S_VERSION: v1.36.2\nsteps:\n'
                          '  - run: curl "https://dl.k8s.io/${K8S_VERSION}/bin/linux/amd64/kubectl"\n')
        self.run_mechanical()
        self.run_fix()
        self.assertIn('K8S_VERSION: v1.37.0', (self.repo / 'kind.yaml').read_text())
        self.assertIn('K8S_VERSION: v1.37.1', client.read_text())

    def test_split_digest_and_custom_tags_survive_both_passes(self):
        for suffix in ('@sha256:' + 'a' * 64, '-custom', '-rc.1'):
            with self.subTest(suffix=suffix):
                path = self.repo / 'kind-common.sh'
                original = ('KIND_IMAGE=kindest/node\nK8S_VERSION=${K8S_VERSION:-v1.36.2' + suffix + '}\n'
                            'kind create cluster --image "${KIND_IMAGE}:${K8S_VERSION}"\n')
                path.write_text(original)
                self.run_mechanical()
                self.run_fix()
                self.assertEqual(path.read_text(), original)

    def test_adjacent_independent_version_on_image_line_updates(self):
        path = self.repo / 'ci.yaml'
        path.write_text('run: KUBECTL_VERSION=v1.36.2 ./check.sh kindest/node:v1.36.2\n')
        self.run_mechanical()
        self.run_fix()
        self.assertEqual(path.read_text(),
                         'run: KUBECTL_VERSION=v1.37.1 ./check.sh kindest/node:v1.37.0\n')

    def test_dockerfile_base_image_and_docker_hub_prefix(self):
        path = self.repo / 'Dockerfile'
        path.write_text('FROM docker.io/kindest/node:v1.36.2\n')
        self.run_mechanical()
        self.run_fix()
        self.assertEqual(path.read_text(), 'FROM docker.io/kindest/node:v1.37.0\n')


if __name__ == "__main__":
    unittest.main(verbosity=2)
