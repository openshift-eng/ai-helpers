#!/usr/bin/env python3
"""Actual artifact helpers in disposable Git repositories; no scanners or models."""

import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]


@unittest.skipUnless(all(shutil.which(name) for name in ('git', 'bash', 'python3')),
                     'Git, Bash and Python are required')
class ArtifactOwnership(unittest.TestCase):
    def setUp(self):
        scratch = PLUGIN.parents[1] / '.work/fix-go-cves-artifact-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.env = {**os.environ, 'GIT_CEILING_DIRECTORIES': str(self.root)}
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / '.gitignore').write_text('/bin\n')
        self.git('add', '.gitignore')
        self.git('commit', '-qm', 'initial')
        self.state = self.root / 'run1.env'
        self.previous = self.repo / '.git/fix-go-cves-artifacts'

    def git(self, *arguments, repo=None):
        return subprocess.run(['git', '-C', str(repo or self.repo), *arguments], env=self.env,
                              text=True, capture_output=True, check=True).stdout.strip()

    def helper(self, operation, state=None):
        subprocess.run(['bash', '-c',
                        'source "$1"; REPO=$2; STATE_FILE=$3; "artifact_manifest_$4"',
                        'bash', str(PLUGIN / 'scripts/lib.sh'), str(self.repo),
                        str(state or self.state), operation],
                       env=self.env, text=True, capture_output=True, check=True, timeout=30)

    def executable(self, name, content='generated'):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o755)
        return path

    def generated(self):
        self.helper('prepare')
        path = self.executable('bin/generated')
        self.helper('record')
        return path

    def test_unchanged_outputs_removed_but_preexisting_and_tracked_files_remain(self):
        user = self.executable('bin/user')
        tracked = self.executable('bin/tracked')
        self.git('add', '-f', 'bin/tracked')
        self.git('commit', '-qm', 'tracked executable')
        output = self.generated()
        self.helper('prepare', self.root / 'run2.env')
        self.assertFalse(output.exists())
        self.assertEqual(user.read_text(), 'generated')
        self.assertEqual(tracked.read_text(), 'generated')
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_current_run_replacement_is_preserved_and_not_readopted(self):
        output = self.generated()
        output.write_text('user replacement')
        self.helper('prepare')
        self.assertEqual(output.read_text(), 'user replacement')
        self.helper('record')
        self.assertNotIn(str(output), json.loads(Path(str(self.state) + '.generated-artifacts').read_text()))
        self.helper('prepare')
        self.assertEqual(output.read_text(), 'user replacement')

    def test_previous_run_replacement_is_preserved_across_later_runs(self):
        output = self.generated()
        output.write_text('user replacement')
        second = self.root / 'run2.env'
        self.helper('prepare', second)
        self.helper('record', second)
        self.helper('prepare', self.root / 'run3.env')
        self.assertEqual(output.read_text(), 'user replacement')
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_parent_link_cannot_delete_outside_target(self):
        output = self.generated()
        outside = self.root / 'outside'
        outside.mkdir()
        target = outside / output.name
        target.write_text(output.read_text())
        target.chmod(0o755)
        shutil.rmtree(output.parent)
        output.parent.symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.helper('prepare', self.root / 'run2.env')
        self.assertTrue(output.parent.is_symlink())
        self.assertEqual(target.read_text(), 'generated')
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_leaf_link_replacement_remains(self):
        output = self.generated()
        outside = self.root / 'outside'
        outside.write_text(output.read_text())
        outside.chmod(0o755)
        output.unlink()
        output.symlink_to(outside)
        self.helper('prepare')
        self.assertTrue(output.is_symlink())
        self.assertEqual(outside.read_text(), 'generated')

    def test_hard_link_replacement_remains(self):
        output = self.generated()
        outside = self.root / 'outside'
        outside.write_text(output.read_text())
        outside.chmod(0o755)
        output.unlink()
        os.link(outside, output)
        self.helper('prepare')
        self.assertTrue(output.exists())
        self.assertEqual(outside.stat().st_nlink, 2)

    def test_tracked_promotion_is_preserved(self):
        output = self.generated()
        self.git('add', '-f', 'bin/generated')
        index = self.git('status', '--porcelain')
        self.helper('prepare')
        self.assertTrue(output.exists())
        self.assertEqual(self.git('status', '--porcelain'), index)

    def test_mode_changes_are_preserved(self):
        output = self.generated()
        output.chmod(0o644)
        self.helper('prepare')
        self.helper('record')
        self.helper('prepare')
        self.assertEqual(output.stat().st_mode & 0o777, 0o644)

    def test_legacy_or_malformed_claims_do_not_establish_ownership(self):
        output = self.executable('bin/legacy')
        for content in (str(output) + '\n', '{broken',
                        json.dumps({str(output): {'kind': 'file'}})):
            with self.subTest(content=content):
                self.previous.write_text(content)
                self.helper('prepare', self.root / ('legacy-' + str(len(content)) + '.env'))
                self.assertEqual(output.read_text(), 'generated')
        self.helper('prepare')
        current = self.executable('bin/unproven')
        Path(str(self.state) + '.generated-artifacts').write_text(str(current) + '\n')
        self.helper('prepare')
        self.helper('record')
        self.helper('prepare')
        self.assertTrue(current.exists())

    def test_nested_git_promotion_preserves_unchanged_owned_output(self):
        self.helper('prepare')
        output = self.executable('bin/nested/output')
        self.helper('record')
        nested = output.parent
        self.git('init', '-q', repo=nested)
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'add', 'output', repo=nested)
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'promote output', repo=nested)
        self.helper('prepare')
        self.assertEqual(output.read_text(), 'generated')
        self.assertEqual(self.git('status', '--porcelain', repo=nested), '')

    def test_worktree_gitfile_promotion_preserves_unchanged_owned_output(self):
        self.helper('prepare')
        output = self.executable('bin/nested/output')
        self.helper('record')
        nested = output.parent
        shutil.rmtree(nested)
        other = self.root / 'other'
        other.mkdir()
        self.git('init', '-q', repo=other)
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '--allow-empty', '-qm', 'initial', repo=other)
        self.git('worktree', 'add', '-q', '--detach', str(nested), repo=other)
        output.write_text('generated')
        output.chmod(0o755)
        self.git('add', 'output', repo=nested)
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'promote output', repo=nested)
        self.assertTrue((nested / '.git').is_file())
        self.helper('prepare')
        self.assertEqual(output.read_text(), 'generated')
        self.assertEqual(self.git('status', '--porcelain', repo=nested), '')

    def test_hardlinked_private_metadata_is_never_truncated(self):
        for suffix in ('baseline-artifacts', 'generated-artifacts'):
            with self.subTest(suffix=suffix):
                self.state = self.root / (suffix + '.env')
                output = self.generated()
                metadata = Path(str(self.state) + '.' + suffix)
                outside = self.root / ('outside-' + suffix)
                os.link(metadata, outside)
                before = outside.read_bytes()
                with self.assertRaises(subprocess.CalledProcessError):
                    self.helper('prepare')
                self.assertEqual(outside.read_bytes(), before)
                self.assertTrue(output.exists())
                outside.unlink()

    def test_hardlinked_previous_cache_is_preserved_with_optional_warning(self):
        output = self.generated()
        outside = self.root / 'outside-cache'
        os.link(self.previous, outside)
        before = outside.read_bytes()
        second = self.root / 'run2.env'
        self.helper('prepare', second)
        self.helper('record', second)
        self.assertEqual(outside.read_bytes(), before)
        self.assertTrue(output.exists())

    def test_preexisting_nonexecutable_is_not_owned_after_build_chmod(self):
        path = self.repo / 'bin/existing'
        path.parent.mkdir()
        path.write_text('preexisting')
        path.chmod(0o644)
        self.helper('prepare')
        path.chmod(0o755)
        self.helper('record')
        self.helper('prepare')
        self.assertEqual(path.read_text(), 'preexisting')

    def test_plain_built_paths_include_new_and_inplace_rebuilds(self):
        rebuilt = self.executable('bin/rebuilt')
        untouched = self.executable('bin/untouched')
        self.helper('prepare')
        rebuilt.write_text('rebuilt')
        fresh = self.executable('bin/new output')
        baseline = Path(str(self.state) + '.baseline-artifacts')
        later = baseline.stat().st_mtime_ns + 1_000_000_000
        for path in (rebuilt, fresh):
            os.utime(path, ns=(later, later))
        self.helper('record')
        built = Path(str(self.state) + '.built-artifacts').read_text().splitlines()
        self.assertEqual(set(built), {str(rebuilt), str(fresh)})
        self.assertNotIn(str(untouched), built)
        self.assertEqual(set(json.loads(Path(str(self.state) + '.generated-artifacts').read_text())), {str(fresh)})
        self.helper('prepare')
        self.assertFalse(fresh.exists())
        self.assertEqual(rebuilt.read_text(), 'rebuilt')
    @unittest.skipUnless(all(shutil.which(name) for name in ('go', 'jq', 'timeout')),
                         'Go, jq and timeout are required')
    def test_actual_scan_uses_fresh_built_paths_for_duplicate_filter_and_alias_proof(self):
        # Real builds/readers; only scanner findings are controlled fixture input.
        (self.repo / 'go.mod').write_text('module example.invalid/artifact\n\ngo 1.24.0\n')
        main = self.repo / 'main.go'
        main.write_text('package main\nfunc main() {}\n')
        self.git('add', 'go.mod', 'main.go')
        self.git('commit', '-qm', 'Go fixture')
        native_env = {**self.env, 'GOTOOLCHAIN': 'local', 'GOWORK': 'off', 'GOENV': 'off',
                      'GOFLAGS': '', 'GOPROXY': 'off', 'GOSUMDB': 'off', 'GOEXPERIMENT': ','}
        for name in ('inplace', 'unproven'):
            subprocess.run(['go', 'build', '-o', 'bin/' + name, '.'], cwd=self.repo,
                           env=native_env, capture_output=True, text=True, check=True, timeout=120)
        main.write_text('package main\nfunc main() { println("rebuilt") }\n')
        self.git('add', 'main.go')
        self.git('commit', '-qm', 'source to rebuild')
        def finding(location, fixed=False):
            return {'artifact': {'type': 'go-module', 'name': 'example.invalid/dep',
                                 'version': 'v1.0.0', 'locations': [{'path': location}]},
                    'vulnerability': {'id': 'CVE-fixable' if fixed else 'CVE-nofix',
                                      'fix': {'versions': ['v1.1.0'] if fixed else [],
                                              'state': 'fixed' if fixed else 'unknown'}}}
        raw = {'matches': [finding('/bin/fresh'), finding('/bin/inplace'),
                           finding('/bin/unproven'), finding('/bin/fresh', True)],
               'ignoredMatches': [finding('/go.mod')]}
        scan = self.root / 'scanner.json'
        scan.write_text(json.dumps(raw))
        tools = self.root / 'tools'
        tools.mkdir()
        scanner = tools / 'grype'
        scanner.write_text('#!/bin/sh\ncat "$ARTIFACT_SCAN_JSON"\n')
        scanner.chmod(0o755)
        alias = self.root / 'repo-alias'
        alias.symlink_to(self.repo, target_is_directory=True)
        values = {'REPO': str(alias), 'BRANCH': 'fixture', 'HAS_LOCAL_GRYPE': 'true',
                  'CONTAINER_CMD': '', 'ENV_UNSET': '', 'BUILD_REPO_NAME': '',
                  'BUILD_CMD': 'go build -o bin/fresh . && go build -o bin/inplace .'}
        self.state.write_text(''.join(key + '=' + shlex.quote(value) + '\n' for key, value in values.items()))
        evidence = self.root / 'evidence'
        result = subprocess.run(['bash', str(PLUGIN / 'scripts/scan.sh'), str(self.state),
                                 '--json', '--no-update'], env={**native_env,
                                 'PATH': str(tools) + os.pathsep + os.environ['PATH'],
                                 'ARTIFACT_SCAN_JSON': str(scan), 'CVE_FIX_GRYPE_VERSION': '',
                                 'CVE_FIX_EVIDENCE_DIR': str(evidence)},
                                capture_output=True, text=True, check=True, timeout=120)
        filtered = json.loads(result.stdout)
        self.assertEqual(filtered['matches'], [raw['matches'][2], raw['matches'][3]])
        self.assertEqual(filtered['generatedBinaryDuplicates'], raw['matches'][:2])
        self.assertEqual(filtered['ignoredMatches'], raw['ignoredMatches'])
        ledger, = evidence.glob('scans/*/binaries.jsonl')
        recorded = {item['path']: item['recorded_build_artifact']
                    for item in map(json.loads, ledger.read_text().splitlines())}
        self.assertEqual(recorded, {'bin/fresh': True, 'bin/inplace': True, 'bin/unproven': False})
        generated = json.loads(Path(str(self.state) + '.generated-artifacts').read_text())
        self.assertEqual(set(generated), {str(self.repo / 'bin/fresh')})


if __name__ == '__main__':
    unittest.main()
