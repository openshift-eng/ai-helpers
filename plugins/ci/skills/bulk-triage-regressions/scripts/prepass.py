#!/usr/bin/env python3
"""Deterministic pre-pass CLI for bulk triage: inventory, clustering, blast radius, baseline diff, oracle, tripwire.

Stdlib only. Orchestration and I/O only; clustering and classification live in
clustering.py and blast_radius.py.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import urllib.request
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blast_radius  # noqa: E402
import clustering  # noqa: E402

SCHEMA_VERSION = '1.0'
POLICY = 'post-ga'
LEVEL_ORDER = {'HIGH': 0, 'ELEVATED': 1, 'LOW': 2}
REPO_ROOT = Path(__file__).resolve().parents[5]
LIST_REGRESSIONS = REPO_ROOT / 'plugins/teams/skills/list-regressions/list_regressions.py'
LABELS_URL = 'https://sippy.dptools.openshift.org/api/jobs/labels'
REEVALUATE = REPO_ROOT / 'plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py'


def iso(dt):
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def is_open(reg):
    closed = reg.get('closed')
    if isinstance(closed, dict):
        return not closed.get('Valid')
    return closed is None


def slim(raw, view):
    return {
        'id': raw['id'], 'release': raw['release'], 'duty_views': [view], 'test_name': raw['test_name'],
        'component': raw['component'], 'capability': raw.get('capability'), 'variants': raw.get('variants') or [],
        'opened': raw['opened'], 'regression_opened': raw.get('regression_opened') or raw['opened'],
        'closed': raw.get('closed'), 'last_failure': raw.get('last_failure'),
        'max_failures': raw.get('max_failures'),
        'triages': [t['id'] if isinstance(t, dict) else t for t in (raw.get('triages') or [])],
        'job_runs': [{'prowjob_name': j['prowjob_name'], 'prowjob_run_id': j['prowjob_run_id'],
                      'start_time': j['start_time'], 'test_failures': j.get('test_failures')}
                     for j in (raw.get('job_runs') or [])],
    }


def _default_fetch(raw_fetch=None):
    spec = importlib.util.spec_from_file_location('list_regressions', LIST_REGRESSIONS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    raw_fetch = raw_fetch or mod.fetch_regressions
    cache = {}

    def fetch(view):
        release = mod.extract_release_from_view(view)
        if release not in cache:
            cache[release] = raw_fetch(release)
            # filter_by_view overwrites `opened` in place with the view's (re)activation date; keep the
            # regression-level date first so the shape can report the real age too.
            for r in cache[release]:
                r.setdefault('regression_opened', r.get('opened'))
        return mod.filter_by_view(cache[release], view)
    return fetch


def view_status(view, regs, now):
    week = now - timedelta(days=7)
    opened = [clustering.parse_ts(r['opened']) for r in regs]
    open_regs = [r for r in regs if is_open(r)]
    return {
        'view': view, 'fetch': 'complete', 'error': None,
        'open': len(open_regs),
        'open_untriaged': sum(1 for r in open_regs if not r.get('triages')),
        'opened_7d': sum(1 for o in opened if week <= o <= now),
        'closed_7d': sum(1 for r in regs if not is_open(r) and isinstance(r.get('closed'), str)
                         and week <= clustering.parse_ts(r['closed']) <= now),
    }


def fetch_inventory(views, fetch=None, now=None):
    """Return (regressions, view_status); a regression in several views is one record with all duty_views."""
    now = now or datetime.now(timezone.utc)
    fetch = fetch or _default_fetch()
    byid, status = {}, []
    for view in views:
        try:
            recs = [slim(r, view) for r in fetch(view)]
        except Exception as e:  # noqa: BLE001 - any failure is reported as a partial view, never as zero
            status.append({'view': view, 'fetch': 'partial', 'error': str(e), 'open': None,
                           'open_untriaged': None, 'opened_7d': None, 'closed_7d': None})
            continue
        status.append(view_status(view, recs, now))
        for r in recs:
            if r['id'] in byid:
                byid[r['id']]['duty_views'].append(view)
            else:
                byid[r['id']] = r
    return list(byid.values()), status


def _statuses_from_records(regs, now):
    views = sorted({v for r in regs for v in r.get('duty_views', [])})
    return [view_status(v, [r for r in regs if v in r.get('duty_views', [])], now) for v in views]


def fetch_labels():
    req = urllib.request.Request(LABELS_URL, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def once(fn):
    """Memoize a no-arg callable, including its exception, so it runs at most once."""
    box = []

    def wrapper():
        if not box:
            try:
                box.append((True, fn()))
            except Exception as e:  # noqa: BLE001
                box.append((False, e))
        ok, val = box[0]
        if ok:
            return val
        raise val
    return wrapper


def _last_json_object(text):
    """Return the last top-level JSON object decodable from text (tolerates leading/trailing noise)."""
    dec = json.JSONDecoder()
    text = text or ''
    last = None
    i = 0
    while i < len(text):
        j = text.find('{', i)
        if j < 0:
            break
        try:
            obj, end = dec.raw_decode(text, j)
        except ValueError:
            i = j + 1
            continue
        if isinstance(obj, dict):
            last = obj
        i = end  # skip the whole object so nested dicts are not mistaken for top-level ones
    return last


def oracle(cluster, runner=None, token=None, labels_fetch=None):
    """Probe up to 5 newest representative runs with a dry-run symptom reevaluation."""
    out = {'status': 'skipped', 'runs_probed': 0, 'labels': {}, 'label_bugs': {}}
    if token is None and runner is None:
        return out
    runs = {}
    for r in cluster:
        for jr in r['job_runs']:
            runs[jr['prowjob_run_id']] = jr['start_time']
    ids = [i for i, _ in sorted(runs.items(), key=lambda kv: (clustering.parse_ts(kv[1]), kv[0]), reverse=True)][:5]
    if not ids:
        return out
    argv = [sys.executable, str(REEVALUATE), '--dry-run', '--format', 'json'] + ids
    if runner is None:
        def runner(argv):
            p = subprocess.run(argv, capture_output=True, text=True, env=dict(os.environ, SIPPY_TOKEN=token))
            return p.returncode, p.stdout, p.stderr
    out['runs_probed'] = len(ids)
    result = runner(argv)
    # Runners may return (code, text) or (code, stdout, stderr); in --format json mode the CLI prints its
    # submission notice to stderr and the batch JSON to stdout, so never parse the two glued together.
    if len(result) == 3:
        code, stdout, stderr = result
    else:
        code, stdout = result
        stderr = ''
    diagnostic = (stderr or '').strip() or (stdout or '').strip()
    if code != 0:
        text = (stdout or '') + (stderr or '')
        out['status'] = 'unauthorized' if ('401' in text or '403' in text) else 'failed'
        out['error'] = diagnostic[:300]
        return out
    batch = _last_json_object(stdout)
    if not isinstance(batch, dict) or not isinstance(batch.get('items'), list):
        out['status'] = 'failed'
        out['error'] = ('no batch JSON in reevaluate output: ' + (stdout or '').strip())[:300]
        return out
    try:
        for item in batch['items']:
            res = item.get('result') or {}
            found = list(res.get('labels_applied') or [])
            if found:
                out['labels'][str(item['item_key'])] = found
    except (KeyError, TypeError, AttributeError) as e:
        out['status'] = 'failed'
        out['labels'] = {}
        out['error'] = ('unexpected batch item shape: %s' % e)[:300]
        return out
    out['status'] = 'ok'
    wanted = {lab for ls in out['labels'].values() for lab in ls}
    if wanted:
        try:
            catalogue = (labels_fetch or fetch_labels)()
            out['label_bugs'] = {l['id']: list(l.get('bugs') or []) for l in catalogue if l.get('id') in wanted}
        except Exception as e:  # noqa: BLE001 - surfaced, never silently empty
            out['label_bugs'] = {}
            out['label_bugs_error'] = str(e)
    return out


def diff_baseline(clusters, baseline, run_id='local'):
    """Mutate clusters with lineage / new_since_baseline / growth; returns the baseline_run block."""
    ok = (isinstance(baseline, dict) and baseline.get('schema_version') == SCHEMA_VERSION
          and (baseline.get('policy') or {}).get('name') == POLICY)
    block = {'run_id': None, 'manifest_url': None, 'schema_version': None, 'compatible': None}
    if isinstance(baseline, dict):
        block.update(run_id=(baseline.get('source_run') or {}).get('run_id'),
                     manifest_url=baseline.get('manifest_url'),
                     schema_version=baseline.get('schema_version'), compatible=ok)
    for c in clusters:
        if not ok:
            c['lineage'].update(first_seen_run=None, cycles_seen=None, supersedes=None)
            c['members']['new_since_baseline'] = None
            c['shape']['growth_since_baseline'] = None
    if not ok:
        return block
    base = {b['id']: b for b in baseline['clusters']}
    owner = {rid: b['id'] for b in baseline['clusters'] for rid in b['members']['regression_ids']}
    for c in clusters:
        ids = c['members']['regression_ids']
        counts = {}
        for rid in ids:
            if rid in owner:
                counts[owner[rid]] = counts.get(owner[rid], 0) + 1
        sizes = {b['id']: len(b['members']['regression_ids']) for b in baseline['clusters']}
        c['lineage']['supersedes'] = sorted(b for b, n in counts.items() if n * 2 >= sizes[b])
        prev = base.get(c['id'])
        if prev:
            c['lineage']['first_seen_run'] = (prev.get('lineage') or {}).get('first_seen_run') or block['run_id']
            c['lineage']['cycles_seen'] = ((prev.get('lineage') or {}).get('cycles_seen') or 1) + 1
        else:
            c['lineage']['first_seen_run'] = run_id
            c['lineage']['cycles_seen'] = 1
        new = [rid for rid in ids if rid not in owner]
        c['members']['new_since_baseline'] = new
        c['shape']['growth_since_baseline'] = len(new)
    return block


def build_clusters(regs, now):
    out = []
    for members in clustering.cluster(regs):
        s = clustering.shape(members, now)
        fp = clustering.fingerprint(members)
        level, score, reasons = blast_radius.classify(s)
        out.append({
            'id': clustering.cluster_id(fp['release'], fp['test_family'], fp['lane_family']),
            'lineage': {'first_seen_run': None, 'cycles_seen': None, 'supersedes': []},
            'fingerprint': fp,
            'members': {'regression_ids': sorted(r['id'] for r in members), 'new_since_baseline': None,
                        'views': s['views'], 'components': s['components']},
            'shape': s,
            'blast_radius': {'level': level, 'score': score, 'reasons': reasons},
            '_members': members,
        })
    out.sort(key=lambda c: (LEVEL_ORDER[c['blast_radius']['level']], -c['blast_radius']['score'], c['id']))
    return out


def _probe_summary(results):
    statuses = [r['status'] for r in results]
    for s in ('unauthorized', 'failed'):
        if s in statuses:
            status = s
            break
    else:
        status = 'ok' if 'ok' in statuses else 'skipped'
    return {'status': status, 'runs_probed': sum(r['runs_probed'] for r in results)}


def weekly(regs, now, baseline, oracle=None, run_id='local', view_status=None):
    """Build the prepass.json document. `oracle` is a callable members -> oracle dict (None = skipped)."""
    open_regs = [r for r in regs if is_open(r) and not r.get('triages')]
    clusters = build_clusters(open_regs, now)
    baseline_run = diff_baseline(clusters, baseline, run_id)
    results = []
    for c in clusters:
        c['oracle'] = oracle(c['_members']) if oracle else {'status': 'skipped', 'runs_probed': 0,
                                                            'labels': {}, 'label_bugs': {}}
        results.append(c['oracle'])
    watch = [{'regression_id': r['id'], 'view': (r.get('duty_views') or [None])[0], 'cluster_id': c['id'],
              'reason': 'LOW & new (<7d)'}
             for c in clusters if c['blast_radius']['level'] == 'LOW'
             and c['shape']['days_open'] is not None and c['shape']['days_open'] < 7
             for r in sorted(c['_members'], key=lambda r: r['id'])]
    for c in clusters:
        del c['_members']
    status = view_status if view_status is not None else _statuses_from_records(regs, now)
    return {
        'schema_version': SCHEMA_VERSION, 'mode': 'weekly', 'policy': {'name': POLICY},
        'source_run': {'run_id': run_id},
        'observation': {'time': iso(now), 'views': status, 'symptom_probe': _probe_summary(results)},
        'baseline_run': baseline_run,
        'clusters': clusters,
        'watch_list_candidates': watch,
    }


def tripwire(regs, now, window_hours, previous_status, view_status=None, run_id='local'):
    start = now - timedelta(hours=window_hours)
    window = [r for r in regs if start <= clustering.parse_ts(r['opened']) < now]
    clusters = build_clusters(window, now)
    prev, prev_fp = {}, {}
    for c in (previous_status or {}).get('clusters', []):
        n = len(c['members']['regression_ids'])
        prev[c['id']] = n
        fp = c.get('fingerprint') or {}
        # a rolling window's test_family is unstable, so a same-release same-lane cluster is the same event
        k = (fp.get('release'), fp.get('lane_family'))
        prev_fp[k] = max(n, prev_fp.get(k, 0))
    triggers = []
    for c in clusters:
        level, s = c['blast_radius']['level'], c['shape']
        if level == 'HIGH' or (level == 'ELEVATED' and s['regressions'] >= 50 and s['distinct_jobs'] <= 3):
            fpk = (c['fingerprint']['release'], c['fingerprint']['lane_family'])
            known = prev.get(c['id'], prev_fp.get(fpk))
            if known is None:
                kind = 'new'
            elif known < s['regressions']:
                kind = 'growth'
            else:
                kind = 'continuing'
            triggers.append({'cluster_id': c['id'], 'kind': kind, 'level': level,
                             'reasons': c['blast_radius']['reasons']})
        del c['_members']
    status = view_status if view_status is not None else _statuses_from_records(window, now)
    return {
        'schema_version': SCHEMA_VERSION, 'mode': 'tripwire', 'policy': {'name': 'post-ga'},
        'source_run': {'run_id': run_id},
        'observation': {'time': iso(now), 'views': status, 'window_hours': window_hours},
        'clusters': clusters,
        'triggers': triggers,
        'previous_status_run': ((previous_status or {}).get('observation') or {}).get('time'),
    }


def _load_optional(path):
    if not path or path == 'none':
        return None
    with open(path) as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--views', nargs='+', required=True)
    ap.add_argument('--now')
    ap.add_argument('--baseline', default='none')
    ap.add_argument('--no-oracle', action='store_true')
    ap.add_argument('--token-env', default='DPCR_TOKEN')
    ap.add_argument('--inventory')
    ap.add_argument('--tripwire', action='store_true')
    ap.add_argument('--window-hours', type=int, default=24)
    ap.add_argument('--previous-status', default='none')
    ap.add_argument('--run-id', default='local')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    now = clustering.parse_ts(args.now) if args.now else datetime.now(timezone.utc)

    if args.inventory:
        with open(args.inventory) as f:
            regs = json.load(f)
        regs = [dict(r, duty_views=[v for v in r.get('duty_views', []) if v in args.views]) for r in regs]
        regs = [r for r in regs if r['duty_views']]
        status = [s for s in _statuses_from_records(regs, now)]
        for v in args.views:
            if v not in {s['view'] for s in status}:
                status.append(view_status(v, [], now))
    else:
        regs, status = fetch_inventory(args.views, now=now)

    if args.tripwire:
        doc = tripwire(regs, now, args.window_hours, _load_optional(args.previous_status), status, args.run_id)
    else:
        runner_oracle = None
        if not args.no_oracle:
            token = os.environ.get(args.token_env)
            catalogue = once(fetch_labels)
            runner_oracle = (lambda members: oracle(members, token=token, labels_fetch=catalogue))
        doc = weekly(regs, now, _load_optional(args.baseline), runner_oracle, args.run_id, status)
    with open(args.out, 'w') as f:
        json.dump(doc, f, indent=2, sort_keys=False)
        f.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
