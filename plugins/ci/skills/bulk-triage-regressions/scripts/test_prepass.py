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
        # the complete expected outcome, from fixtures/expected-backtest.json (not just representatives)
        with open(os.path.join(HERE, 'fixtures', 'expected-backtest.json')) as f:
            exp = json.load(f)['frozen-2026-10-07']
        levels = {}
        for c in doc['clusters']:
            levels[c['blast_radius']['level']] = levels.get(c['blast_radius']['level'], 0) + 1
        self.assertEqual(levels, exp['distribution'])
        self.assertEqual(sorted(c['id'] for c in doc['clusters'] if c['blast_radius']['level'] == 'HIGH'), exp['HIGH']['ids'])
        self.assertEqual(sorted(c['id'] for c in doc['clusters'] if c['blast_radius']['level'] == 'ELEVATED'), exp['ELEVATED']['ids'])
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
        self.assertGreaterEqual(s['distinct_jobs'], 8)   # as-of 09-24T12 evidence (11 with runs that happened later)
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
        # the majority successor continues the superseded cluster's lineage (its id changed, not its identity)
        self.assertEqual(big['lineage']['first_seen_run'], 'r0')
        self.assertEqual(big['lineage']['cycles_seen'], 2)
        self.assertEqual((small['lineage']['first_seen_run'], small['lineage']['cycles_seen']), ('r1', 1))

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
            {"item_key": "2109437410046644224", "state": "completed", "result": {"status": "success", "labels_applied": ["QuayCDNImageConfigEOF"]}},
            {"item_key": "2109075017747664896", "state": "completed", "result": {"status": "success", "labels_applied": []}}]}, indent=2)
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
            items = [{'item_key': k, 'state': 'completed',
                      'result': {'status': 'success', 'symptoms_matched': ['S1'] if k == '7' else [],
                                 'labels_applied': ['L1'] if k == '7' else []}} for k in argv[-5:]]
            return 0, json.dumps({'items': items})

        o = p.oracle(self.MEMBERS, runner=runner, token='t', labels_fetch=lambda: [])
        self.assertEqual(o['status'], 'ok')
        self.assertEqual(o['labels'], {'7': ['L1']})
        self.assertEqual(o['runs_probed'], 5)
        self.assertEqual(seen[0][-5:], ['7', '6', '5', '4', '3'])
        self.assertIn('--dry-run', seen[0])

    # every probed run (the five newest: 7..3) must be reported by the batch, else the probe is incomplete
    OK = json.dumps({'items': [{'item_key': str(i), 'state': 'completed',
                                'result': {'status': 'success', 'labels_applied': ['L1'] if i == 7 else []}}
                               for i in range(7, 2, -1)]})

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
        self.assertIsNone(o['label_bugs'])            # unknown mapping, never "these labels have no bugs"
        self.assertIn('catalogue down', o['label_bugs_error'])

    def test_oracle_other_failure_and_skipped(self):
        self.assertEqual(p.oracle(self.MEMBERS, runner=lambda a: (2, 'oops'), token='t')['status'], 'failed')
        self.assertEqual(p.oracle(self.MEMBERS)['status'], 'skipped')


class ReviewFixesTest(unittest.TestCase):
    """Pre-merge review findings C4, C5, I1, I2, I4, I6 and the closed_7d struct minor."""

    @classmethod
    def setUpClass(cls):
        cls.frozen = load('frozen-2026-10-07.json.gz')

    # ---- I3: separate clusters never share an id ----
    def test_distinct_clusters_get_distinct_ids(self):
        now = ts('2026-10-07T12:00:00Z')
        doc = p.weekly([reg(1, '[a] same test', [run('1')]), reg(2, '[b] same test', [run('2')]),
                        reg(3, '[c] same test', [run('3')])], now, None)
        ids = [c['id'] for c in doc['clusters']]
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), 3, ids)
        self.assertTrue(all(len(i.split('-')) == 3 for i in ids), ids)   # every colliding cluster is suffixed by its own test names
        # deterministic: same input → same ids
        self.assertEqual(ids, [c['id'] for c in p.weekly([reg(1, '[a] same test', [run('1')]), reg(2, '[b] same test', [run('2')]),
                                                          reg(3, '[c] same test', [run('3')])], now, None)['clusters']])

    def test_backtest_ids_are_unique(self):
        doc = p.weekly(self.frozen, ts('2026-10-07T12:00:00Z'), None)
        ids = [c['id'] for c in doc['clusters']]
        self.assertEqual(len(ids), len(set(ids)))

    # ---- C4: a failed/incomplete reevaluate result is never an empty success ----
    def test_oracle_item_error_is_failed_and_keeps_partial_labels(self):
        members = [reg(1, 't', [run('1', start='2026-10-06T12:00:00Z'), run('2', start='2026-10-05T12:00:00Z')])]
        batch = {'batch_id': 'b', 'status': 'complete', 'items': [
            {'item_key': '1', 'state': 'completed', 'result': {'status': 'success', 'labels_applied': ['L1']}},
            {'item_key': '2', 'state': 'completed', 'result': {'status': 'eval_error', 'error': 'GCS timeout'}}]}
        o = p.oracle(members, runner=lambda a: (0, json.dumps(batch), ''), token='t', labels_fetch=lambda: [])
        self.assertEqual(o['status'], 'failed')
        self.assertIn('eval_error', o['error'])
        self.assertEqual(o['labels'], {'1': ['L1']})      # positive evidence retained
        for bad in ({'items': []},
                    {'items': [{'item_key': '1', 'state': 'completed', 'result': {'status': 'success', 'labels_applied': []}}]},  # run 2 missing
                    {'items': [{'item_key': '1', 'state': 'failed'}, {'item_key': '2', 'state': 'discarded'}]}):
            o = p.oracle(members, runner=lambda a, b=bad: (0, json.dumps(b), ''), token='t', labels_fetch=lambda: [])
            self.assertEqual(o['status'], 'failed', bad)
            self.assertTrue(o['error'], bad)

    def test_oracle_all_completed_success_is_ok(self):
        members = [reg(1, 't', [run('1')])]
        batch = {'items': [{'item_key': '1', 'state': 'completed', 'result': {'status': 'success', 'labels_applied': []}}]}
        o = p.oracle(members, runner=lambda a: (0, json.dumps(batch), ''), token='t', labels_fetch=lambda: [])
        self.assertEqual((o['status'], o['labels']), ('ok', {}))

    # ---- I6: the subprocess is bounded ----
    def test_oracle_subprocess_timeout_is_failed_not_an_exception(self):
        import subprocess
        from unittest import mock
        with mock.patch.object(p.subprocess, 'run', side_effect=subprocess.TimeoutExpired('reevaluate', 1)) as sr:
            o = p.oracle([reg(1, 't', [run('1')])], token='t', labels_fetch=lambda: [])
        self.assertEqual(o['status'], 'failed')
        self.assertIn('timed out', o['error'])
        self.assertIn('timeout', sr.call_args.kwargs)

    # ---- C5: a malformed or empty release inventory is unavailable, not a clean board ----
    def test_malformed_or_empty_release_inventory_is_partial(self):
        for bad in ({}, [], None, 'nope', [{'no_id': 1}]):
            fetch = p._default_fetch(raw_fetch=lambda release, b=bad: b)
            _, status = p.fetch_inventory(['4.22-main'], fetch=fetch, now=ts('2026-10-12T12:00:00Z'))
            self.assertEqual(status[0]['fetch'], 'partial', bad)
            self.assertIsNone(status[0]['open'], bad)

    def test_view_absent_from_populated_release_is_partial(self):
        raw = [{'id': 1, 'release': '4.22', 'test_name': 't', 'component': 'c', 'variants': [], 'opened': '2026-10-01T00:00:00Z',
                'closed': None, 'views': [{'view_name': '4.22-main', 'active': True, 'opened_at': '2026-10-01T00:00:00Z',
                                            'closed_at': {'Time': '0001-01-01T00:00:00Z', 'Valid': False}}], 'job_runs': []}]
        fetch = p._default_fetch(raw_fetch=lambda release: raw)
        _, status = p.fetch_inventory(['4.22-main', '4.22-nope'], fetch=fetch, now=ts('2026-10-12T12:00:00Z'))
        by = {s['view']: s for s in status}
        self.assertEqual(by['4.22-main']['fetch'], 'complete')
        self.assertEqual(by['4.22-nope']['fetch'], 'partial')
        self.assertIn('no regressions reference view', by['4.22-nope']['error'])

    # ---- closed_7d with the nullable struct shape ----
    def test_closed_7d_counts_struct_closures(self):
        now = ts('2026-10-12T12:00:00Z')
        r = reg(1, 't', [run('1')]); r['closed'] = {'Time': '2026-10-10T00:00:00Z', 'Valid': True}
        self.assertEqual(p.view_status('4.22-main', [r], now)['closed_7d'], 1)
        r['closed'] = {'Time': '0001-01-01T00:00:00Z', 'Valid': False}
        self.assertEqual(p.view_status('4.22-main', [r], now)['closed_7d'], 0)

    # ---- I4: evidence is as-of the observation time ----
    def test_future_runs_do_not_shape_or_cluster(self):
        now = ts('2026-10-07T12:00:00Z')
        future = 'periodic-ci-x-nightly-4.22-e2e-gcp-ovn'
        regs = [reg(1, 't', [run('1', start='2026-10-06T12:00:00Z'), run('9', job=future, start='2026-10-08T12:00:00Z')]),
                reg(2, 'other', [run('9', job=future, start='2026-10-08T12:00:00Z'), run('3', start='2026-10-06T13:00:00Z')])]
        doc = p.weekly(regs, now, None)
        self.assertEqual(len(doc['clusters']), 2)       # the shared run 9 is in the future → no merge
        for c in doc['clusters']:
            self.assertEqual(c['shape']['distinct_jobs'], 1)
            self.assertNotIn(future, c['shape']['top_jobs'])
            self.assertGreaterEqual(c['shape']['days_since_last_failure'], 0)

    # ---- I1: the first HIGH on a lane that only had an un-notified LOW is `new`, not `continuing` ----
    def test_first_high_after_unnotified_low_is_new(self):
        base = 'periodic-ci-openshift-release-main-nightly-4.22-e2e-'
        def regs(offset, opened, started, broad, n=8):
            out = []
            for i in range(n):
                plat = 'gcp' if broad and i % 2 else 'aws'
                suffix = '-runc' if broad and i % 4 < 2 else ''
                r = reg(offset + i, 'same test', [run(str(offset + i), job=base + plat + '-ovn' + suffix, start=started)], opened=opened)
                r['variants'] = ['Platform:' + plat]
                out.append(r)
            return out
        low = regs(0, '2026-10-21T04:00:00Z', '2026-10-21T05:00:00Z', broad=False)
        prev = p.tripwire(low, ts('2026-10-21T06:00:00Z'), 24, None)
        self.assertEqual(prev['triggers'], [])
        high = regs(20, '2026-10-21T10:00:00Z', '2026-10-21T11:00:00Z', broad=True)
        cur = p.tripwire(high, ts('2026-10-21T12:00:00Z'), 24, prev)
        self.assertEqual([(t['level'], t['kind']) for t in cur['triggers']], [('HIGH', 'new')])
        again = p.tripwire(high, ts('2026-10-21T18:00:00Z'), 24, cur)      # same event, next pass
        self.assertEqual([(t['level'], t['kind']) for t in again['triggers']], [('HIGH', 'continuing')])

    # ---- I2: growth of a known weekly HIGH cluster (spec §4 step 6 / §11 "old broad cluster + one new failure") ----
    def test_tripwire_reports_growth_of_known_weekly_high_cluster(self):
        now = ts('2026-10-07T12:00:00Z')
        newcomers = {51109, 51110, 51111, 51112, 51113}          # opened 10-06/07, i.e. after the "weekly run"
        baseline = p.weekly([r for r in self.frozen if r['id'] not in newcomers], now, None)
        high = {c['id']: c for c in baseline['clusters'] if c['blast_radius']['level'] == 'HIGH'}
        self.assertIn('c-6f44f1', high)
        doc = p.tripwire(self.frozen, now, 24, None, baseline=baseline)
        growth = [t for t in doc['triggers'] if t['kind'] == 'growth']
        self.assertTrue(growth, doc['triggers'])
        g = [t for t in growth if t['cluster_id'] == 'c-6f44f1']
        self.assertEqual(len(g), 1, growth)
        self.assertEqual(g[0]['level'], 'HIGH')
        self.assertEqual(sorted(g[0]['new_members']), [51109, 51110, 51111, 51112, 51113])
        # the next pass with the same window content dedups to continuing
        again = p.tripwire(self.frozen, now, 24, doc, baseline=baseline)
        self.assertEqual([t['kind'] for t in again['triggers'] if t['cluster_id'] == 'c-6f44f1'], ['continuing'])
        # an incompatible baseline contributes nothing (and does not raise)
        self.assertEqual([t for t in p.tripwire(self.frozen, now, 24, None, baseline={'schema_version': '0.9'})['triggers']
                          if t['kind'] == 'growth'], [])


class ReviewWave2Test(unittest.TestCase):
    """Review wave 2: N3 oracle strictness, N6 tripwire promotion/continuity, N7 growth association, N8 stable ids."""

    @classmethod
    def setUpClass(cls):
        cls.frozen = load('frozen-2026-10-07.json.gz')

    # ---- N3 ----
    def test_oracle_requires_an_explicit_success_result(self):
        members = [reg(1, 't', [run('1')])]
        for res in ({'error': 'GCS timeout'}, {}, None, {'labels_applied': []}):
            batch = {'items': [{'item_key': '1', 'state': 'completed', 'result': res}]}
            o = p.oracle(members, runner=lambda a, b=batch: (0, json.dumps(b), ''), token='t', labels_fetch=lambda: [])
            self.assertEqual(o['status'], 'failed', res)

    def test_label_missing_from_catalogue_is_unknown_not_empty(self):
        members = [reg(1, 't', [run('1')])]
        batch = {'items': [{'item_key': '1', 'state': 'completed', 'result': {'status': 'success', 'labels_applied': ['L1', 'L2']}}]}
        o = p.oracle(members, runner=lambda a: (0, json.dumps(batch), ''), token='t',
                     labels_fetch=lambda: [{'id': 'L1', 'bugs': []}])
        self.assertEqual(o['status'], 'ok')
        self.assertEqual(o['label_bugs'], {'L1': [], 'L2': None})      # L1 observed with no bugs; L2 unknown

    # ---- N6 ----
    def _burst(self, offset, opened, started, broad, n=8):
        base = 'periodic-ci-openshift-release-main-nightly-4.22-e2e-'
        out = []
        for i in range(n):
            plat = 'gcp' if broad and i % 2 else 'aws'
            suffix = '-runc' if broad and i % 4 < 2 else ''
            r = reg(offset + i, 'same test', [run(str(offset + i), job=base + plat + '-ovn' + suffix, start=started)], opened=opened)
            r['variants'] = ['Platform:' + plat]
            out.append(r)
        return out

    def test_elevated_to_high_promotion_is_new(self):
        # an informational ELEVATED mass-failure trigger is not HIGH notification history
        lane = 'periodic-ci-openshift-release-main-nightly-4.22-e2e-aws-ovn'
        mass = [reg(100 + i, 'same test', [run(str(100 + i), job=lane, start='2026-10-21T05:00:00Z')], opened='2026-10-21T04:00:00Z') for i in range(50)]
        prev = p.tripwire(mass, ts('2026-10-21T06:00:00Z'), 24, None)
        self.assertEqual([t['level'] for t in prev['triggers']], ['ELEVATED'])
        cur = p.tripwire(self._burst(0, '2026-10-21T10:00:00Z', '2026-10-21T11:00:00Z', broad=True), ts('2026-10-21T12:00:00Z'), 24, prev)
        self.assertEqual([(t['level'], t['kind']) for t in cur['triggers']], [('HIGH', 'new')])

    def test_burst_growth_then_unchanged_is_continuing(self):
        now = ts('2026-10-21T12:00:00Z')
        eight = self._burst(0, '2026-10-21T10:00:00Z', '2026-10-21T11:00:00Z', broad=True)
        first = p.tripwire(eight, now, 24, None)
        nine = eight + self._burst(8, '2026-10-21T10:30:00Z', '2026-10-21T11:30:00Z', broad=True, n=1)
        second = p.tripwire(nine, now, 24, first)
        third = p.tripwire(nine, now, 24, second)
        self.assertEqual([t['kind'] for t in first['triggers']], ['new'])
        self.assertEqual([t['kind'] for t in second['triggers']], ['growth'])
        self.assertEqual([t['kind'] for t in third['triggers']], ['continuing'])

    # ---- N7 ----
    def test_growth_on_a_non_dominant_lane_of_a_known_cluster(self):
        old = self._burst(0, '2026-10-20T11:00:00Z', '2026-10-20T12:00:00Z', broad=True)
        weekly = p.weekly(old, ts('2026-10-21T06:00:00Z'), None)
        self.assertEqual(weekly['clusters'][0]['blast_radius']['level'], 'HIGH')
        kid = weekly['clusters'][0]['id']
        # one new member sharing a RUN with an existing member, on the cluster's minority lane
        new = reg(50, 'same test', [run('50', job='periodic-ci-openshift-release-main-nightly-4.22-e2e-gcp-ovn-runc', start='2026-10-21T11:00:00Z'),
                                   run('1', job=old[1]['job_runs'][0]['prowjob_name'], start='2026-10-20T12:00:00Z')],
                  opened='2026-10-21T10:00:00Z')
        new['variants'] = ['Platform:gcp']
        doc = p.tripwire(old + [new], ts('2026-10-21T12:00:00Z'), 24, None, baseline=weekly)
        g = [t for t in doc['triggers'] if t['kind'] == 'growth']
        self.assertEqual(len(g), 1, doc['triggers'])
        self.assertEqual((g[0]['cluster_id'], g[0]['new_members']), (kid, [50]))
        self.assertTrue(doc['known_growth'] and doc['known_growth'][0]['active_cluster']['shape']['regressions'] == 9)

    def test_unrelated_test_on_a_shared_job_name_is_not_growth(self):
        old = self._burst(0, '2026-10-20T11:00:00Z', '2026-10-20T12:00:00Z', broad=True)
        weekly = p.weekly(old, ts('2026-10-21T06:00:00Z'), None)
        new = reg(50, 'an unrelated assertion', [run('50', job=old[0]['job_runs'][0]['prowjob_name'], start='2026-10-21T11:00:00Z')],
                  opened='2026-10-21T10:00:00Z')
        doc = p.tripwire(old + [new], ts('2026-10-21T12:00:00Z'), 24, None, baseline=weekly)
        self.assertEqual([t for t in doc['triggers'] if t['kind'] == 'growth'], [])

    # ---- N8 ----
    def test_colliding_ids_are_stable_when_a_neighbour_disappears(self):
        now = ts('2026-10-07T12:00:00Z')
        a, b, c3 = (reg(1, '[a] same test', [run('1')]), reg(2, '[b] same test', [run('2')]), reg(3, '[c] same test', [run('3')]))
        base = p.weekly([a, b], now, None)
        base['source_run'] = {'run_id': 'r0'}
        for cl in base['clusters']:
            cl['lineage']['cycles_seen'] = 20 if 1 in cl['members']['regression_ids'] else 1
            cl['lineage']['first_seen_run'] = 'hist-%d' % cl['members']['regression_ids'][0]
        nxt = p.weekly([b, c3], now, base)
        by_member = {cl['members']['regression_ids'][0]: cl for cl in nxt['clusters']}
        self.assertEqual(by_member[2]['id'], [cl for cl in base['clusters'] if 2 in cl['members']['regression_ids']][0]['id'])
        self.assertEqual(by_member[2]['lineage']['cycles_seen'], 2)          # b's own history continues
        self.assertEqual(by_member[3]['lineage']['cycles_seen'], 1)          # c is new, inherits nothing
        self.assertEqual(by_member[3]['lineage']['first_seen_run'], 'local')

    def test_lineage_follows_a_majority_successor_when_the_id_changes(self):
        now = ts('2026-10-07T12:00:00Z')
        a, b = reg(1, '[a] same test', [run('1')]), reg(2, '[b] same test', [run('2')])
        base = p.weekly([a, b], now, None); base['source_run'] = {'run_id': 'r0'}
        for cl in base['clusters']:
            cl['lineage']['cycles_seen'] = 3; cl['lineage']['first_seen_run'] = 'hist-%d' % cl['members']['regression_ids'][0]
        nxt = p.weekly([b], now, base)                      # b alone: no collision any more → bare id
        cl = nxt['clusters'][0]
        self.assertEqual(cl['lineage']['cycles_seen'], 4)
        self.assertEqual(cl['lineage']['first_seen_run'], 'hist-2')


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
