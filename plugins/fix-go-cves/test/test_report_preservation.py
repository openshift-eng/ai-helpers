#!/usr/bin/env python3
"""Actual report/detect/scan controls with disposable Git and a fixed scanner."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]


@unittest.skipUnless(all(shutil.which(tool) for tool in ('bash', 'git', 'go', 'jq', 'make', 'timeout')),
                     'Bash, Git, Go, jq, make and timeout are required')
class ReportPreservation(unittest.TestCase):
    def setUp(self):
        scratch = PLUGIN.parents[1] / '.work/fix-go-cves-report-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.scripts = self.root / 'scripts'
        shutil.copytree(PLUGIN / 'scripts', self.scripts,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        # Exercise the real producer and scanner path without installing tools
        # or consulting a Docker daemon. The scanner response is fixed data.
        with (self.scripts / 'lib.sh').open('a') as library:
            library.write('\npreflight_check() { return 0; }\n')
        (self.bin / 'grype').write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$REPORT_SCANS"
printf '{"matches":[],"ignoredMatches":[]}'
''')
        for tool in ('docker', 'podman'):
            (self.bin / tool).write_text('#!/bin/sh\nexit 1\n')
        for path in self.bin.iterdir():
            path.chmod(0o755)
        self.tmp = self.root / 'tmp'
        self.tmp.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('CVE_FIX_') and key not in ('GIT_DIR', 'GIT_WORK_TREE')}
        self.env.update(PATH=str(self.bin) + ':' + str(Path(sys.executable).parent) + ':' + os.environ['PATH'],
                        TMPDIR=str(self.tmp), XDG_CONFIG_HOME=str(self.root / 'config'),
                        GIT_CEILING_DIRECTORIES=str(self.root), GIT_CONFIG_NOSYSTEM='1',
                        GOENV='off', GOWORK='off', GOFLAGS='', GOTOOLCHAIN='local',
                        REPORT_SCANS=str(self.root / 'scans.log'),
                        REPORT_BUILD_MARKER=str(self.root / 'build.log'))
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'go.mod').write_text('module example.invalid/report\n\ngo 1.24.0\n')
        (self.repo / 'tracked.txt').write_text('base\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        self.head = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], env=self.env, text=True).strip()

    def state(self):
        return ((self.repo / 'tracked.txt').read_bytes(), self.git('diff', '--binary'),
                self.git('diff', '--cached', '--binary'), self.git('status', '--porcelain'),
                self.git('rev-parse', 'HEAD'), self.git('symbolic-ref', 'HEAD'))

    def report(self, build=''):
        return subprocess.run(['bash', str(self.scripts / 'report.sh')], cwd=self.repo,
                              env={**self.env, 'CVE_FIX_BUILD_CMD': build},
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)

    def build_command(self, extra=''):
        return 'printf "started\\n" >> "$REPORT_BUILD_MARKER"; printf "generated\\n" > tracked.txt' + extra

    def assert_no_private_state(self):
        self.assertEqual(list(self.tmp.glob('cve-fix-*/state.env')), [])

    def test_dirty_build_input_is_preserved_before_build_or_scan(self):
        for kind in ('worktree', 'index-and-worktree', 'untracked'):
            with self.subTest(kind=kind):
                self.git('reset', '--hard', '-q', self.head)
                untracked = self.repo / 'caller.txt'
                untracked.unlink(missing_ok=True)
                if kind == 'untracked':
                    untracked.write_text('caller file\n')
                else:
                    (self.repo / 'tracked.txt').write_text('staged\n')
                    if kind == 'index-and-worktree':
                        self.git('add', 'tracked.txt')
                        (self.repo / 'tracked.txt').write_text('working\n')
                before = self.state()
                result = self.report(self.build_command())
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('INCOMPLETE: configured report build requires a clean checkout', result.stderr)
                self.assertEqual(self.state(), before)
                if kind == 'untracked':
                    self.assertEqual(untracked.read_text(), 'caller file\n')
                self.assertFalse((self.root / 'build.log').exists())
                self.assertFalse((self.root / 'scans.log').exists())
                self.assert_no_private_state()

    def test_dirty_input_without_build_remains_read_only(self):
        (self.repo / 'tracked.txt').write_text('staged\n')
        self.git('add', 'tracked.txt')
        (self.repo / 'tracked.txt').write_text('working\n')
        (self.repo / 'caller.txt').write_text('caller file\n')
        before = self.state()
        result = self.report()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(), before)
        self.assertEqual((self.repo / 'caller.txt').read_text(), 'caller file\n')
        self.assertIn('VULNERABILITY', result.stdout)
        self.assertEqual(len((self.root / 'scans.log').read_text().splitlines()), 1)
        self.assert_no_private_state()

    def test_clean_build_restores_worktree_and_index(self):
        result = self.report(self.build_command('; git add tracked.txt'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.repo / 'tracked.txt').read_text(), 'base\n')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.head)
        self.assertEqual(self.git('branch', '--show-current'), 'main')
        self.assertEqual(self.git('branch', '--list'), '* main')
        self.assert_no_private_state()

    def test_failed_build_still_restores_tracked_changes(self):
        result = self.report(self.build_command('; exit 7'))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('INCOMPLETE: build-failed', result.stderr)
        self.assertEqual((self.repo / 'tracked.txt').read_text(), 'base\n')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assert_no_private_state()

    def test_native_git_restore_failure_is_visible(self):
        result = self.report(self.build_command('; printf lock > .git/index.lock'))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('INCOMPLETE: could not restore tracked build changes', result.stderr)
        self.assertIn('index.lock', result.stderr)
        self.assertIn('Recovery state:', result.stderr)
        self.assertEqual((self.repo / 'tracked.txt').read_text(), 'generated\n')
        self.assertTrue(list(self.tmp.glob('cve-fix-*/state.env')))

    def test_moved_checkout_is_preserved_instead_of_restored(self):
        result = self.report(self.build_command('; git checkout -qb build-branch'))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('INCOMPLETE: checkout moved during the build', result.stderr)
        self.assertEqual(self.git('branch', '--show-current'), 'build-branch')
        self.assertEqual((self.repo / 'tracked.txt').read_text(), 'generated\n')
        self.assertTrue(list(self.tmp.glob('cve-fix-*/state.env')))

    def test_build_commit_is_preserved_and_report_is_incomplete(self):
        result = self.report(self.build_command('; git add tracked.txt; git commit -qm build-change'))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('INCOMPLETE: checkout moved during the build', result.stderr)
        self.assertNotEqual(self.git('rev-parse', 'HEAD'), self.head)
        self.assertEqual((self.repo / 'tracked.txt').read_text(), 'generated\n')
        self.assertTrue(list(self.tmp.glob('cve-fix-*/state.env')))


if __name__ == '__main__':
    unittest.main()
