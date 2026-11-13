#!/usr/bin/env python3
"""Tests for memory_runner.py (predecessor selection, publication) and, when the openshift/release checkout
sits beside this repository, for the bulk-triage step script run end to end against fakes.

Nothing here reaches the network: `gcloud` and `agentic-ci` are replaced by small scripts on PATH and the
inventory comes from a file."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import manifest  # noqa: E402
import memory_runner as mr  # noqa: E402
from test_devel import reg  # noqa: E402

REPO = HERE.parents[4]
STEP = (REPO.parent / 'release/ci-operator/step-registry/openshift/claude/bulk-triage'
        / 'openshift-claude-bulk-triage-commands.sh')
JOB = 'periodic-ci-openshift-eng-ai-helpers-main-periodics-bulk-triage-regressions'
BUCKET = 'test-platform-results-public'
STEP_NAME = 'openshift-claude-bulk-triage'

FAKE_GCLOUD = r'''#!/usr/bin/env python3
"""Offline stand-in for `gcloud storage ls|cp` over $FAKE_GCS_ROOT/<bucket>/<path>."""
import glob, json, os, shutil, sys
root = os.environ['FAKE_GCS_ROOT']
args = sys.argv[1:]
with open(os.environ['FAKE_GCS_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\n')
def local(url):
    assert url.startswith('gs://'), url
    return os.path.join(root, url[5:])
def remote(path):
    return 'gs://' + os.path.relpath(path, root)
if args[:2] == ['storage', 'ls']:
    url = args[2]
    if os.environ.get('FAKE_GCS_FAIL_LS'):
        print(url + '99/')                      # partial output before the failure
        print('ERROR: connection reset', file=sys.stderr)
        sys.exit(1)
    if '*' in url:
        found = sorted(glob.glob(local(url)))
    elif url.endswith('/') and os.path.isdir(local(url)):
        found = sorted(os.path.join(local(url), n) for n in os.listdir(local(url)))
    else:
        found = [local(url)] if os.path.exists(local(url)) else []
    if not found:
        print('ERROR: One or more URLs matched no objects.', file=sys.stderr)
        sys.exit(1)
    for f in found:
        print(remote(f) + ('/' if os.path.isdir(f) else ''))
elif args[:2] == ['storage', 'cp']:
    if os.environ.get('FAKE_GCS_FAIL_CP'):
        print('ERROR: download failed', file=sys.stderr)
        sys.exit(1)
    shutil.copyfile(local(args[2]), args[3])
else:
    print('unsupported: %r' % args, file=sys.stderr)
    sys.exit(2)
'''

FAKE_AGENT = r'''#!/usr/bin/env python3
"""Offline stand-in for `agentic-ci run`: records its prompt and plays $FAKE_AGENT_SCENARIO."""
import glob, json, os, re, sys
args = sys.argv[1:]
workdir = args[args.index('--workdir') + 1]
prompt = args[args.index('--') - 1]
with open(os.environ['FAKE_AGENT_LOG'], 'a') as log:
    log.write(json.dumps({'workdir': workdir, 'prompt': prompt, 'args': args}) + '\n')
scenario = os.environ.get('FAKE_AGENT_SCENARIO', 'final')
if scenario != 'no-report':
    with open(os.path.join(workdir, 'triage-duty-report-%s.md' % os.environ['TRIAGE_VIEW']), 'w') as f:
        f.write('# duty report\n')
path = os.path.join(workdir, 'triage-manifest.json')
if scenario in ('final', 'reuse', 'partial', 'tamper') and os.path.exists(path):
    doc = json.load(open(path))
    if scenario != 'partial':
        sys.path.insert(0, os.path.join(os.environ['AI_HELPERS_DIR'], 'plugins/ci/skills/bulk-triage-regressions/scripts'))
        import devel, manifest
        prepared = json.load(open(os.path.join(workdir, 'prepass.json')))
        baseline_path = re.search(r'--baseline (\S+)', prompt).group(1)
        baseline = json.load(open(baseline_path)) if baseline_path != 'none' else None
        grouping = {'groups': [{'coverage': c['members']['coverage'],
                               'signature': {'stage': 'test', 'discriminator': 'fixture failure'}}
                              for c in prepared['clusters']]}
        prepared = devel.regroup(prepared, grouping, baseline)
        json.dump(prepared, open(os.path.join(workdir, 'prepass.json'), 'w'))
        doc = devel.checkpoint(prepared)
    for c in doc['clusters']:
        if scenario == 'partial':
            c['disposition']['analysis']['root_cause'] = 'budget exhausted after the first pass'
        else:
            c['signature'] = {'stage': 'test', 'discriminator': 'fixture failure'}
            c['disposition']['state'] = 'UNEXPLAINED'
            c['disposition']['analysis'].update(depth='deep-dive', confidence='high', root_cause='verified fixture',
                evidence=[{'prowjob_run_id': e['run_ids'][0], 'supports_regression_ids': [e['regression_id']],
                           'artifact': 'fixture', 'quote': 'fixture failure'} for e in c['members']['coverage']])
            c['disposition']['bug_search'] = {'candidates': []}
            if scenario == 'reuse':
                source = c['prior']['sources'][0]
                an = c['disposition']['analysis']
                an['depth'] = 'carried-forward'
                an['reverification'] = {'source_run_id': c['prior']['run_id'],
                    'source_cluster_ids': [source['cluster_id']], 'basis': source['analysis']['basis'],
                    'outcome': 'carried', 'reason': 'same fixture signature, current checks',
                    'checked_at': doc['observation']['time'],
                    'own_run_ids': sorted({e['prowjob_run_id'] for e in an['evidence']}),
                    'lookup_locators': ['https://example.invalid/current-search']}
    if scenario != 'partial':
        doc = manifest.merge(prepared, {c['id']: c['disposition'] for c in doc['clusters']}, {},
                             {'unanalysed': [], 'stale_triage_sweep': []})
    if scenario == 'tamper':
        doc['inventory'] = []
        doc['clusters'] = []
        doc['unanalysed'] = []
    json.dump(doc, open(path, 'w'))
elif scenario == 'garbage':
    open(path, 'w').write('{"clusters": ')
'''


def executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class Sandbox(unittest.TestCase):
    """A temp dir with a fake GCS tree and fake gcloud first on PATH."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='memory-runner-test-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.gcs = self.tmp / 'gcs'
        self.bin = self.tmp / 'bin'
        self.bin.mkdir()
        self.gcs.mkdir()
        executable(self.bin / 'gcloud', FAKE_GCLOUD)
        self.gcs_log = self.tmp / 'gcloud.log'
        self.env = {'PATH': '%s%s%s' % (self.bin, os.pathsep, os.environ['PATH']),
                    'FAKE_GCS_ROOT': str(self.gcs), 'FAKE_GCS_LOG': str(self.gcs_log)}
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_dir(self, run, job=JOB, prefix='logs', bucket=BUCKET):
        d = self.gcs / bucket / prefix / job / str(run)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def put_manifest(self, run, doc=None, test='bulk-triage-regressions', **kw):
        d = self.run_dir(run, **kw) / 'artifacts' / test / STEP_NAME / 'artifacts'
        d.mkdir(parents=True, exist_ok=True)
        text = doc if isinstance(doc, str) else json.dumps(doc if doc is not None else {'run': str(run)})
        (d / 'triage-manifest.json').write_text(text)
        return d / 'triage-manifest.json'

    def gcloud_calls(self):
        if not self.gcs_log.exists():
            return []
        return [json.loads(line) for line in self.gcs_log.read_text().splitlines()]

    def select(self, build_id='200', **kw):
        kw.setdefault('job', JOB)
        return mr.select(build_id=build_id, dest=str(self.tmp / 'baseline.json'), **kw)


class HistoryPrefixTest(unittest.TestCase):
    def test_periodic_and_rehearsal_histories_are_distinct(self):
        self.assertEqual(mr.history_prefix(JOB), 'gs://%s/logs/%s' % (BUCKET, JOB))
        self.assertEqual(mr.history_prefix(JOB, pull_number='86893', repo_owner='openshift', repo_name='release'),
                         'gs://%s/pr-logs/pull/openshift_release/86893/%s' % (BUCKET, JOB))
        self.assertEqual(mr.history_prefix(JOB, bucket='other'), 'gs://other/logs/%s' % JOB)

    def test_incomplete_or_unsafe_identity_has_no_history(self):
        for kw in ({'job': ''}, {'job': None}, {'job': 'a/../b'}, {'job': 'job*'}, {'job': JOB, 'pull_number': '12'},
                   {'job': JOB, 'pull_number': 'x', 'repo_owner': 'o', 'repo_name': 'r'},
                   {'job': JOB, 'pull_number': '1', 'repo_owner': 'o/p', 'repo_name': 'r'},
                   {'job': JOB, 'bucket': 'b/c'}):
            self.assertIsNone(mr.history_prefix(**kw), kw)

    def test_run_ids_are_direct_numeric_children_only(self):
        prefix = 'gs://b/logs/job'
        listing = '\n'.join([prefix + '/12/', prefix + '/7/', prefix + '/latest-build.txt', prefix + '/x9/',
                             prefix + '/12/artifacts/', 'gs://b/logs/other/99/', prefix + '/007/', ''])
        self.assertEqual(mr.parse_run_ids(listing, prefix), [7, 12])


class SelectTest(Sandbox):
    def test_selects_the_latest_preceding_attempt(self):
        for run in (99, 150, 1000, 200, 201):
            self.put_manifest(run)
        sel = self.select('200')
        self.assertEqual((sel['status'], sel['preceding_run_id']), ('selected', '150'))
        self.assertEqual(json.loads((self.tmp / 'baseline.json').read_text()), {'run': '150'})
        self.assertEqual(sel['baseline_path'], str(self.tmp / 'baseline.json'))
        self.assertTrue(sel['manifest_url'].startswith('gs://%s/logs/%s/150/artifacts/' % (BUCKET, JOB)))
        self.assertEqual(sel['history_url'], 'gs://%s/logs/%s' % (BUCKET, JOB))
        self.assertEqual(sel['current_run_url'],
                         'https://prow.ci.openshift.org/view/gs/%s/logs/%s/200' % (BUCKET, JOB))

    def test_run_ids_compare_as_exact_integers(self):
        # adjacent 19-digit ids are indistinguishable as floats
        for run in (2121136258473267200, 2121136258473267201, 2121136258473267203):
            self.put_manifest(run)
        sel = self.select('2121136258473267202')
        self.assertEqual(sel['preceding_run_id'], '2121136258473267201')
        self.put_manifest(999)                     # shorter, lexically greater: still older
        self.assertEqual(self.select('2121136258473267202')['preceding_run_id'], '2121136258473267201')

    def test_never_falls_back_to_an_older_success(self):
        self.put_manifest(100)
        self.run_dir(150)                          # the latest preceding attempt published no manifest
        sel = self.select('200')
        self.assertEqual((sel['status'], sel['preceding_run_id']), ('manifest-unavailable', '150'))
        self.assertIsNone(sel['baseline_path'])
        self.assertFalse((self.tmp / 'baseline.json').exists())
        self.assertFalse(any('/100/' in ' '.join(call) for call in self.gcloud_calls()))
        self.assertIn('matched no objects', sel['detail'])

    def test_failed_listing_discards_partial_output(self):
        self.put_manifest(99)
        with mock.patch.dict(os.environ, {'FAKE_GCS_FAIL_LS': '1'}):
            sel = self.select('200')
        self.assertEqual(sel['status'], 'history-unreadable')
        self.assertIsNone(sel['preceding_run_id'])
        self.assertIn('connection reset', sel['detail'])
        self.assertFalse((self.tmp / 'baseline.json').exists())

    def test_ambiguous_manifest_is_not_selected(self):
        self.put_manifest(150)
        self.put_manifest(150, test='another-test')
        sel = self.select('200')
        self.assertEqual(sel['status'], 'manifest-ambiguous')
        self.assertFalse((self.tmp / 'baseline.json').exists())
        self.assertFalse(any(call[:2] == ['storage', 'cp'] for call in self.gcloud_calls()))

    def test_unreadable_download_is_never_exposed(self):
        self.put_manifest(150, doc='{"truncated": ')
        sel = self.select('200')
        self.assertEqual(sel['status'], 'manifest-unreadable')
        self.assertFalse(list(self.tmp.glob('baseline.json*')))
        self.put_manifest(150, doc='[1, 2]')
        self.assertEqual(self.select('200')['status'], 'manifest-unreadable')
        self.put_manifest(150)
        with mock.patch.dict(os.environ, {'FAKE_GCS_FAIL_CP': '1'}):
            sel = self.select('200')
        self.assertEqual(sel['status'], 'manifest-unreadable')
        self.assertFalse(list(self.tmp.glob('baseline.json*')))

    def test_stale_local_baseline_is_removed_on_cold_start(self):
        (self.tmp / 'baseline.json').write_text('{"stale": true}')
        self.run_dir(150)
        self.select('200')
        self.assertFalse((self.tmp / 'baseline.json').exists())

    def test_first_run_has_no_preceding_attempt(self):
        self.run_dir(200)
        self.run_dir(300)
        sel = self.select('200')
        self.assertEqual((sel['status'], sel['preceding_run_id']), ('no-preceding-attempt', None))

    def test_missing_job_metadata_is_a_cold_start_without_lookup(self):
        for kw in ({'job': ''}, {'build_id': ''}, {'build_id': 'local'}, {'build_id': '12a'}):
            args = {'build_id': '200', 'job': JOB}
            args.update(kw)
            sel = mr.select(dest=str(self.tmp / 'baseline.json'), **args)
            self.assertEqual(sel['status'], 'metadata-missing', kw)
            self.assertIsNone(sel['current_run_url'])
        self.assertEqual(self.gcloud_calls(), [])

    def test_rehearsal_never_reads_the_periodic_history(self):
        self.put_manifest(150)
        pr = {'pull_number': '86893', 'repo_owner': 'openshift', 'repo_name': 'release'}
        self.assertEqual(self.select('200', **pr)['status'], 'history-unreadable')    # no such prefix yet
        self.put_manifest(120, prefix='pr-logs/pull/openshift_release/86893')
        self.put_manifest(130, prefix='pr-logs/pull/openshift_release/11111')
        sel = self.select('200', **pr)
        self.assertEqual((sel['status'], sel['preceding_run_id']), ('selected', '120'))
        self.assertIn('pr-logs/pull/openshift_release/86893', sel['manifest_url'])
        self.assertEqual(sel['pull_number'], '86893')

    def test_another_job_is_never_consulted(self):
        self.put_manifest(150, job='some-other-job')
        self.run_dir(10)
        self.assertEqual(self.select('200')['status'], 'manifest-unavailable')

    def test_injected_runner_boundary(self):
        calls = []

        def run(argv):
            calls.append(argv)
            return 0, 'gs://%s/logs/%s/5/\n' % (BUCKET, JOB), ''
        sel = mr.select(job=JOB, build_id='9', dest=str(self.tmp / 'b.json'), run=lambda argv: (
            run(argv) if argv[:3] == ['gcloud', 'storage', 'ls'] and argv[3].endswith(JOB + '/') else (1, '', 'boom')))
        self.assertEqual((sel['status'], sel['preceding_run_id'], sel['detail']), ('manifest-unavailable', '5', 'boom'))
        self.assertEqual(calls, [['gcloud', 'storage', 'ls', 'gs://%s/logs/%s/' % (BUCKET, JOB)]])

    def test_cli_prints_the_baseline_and_writes_provenance(self):
        self.put_manifest(150)
        out = self.tmp / 'sel' / 'memory-selection.json'
        out.parent.mkdir()
        argv = [sys.executable, str(HERE / 'memory_runner.py'), 'select', '--job', JOB, '--build-id', '200',
                '--mode', 'reuse', '--dest', str(self.tmp / 'baseline.json'), '--out', str(out)]
        cp = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual((cp.returncode, cp.stdout.strip()), (0, str(self.tmp / 'baseline.json')), cp.stderr)
        sel = json.loads(out.read_text())
        self.assertEqual((sel['status'], sel['mode'], sel['job'], sel['current_build_id']),
                         ('selected', 'reuse', JOB, '200'))
        argv[argv.index('--build-id') + 1] = '100'
        cp = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual((cp.returncode, cp.stdout.strip()), (0, 'none'), cp.stderr)
        self.assertEqual(json.loads(out.read_text())['status'], 'no-preceding-attempt')


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='memory-publish-test-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.work, self.keep, self.art = self.tmp / 'work', self.tmp / 'keep', self.tmp / 'artifacts'
        for d in (self.work, self.keep, self.art):
            d.mkdir()
        (self.tmp / 'inventory.json').write_text(json.dumps([reg(1, ['a1', 'a2']), reg(2, [])]))
        devel = [sys.executable, str(HERE / 'devel.py')]
        for args in (['prepare', '--inventory', str(self.tmp / 'inventory.json'), '--view', '5.1-main',
                      '--run-id', '200', '--out', str(self.work / 'prepass.json')],
                     ['checkpoint', '--prepass', str(self.work / 'prepass.json'),
                      '--out', str(self.work / 'triage-manifest.json')]):
            subprocess.run(devel + args, check=True, capture_output=True)
        shutil.copy(self.work / 'prepass.json', self.keep / 'inventory-prepass.json')
        shutil.copy(self.work / 'triage-manifest.json', self.keep / 'checkpoint-manifest.json')

    def publish(self):
        return mr.publish(initial=str(self.keep / 'inventory-prepass.json'),
                          checkpoint=str(self.keep / 'checkpoint-manifest.json'),
                          final=str(self.work / 'triage-manifest.json'), workdir=str(self.work),
                           artifact_dir=str(self.art))

    def reset_checkpoint(self, records):
        import devel
        prepared = devel.prepare(records, '5.1-main', datetime.now(timezone.utc), run_id='200')
        checkpoint = devel.checkpoint(prepared)
        for path, data in ((self.keep / 'inventory-prepass.json', prepared), (self.work / 'prepass.json', prepared),
                           (self.keep / 'checkpoint-manifest.json', checkpoint),
                           (self.work / 'triage-manifest.json', checkpoint)):
            path.write_text(json.dumps(data))
        return prepared

    def sweep_result(self, prepared, rid=1, tid=7):
        return {'regression_id': rid, 'triage_id': tid, 'jira': 'OCPBUGS-1', 'jira_status': 'Closed',
                'last_failure': prepared['inventory'][0]['last_failure'], 'verdict': 'alarm',
                'checked_at': prepared['observation']['time'],
                'lookup_locators': ['https://example.invalid/triages/7', 'https://example.invalid/OCPBUGS-1']}

    def test_non_object_analysis_is_rejected_before_artifact_promotion(self):
        for bad in (None, [], 'unfinished', False, 0):
            self.reset_checkpoint([reg(1, ['a1'])])
            self.edit(lambda d: d['clusters'][0]['disposition'].update(analysis=bad))
            status = self.publish()
            self.assertEqual(status['status'], 'invalid-final', bad)
            self.assertEqual(self.promoted(), json.loads((self.keep / 'checkpoint-manifest.json').read_text()))
            self.assertTrue((self.art / 'memory-publication.json').exists())
            self.assertTrue((self.art / 'triage-manifest.invalid.json').exists())

    def test_changing_only_state_cannot_complete_a_checkpoint(self):
        self.reset_checkpoint([reg(1, ['a1'])])
        def fake_completion(d):
            d['clusters'][0]['disposition']['state'] = 'UNEXPLAINED'
            d['unanalysed'] = []
        self.edit(fake_completion)
        self.assertEqual(self.publish()['status'], 'invalid-final')

    def test_missing_sweep_on_an_already_triaged_board_is_partial(self):
        self.reset_checkpoint([reg(1, ['a1'], [7])])
        self.edit(lambda d: d.update(stale_triage_sweep=[], sweep_candidates=[]))
        status = self.publish()
        self.assertEqual(status['status'], 'partial')
        self.assertEqual(status['sweep_pending'], [{'regression_id': 1, 'triage_id': 7}])
        cp = subprocess.run([sys.executable, str(HERE / 'memory_runner.py'), 'publish',
            '--initial', str(self.keep / 'inventory-prepass.json'), '--checkpoint', str(self.keep / 'checkpoint-manifest.json'),
            '--final', str(self.work / 'triage-manifest.json'), '--workdir', str(self.work), '--artifact-dir', str(self.art)],
            capture_output=True, text=True)
        self.assertEqual((cp.returncode, cp.stdout.strip()), (1, 'partial'), cp.stderr)

    def test_every_current_triage_needs_a_sweep_result(self):
        p = self.reset_checkpoint([reg(1, ['a1'], [7, 8])])
        self.edit(lambda d: d.update(stale_triage_sweep=[self.sweep_result(p)]))
        self.assertEqual(self.publish()['status'], 'partial')
        self.edit(lambda d: d['stale_triage_sweep'].append(self.sweep_result(p, tid=8)))
        self.assertEqual(self.publish()['status'], 'final')

    def test_explicit_unfinished_sweep_preserves_progress_as_partial(self):
        self.reset_checkpoint([reg(1, ['a1'], [7])])
        self.edit(lambda d: d.update(stale_triage_sweep=[{'regression_id': 1, 'triage_id': 7,
                                                        'verdict': 'incomplete', 'reason': 'Jira lookup unavailable'}]))
        self.assertEqual(self.publish()['status'], 'partial')
        self.assertEqual(self.promoted()['stale_triage_sweep'][0]['reason'], 'Jira lookup unavailable')

    def test_stale_or_malformed_sweep_cannot_establish_completion(self):
        for field, bad in (('checked_at', '2020-01-01T00:00:00Z'), ('lookup_locators', []),
                           ('jira_status', None), ('triage_id', 99), ('verdict', 'invented')):
            p = self.reset_checkpoint([reg(1, ['a1'], [7])])
            result = self.sweep_result(p)
            result[field] = bad
            self.edit(lambda d: d.update(stale_triage_sweep=[result]))
            self.assertEqual(self.publish()['status'], 'invalid-final', (field, bad))

    def test_unfinished_sweep_also_prevents_final_with_gaps(self):
        p = self.reset_checkpoint([reg(1, []), reg(2, ['b1'], [7])])
        def exhausted(d):
            d['clusters'][0]['disposition']['analysis']['evidence_unavailable'] = {
                'reason': 'no own runs after details lookup', 'checked_at': p['observation']['time'],
                'lookup_locators': ['https://example.invalid/regressions/1']}
        self.edit(exhausted)
        self.assertEqual(self.publish()['status'], 'partial')

    def test_empty_board_with_no_sweep_candidates_can_finish(self):
        self.reset_checkpoint([])
        self.edit(lambda d: d.update(stale_triage_sweep=[]))
        self.assertEqual(self.publish()['status'], 'final')

    def edit(self, fn):
        doc = json.loads((self.work / 'triage-manifest.json').read_text())
        fn(doc)
        (self.work / 'triage-manifest.json').write_text(json.dumps(doc))

    def progress(self, doc):
        for c in doc['clusters']:
            c['disposition']['analysis']['root_cause'] = 'budget exhausted after the first pass'

    def promoted(self):
        path = self.art / 'triage-manifest.json'
        return json.loads(path.read_text()) if path.exists() else None

    def test_valid_partial_manifest_preserves_progress_but_does_not_pass(self):
        self.edit(self.progress)
        status = self.publish()
        self.assertEqual((status['status'], status['promoted'], status['errors']), ('partial', 'final', []))
        self.assertEqual(manifest.validate(self.promoted()), [])
        self.assertEqual(self.promoted()['clusters'][0]['disposition']['analysis']['root_cause'],
                         'budget exhausted after the first pass')
        self.assertEqual(json.loads((self.art / 'memory-publication.json').read_text()), status)
        self.assertFalse((self.art / 'triage-manifest.invalid.json').exists())

    def test_cluster_deterministic_fields_are_recomputed_before_publication(self):
        for field in ('id', 'prior', 'blast_radius'):
            shutil.copy(self.keep / 'checkpoint-manifest.json', self.work / 'triage-manifest.json')
            def tamper(doc):
                self.progress(doc)
                c = doc['clusters'][0]
                if field == 'id':
                    c['id'] = 'made-up'
                elif field == 'prior':
                    c['prior'] = None
                    # The baseline-free groups already have null prior; tamper the lineage instead.
                    c['lineage']['cycles_seen'] = 999
                else:
                    c['blast_radius']['score'] = 999
            self.edit(tamper)
            status = self.publish()
            self.assertEqual(status['status'], 'invalid-final', (field, status))

    def test_exhausted_zero_run_lookup_is_explicit_final_with_gaps(self):
        def finish(doc):
            doc['unanalysed'] = []
            for c in doc['clusters']:
                an = c['disposition']['analysis']
                if any(e['run_ids'] for e in c['members']['coverage']):
                    c['disposition']['state'] = 'UNEXPLAINED'
                    an.update(depth='deep-dive', confidence='high', root_cause='verified fixture',
                              evidence=[{'prowjob_run_id': e['run_ids'][0], 'supports_regression_ids': [e['regression_id']],
                                         'artifact': 'fixture', 'quote': 'fixture failure'} for e in c['members']['coverage']])
                else:
                    an['evidence_unavailable'] = {'reason': 'current details still have no own runs',
                        'checked_at': doc['observation']['time'], 'lookup_locators': ['https://example.invalid/regressions/2']}
                    doc['unanalysed'].append({'cluster_id': c['id'], 'reason': 'no own runs'})
        self.edit(finish)
        status = self.publish()
        self.assertEqual(status['status'], 'final-with-gaps')
        self.assertEqual(status['unanalysed'], 1)

    def test_exhaustion_marker_cannot_excuse_unexamined_available_runs(self):
        self.edit(lambda d: d['clusters'][0]['disposition']['analysis'].update(evidence_unavailable={
            'reason': 'no time', 'checked_at': d['observation']['time'], 'lookup_locators': ['fixture']}))
        self.assertEqual(self.publish()['status'], 'invalid-final')

    def test_untouched_checkpoint_is_published_but_not_final(self):
        status = self.publish()
        self.assertEqual((status['status'], status['promoted']), ('checkpoint', 'checkpoint'))
        self.assertEqual(self.promoted(), json.loads((self.keep / 'checkpoint-manifest.json').read_text()))

    def test_missing_final_falls_back_to_the_checkpoint(self):
        (self.work / 'triage-manifest.json').unlink()
        status = self.publish()
        self.assertEqual((status['status'], status['promoted']), ('checkpoint', 'checkpoint'))
        self.assertIsNotNone(self.promoted())

    def test_deterministic_fields_cannot_change(self):
        for key, change in (('inventory', lambda d: d['inventory'][0].update(required=False)),
                            ('policy', lambda d: d['policy'].update(memory_mode='reuse')),
                            ('source_run', lambda d: d['source_run'].update(run_id='201')),
                            ('observation', lambda d: d['observation'].update(time='2020-01-01T00:00:00Z')),
                            ('baseline_run', lambda d: d['baseline_run'].update(reason='edited'))):
            shutil.copy(self.keep / 'checkpoint-manifest.json', self.work / 'triage-manifest.json')
            self.edit(lambda d: (self.progress(d), change(d)))
            status = self.publish()
            self.assertEqual((status['status'], status['promoted']), ('invalid-final', 'checkpoint'), key)
            self.assertTrue(any(key in e and 'differs from the runner' in e for e in status['errors']), status['errors'])
            self.assertEqual(self.promoted(), json.loads((self.keep / 'checkpoint-manifest.json').read_text()))
            self.assertTrue((self.art / 'triage-manifest.invalid.json').exists())

    def test_invalid_final_is_kept_only_as_a_diagnostic(self):
        self.edit(lambda d: d['clusters'][0]['disposition'].update(state='BOGUS'))
        status = self.publish()
        self.assertEqual((status['status'], status['promoted']), ('invalid-final', 'checkpoint'))
        self.assertTrue(status['errors'])
        self.assertEqual(self.promoted()['clusters'][0]['disposition']['state'], 'UNANALYSED')
        invalid = json.loads((self.art / 'triage-manifest.invalid.json').read_text())
        self.assertEqual(invalid['clusters'][0]['disposition']['state'], 'BOGUS')

    def test_unparseable_final(self):
        (self.work / 'triage-manifest.json').write_text('{"clusters": ')
        status = self.publish()
        self.assertEqual((status['status'], status['promoted']), ('invalid-final', 'checkpoint'))
        self.assertEqual((self.art / 'triage-manifest.invalid.json').read_text(), '{"clusters": ')

    def test_nothing_valid_promotes_nothing_and_clears_stale_output(self):
        (self.art / 'triage-manifest.json').write_text('{"stale": true}')
        (self.keep / 'checkpoint-manifest.json').unlink()
        self.edit(lambda d: d.update(inventory=[]))
        status = self.publish()
        self.assertEqual((status['status'], status['promoted']), ('none', None))
        self.assertIsNone(self.promoted())

    def test_without_the_runner_snapshot_nothing_is_trusted(self):
        (self.keep / 'inventory-prepass.json').unlink()
        self.edit(self.progress)
        status = self.publish()
        self.assertEqual((status['status'], status['promoted']), ('none', None))
        self.assertIsNone(self.promoted())
        self.assertTrue((self.art / 'triage-manifest.invalid.json').exists())

    def test_working_documents_are_exported_and_republishing_is_stable(self):
        (self.work / 'groups.json').write_text('{"groups": []}')
        (self.work / 'dispositions.json').write_text('{}')
        self.edit(self.progress)
        first = self.publish()
        for name in ('prepass.json', 'inventory-prepass.json', 'groups.json', 'dispositions.json'):
            self.assertTrue((self.art / name).exists(), name)
        self.assertEqual(json.loads((self.art / 'inventory-prepass.json').read_text()),
                         json.loads((self.keep / 'inventory-prepass.json').read_text()))
        self.assertEqual(self.publish(), first)

    def test_cli_exit_status_follows_finality(self):
        argv = [sys.executable, str(HERE / 'memory_runner.py'), 'publish',
                '--initial', str(self.keep / 'inventory-prepass.json'),
                '--checkpoint', str(self.keep / 'checkpoint-manifest.json'),
                '--final', str(self.work / 'triage-manifest.json'), '--workdir', str(self.work),
                '--artifact-dir', str(self.art)]
        cp = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual((cp.returncode, cp.stdout.strip()), (1, 'checkpoint'), cp.stderr)
        self.edit(self.progress)
        cp = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual((cp.returncode, cp.stdout.strip()), (1, 'partial'), cp.stderr)


@unittest.skipUnless(STEP.exists() and shutil.which('bash') and shutil.which('jq'),
                     'needs the openshift/release checkout beside this repository, bash and jq')
class StepScriptTest(Sandbox):
    """Runs the real step script; only gcloud, agentic-ci and the inventory source are replaced."""

    def setUp(self):
        super().setUp()
        executable(self.bin / 'agentic-ci', FAKE_AGENT)
        # The legacy runner cleans global agentic-ci scratch directories. Never let
        # a fake session touch another real session on the host running this test.
        executable(self.bin / 'rm', '#!/usr/bin/env python3\nimport sys\n'
                   'assert sys.argv[1] == "-rf" and all(p.startswith("/tmp/agentic-ci-run.") for p in sys.argv[2:])\n')
        self.agent_log = self.tmp / 'agent.log'
        (self.tmp / 'inventory.json').write_text(json.dumps([reg(1, ['a1', 'a2']), reg(2, ['b1'])]))

    def step(self, build_id='200', scenario='final', **extra):
        art = self.tmp / ('artifacts-%s-%d' % (build_id, len(list(self.tmp.glob('artifacts-*')))))
        art.mkdir()
        (self.tmp / 'shared').mkdir(exist_ok=True)
        (self.tmp / 'home').mkdir(exist_ok=True)
        env = dict(self.env, HOME=str(self.tmp / 'home'), TMPDIR=str(self.tmp), ARTIFACT_DIR=str(art), SHARED_DIR=str(self.tmp / 'shared'),
                   TRIAGE_VIEW='5.1-main', TRIAGE_COMPONENTS='all', TRIAGE_EXISTING_ONLY='true',
                   CLAUDE_MODEL='fake-model', AI_HELPERS_REPO='', JOB_NAME=JOB, BUILD_ID=build_id,
                   AI_HELPERS_DIR=str(REPO), TRIAGE_INVENTORY_FILE=str(self.tmp / 'inventory.json'),
                   FAKE_AGENT_LOG=str(self.agent_log), FAKE_AGENT_SCENARIO=scenario)
        env.update(extra)
        env = {k: v for k, v in env.items() if v is not None}
        before = len(self.agent_calls())
        cp = subprocess.run(['bash', str(STEP)], env=env, capture_output=True, text=True, timeout=120)
        calls = self.agent_calls()[before:]
        for call in calls:
            self.assertEqual(Path(call['workdir']).parent, self.tmp, 'step scratch must stay inside its TMPDIR')
        return cp, art, calls

    def agent_calls(self):
        if not self.agent_log.exists():
            return []
        return [json.loads(line) for line in self.agent_log.read_text().splitlines()]

    def load(self, art, name):
        return json.loads((art / name).read_text())

    def junit_failures(self, art):
        text = (art / 'junit_claude-ci.xml').read_text()
        import xml.etree.ElementTree as ET
        root = ET.fromstring(text)
        failed = [tc.get('name') for tc in root.iter('testcase') if tc.find('failure') is not None]
        self.assertEqual(int(root.get('failures')), len(failed))
        self.assertEqual(int(root.get('tests')), len(list(root.iter('testcase'))))
        return failed

    def publish_to_history(self, art, run):
        self.put_manifest(run, doc=(art / 'triage-manifest.json').read_text())

    def test_first_run_records_memory_and_passes(self):
        self.run_dir(200)                                 # Prow has already created this run's own directory
        cp, art, calls = self.step()
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertEqual(len(calls), 1)
        sel = self.load(art, 'memory-selection.json')
        self.assertEqual((sel['status'], sel['mode'], sel['baseline_path']), ('no-preceding-attempt', 'record', None))
        doc = self.load(art, 'triage-manifest.json')
        self.assertEqual(manifest.validate(doc), [])
        self.assertEqual(doc['policy']['memory_mode'], 'record')
        self.assertEqual(doc['policy']['scope'], {'views': ['5.1-main'], 'components': ['*']})
        self.assertEqual(doc['source_run'], {'run_id': '200', 'url': sel['current_run_url']})
        self.assertFalse(doc['baseline_run']['compatible'])
        self.assertEqual(self.load(art, 'memory-publication.json')['status'], 'final')
        self.assertEqual(self.load(art, 'inventory-prepass.json')['inventory'], doc['inventory'])
        self.assertEqual(self.junit_failures(art), [])
        self.assertTrue((art / 'triage-duty-report-5.1-main.md').exists())
        prompt, workdir = calls[0]['prompt'], calls[0]['workdir']
        # the agent is pointed at the files the runner actually created
        for name in ('prepass.json', 'inventory-prepass.json', 'triage-manifest.json'):
            self.assertIn('%s/%s' % (workdir, name), prompt)
        self.assertIn(str(REPO / 'plugins/ci/skills/bulk-triage-regressions/references/devel-memory.md'), prompt)
        self.assertIn('--baseline none', prompt)
        self.assertIn('EXISTING-ONLY MODE', prompt)

    def test_next_run_loads_only_the_latest_preceding_attempt(self):
        cp, first, _ = self.step('200')
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.publish_to_history(first, 200)
        time.sleep(1.1)                                   # observation times have one-second resolution
        cp, art, calls = self.step('300', scenario='reuse', TRIAGE_MEMORY='reuse')
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        sel = self.load(art, 'memory-selection.json')
        self.assertEqual((sel['status'], sel['preceding_run_id'], sel['mode']), ('selected', '200', 'reuse'))
        doc = self.load(art, 'triage-manifest.json')
        self.assertEqual((doc['baseline_run']['run_id'], doc['baseline_run']['compatible']), ('200', True))
        self.assertEqual(doc['policy']['memory_mode'], 'reuse')
        self.assertTrue(all(c['prior'] and c['prior']['run_id'] == '200' for c in doc['clusters']))
        self.assertTrue(all(c['disposition']['analysis']['depth'] == 'carried-forward' for c in doc['clusters']))
        self.assertIn('--baseline %s' % sel['baseline_path'], calls[0]['prompt'])
        # a later attempt that published nothing hides the older manifest: cold start, reported
        self.run_dir(350)
        cp, art, calls = self.step('400')
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        sel = self.load(art, 'memory-selection.json')
        self.assertEqual((sel['status'], sel['preceding_run_id']), ('manifest-unavailable', '350'))
        self.assertFalse(self.load(art, 'triage-manifest.json')['baseline_run']['compatible'])
        self.assertIn('--baseline none', calls[0]['prompt'])

    def test_gangway_override_selects_the_mode(self):
        cp, art, _ = self.step(TRIAGE_MEMORY='record', MULTISTAGE_PARAM_OVERRIDE_TRIAGE_MEMORY='reuse')
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertEqual(self.load(art, 'triage-manifest.json')['policy']['memory_mode'], 'reuse')

    def test_component_filter_reaches_the_scope(self):
        cp, art, _ = self.step(TRIAGE_COMPONENTS='Networking Unknown')
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertEqual(self.load(art, 'triage-manifest.json')['policy']['scope']['components'],
                         ['networking', 'unknown'])

    def test_agent_without_a_manifest_fails_the_job_but_publishes_the_checkpoint(self):
        cp, art, _ = self.step(scenario='report-only')
        self.assertEqual(cp.returncode, 1, cp.stdout + cp.stderr)
        self.assertEqual(self.load(art, 'memory-publication.json')['status'], 'checkpoint')
        doc = self.load(art, 'triage-manifest.json')
        self.assertEqual(manifest.validate(doc), [])
        self.assertTrue(all(c['disposition']['state'] == 'UNANALYSED' for c in doc['clusters']))
        self.assertEqual(self.junit_failures(art), ['[sig-claude] Claude should produce a valid triage memory manifest'])

    def test_tampered_manifest_fails_and_is_only_a_diagnostic(self):
        cp, art, _ = self.step(scenario='tamper')
        self.assertEqual(cp.returncode, 1, cp.stdout + cp.stderr)
        self.assertEqual(self.load(art, 'memory-publication.json')['status'], 'invalid-final')
        self.assertEqual(self.load(art, 'triage-manifest.invalid.json')['inventory'], [])
        self.assertEqual(len(self.load(art, 'triage-manifest.json')['inventory']), 2)
        self.assertEqual(len(self.junit_failures(art)), 1)

    def test_partial_analysis_is_published_without_reporting_success(self):
        cp, art, _ = self.step(scenario='partial')
        self.assertEqual(cp.returncode, 1, cp.stdout + cp.stderr)
        self.assertEqual(self.load(art, 'memory-publication.json')['status'], 'partial')
        doc = self.load(art, 'triage-manifest.json')
        self.assertEqual(doc['clusters'][0]['disposition']['analysis']['root_cause'],
                         'budget exhausted after the first pass')
        self.assertEqual(len(self.junit_failures(art)), 1)

    def test_unparseable_manifest_fails(self):
        cp, art, _ = self.step(scenario='garbage')
        self.assertEqual(cp.returncode, 1, cp.stdout + cp.stderr)
        self.assertEqual(self.load(art, 'memory-publication.json')['status'], 'invalid-final')

    def test_missing_report_still_publishes_memory(self):
        cp, art, _ = self.step(scenario='no-report')
        self.assertEqual(cp.returncode, 1, cp.stdout + cp.stderr)
        self.assertEqual(self.load(art, 'memory-publication.json')['status'], 'checkpoint')
        self.assertIn('[sig-claude] Claude should produce a triage duty report', self.junit_failures(art))

    def test_memory_off_is_the_legacy_run(self):
        self.put_manifest(150)
        cp, art, calls = self.step(TRIAGE_MEMORY='off', AI_HELPERS_DIR=str(self.tmp / 'old-image'))
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertEqual(sorted(p.name for p in art.iterdir()),
                         ['junit_claude-ci.xml', 'triage-duty-report-5.1-main.md'])
        self.assertEqual(self.gcloud_calls(), [])
        self.assertEqual(self.junit_failures(art), [])
        self.assertNotIn('devel-memory.md', calls[0]['prompt'])
        self.assertEqual(os.listdir(calls[0]['workdir']), ['triage-duty-report-5.1-main.md'])

    def test_old_image_without_the_helper_fails_before_the_agent(self):
        cp, art, calls = self.step(AI_HELPERS_DIR=str(self.tmp / 'old-image'))
        self.assertEqual(cp.returncode, 1)
        self.assertEqual(calls, [])
        self.assertIn('memory_runner.py', cp.stdout + cp.stderr)
        self.assertIn('TRIAGE_MEMORY=off', cp.stdout + cp.stderr)

    def test_unknown_mode_is_rejected(self):
        cp, _, calls = self.step(TRIAGE_MEMORY='fast')
        self.assertEqual(cp.returncode, 1)
        self.assertEqual(calls, [])

    def test_failed_inventory_keeps_the_selection_record_and_never_starts_the_agent(self):
        (self.tmp / 'inventory.json').write_text('[{"id": ')
        self.put_manifest(150)
        cp, art, calls = self.step()
        self.assertEqual(cp.returncode, 1)
        self.assertEqual(calls, [])
        self.assertEqual(self.load(art, 'memory-selection.json')['preceding_run_id'], '150')
        self.assertFalse((art / 'triage-manifest.json').exists())

    def test_manual_run_without_job_metadata_cold_starts(self):
        cp, art, _ = self.step(JOB_NAME=None, BUILD_ID=None)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertEqual(self.load(art, 'memory-selection.json')['status'], 'metadata-missing')
        doc = self.load(art, 'triage-manifest.json')
        self.assertEqual(doc['source_run'], {'run_id': 'local', 'url': None})
        self.assertEqual(self.gcloud_calls(), [])

    def test_rehearsal_reads_its_own_pull_request_history(self):
        cp, first, _ = self.step('200')
        self.publish_to_history(first, 200)               # periodic history only
        pr = {'PULL_NUMBER': '86893', 'REPO_OWNER': 'openshift', 'REPO_NAME': 'release'}
        cp, art, _ = self.step('300', **pr)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        sel = self.load(art, 'memory-selection.json')
        self.assertEqual(sel['status'], 'history-unreadable')
        self.assertIn('pr-logs/pull/openshift_release/86893', sel['history_url'])


if __name__ == '__main__':
    unittest.main()
