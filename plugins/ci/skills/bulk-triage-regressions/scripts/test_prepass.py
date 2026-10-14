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

    def test_tripwire_records_source_run(self):
        regs = [r for r in self.replay if '4.22-main' in r['duty_views']]
        doc = p.tripwire(regs, ts('2026-09-24T12:00:00Z'), 24, None, run_id='2200')
        self.assertEqual(doc['source_run'], {'run_id': '2200'})
        self.assertEqual(doc['policy'], {'name': 'post-ga'})

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
    def test_default_fetch_keeps_regression_level_opened_beside_view_activation(self):
        raw = [{'id': 48389, 'release': '4.22', 'test_name': 't', 'component': 'c', 'variants': [],
                'opened': '2026-09-05T04:09:53.827559Z', 'closed': {'Time': '0001-01-01T00:00:00Z', 'Valid': False},
                'views': [{'view_name': '4.22-main', 'active': True, 'opened_at': '2026-10-12T04:10:07.774716Z',
                           'closed_at': {'Time': '0001-01-01T00:00:00Z', 'Valid': False}}],
                'job_runs': []}]
        fetch = p._default_fetch(raw_fetch=lambda release: raw)
        regs, status = p.fetch_inventory(['4.22-main'], fetch=fetch, now=ts('2026-10-12T12:00:00Z'))
        self.assertEqual(regs[0]['opened'], '2026-10-12T04:10:07.774716Z')      # view activation (frozen rules)
        self.assertEqual(regs[0]['regression_opened'], '2026-09-05T04:09:53.827559Z')
        self.assertEqual(status[0]['open'], 1)

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
            self.assertIsNone(c['lineage']['supersedes'])

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
                    'clusters': [{'id': cid, 'lineage': {'cycles_seen': 2, 'first_seen_run': 'r-first'}, 'members': {'regression_ids': [1]}}]}
        c = p.weekly(regs, self.NOW, baseline)['clusters'][0]
        self.assertEqual(c['id'], cid)
        self.assertEqual(c['lineage']['first_seen_run'], 'r-first')
        self.assertEqual(c['lineage']['cycles_seen'], 3)
        self.assertEqual(c['members']['new_since_baseline'], [2])
        self.assertEqual(c['shape']['growth_since_baseline'], 1)


class TriagedTest(unittest.TestCase):
    def test_weekly_excludes_triaged_open_regressions(self):
        now = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
        runs = [run('1'), run('2')]
        a, b, c = reg(1, 'a', runs), reg(2, 'b', runs), reg(3, 'c', runs)
        b['triages'] = [{'id': 810}]
        c['triages'] = None
        doc = p.weekly([a, b, c], now, None)
        ids = [i for cl in doc['clusters'] for i in cl['members']['regression_ids']]
        self.assertEqual(sorted(ids), [1, 3])
        st = p.view_status('4.22-main', [a, b, c], now)
        self.assertEqual((st['open'], st['open_untriaged']), (3, 2))


class OracleTest(unittest.TestCase):
    MEMBERS = [reg(1, 'a', [run(str(i), start='2026-10-0%dT00:00:00Z' % i) for i in range(1, 8)])]

    def test_oracle_parses_json_despite_stderr_notice(self):
        # Real CLI shape in --format json mode: the submission notice goes to stderr, the batch JSON to stdout.
        batch = json.dumps({"batch_id": "b1", "status": "completed", "items": [
            {"item_key": "2109437410046644224", "state": "completed", "result": {"labels_applied": ["QuayCDNImageConfigEOF"]}},
            {"item_key": "2109075017747664896", "state": "completed", "result": {"labels_applied": []}}]}, indent=2)
        notice = "Submitted reevaluation (DRY RUN) batch b1; status: https://sippy-auth/x (save this URL ...)\n"
        members = [{'id': 1, 'release': '4.22', 'test_name': 't', 'component': 'c', 'variants': [], 'opened': '2026-10-01T00:00:00Z',
                    'closed': None, 'duty_views': ['4.22-main'],
                    'job_runs': [{'prowjob_name': 'j', 'prowjob_run_id': '2109437410046644224', 'start_time': '2026-10-11T00:00:00Z', 'test_failures': 1},
                                 {'prowjob_name': 'j', 'prowjob_run_id': '2109075017747664896', 'start_time': '2026-10-10T00:00:00Z', 'test_failures': 1}]}]
        # 3-tuple runner: (code, stdout, stderr)
        out = p.oracle(members, runner=lambda argv: (0, batch, notice), token='t', labels_fetch=lambda: [{"id": "QuayCDNImageConfigEOF", "bugs": ["TRT-3003"]}])
        self.assertEqual(out['status'], 'ok', out)
        self.assertEqual(out['labels'], {'2109437410046644224': ['QuayCDNImageConfigEOF']})
        self.assertEqual(out['label_bugs'], {'QuayCDNImageConfigEOF': ['TRT-3003']})
        # legacy 2-tuple runner with the notice glued in front of the JSON must still parse
        out2 = p.oracle(members, runner=lambda argv: (0, notice + batch), token='t', labels_fetch=lambda: [])
        self.assertEqual(out2['status'], 'ok', out2)

    def test_oracle_failure_records_error_text(self):
        members = [{'id': 1, 'release': '4.22', 'test_name': 't', 'component': 'c', 'variants': [], 'opened': '2026-10-01T00:00:00Z',
                    'closed': None, 'duty_views': ['4.22-main'],
                    'job_runs': [{'prowjob_name': 'j', 'prowjob_run_id': '1', 'start_time': '2026-10-11T00:00:00Z', 'test_failures': 1}]}]
        out = p.oracle(members, runner=lambda argv: (1, "", "Error: batch status item 0 is missing item_key"), token='t')
        self.assertEqual(out['status'], 'failed')
        self.assertIn('missing item_key', out['error'])
        out = p.oracle(members, runner=lambda argv: (0, "not json at all", ""), token='t')
        self.assertEqual(out['status'], 'failed')
        self.assertIn('not json', out['error'])

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

        o = p.oracle(self.MEMBERS, runner=runner, token='t', labels_fetch=lambda: [])
        self.assertEqual(o['status'], 'ok')
        self.assertEqual(o['labels'], {'7': ['L1']})
        self.assertEqual(o['runs_probed'], 5)
        self.assertEqual(seen[0][-5:], ['7', '6', '5', '4', '3'])
        self.assertIn('--dry-run', seen[0])

    OK = json.dumps({'items': [{'item_key': '7', 'state': 'completed', 'result': {'labels_applied': ['L1']}}]})

    def test_label_bugs_from_catalogue(self):
        calls = []

        def lf():
            calls.append(1)
            return [{'id': 'L1', 'bugs': ['OCPBUGS-1']}, {'id': 'L2', 'bugs': ['OCPBUGS-2']}]

        o = p.oracle(self.MEMBERS, runner=lambda a: (0, self.OK), token='t', labels_fetch=lf)
        self.assertEqual(o['label_bugs'], {'L1': ['OCPBUGS-1']})
        self.assertNotIn('label_bugs_error', o)
        self.assertEqual(len(calls), 1)

    def test_label_bugs_fetch_failure_is_reported(self):
        def lf():
            raise OSError('catalogue down')

        o = p.oracle(self.MEMBERS, runner=lambda a: (0, self.OK), token='t', labels_fetch=lf)
        self.assertEqual(o['status'], 'ok')
        self.assertEqual(o['label_bugs'], {})
        self.assertIn('catalogue down', o['label_bugs_error'])

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

    def test_cli_inventory_mode_marks_absent_views_unknown_not_zero(self):
        # An inventory file cannot distinguish "clean view" from "view not collected"; a view with no records
        # must surface as partial/unknown, never as fetch complete with open 0 (CodeRabbit on #804).
        with tempfile.TemporaryDirectory() as d:
            inv = os.path.join(d, 'inv.json')
            with gzip.open(os.path.join(HERE, 'fixtures', 'frozen-2026-10-07.json.gz'), 'rt') as f, open(inv, 'w') as g:
                g.write(f.read())
            out = os.path.join(d, 'out.json')
            self.assertEqual(p.main(['--views', '4.16-main', '4.22-main', '--inventory', inv, '--now', '2026-10-07T12:00:00Z',
                                     '--no-oracle', '--baseline', 'none', '--out', out]), 0)
            with open(out) as f:
                views = {v['view']: v for v in json.load(f)['observation']['views']}
            self.assertEqual(views['4.22-main']['fetch'], 'complete')
            self.assertEqual(views['4.16-main']['fetch'], 'partial')
            self.assertIsNone(views['4.16-main']['open'])
            self.assertIn('absent from inventory', views['4.16-main']['error'])


if __name__ == '__main__':
    unittest.main()
