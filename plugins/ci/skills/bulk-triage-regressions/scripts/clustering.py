#!/usr/bin/env python3
"""Deterministic clustering and shape layer for the bulk-triage pre-pass.

Stdlib only. Input records are Component Readiness regressions as returned by
the list-regressions script.
"""
import hashlib
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone


def parse_ts(s):
    s = s.replace('Z', '+00:00')
    s = re.sub(r'\.(\d+)', lambda m: '.' + m.group(1)[:6].ljust(6, '0'), s)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def lane_family(job):
    """Collapse a prow job name to its lane family: strip the periodic prefix and run-specific noise."""
    j = re.sub(r'^periodic-ci-', '', job)
    j = re.sub(r'-[45]\.\d+(?=-|$)', '-REL', j)
    j = re.sub(r'-(amd64|arm64|ppc64le|s390x|multi)(?=-|$)', '', j)
    j = re.sub(r'-(aws|azure|gcp|vsphere|metal|ibmcloud|openstack|nutanix|alibaba|powervs)(?=-|$)', '-PLATFORM', j)
    j = re.sub(r'-(ipv4|ipv6|dualstack)(?=-|$)', '', j)
    return j.strip('-')


def test_family(test_name):
    t = re.sub(r'\[[^\]]*\]', ' ', test_name)
    return re.sub(r'\s+', ' ', t).strip().lower()


# not a test case; keep pytest from collecting it
test_family.__test__ = False


def variant(reg, key):
    for v in reg.get('variants') or []:
        if v.startswith(key + ':'):
            return v.split(':', 1)[1]
    return None


class DSU:
    def __init__(self, items):
        self.p = {i: i for i in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            # keep the smaller id as root so output does not depend on call order
            if b < a:
                a, b = b, a
            self.p[b] = a


def cluster(regs, min_shared_runs=2, min_jaccard=0.5):
    regs = sorted(regs, key=lambda r: r['id'])
    byid = {r['id']: r for r in regs}
    runs = {r['id']: {jr['prowjob_run_id'] for jr in r['job_runs']} for r in regs}
    dsu = DSU(byid)
    # signal 1: shared failed job runs (strong) — index runs to regressions
    run_index = defaultdict(set)
    for rid, rs in runs.items():
        for run in rs:
            run_index[run].add(rid)
    seen = set()
    for run in sorted(run_index):
        rids = sorted(run_index[run])
        for i, a in enumerate(rids):
            for b in rids[i + 1:]:
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                shared = len(runs[a] & runs[b])
                jacc = shared / max(1, len(runs[a] | runs[b]))
                if shared >= min_shared_runs or jacc >= min_jaccard:
                    dsu.union(a, b)
    # signal 2: identical test name within the same release (same test, different variants)
    by_test = defaultdict(list)
    for r in regs:
        by_test[(r['release'], r['test_name'])].append(r['id'])
    for ids in by_test.values():
        for b in ids[1:]:
            dsu.union(ids[0], b)
    groups = defaultdict(list)
    for rid in byid:
        groups[dsu.find(rid)].append(byid[rid])
    return [groups[k] for k in sorted(groups)]


INSTALL_WRAPPER = re.compile(
    r'install should succeed|cluster bootstrap|cluster creation|cluster readiness'
    r'|machines should be in Running|mass test failures', re.I)


def shape(members, now):
    jobs = Counter()
    run_tf = {}   # run id -> test_failures (a run shared by several regressions counts once)
    all_runs = set()
    recent_runs = set()
    first = None
    last = None
    opened = None
    reg_opened = None
    platforms = set()
    arches = set()
    for r in members:
        for jr in r['job_runs']:
            jobs[jr['prowjob_name']] += 1
            all_runs.add(jr['prowjob_run_id'])
            if jr.get('test_failures') is not None:
                run_tf[jr['prowjob_run_id']] = jr['test_failures']
            st = parse_ts(jr['start_time'])
            first = st if first is None or st < first else first
            last = st if last is None or st > last else last
            if 0 <= (now - st).total_seconds() <= 7 * 86400:
                recent_runs.add(jr['prowjob_run_id'])
        if r['job_runs']:
            platforms.add(variant(r, 'Platform'))
            arches.add(variant(r, 'Architecture'))
        o = parse_ts(r['opened'])
        opened = o if opened is None or o < opened else opened
        ro = parse_ts(r.get('regression_opened') or r['opened'])
        reg_opened = ro if reg_opened is None or ro < reg_opened else reg_opened
    platforms.discard(None)
    arches.discard(None)
    tf_med = statistics.median(run_tf.values()) if run_tf else 0
    tf_med = int(tf_med) if float(tf_med).is_integer() else tf_med
    return {
        'regressions': len(members),
        'distinct_jobs': len(jobs),
        'lane_families': len({lane_family(j) for j in jobs}),
        'platforms': sorted(platforms),
        'arches': sorted(arches),
        'upgrade_lane': any('upgrade' in j for j in jobs),
        'minor_upgrade_lane': any('upgrade-from-stable' in j for j in jobs),
        'install_wrapper': any(INSTALL_WRAPPER.search(r['test_name']) for r in members),
        'mass_failure_marker': tf_med >= 20,
        'median_test_failures_per_run': tf_med,
        'distinct_runs': len(all_runs),
        'failing_runs_7d': len(recent_runs),
        'first_failure': first.isoformat() if first else None,
        'last_failure': last.isoformat() if last else None,
        # `opened` is the view-level (re)activation date (the rules' frozen input); `regression_opened` is Sippy's
        # regression-level opened, which a brief recovery does not reset — informational, not a rule input.
        'days_open': (now - opened).days if opened else None,
        'regression_days_open': (now - reg_opened).days if reg_opened else None,
        'days_since_last_failure': (now - last).days if last else None,
        'growth_since_baseline': None,
        'components': sorted({r['component'] for r in members}),
        'views': sorted({v for r in members for v in r.get('duty_views', [])}),
        'top_jobs': [j for j, _ in sorted(jobs.items(), key=lambda kv: (-kv[1], kv[0]))[:3]],
    }


def cluster_id(release, tf, lf):
    return 'c-' + hashlib.sha1(f'{release}|{tf}|{lf}'.encode()).hexdigest()[:6]


def fingerprint(members):
    fams = Counter(lane_family(jr['prowjob_name']) for r in members for jr in r['job_runs'])
    lf = sorted(fams.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if fams else ''
    return {
        'release': min(r['release'] for r in members),
        'test_family': min(test_family(r['test_name']) for r in members),
        'lane_family': lf,
        'labels': [],
    }
