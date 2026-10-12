#!/usr/bin/env python3
"""Tests for the bulk-triage pre-pass CLI: backtest fixtures, tripwire, baseline diff, oracle."""
import gzip
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import clustering  # noqa: E402
import prepass as p  # noqa: E402


def load(name):
    with gzip.open(os.path.join(HERE, 'fixtures', name), 'rt') as f:
        return json.load(f)


def ts(s):
    return clustering.parse_ts(s)


def find(doc, rid):
    return [c for c in doc['clusters'] if rid in c['members']['regression_ids']][0]


def run(rid, job='periodic-ci-x-nightly-4.22-e2e-aws-ovn', start='2026-10-06T12:00:00Z'):
    return {'prowjob_name': job, 'prowjob_run_id': rid, 'start_time': start, 'test_failures': 1}


def reg(rid, test, runs, opened='2026-10-01T00:00:00Z'):
    return {'id': rid, 'release': '4.22', 'duty_views': ['4.22-main'], 'test_name': test, 'component': 'c',
            'variants': ['Platform:aws'], 'opened': opened, 'closed': None, 'triages': [], 'job_runs': runs}


ALL_VIEWS = ['4.%d-main' % i for i in range(16, 23)]


class BacktestTest(unittest.TestCase):
    def test_backtest_frozen_inventory(self):
        now = ts('2026-10-07T12:00:00Z')
        frozen = load('frozen-2026-10-07.json.gz')
        regs, status = p.fetch_inventory(ALL_VIEWS, fetch=lambda v: [r for r in frozen if v in r['duty_views']], now=now)
        self.assertEqual(len(regs), 326)
        doc = p.weekly(regs, now, None, view_status=status)
        self.assertEqual(len(doc['clusters']), 15)
        c = find(doc, 49531)
        self.assertEqual(c['blast_radius']['level'], 'HIGH')
        self.assertEqual(c['shape']['regressions'], 230)
        self.assertEqual(find(doc, 50051)['blast_radius']['level'], 'HIGH')
        c = find(doc, 50173)
        self.assertEqual(c['blast_radius']['level'], 'ELEVATED')
        self.assertTrue(c['shape']['mass_failure_marker'])
        self.assertEqual(find(doc, 46428)['blast_radius']['level'], 'ELEVATED')
        self.assertEqual(find(doc, 36206)['blast_radius']['level'], 'LOW')
        self.assertEqual(len(doc['observation']['views']), 7)
        self.assertTrue(all(v['fetch'] == 'complete' for v in doc['observation']['views']))
        self.assertEqual(doc['observation']['symptom_probe']['status'], 'skipped')


class TripwireTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.replay = load('replay-days.json.gz')

    def trip(self, now, view, prev=None):
        regs = [r for r in self.replay if view in r['duty_views']]
        return p.tripwire(regs, ts(now), 24, prev)

    def test_tripwire_0924_high_0830_elevated(self):
        doc = self.trip('2026-09-24T12:00:00Z', '4.22-main')
        self.assertEqual([t['level'] for t in doc['triggers']], ['HIGH'])
        s = [c for c in doc['clusters'] if c['id'] == doc['triggers'][0]['cluster_id']][0]['shape']
        self.assertGreaterEqual(s['regressions'], 100)
        self.assertGreaterEqual(s['distinct_jobs'], 10)
        doc = self.trip('2026-08-30T12:00:00Z', '4.20-main')
        self.assertTrue(doc['triggers'])
        self.assertNotIn('HIGH', [t['level'] for t in doc['triggers']])
        t = doc['triggers'][0]
        s = [c for c in doc['clusters'] if c['id'] == t['cluster_id']][0]['shape']
        self.assertEqual(t['level'], 'ELEVATED')
        self.assertGreaterEqual(s['regressions'], 300)
        self.assertLessEqual(s['distinct_jobs'], 3)

    def test_tripwire_0920_precursor_high(self):
        doc = self.trip('2026-09-20T00:00:00Z', '4.22-main')
        self.assertIn('HIGH', [t['level'] for t in doc['triggers']])

    def test_tripwire_0925_is_continuing_not_new(self):
        prev = self.trip('2026-09-24T12:00:00Z', '4.22-main')
        doc = self.trip('2026-09-25T12:00:00Z', '4.22-main', prev)
        self.assertTrue(doc['triggers'])
        self.assertTrue(all(t['kind'] in ('continuing', 'growth') for t in doc['triggers']))


class InventoryTest(unittest.TestCase):
    def test_partial_fetch_is_partial_not_zero(self):
        replay = load('replay-days.json.gz')
        views = ['4.20-main', '4.22-main']

        def fetch(view):
            if view == '4.20-main':
                raise RuntimeError('boom')
            return [r for r in replay if view in r['duty_views']]

        regs, status = p.fetch_inventory(views, fetch=fetch)
        st = {s['view']: s for s in status}
        self.assertEqual(st['4.20-main']['fetch'], 'partial')
        self.assertIsNone(st['4.20-main']['open'])
        self.assertIn('boom', st['4.20-main']['error'])
        self.assertEqual(st['4.22-main']['fetch'], 'complete')
        doc = p.weekly(regs, ts('2026-09-25T12:00:00Z'), None, view_status=status)
        self.assertTrue(all('4.20-main' not in c['members']['views'] for c in doc['clusters']))

    def test_multi_view_regression_merged(self):
        a = reg(1, 't', [run('1')])
        regs, _ = p.fetch_inventory(['4.22-main', '4.22-rc'], fetch=lambda v: [dict(a)])
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]['duty_views'], ['4.22-main', '4.22-rc'])

    def test_closed_struct_valid_false_is_open(self):
        self.assertIs(p.is_open({'closed': {'Time': '2026-01-01T00:00:00Z', 'Valid': False}}), True)
        self.assertIs(p.is_open({'closed': {'Time': '2026-01-01T00:00:00Z', 'Valid': True}}), False)
        self.assertIs(p.is_open({'closed': None}), True)
        self.assertIs(p.is_open({'closed': '2026-01-01T00:00:00Z'}), False)


class BaselineTest(unittest.TestCase):
    NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)

    def test_incompatible_baseline_nulls_growth(self):
        regs = [reg(1, 'a', [run('1')]), reg(2, 'b', [run('2')])]
        doc = p.weekly(regs, self.NOW, {'schema_version': '0.9', 'policy': {'name': 'post-ga'}, 'clusters': []})
        self.assertIs(doc['baseline_run']['compatible'], False)
        for c in doc['clusters']:
            self.assertIsNone(c['shape']['growth_since_baseline'])
            self.assertIsNone(c['lineage']['cycles_seen'])
            self.assertIsNone(c['members']['new_since_baseline'])

    def test_no_baseline_is_none_compatible(self):
        doc = p.weekly([reg(1, 'a', [run('1')])], self.NOW, None)
        self.assertIsNone(doc['baseline_run']['compatible'])

    def test_split_cluster_records_supersedes(self):
        runs_a = [run('1'), run('2')]
        runs_b = [run('3'), run('4')]
        regs = [reg(i, 'a', runs_a) for i in (1, 2, 3, 4)] + [reg(i, 'b', runs_b) for i in (5, 6)]
        baseline = {'schema_version': '1.0', 'policy': {'name': 'post-ga'}, 'source_run': {'run_id': 'r0'},
                    'clusters': [{'id': 'c-old', 'members': {'regression_ids': [1, 2, 3, 4, 5, 6]}}]}
        doc = p.weekly(regs, self.NOW, baseline, run_id='r1')
        self.assertTrue(doc['baseline_run']['compatible'])
        big, small = find(doc, 1), find(doc, 5)
        self.assertEqual(len(big['members']['regression_ids']), 4)
        self.assertIn('c-old', big['lineage']['supersedes'])
        self.assertNotIn('c-old', small['lineage']['supersedes'])
        self.assertEqual(big['lineage']['first_seen_run'], 'r1')
        self.assertEqual(big['lineage']['cycles_seen'], 1)

    def test_same_id_increments_cycles_and_counts_new(self):
        regs = [reg(1, 'a', [run('1')]), reg(2, 'a', [run('1')])]
        cid = p.build_clusters(regs[:1], self.NOW)[0]['id']
        baseline = {'schema_version': '1.0', 'policy': {'name': 'post-ga'}, 'source_run': {'run_id': 'r0'},
                    'clusters': [{'id': cid, 'lineage': {'cycles_seen': 2}, 'members': {'regression_ids': [1]}}]}
        c = p.weekly(regs, self.NOW, baseline)['clusters'][0]
        self.assertEqual(c['id'], cid)
        self.assertEqual(c['lineage']['first_seen_run'], 'r0')
        self.assertEqual(c['lineage']['cycles_seen'], 3)
        self.assertEqual(c['members']['new_since_baseline'], [2])
        self.assertEqual(c['shape']['growth_since_baseline'], 1)


class OracleTest(unittest.TestCase):
    MEMBERS = [reg(1, 'a', [run(str(i), start='2026-10-0%dT00:00:00Z' % i) for i in range(1, 8)])]

    def test_oracle_403_is_unauthorized_not_empty(self):
        o = p.oracle(self.MEMBERS, runner=lambda argv: (1, 'HTTP 403 Forbidden'), token='t')
        self.assertEqual(o['status'], 'unauthorized')
        self.assertEqual(o['labels'], {})
        doc = p.weekly(self.MEMBERS, datetime(2026, 10, 7, tzinfo=timezone.utc), None,
                       oracle=lambda m: p.oracle(m, runner=lambda argv: (1, '403'), token='t'))
        self.assertEqual(doc['observation']['symptom_probe']['status'], 'unauthorized')

    def test_oracle_ok_parses_labels_and_probes_five_newest(self):
        seen = []

        def runner(argv):
            seen.append(argv)
            return 0, json.dumps({'items': [{'item_key': '7', 'state': 'completed',
                                             'result': {'symptoms_matched': ['S1'], 'labels_applied': ['L1']}}]})

        o = p.oracle(self.MEMBERS, runner=runner, token='t')
        self.assertEqual(o['status'], 'ok')
        self.assertEqual(o['labels'], {'7': ['L1', 'S1']})
        self.assertEqual(o['runs_probed'], 5)
        self.assertEqual(seen[0][-5:], ['7', '6', '5', '4', '3'])
        self.assertIn('--dry-run', seen[0])

    def test_oracle_other_failure_and_skipped(self):
        self.assertEqual(p.oracle(self.MEMBERS, runner=lambda a: (2, 'oops'), token='t')['status'], 'failed')
        self.assertEqual(p.oracle(self.MEMBERS)['status'], 'skipped')


class CliTest(unittest.TestCase):
    def test_cli_weekly_and_tripwire(self):
        with tempfile.TemporaryDirectory() as d:
            inv = os.path.join(d, 'inv.json')
            with gzip.open(os.path.join(HERE, 'fixtures', 'frozen-2026-10-07.json.gz'), 'rt') as f, open(inv, 'w') as g:
                g.write(f.read())
            out = os.path.join(d, 'out.json')
            self.assertEqual(p.main(['--views', '4.22-main', '--inventory', inv, '--now', '2026-10-07T12:00:00Z',
                                     '--no-oracle', '--baseline', 'none', '--out', out]), 0)
            with open(out) as f:
                doc = json.load(f)
            self.assertEqual(doc['schema_version'], '1.0')
            self.assertEqual(doc['mode'], 'weekly')
            lv = [p.LEVEL_ORDER[c['blast_radius']['level']] for c in doc['clusters']]
            self.assertEqual(lv, sorted(lv))
            self.assertEqual(p.main(['--tripwire', '--views', '4.22-main', '--inventory', inv,
                                     '--now', '2026-10-07T12:00:00Z', '--out', out]), 0)
            with open(out) as f:
                self.assertEqual(json.load(f)['mode'], 'tripwire')


if __name__ == '__main__':
    unittest.main()
