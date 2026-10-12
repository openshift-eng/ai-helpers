#!/usr/bin/env python3
"""Tests for the bulk-triage pre-pass blast-radius classifier."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blast_radius as b  # noqa: E402


def shape(**kw):
    s = {'regressions': 1, 'distinct_jobs': 1, 'lane_families': 1, 'platforms': ['aws'], 'arches': ['amd64'],
         'upgrade_lane': False, 'minor_upgrade_lane': False, 'install_wrapper': False,
         'mass_failure_marker': False, 'median_test_failures_per_run': None, 'distinct_runs': 1,
         'failing_runs_7d': 0, 'first_failure': None, 'last_failure': None, 'days_open': 0,
         'days_since_last_failure': 0, 'growth_since_baseline': None, 'components': [], 'views': [],
         'top_jobs': []}
    s.update(kw)
    return s


class ClassifyTest(unittest.TestCase):
    def test_multiarch_shape_is_high(self):
        level, _, reasons = b.classify(shape(
            regressions=230, distinct_jobs=11, lane_families=6, platforms=['aws', 'azure', 'gcp'],
            minor_upgrade_lane=True, upgrade_lane=True, days_open=19, days_since_last_failure=0,
            failing_runs_7d=40, distinct_runs=100))
        self.assertEqual(level, 'HIGH')
        self.assertGreaterEqual(len(reasons), 3)

    def _mass(self, days_open):
        return shape(regressions=65, distinct_jobs=1, lane_families=1, mass_failure_marker=True,
                     median_test_failures_per_run=331, days_open=days_open, days_since_last_failure=0,
                     failing_runs_7d=9, distinct_runs=9)

    def test_single_job_mass_failure_caps_elevated(self):
        level, _, reasons = b.classify(self._mass(8))
        self.assertEqual(level, 'ELEVATED')
        self.assertIn('single-job mass failure persisting 8d', reasons)
        self.assertIn('mass-failure marker (median 331 failures/run)', reasons)

    def test_dead_lane_over_14d_is_high(self):
        self.assertEqual(b.classify(self._mass(15))[0], 'HIGH')

    def test_minor_upgrade_needs_6_regs_3_jobs_2_platforms(self):
        kw = dict(minor_upgrade_lane=True, distinct_jobs=3, platforms=['aws', 'gcp'])
        self.assertNotEqual(b.classify(shape(regressions=5, **kw))[0], 'HIGH')
        self.assertEqual(b.classify(shape(regressions=6, **kw))[0], 'HIGH')

    def test_twelve_from_one_job_is_elevated_by_size(self):
        level, _, _ = b.classify(shape(regressions=12, distinct_jobs=1))
        self.assertEqual(level, 'ELEVATED')

    def test_default_low(self):
        level, _, _ = b.classify(shape(regressions=3, distinct_jobs=2, days_open=9))
        self.assertEqual(level, 'LOW')

    def test_score_monotonic_in_jobs(self):
        self.assertLess(b.score(shape(distinct_jobs=2)), b.score(shape(distinct_jobs=5)))

    def test_zero_runs_shape_is_low(self):
        s = shape(regressions=1, distinct_jobs=0, distinct_runs=0, days_open=None,
                  days_since_last_failure=None)
        self.assertEqual(b.classify(s)[0], 'LOW')


if __name__ == '__main__':
    unittest.main()
