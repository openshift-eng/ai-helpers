#!/usr/bin/env python3
"""Equivalent YAML selects the same actual audits; Go resolution is controlled."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


class PolicyReaders(unittest.TestCase):
    def setUp(self):
        scratch = PLUGIN.parents[1] / ".work" / "fix-go-cves-policy-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.tools = self.root / "bin"
        self.tools.mkdir()
        (self.tools / "go").write_text('''#!/usr/bin/env python3
import json,sys
if '-json' in sys.argv:
 print(json.dumps({'Path':'example.com/dep','Version':'v1.0.0'}))
else:
 print('v1.0.0')
''')
        (self.tools / "go").chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.tools) + os.pathsep + str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
                    "GOENV": "off", "GOFLAGS": "", "GOWORK": "off", "GOTOOLCHAIN": "local",
                    "GOPROXY": "off", "GOSUMDB": "off", "GIT_CEILING_DIRECTORIES": str(self.root)}
        for args in (["git", "init", "-q"], ["git", "config", "user.name", "Test"],
                     ["git", "config", "user.email", "test@example.invalid"]):
            self.run_cmd(args)
        (self.repo / "go.mod").write_text("module example.com/target\n\ngo 1.24.0\n\nrequire example.com/dep v1.0.0\n")
        self.state = self.root / "state.env"
        self.state.write_text(f"REPO={str(self.repo)!r}\nBRANCH=devel\n")
        self.reports = self.root / "reports"
        self.reports.mkdir()
        finding = {"artifact": {"type": "go-module", "name": "example.com/dep", "version": "v1.0.0", "locations": [{"path": "/go.mod"}]},
                   "vulnerability": {"id": "CVE-2026-1001", "fix": {"versions": ["v1.1.0"], "state": "unknown"}}}
        (self.reports / "initial-scan.json").write_text(json.dumps({"matches": [], "ignoredMatches": [finding]}))

    def run_cmd(self, args, *, check=True, input=None):
        result = subprocess.run(args, cwd=self.repo, env=self.env, input=input, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def policy(self, text):
        (self.repo / ".grype.yaml").write_text(text)
        self.run_cmd(["git", "add", "-A"])
        self.run_cmd(["git", "commit", "--allow-empty", "-qm", "policy fixture"])
        self.run_cmd(["git", "update-ref", "refs/remotes/origin/devel", "HEAD"])

    def audit(self, name, check=True):
        return self.run_cmd(["bash", str(PLUGIN / "subagents" / f"{name}.sh"), str(self.state), str(self.reports)], check=check)

    def shell(self, command, check=True):
        return self.run_cmd(["bash", "-c", 'source "$1/lib.sh"; ' + command,
                             "bash", str(SCRIPTS)], check=check)

    def test_equivalent_block_flow_alias_merge_and_package_first(self):
        for state in ("", "unknown"):
            state_field = f"fix-state: {state}\n" if state else ""
            shapes = [
                "ignore:\n  - vulnerability: CVE-2026-1001\n    package:\n      name: example.com/dep\n      type: go-module\n" + ("    " + state_field if state else ""),
                "ignore:\n  - package:\n      type: go-module\n      name: example.com/dep\n    vulnerability: CVE-2026-1001\n" + ("    " + state_field if state else ""),
                "ignore: [{vulnerability: CVE-2026-1001, package: {name: example.com/dep, type: go-module}" + (", fix-state: unknown" if state else "") + "}]\n",
                "selector: &rule\n  vulnerability: CVE-2026-1001\n  package: {name: example.com/dep, type: go-module}\n" + ("  " + state_field if state else "") + "ignore: [*rule]\n",
                "selector: &rule {vulnerability: CVE-2026-1001, package: {name: example.com/dep, type: go-module}}\nignore:\n  - <<: *rule\n" + ("    " + state_field if state else ""),
                "<<: {ignore: [{vulnerability: CVE-2026-1001, package: {name: example.com/dep, type: go-module}" + (", fix-state: unknown" if state else "") + "}]}\n",
            ]
            observed = []
            for number, text in enumerate(shapes):
                with self.subTest(state=state, shape=number):
                    self.policy(text)
                    existing = self.audit("existing-entries").stdout
                    available = self.audit("fix-availability").stdout
                    integrity = self.audit("yaml-integrity").stdout
                    self.assertIn("NEW_ISSUES=1", existing)
                    self.assertIn("FIX-NOW-AVAILABLE:" if state else "FIX-AVAILABLE:", existing)
                    self.assertIn("NEW_ISSUES=1" if state else "NEW_ISSUES=0", available)
                    self.assertIn("NEW_ISSUES=0", integrity)
                    observed.append((existing, available, integrity))
                    self.assertEqual((self.repo / ".grype.yaml").read_text(), text)
            self.assertTrue(all(item == observed[0] for item in observed))

    def test_missing_scan_is_not_clean_and_non_go_entries_are_not_audited(self):
        self.policy("ignore: [{vulnerability: CVE-2026-1001, fix-state: unknown, package: {name: example.com/dep, type: go-module}}]\n")
        (self.reports / "initial-scan.json").unlink()
        for name in ("existing-entries", "fix-availability"):
            result = self.audit(name, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SCAN_FAILED=1", result.stdout)
        self.policy("ignore: [{vulnerability: CVE-2026-1001, fix-state: unknown, package: {name: example.com/dep, type: rpm}}]\n")
        for name in ("existing-entries", "fix-availability"):
            self.assertIn("NEW_ISSUES=0", self.audit(name).stdout)

    def test_scope_normalization_matches_existing_scan_locations(self):
        for location, expected in (("/src/tools/go.mod", "/tools/go.mod"),
                                   ("tools/go.mod", "/tools/go.mod"),
                                   ("/tools/go.mod", "/tools/go.mod"),
                                   ("//tools/go.mod", "//tools/go.mod")):
            with self.subTest(location=location):
                self.policy("ignore: [{vulnerability: CVE-2026-1001, package: {name: example.com/dep, location: " + location + "}}]\n")
                result = self.run_cmd([sys.executable, str(SCRIPTS / "check-grype-ignores.py"), "--entries", ".grype.yaml"])
                self.assertEqual(json.loads(result.stdout)[0]["location"], expected)
                self.shell('grype_ignore_entry_exists .grype.yaml CVE-2026-1001 example.com/dep ' + expected)

    def test_scope_and_identity_use_decoded_normalized_values(self):
        self.policy('''rules: &rule {vulnerability: CVE-2026-1001, package: {name: example.com/dep}, fix-state: unknown}
ignore:
  - *rule
  - {vulnerability: CVE-2026-1001, package: {name: example.com/dep, location: /src/tools/go.mod}}
''')
        result = self.shell('grype_ignore_scope_conflicts .grype.yaml').stdout
        self.assertIn("SCOPE_CONFLICT: CVE-2026-1001 (example.com/dep)", result)
        self.assertIn("/tools/go.mod", result)
        self.shell('grype_ignore_entry_exists .grype.yaml CVE-2026-1001 example.com/dep tools/go.mod')
        self.shell('grype_ignore_scoped_entry_exists .grype.yaml CVE-2026-1001 example.com/dep')

    def test_unsupported_mutation_preserves_bytes(self):
        for text in (
            "ignore: [{vulnerability: CVE-2026-1001, package: {name: example.com/dep}}]\n",
            "selector: &rule {vulnerability: CVE-2026-1001, package: {name: example.com/dep}}\nignore: [*rule]\n",
            "ignore:\n  - package:\n      name: example.com/dep\n    vulnerability: CVE-2026-1001\n",
        ):
            self.policy(text)
            for command in ('remove_grype_ignore .grype.yaml CVE-2026-1001 example.com/dep',
                            'insert_grype_ignore .grype.yaml CVE-2026-1001 example.com/dep reason unknown',
                            'remove_invalid_grype_ignores .grype.yaml'):
                result = self.shell(command, check=False)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("UNSUPPORTED_IGNORE_LAYOUT", result.stdout)
                self.assertEqual((self.repo / ".grype.yaml").read_text(), text)

    def test_canonical_mutation_keeps_comments_and_unrelated_policy(self):
        self.policy("""ignore:
  # Retain this scoped reason.
  - vulnerability: CVE-2026-1001
    fix-state: 'unknown'
    package:
      name: example.com/dep
      location: /src/tools/go.mod
exclude: ['**/node_modules/**']
""")
        info = self.shell('grype_ignore_entry_info .grype.yaml CVE-2026-1001 example.com/dep tools/go.mod').stdout
        self.assertEqual(info, "unknown\tRetain this scoped reason.\n")
        self.shell('remove_grype_ignore .grype.yaml CVE-2026-1001 example.com/dep tools/go.mod')
        remaining = (self.repo / ".grype.yaml").read_text()
        self.assertNotIn("CVE-2026-1001", remaining)
        self.assertIn("exclude: ['**/node_modules/**']", remaining)

    def test_changed_go_rules_preserve_inherited_and_non_go_states(self):
        text = "ignore:\n  - vulnerability: CVE-2026-1001\n    fix-state: fixed\n    package: {name: example.com/dep, type: go-module}\n"
        self.policy(text)
        self.assertIn("NEW_ISSUES=0", self.audit("yaml-integrity").stdout)
        with (self.repo / ".grype.yaml").open("a") as file:
            file.write("  - vulnerability: IMAGE-ADVISORY\n    fix-state: fixed\n    package: {name: image-package, type: rpm}\n")
        self.assertIn("NEW_ISSUES=0", self.audit("yaml-integrity").stdout)
        (self.repo / ".grype.yaml").write_text(text.replace("fix-state: fixed", "fix-state: unknown#literal"))
        self.assertIn("BAD_FIX_STATE", self.audit("yaml-integrity").stdout)

    def test_canonical_broad_cleanup_preserves_valid_neighbor(self):
        self.policy("""ignore:
  - vulnerability: CVE-BROAD
  - package:
      name: example.com/broad
  # Retain this neighbor reason.
  - vulnerability: CVE-2026-1001
    fix-state: unknown
    package:
      name: example.com/dep
""")
        self.shell('remove_invalid_grype_ignores .grype.yaml')
        remaining = (self.repo / ".grype.yaml").read_text()
        self.assertNotIn("CVE-BROAD", remaining)
        self.assertNotIn("example.com/broad", remaining)
        self.assertIn("Retain this neighbor reason.", remaining)
        self.shell('grype_ignore_entry_exists .grype.yaml CVE-2026-1001 example.com/dep')

    def test_equivalent_existing_ignore_is_a_true_noop(self):
        text = "selector: &rule {vulnerability: CVE-2026-1001, fix-state: unknown, package: {name: example.com/dep}}\nignore: [*rule]\n"
        self.policy(text)
        before = self.run_cmd(["git", "rev-parse", "HEAD"]).stdout
        result = self.run_cmd(["bash", str(SCRIPTS / "ignore.sh"), str(self.state),
                               "example.com/dep", "High", "Already known", "--fix-state", "unknown", "CVE-2026-1001"])
        self.assertIn("already ignored", result.stdout)
        self.assertEqual(self.run_cmd(["git", "rev-parse", "HEAD"]).stdout, before)
        self.assertEqual((self.repo / ".grype.yaml").read_text(), text)

    def test_root_merge_is_readable_but_not_writable(self):
        text = "<<: {ignore: [{vulnerability: CVE-2026-1001, package: {name: example.com/dep}}]}\n"
        self.policy(text)
        self.shell('grype_ignore_entry_exists .grype.yaml CVE-2026-1001 example.com/dep')
        result = self.shell('remove_grype_ignore .grype.yaml CVE-2026-1001 example.com/dep', check=False)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual((self.repo / ".grype.yaml").read_text(), text)

    def test_removal_decodes_location_and_preserves_non_go_collision(self):
        text = """ignore:
  # Keep the RPM policy.
  - vulnerability: CVE-2026-1001
    package:
      name: example.com/dep # same package label
      type: rpm
      location: '/tools/go.mod'
  # Remove only the requested Go selector.
  - vulnerability: CVE-2026-1001
    package:
      name: 'example.com/dep' # decoded value
      location: '/src/tools/go.mod' # normalized value
      type: 'go-module'
  # Keep this other Go module.
  - vulnerability: CVE-2026-1001
    package:
      name: example.com/dep
      location: /other/go.mod
"""
        self.policy(text)
        self.shell('remove_grype_ignore .grype.yaml CVE-2026-1001 example.com/dep tools/go.mod')
        remaining = (self.repo / ".grype.yaml").read_text()
        self.assertIn("Keep the RPM policy.", remaining)
        self.assertIn("type: rpm", remaining)
        self.assertIn("Keep this other Go module.", remaining)
        self.assertNotIn("Remove only the requested Go selector.", remaining)
        self.assertNotIn("/src/tools/go.mod", remaining)

    def test_mutation_rejects_linked_policy_without_touching_target(self):
        self.policy("ignore: []\n")
        for kind in ("symlink", "dangling", "hardlink"):
            with self.subTest(kind=kind):
                policy = self.repo / ".grype.yaml"
                if policy.exists() or policy.is_symlink():
                    policy.unlink()
                target = self.root / (kind + ".yaml")
                text = "ignore: []\n"
                if kind != "dangling":
                    target.write_text(text)
                if kind == "hardlink":
                    os.link(target, policy)
                else:
                    policy.symlink_to(target)
                result = self.run_cmd(["bash", str(SCRIPTS / "ignore.sh"), str(self.state),
                    "example.com/dep", "High", "No fix", "--no-fix", "CVE-2026-1001"], check=False)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("unlinked policy file", result.stdout)
                for command in ('remove_grype_ignore .grype.yaml CVE-2026-1001 example.com/dep',
                                'remove_invalid_grype_ignores .grype.yaml'):
                    self.assertEqual(self.shell(command, check=False).returncode, 2)
                self.assertTrue(policy.is_symlink() if kind != "hardlink" else policy.stat().st_nlink == 2)
                if kind == "dangling":
                    self.assertFalse(target.exists())
                else:
                    self.assertEqual(target.read_text(), text)

    def test_audit_rejects_missing_base_and_git_read_errors(self):
        self.policy("ignore: []\n")
        self.run_cmd(["git", "update-ref", "-d", "refs/remotes/origin/devel"])
        result = self.audit("yaml-integrity")
        self.assertIn("GIT_POLICY_DIFF_ERROR", result.stdout)
        self.assertNotIn("NEW_ISSUES=0", result.stdout)
        self.run_cmd(["git", "update-ref", "refs/remotes/origin/devel", "HEAD"])
        real_git = shutil.which("git")
        (self.tools / "git").write_text('#!/usr/bin/env bash\nif [[ "$1" == show ]]; then exit 19; fi\nexec ' + repr(real_git) + ' "$@"\n')
        (self.tools / "git").chmod(0o755)
        result = self.audit("yaml-integrity")
        self.assertIn("GIT_POLICY_BASE_ERROR", result.stdout)
        self.assertNotIn("NEW_ISSUES=0", result.stdout)

    def test_valid_base_without_policy_allows_new_well_formed_rule(self):
        self.run_cmd(["git", "add", "go.mod"])
        self.run_cmd(["git", "commit", "-qm", "base without policy"])
        self.run_cmd(["git", "update-ref", "refs/remotes/origin/devel", "HEAD"])
        (self.repo / ".grype.yaml").write_text("ignore:\n  # No fix.\n  - vulnerability: CVE-2026-1001\n    fix-state: unknown\n    package:\n      name: example.com/dep\n")
        self.assertIn("NEW_ISSUES=0", self.audit("yaml-integrity").stdout)

    def test_malformed_policy_cannot_become_zero_entry_audit(self):
        self.policy("ignore: [{vulnerability: CVE-2026-1001}]\n")
        for name in ("existing-entries", "fix-availability"):
            result = self.audit(name, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SKIP: Grype ignore policy could not be decoded", result.stdout)
        self.assertIn("MISSING_PACKAGE_FIELD", self.audit("yaml-integrity").stdout)


if __name__ == "__main__":
    unittest.main()
