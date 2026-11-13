#!/usr/bin/env python3
"""Development memory integration tests: own-run windows survive prepare/regroup/merge."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest
import prepass
import test_devel_contract as contract

SPEC = importlib.util.find_spec('devel')
if SPEC:
    import devel

NOW = datetime(2026, 11, 13, 7, tzinfo=timezone.utc)


def reg(rid, runs, triages=None):
    return {'id': rid, 'release': '5.1', 'test_name': 'test %s' % rid, 'component': 'Networking / router',
            'capability': 'Router', 'variants': ['Platform:aws', 'Architecture:amd64'],
            'opened': '2026-11-10T00:00:00Z', 'closed': None, 'last_failure': contract.T0,
            'duty_views': ['5.1-main'], 'triages': triages or [],
            'job_runs': [{'prowjob_run_id': run, 'prowjob_name': 'periodic-ci-example-5.1-aws',
                          'start_time': contract.T0, 'test_failed': False, 'test_failures': 3} for run in runs]}


def group(rid, runs, discriminator='DNS NXDOMAIN'):
    return {'coverage': [{'regression_id': rid, 'run_ids': runs}],
            'signature': {'stage': 'test', 'discriminator': discriminator}}


class DevelPipelineTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(SPEC, 'devel memory pipeline must exist')

    def prep(self, regs=None, baseline=None, **kwargs):
        return devel.prepare(regs if regs is not None else [reg(1, ['a1', 'a2'])],
                             '5.1-main', NOW, baseline=baseline, run_id='r1', **kwargs)

    def test_cold_start_is_valid_unfinished_not_empty(self):
        p = self.prep([reg(1, ['a1']), reg(2, []), reg(3, ['b1'], [7])])
        result = devel.checkpoint(p)
        self.assertEqual(manifest.validate(result), [])
        self.assertFalse(result['baseline_run']['compatible'])
        self.assertEqual([r['id'] for r in result['inventory'] if r['required']], [1, 2])
        self.assertEqual(p['sweep_candidates'], [3])
        self.assertEqual(len(result['unanalysed']), 2)

    def test_shared_regression_disjoint_windows_do_not_merge_priors(self):
        baseline = contract.doc([contract.cluster('g-a', contract.cov(r1=['a1'])),
                                 contract.cluster('g-c', contract.cov(r1=['c1']))],
                                [contract.inv(1, ['a1', 'c1'])])
        p = self.prep([reg(1, ['a1', 'c1', 'c2'])], baseline, mode='reuse')
        out = devel.regroup(p, {'groups': [group(1, ['a1']), group(1, ['c1', 'c2'])], 'unassigned': []}, baseline)
        self.assertEqual({c['id'] for c in out['clusters']}, {'g-a', 'g-c'})
        self.assertEqual([s['cluster_id'] for s in out['clusters'][0]['prior']['sources']], ['g-a'])
        c = next(c for c in out['clusters'] if c['id'] == 'g-c')
        self.assertEqual(c['prior']['run_delta']['added'], contract.cov(r1=['c2']))
        self.assertEqual(manifest.validate(devel.checkpoint(out)), [])

    def test_split_and_merge_are_not_same_id(self):
        baseline = contract.baseline_one()
        p = self.prep(baseline=baseline)
        split = devel.regroup(p, {'groups': [group(1, ['a1']), group(1, ['a2'], 'EOF')]}, baseline)
        self.assertEqual({c['prior']['relationship'] for c in split['clusters']}, {'split'})
        again = devel.regroup(p, {'groups': [group(1, ['a2'], 'EOF'), group(1, ['a1'])]}, baseline)
        self.assertEqual([c['id'] for c in split['clusters']], [c['id'] for c in again['clusters']])
        split_baseline = devel.checkpoint(split)
        split_baseline['source_run']['run_id'] = 'older'
        split_baseline['observation']['time'] = contract.T0
        merged = devel.regroup(self.prep(baseline=split_baseline), {'groups': [group(1, ['a1', 'a2'])]}, split_baseline)
        self.assertEqual(merged['clusters'][0]['prior']['relationship'], 'merge')

    def test_triaged_baseline_members_stay_required(self):
        p = self.prep([reg(1, ['a1', 'a2'], [99])], contract.baseline_one())
        self.assertTrue(p['inventory'][0]['required'])
        self.assertEqual(p['sweep_candidates'], [1])
        self.assertEqual(p['clusters'][0]['id'], 'g-a')

    def test_invalid_or_different_scope_baseline_cold_starts(self):
        for mutate in (lambda b: b.update(inventory=[]),
                       lambda b: b['policy']['scope'].update(views=['5.0-main']),
                       lambda b: b['source_run'].update(run_id='r1')):
            b = contract.baseline_one()
            mutate(b)
            p = self.prep(baseline=b)
            self.assertFalse(p['baseline_run']['compatible'])
            self.assertTrue(p['baseline_run']['reason'])
            self.assertTrue(all(c['prior'] is None for c in p['clusters']))

    def test_regroup_rejects_duplicate_foreign_or_unaccounted_runs(self):
        p = self.prep()
        for groups in ([group(1, ['a1'])], [group(1, ['a1', 'a2']), group(1, ['a1'])],
                       [group(1, ['a1', 'a2', 'foreign'])], [group(1, [])]):
            with self.assertRaises(ValueError):
                devel.regroup(p, {'groups': groups})

    def test_unassigned_has_no_claimed_cause_and_can_include_sweep_alarm(self):
        p = self.prep([reg(1, ['a1']), reg(2, ['b1'], [7])])
        out = devel.regroup(p, {'groups': [group(2, ['b1'])],
                                'unassigned': [{'regression_id': 1, 'run_ids': ['a1'], 'reason': 'logs unavailable'}]})
        result = devel.checkpoint(out)
        self.assertEqual(manifest.validate(result), [])
        self.assertEqual(len(result['clusters']), 2)
        self.assertIn('logs unavailable', [c['disposition']['analysis']['root_cause'] for c in result['clusters']])

    def test_current_inventory_failure_is_not_a_clean_board(self):
        with self.assertRaises(ValueError):
            devel.collect('5.1-main', fetch=lambda release: [])
        with self.assertRaises(ValueError):
            devel.collect('5.1-main', fetch=lambda release: {'error': 'unavailable'})

    def test_collect_preserves_component_filter_and_false_test_failed_runs(self):
        r = reg(1, ['a1'])
        r['views'] = [{'view_name': '5.1-main', 'active': True, 'opened_at': r['opened']}]
        other = copy.deepcopy(r)
        other.update(id=2, component='Etcd')
        records = devel.collect('5.1-main', ['router'], fetch=lambda release: [r, other])
        self.assertEqual([r['id'] for r in records], [1])
        self.assertEqual(records[0]['job_runs'][0]['prowjob_run_id'], 'a1')

    def test_completed_proposal_survives_next_prepare_without_replayed_actions(self):
        p = self.prep()
        p = devel.regroup(p, {'groups': [group(1, ['a1', 'a2'])]})
        c = p['clusters'][0]
        disposition = contract.cluster('unused', contract.cov(r1=['a1', 'a2']),
                                        state='NEW-BUG-NEEDED', proposal=contract.proposal())['disposition']
        baseline = manifest.merge(p, {c['id']: disposition}, {}, {'unanalysed': []})
        baseline['source_run']['run_id'] = 'r0'
        baseline['observation']['time'] = contract.T0
        self.assertEqual(manifest.validate(baseline), [])
        result = devel.checkpoint(self.prep(baseline=baseline))
        self.assertEqual(result['clusters'][0]['actions'], [])
        self.assertIn('draft_sha256', result['clusters'][0]['prior']['sources'][0]['new_bug_proposal'])
        self.assertEqual(result['clusters'][0]['disposition']['state'], 'UNANALYSED')

    def test_cli_prepare_and_checkpoint_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'inventory.json').write_text(json.dumps([reg(1, ['a1'])]))
            script = str(Path(__file__).with_name('devel.py'))
            for args in (['prepare', '--inventory', str(root / 'inventory.json'), '--view', '5.1-main',
                          '--now', contract.T1, '--out', str(root / 'prepass.json')],
                         ['checkpoint', '--prepass', str(root / 'prepass.json'), '--out', str(root / 'manifest.json')]):
                cp = subprocess.run([sys.executable, script] + args, capture_output=True, text=True)
                self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertEqual(manifest.validate(json.loads((root / 'manifest.json').read_text())), [])

    def test_proposal_draft_survives_an_unfinished_attempt(self):
        base = contract.doc([contract.cluster('g-a', contract.cov(r1=['a1', 'a2']),
                            state='NEW-BUG-NEEDED', proposal=contract.proposal())], [contract.inv(1, ['a1', 'a2'])])
        partial = devel.checkpoint(self.prep(baseline=base))
        later = devel.prepare([reg(1, ['a1', 'a2'])], '5.1-main',
                              datetime(2026, 11, 14, 7, tzinfo=timezone.utc), baseline=partial, run_id='r2')
        source = next(s for s in later['clusters'][0]['prior']['sources'] if s['history_only'])
        self.assertEqual(later['proposal_drafts'][source['new_bug_proposal']['draft_sha256']], contract.DRAFT)

    def test_proposal_archive_cannot_be_overwritten_or_forged(self):
        p = self.prep()
        with self.assertRaises(ValueError):
            manifest.merge(p, {}, {}, {'proposal_drafts': {'bad': 'forged'}})
        doc = devel.checkpoint(p)
        doc['proposal_drafts'] = {'bad': 'forged'}
        self.assertTrue(manifest.validate(doc))

    def test_bad_baseline_cycle_count_is_not_an_inventory_outage(self):
        baseline = contract.baseline_one()
        baseline['clusters'][0]['lineage']['cycles_seen'] = 'unknown'
        result = self.prep(baseline=baseline)
        self.assertEqual(manifest.validate(devel.checkpoint(result)), [])

    def test_invalid_unicode_draft_is_rejected_without_crashing(self):
        baseline = contract.doc([contract.cluster('g-a', contract.cov(r1=['a1', 'a2']),
                            state='NEW-BUG-NEEDED', proposal=contract.proposal('\ud83d'))], [contract.inv(1, ['a1', 'a2'])])
        self.assertTrue(manifest.validate(baseline))
        self.assertFalse(self.prep(baseline=baseline)['baseline_run']['compatible'])
        baseline['proposal_drafts'] = {'bad': '\ud83d'}
        self.assertTrue(manifest.validate(baseline))

    def test_candidate_high_urgency_cannot_be_lost_by_singleton_partition(self):
        regs = [reg(i, ['shared-a', 'shared-b']) for i in range(1, 10)]
        for i, r in enumerate(regs):
            r['opened'] = '2026-10-01T00:00:00Z'
            r['job_runs'].append(dict(r['job_runs'][0], prowjob_run_id='recent-%d' % i,
                                      prowjob_name='job-%d' % i))
        p = self.prep(regs)
        self.assertEqual(p['candidate_groups'][0]['blast_radius']['level'], 'HIGH')
        self.assertTrue(all(c['blast_radius']['level'] == 'HIGH' for c in p['clusters']))
        groups = [group(r['id'], [j['prowjob_run_id'] for j in r['job_runs']]) for r in regs]
        out = devel.regroup(p, {'groups': groups})
        self.assertTrue(all(c['blast_radius']['level'] == 'HIGH' for c in out['clusters']))

    def test_invalid_merge_does_not_destroy_a_valid_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = self.prep()
            before = devel.checkpoint(p)
            files = {'p.json': p, 'd.json': {p['clusters'][0]['id']: {'state': 'BOGUS'}}, 'a.json': {},
                     'result.json': before}
            for name, data in files.items():
                (root / name).write_text(json.dumps(data))
            cp = subprocess.run([sys.executable, str(Path(manifest.__file__)), 'merge', '--prepass', str(root / 'p.json'),
                '--dispositions', str(root / 'd.json'), '--actions', str(root / 'a.json'), '--out', str(root / 'result.json')],
                capture_output=True, text=True)
            self.assertEqual(cp.returncode, 1)
            self.assertEqual(json.loads((root / 'result.json').read_text()), before)


class GAAliasTest(unittest.TestCase):
    def test_ga_baseline_diff_and_prior_agree(self):
        baseline = prepass.weekly([reg(1, ['a1'])], NOW, None)
        baseline['policy']['name'] = 'ga'
        result = prepass.weekly([reg(1, ['a1'])], NOW, baseline)
        self.assertTrue(result['baseline_run']['compatible'])
        self.assertIsNotNone(result['clusters'][0]['prior'])


if __name__ == '__main__':
    unittest.main()
