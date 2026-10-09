#!/usr/bin/env python3
"""Tests for the bulk-triage pre-pass clustering and shape layer."""
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import clustering as c  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def run(rid, job='periodic-ci-x-nightly-4.22-e2e-aws-ovn', start='2026-10-06T12:00:00Z', tf=None):
    return {'prowjob_name': job, 'prowjob_run_id': rid, 'start_time': start, 'test_failures': tf}


def reg(rid, test='t', release='4.22', runs=(), variants=('Platform:aws', 'Architecture:amd64'),
        opened='2026-10-01T00:00:00Z'):
    return {'id': rid, 'release': release, 'test_name': test, 'component': 'comp', 'variants': list(variants),
            'opened': opened, 'closed': None, 'last_failure': None, 'job_runs': list(runs), 'duty_views': ['4.22-main']}


class ClusterTest(unittest.TestCase):
    def test_shared_runs_merge(self):
        a = reg(1, 'a', runs=[run('1'), run('2')])
        b = reg(2, 'b', runs=[run('1'), run('2')])
        self.assertEqual(len(c.cluster([a, b])), 1)

    def test_same_test_same_release_merge(self):
        self.assertEqual(len(c.cluster([reg(1, 'same'), reg(2, 'same')])), 1)

    def test_same_test_different_release_not_merged(self):
        self.assertEqual(len(c.cluster([reg(1, 'same', '4.22'), reg(2, 'same', '4.21')])), 2)

    def test_deterministic_order(self):
        regs = [reg(i, 't%d' % i) for i in (5, 3, 9, 1)]
        self.assertEqual([[m['id'] for m in g] for g in c.cluster(regs)],
                         [[m['id'] for m in g] for g in c.cluster(list(reversed(regs)))])


class LaneTest(unittest.TestCase):
    def test_lane_family_normalises_release_platform_arch(self):
        a = c.lane_family('periodic-ci-openshift-release-main-nightly-4.20-e2e-gcp-ovn-runc')
        b = c.lane_family('periodic-ci-openshift-release-main-nightly-4.21-e2e-aws-ovn-runc-arm64')
        self.assertEqual(a, b)

    def test_test_family(self):
        self.assertEqual(c.test_family('[sig-a] Foo   Bar [Late]'), 'foo bar')

    def test_cluster_id(self):
        self.assertRegex(c.cluster_id('4.22', 'a', 'b'), r'^c-[0-9a-f]{6}$')

    def test_parse_ts_handles_long_fraction(self):
        t = c.parse_ts('2025-09-24T12:10:16.34684+00:00')
        self.assertEqual((t.year, t.second, t.microsecond), (2025, 16, 346840))
        self.assertIsNotNone(c.parse_ts('2025-09-24T12:10:16Z').tzinfo)
        self.assertEqual(c.parse_ts('2025-09-24T12:10:16.1234567+00:00').microsecond, 123456)


class ShapeTest(unittest.TestCase):
    def test_platforms_from_failing_own_runs_only(self):
        a = reg(1, runs=[run('1')])
        b = reg(2, runs=[], variants=('Platform:metal', 'Architecture:arm64'))
        s = c.shape([a, b], NOW)
        self.assertEqual(s['platforms'], ['aws'])
        self.assertEqual(s['arches'], ['amd64'])

    def test_mass_failure_marker_median_ge_20(self):
        s = c.shape([reg(1, runs=[run('1', tf=25), run('2', tf=30), run('3', tf=5)])], NOW)
        self.assertEqual(s['median_test_failures_per_run'], 25)
        self.assertTrue(s['mass_failure_marker'])
        s = c.shape([reg(1, runs=[run('1', tf=1), run('2', tf=None)])], NOW)
        self.assertFalse(s['mass_failure_marker'])

    def test_regression_without_runs_is_low_with_null_recency(self):
        s = c.shape([reg(1, runs=[])], NOW)
        self.assertEqual(s['distinct_runs'], 0)
        self.assertIsNone(s['days_since_last_failure'])
        self.assertIsNone(s['first_failure'])
        self.assertIsNone(s['last_failure'])
        self.assertEqual(s['days_open'], 6)

    def test_shape_keys_and_recency(self):
        up = 'periodic-ci-x-nightly-4.22-upgrade-from-stable-4.21-e2e-aws'
        s = c.shape([reg(1, 'install should succeed', runs=[run('1', up, '2026-10-05T12:00:00Z'),
                                                              run('2', up, '2026-10-01T12:00:00Z')])], NOW)
        self.assertEqual(s['days_since_last_failure'], 2)
        self.assertEqual(s['failing_runs_7d'], 2)
        self.assertTrue(s['upgrade_lane'] and s['minor_upgrade_lane'] and s['install_wrapper'])
        self.assertIsNone(s['growth_since_baseline'])
        self.assertEqual(s['top_jobs'], [up])

    def test_fingerprint(self):
        f = c.fingerprint([reg(1, 'B x', runs=[run('1')]), reg(2, '[s] A x', runs=[run('2')])])
        self.assertEqual(f['release'], '4.22')
        self.assertEqual(f['test_family'], 'a x')
        self.assertEqual(f['labels'], [])
        self.assertEqual(f['lane_family'], c.lane_family('periodic-ci-x-nightly-4.22-e2e-aws-ovn'))


if __name__ == '__main__':
    unittest.main()
