#!/usr/bin/env python3
"""Actual report/detect/scan controls with disposable Git and a fixed scanner."""
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
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
                    if not key.startswith(('CVE_FIX_', 'GIT_'))}
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

    def stalled_command(self, ignore_term, child_ignore_term=None):
        """Real nested processes retain their output pipe until timeout stops them."""
        command = self.root / 'stall.py'
        pids = self.root / 'owned-pids.json'
        if child_ignore_term is None:
            child_ignore_term = ignore_term
        child = ('import signal,time; '
                 + ('signal.signal(signal.SIGTERM,signal.SIG_IGN); ' if child_ignore_term else '')
                 + 'print("CHILD_PARTIAL",flush=True); time.sleep(60)')
        command.write_text(
            'import json,os,signal,subprocess,sys,time\n'
            + ('signal.signal(signal.SIGTERM,signal.SIG_IGN)\n' if ignore_term else '')
            + f'child=subprocess.Popen([sys.executable,"-c",{child!r}])\n'
            + f'open({str(pids)!r},"w").write(json.dumps([os.getpid(),child.pid]))\n'
            + 'print("BUILD_PARTIAL",flush=True)\ntime.sleep(60)\n')
        return shlex.join([sys.executable, str(command)]), pids

    def assert_owned_processes_stopped(self, pids):
        deadline = time.monotonic() + 1
        while True:
            active = []
            for pid in pids:
                stat = Path(f'/proc/{pid}/stat')
                try:
                    if stat.read_text().split()[2] != 'Z':
                        active.append(pid)
                except (FileNotFoundError, ProcessLookupError):
                    pass
            if not active:
                return
            if time.monotonic() >= deadline:
                # Cleanup only the processes this fixture created, even on failure.
                for pid in active:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                self.fail(f'timeout left executing owned processes: {active}')
            time.sleep(.01)

    def test_timed_out_build_retains_partial_log_status_and_checkout(self):
        before = self.state()
        for ignore_term, child_ignore, expected in ((False, False, 124), (False, True, 124), (True, True, 137)):
            with self.subTest(ignore_term=ignore_term, child_ignore=child_ignore):
                evidence = self.root / f'evidence-{expected}-{child_ignore}'
                self.env.update(CVE_FIX_BUILD_TIMEOUT='1',
                                CVE_FIX_EVIDENCE_DIR=str(evidence),
                                CVE_FIX_EVIDENCE_PHASE='report')
                command, pids = self.stalled_command(ignore_term, child_ignore)
                result = self.report(self.build_command('; exec ' + command))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('INCOMPLETE: build-failed', result.stderr)
                scans = list((evidence / 'scans').iterdir())
                self.assertEqual(len(scans), 1)
                status = json.loads((scans[0] / 'status.json').read_text())
                self.assertEqual(status['build_exit_code'], expected)
                self.assertTrue(status['build_failed'])
                partial = (scans[0] / 'build.log').read_text()
                self.assertIn('BUILD_PARTIAL', partial)
                self.assert_owned_processes_stopped(json.loads(pids.read_text()))
                self.assertEqual(self.state(), before)
                self.assert_no_private_state()

    def test_scan_cancellation_stops_term_ignoring_scanner(self):
        command, pids = self.stalled_command(True)
        # The actual scanner producer receives TERM while awaiting its owned
        # timeout; no enclosing scan timeout or process framework is involved.
        (self.bin / 'grype').write_text('#!/bin/sh\nexec ' + command + '\n')
        evidence = self.root / 'cancel-evidence'
        self.env.update(CVE_FIX_EVIDENCE_DIR=str(evidence),
                        CVE_FIX_EVIDENCE_PHASE='cancel', CVE_FIX_SCAN_TIMEOUT='30')
        detected = subprocess.run(['bash', str(self.scripts / 'detect.sh')],
                                  cwd=self.repo, env=self.env, capture_output=True,
                                  text=True, timeout=10, check=True)
        state_file = detected.stdout.splitlines()[-1]
        process = subprocess.Popen(['bash', str(self.scripts / 'scan.sh'), state_file,
                                    '--skip-build', '--no-update', '--json'],
                                   cwd=self.repo, env=self.env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not pids.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(pids.exists(), 'scanner never reached the actual command')
            process.send_signal(signal.SIGTERM)
            output, errors = process.communicate(timeout=8)
            self.assertEqual(process.returncode, 143, errors)
            self.assertEqual(output, '')
            self.assert_owned_processes_stopped(json.loads(pids.read_text()))
            scans = list((evidence / 'scans').iterdir())
            status = json.loads((scans[0] / 'status.json').read_text())
            # Cancellation leaves an incomplete receipt, never completed scan evidence.
            self.assertIsNone(status['exit_code'])
            self.assertEqual(status['build_status'], 'skipped')
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=2)
            if pids.exists():
                for pid in json.loads(pids.read_text()):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_rejected_module_metadata_cleans_state_before_build_or_scan(self):
        self.git('rm', '--cached', 'go.mod')
        before = self.state()
        metadata = (self.repo / 'go.mod').read_bytes()
        refs = self.git('show-ref')
        result = self.report(self.build_command())
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('NEEDS_REVIEW: Go metadata is outside the owned transaction', result.stderr)
        self.assertEqual(self.state(), before)
        self.assertEqual((self.repo / 'go.mod').read_bytes(), metadata)
        self.assertEqual(self.git('show-ref'), refs)
        self.assertFalse(Path(self.env['REPORT_BUILD_MARKER']).exists())
        self.assertFalse(Path(self.env['REPORT_SCANS']).exists())
        self.assertEqual(list(self.tmp.glob('cve-fix-*')), [])

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

    def test_report_on_retained_fix_branch_preserves_ref_and_commits(self):
        self.git('checkout', '-qb', 'fix-main-cves-2026-11-04-v2')
        refs = self.git('show-ref')
        for count, build in enumerate(('', self.build_command('; git add tracked.txt')), 1):
            with self.subTest(build=bool(build)):
                before = self.state()
                result = self.report(build)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('VULNERABILITY', result.stdout)
                self.assertEqual(self.state(), before)
                self.assertEqual(self.git('show-ref'), refs)
                self.assertEqual(len((self.root / 'scans.log').read_text().splitlines()), count)
                self.assert_no_private_state()

    def test_failed_build_still_restores_tracked_changes(self):
        result = self.report(self.build_command('; exit 7'))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('INCOMPLETE: build-failed', result.stderr)
        self.assertEqual((self.repo / 'tracked.txt').read_text(), 'base\n')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assert_no_private_state()

    def test_scanner_failures_are_incomplete_and_restore_build_changes(self):
        for name, body, diagnostic in (
            ('scanner-failed', 'echo SCANNER_FAILURE_DIAGNOSTIC >&2; exit 17',
             'SCANNER_FAILURE_DIAGNOSTIC'),
            ('invalid-json', "printf 'not-json'", 'invalid Grype JSON evidence'),
        ):
            with self.subTest(failure=name):
                (self.bin / 'grype').write_text('#!/bin/sh\n' + body + '\n')
                evidence = self.root / name
                self.env.update(CVE_FIX_EVIDENCE_DIR=str(evidence), CVE_FIX_EVIDENCE_PHASE='report')
                before = self.state()
                result = self.report(self.build_command('; git add tracked.txt'))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('INCOMPLETE:', result.stderr)
                self.assertIn('exit 1', result.stderr)
                self.assertIn(diagnostic, result.stderr)
                scans = list((evidence / 'scans').iterdir())
                self.assertEqual(len(scans), 1)
                self.assertEqual(json.loads((scans[0] / 'status.json').read_text())['exit_code'], 1)
                self.assertNotIn('VULNERABILITY', result.stdout)
                self.assertEqual(self.state(), before)
                self.assert_no_private_state()

    def test_formatter_failure_is_incomplete_and_restores_build_changes(self):
        # This document passes scan evidence validation, but its scalar versions
        # field cannot be rendered as the table's list of fixes.
        finding = {'artifact': {'type': 'go-module', 'name': 'example.invalid/dep', 'version': 'v1.0.0'},
                   'vulnerability': {'id': 'CVE-REPORT', 'severity': 'High', 'fix': {'versions': 'v1.0.1'}}}
        (self.bin / 'grype').write_text('#!/bin/sh\nprintf \'%s\\n\' '
                                      + shlex.quote(json.dumps({'matches': [finding]})) + '\n')
        evidence = self.root / 'formatter-evidence'
        self.env.update(CVE_FIX_EVIDENCE_DIR=str(evidence), CVE_FIX_EVIDENCE_PHASE='report')
        before = self.state()
        result = self.report(self.build_command('; git add tracked.txt'))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('INCOMPLETE:', result.stderr)
        self.assertIn('exit 5', result.stderr)
        self.assertIn('jq: error', result.stderr)
        scans = list((evidence / 'scans').iterdir())
        self.assertEqual(len(scans), 1)
        self.assertEqual(json.loads((scans[0] / 'status.json').read_text())['exit_code'], 0)
        self.assertEqual(self.state(), before)
        self.assert_no_private_state()

    def test_completed_report_with_findings_exits_zero(self):
        finding = {'artifact': {'type': 'go-module', 'name': 'example.invalid/dep', 'version': 'v1.0.0'},
                   'vulnerability': {'id': 'CVE-REPORT', 'severity': 'High', 'fix': {'versions': ['v1.0.1']}}}
        (self.bin / 'grype').write_text('#!/bin/sh\nprintf \'%s\\n\' '
                                      + shlex.quote(json.dumps({'matches': [finding]})) + '\n')
        before = self.state()
        result = self.report(self.build_command('; git add tracked.txt'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('INCOMPLETE:', result.stderr)
        self.assertIn('CVE-REPORT', result.stdout)
        self.assertIn('v1.0.1', result.stdout)
        self.assertIn('\tfinding', result.stdout)
        self.assertEqual(self.state(), before)
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
