#!/usr/bin/env python3
"""Run the actual exit cleanup against disposable Git checkouts."""
from pathlib import Path
import subprocess
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]


class CleanupOwnership(unittest.TestCase):
    def setUp(self):
        scratch = PLUGIN.parents[1] / '.work/fix-go-cves-cleanup-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'source').write_text('base\n')
        self.git('add', 'source')
        self.git('commit', '-qm', 'base')
        self.git('checkout', '-qb', 'fix-test')
        source = (PLUGIN / 'scripts/fix-all.sh').read_text()
        self.cleanup = source[source.index('cleanup() {'):source.index('\nRUN_COMPLETED=false')]

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def run_cleanup(self, completed=False, tested_head="", remove_before=False, archive_failure=False, exit_code=130):
        script = 'source "$4/lib.sh"\n_record_run_evidence() { return "$ARCHIVE_FAILURE"; }\n' + self.cleanup + '\n'
        script += 'REPO=$1 FIX_BRANCH=fix-test ORIGINAL_REF=main RUN_COMPLETED=$2 TESTED_HEAD=$3\n'
        script += 'ARCHIVE_FAILURE=$6\ncd \"$REPO\" || exit 1\n[[ $5 != true ]] || remove_fix_branch >/dev/null\n'
        script += 'if [[ $6 == 1 ]]; then STATE_FILE=$REPO/state.env; TEST_LOG=$REPO/tests.log; FIX_LOG=$REPO/fixes.log; SUBAGENT_REPORT_DIR=$REPO/reports; fi\ncleanup \"$7\"\n'
        return subprocess.run(['bash', '-c', script, 'cleanup-test', str(self.repo), str(completed).lower(),
                               tested_head, str(PLUGIN / 'scripts'), str(remove_before).lower(),
                               str(int(archive_failure)), str(exit_code)],
                              capture_output=True, text=True, timeout=15)

    def test_owned_abort_keeps_existing_rollback_policy(self):
        (self.repo / 'source').write_text('run change\n')
        result = self.run_cleanup()
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertEqual(self.git('branch', '--show-current'), 'main')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertNotIn('fix-test', self.git('branch', '--list'))

    def test_completed_run_retains_fix_branch(self):
        result = self.run_cleanup(completed=True)
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertEqual(self.git('branch', '--show-current'), 'fix-test')

    def test_changed_commit_after_tests_preserves_index(self):
        tested = self.git('rev-parse', 'HEAD')
        (self.repo / 'source').write_text('unexpected commit\n')
        self.git('commit', '-qam', 'new commit')
        (self.repo / 'source').write_text('staged edit\n')
        self.git('add', 'source')
        before = (self.git('rev-parse', 'HEAD'), self.git('diff', '--cached'))
        result = self.run_cleanup(tested_head=tested)
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertEqual((self.git('rev-parse', 'HEAD'), self.git('diff', '--cached')), before)
        self.assertEqual(self.git('branch', '--show-current'), 'fix-test')
        self.assertIn('preserving', result.stderr)

    def test_confirmed_empty_branch_removal_releases_ownership(self):
        result = self.run_cleanup(remove_before=True)
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertEqual(self.git('branch', '--show-current'), 'main')
        self.assertNotIn('fix-test', self.git('branch', '--list'))
        self.assertNotIn('WARNING', result.stderr)

    def test_failed_archive_preserves_private_diagnostics_and_engine_exit(self):
        for name in ('state.env', 'tests.log', 'fixes.log'):
            (self.repo / name).write_text(name + '\n')
        (self.repo / 'reports').mkdir()
        (self.repo / 'reports/audit.txt').write_text('diagnostic\n')
        result = self.run_cleanup(completed=True, archive_failure=True, exit_code=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('state.env', 'tests.log', 'fixes.log'):
            self.assertEqual((self.repo / name).read_text(), name + '\n')
        self.assertEqual((self.repo / 'reports/audit.txt').read_text(), 'diagnostic\n')
        self.assertIn(str(self.repo / 'state.env'), result.stderr)
        self.assertIn('private diagnostics are preserved', result.stderr)

    def test_moved_branch_or_detached_checkout_preserves_work_and_index(self):
        for detached in (False, True):
            with self.subTest(detached=detached):
                self.git('reset', '--hard', '-q')
                self.git('checkout', '-q', 'fix-test')
                if detached:
                    self.git('checkout', '-q', '--detach')
                else:
                    self.git('checkout', '-qB', 'user-work')
                (self.repo / 'source').write_text('user change\n')
                self.git('add', 'source')
                before = (self.git('status', '--porcelain'), self.git('diff', '--cached'),
                          self.git('branch', '--show-current'), self.git('rev-parse', 'HEAD'))
                result = self.run_cleanup()
                after = (self.git('status', '--porcelain'), self.git('diff', '--cached'),
                         self.git('branch', '--show-current'), self.git('rev-parse', 'HEAD'))
                self.assertEqual(result.returncode, 130, result.stderr)
                self.assertEqual(after, before)
                self.assertEqual((self.repo / 'source').read_text(), 'user change\n')
                self.assertIn('fix-test', self.git('branch', '--list'))
                self.assertIn('preserving', result.stderr)


if __name__ == '__main__':
    unittest.main()
