#!/usr/bin/env python3
"""Blast-radius classifier for the bulk-triage pre-pass.

Stdlib only. Consumes the shape dict from clustering.shape(). The rules and
thresholds are frozen shadow hypotheses; do not tune them here.
"""

THRESHOLDS = {
    'persist_min_days_open': 7,
    'persist_max_days_since_last': 2,
    'persist_min_failing_runs_7d': 3,
    'persist_min_regressions': 8,
    'persist_high_min_jobs': 2,
    'persist_high_min_days_open': 14,
    'high_broad_min_regressions': 8,
    'high_broad_min_jobs': 4,
    'high_broad_min_lane_families': 2,
    'high_broad_min_spread': 2,
    'high_minor_min_platforms': 2,
    'high_minor_min_regressions': 6,
    'high_minor_min_jobs': 3,
    'elevated_min_regressions': 12,
    'elevated_min_jobs': 3,
    'elevated_install_min_platforms': 2,
    'elevated_min_runs': 30,
    'elevated_min_days_open': 14,
    'score_regressions_cap': 50,
    'score_jobs_cap': 10,
    'score_lane_families_cap': 5,
}
T = THRESHOLDS


def _persisting(s):
    d, last = s['days_open'], s['days_since_last_failure']
    return (d is not None and d > T['persist_min_days_open']
            and last is not None and last <= T['persist_max_days_since_last']
            and s['failing_runs_7d'] >= T['persist_min_failing_runs_7d']
            and s['regressions'] >= T['persist_min_regressions'])


def score(s):
    return (0.3 * min(1, s['regressions'] / T['score_regressions_cap'])
            + 0.3 * min(1, s['distinct_jobs'] / T['score_jobs_cap'])
            + 0.2 * min(1, s['lane_families'] / T['score_lane_families_cap'])
            + 0.2 * (1 if _persisting(s) else 0))


def classify(s):
    """Return (level, score, reasons) for a cluster shape."""
    reasons = []
    regs, jobs = s['regressions'], s['distinct_jobs']
    n_plat, n_arch = len(s['platforms']), len(s['arches'])
    spread = max(n_plat, n_arch) >= T['high_broad_min_spread']
    persisting = _persisting(s)
    days_open = s['days_open']
    level = 'LOW'

    broad = (regs >= T['high_broad_min_regressions'] and jobs >= T['high_broad_min_jobs']
             and s['lane_families'] >= T['high_broad_min_lane_families'] and spread)
    minor = (s['minor_upgrade_lane'] and n_plat >= T['high_minor_min_platforms']
             and regs >= T['high_minor_min_regressions'] and jobs >= T['high_minor_min_jobs'])
    persist_high = persisting and (jobs >= T['persist_high_min_jobs']
                                   or days_open > T['persist_high_min_days_open'])
    if broad:
        level = 'HIGH'
        reasons.append('%d regressions across %d jobs and %d lane families with platform/arch spread'
                       % (regs, jobs, s['lane_families']))
    if minor:
        level = 'HIGH'
        reasons.append('minor-upgrade lane: %d regressions, %d jobs, %d platforms' % (regs, jobs, n_plat))
    if persist_high:
        level = 'HIGH'
        reasons.append('persisting %sd, last failure %sd ago, %d failing runs in 7d'
                       % (days_open, s['days_since_last_failure'], s['failing_runs_7d']))

    if level == 'LOW':
        if regs >= T['elevated_min_regressions']:
            level = 'ELEVATED'
            reasons.append('%d regressions' % regs)
        if jobs >= T['elevated_min_jobs']:
            level = 'ELEVATED'
            reasons.append('%d distinct jobs' % jobs)
        if s['install_wrapper'] and n_plat >= T['elevated_install_min_platforms']:
            level = 'ELEVATED'
            reasons.append('install failures on %d platforms' % n_plat)
        if (s['distinct_runs'] >= T['elevated_min_runs'] and days_open is not None
                and days_open >= T['elevated_min_days_open']):
            level = 'ELEVATED'
            reasons.append('%d failing runs over %dd' % (s['distinct_runs'], days_open))
        if persisting:
            level = 'ELEVATED'
            reasons.append('single-job mass failure persisting %sd' % days_open)

    if s['mass_failure_marker']:
        reasons.append('mass-failure marker (median %s failures/run)' % s['median_test_failures_per_run'])
    return level, score(s), reasons
