#!/usr/bin/env python3
"""One-off generator for the pre-pass backtest fixtures (kept for provenance). See fixtures/README.md."""
import gzip
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN_SRC = '/root/OPNET-595-BGP/tmp-opencode/bulk-existing-triage-4.16-4.22-2026-10-07/inventory.json'
LIVE_DIR = '/root/OPNET-595-BGP/tmp-opencode/chaibot-design'
RELEASES = ['4.16', '4.17', '4.18', '4.19', '4.20', '4.21', '4.22']
REPLAY_DAYS = ['2026-08-30', '2026-09-20', '2026-09-24', '2026-09-25']
REGRESSIONS_URL = 'https://sippy.dptools.openshift.org/api/component_readiness/regressions?release=%s'


sys.path.insert(0, HERE)
import clustering  # noqa: E402


def parse(s):
    # Go RFC3339Nano drops trailing zero fractions, so whole-second timestamps are valid input; parse_ts
    # handles those, any fraction length and non-UTC offsets (CodeRabbit on #804).
    return clustering.parse_ts(s)


def slim(r, views):
    return {
        'id': r['id'], 'release': r['release'], 'duty_views': views, 'test_name': r['test_name'],
        'component': r['component'], 'capability': r.get('capability'), 'variants': r.get('variants') or [],
        'opened': r['opened'], 'closed': r.get('closed'), 'last_failure': r.get('last_failure'),
        'max_failures': r.get('max_failures'),
        'triages': [t['id'] if isinstance(t, dict) else t for t in (r.get('triages') or [])],
        'job_runs': [{'prowjob_name': j['prowjob_name'], 'prowjob_run_id': j['prowjob_run_id'],
                      'start_time': j['start_time'], 'test_failures': j.get('test_failures')}
                     for j in (r.get('job_runs') or [])],
    }


def enrich_regression_opened(recs, live=True):
    """Both sources were produced through list_regressions.filter_by_view, which replaces `opened` with the
    view's (re)activation date. Sippy's regression-level `opened` is immutable, so it can be re-fetched by
    (release, id) at any later time; records the API no longer returns fall back to `opened`."""
    live_opened = {}
    if live:
        for rel in sorted({r['release'] for r in recs}):
            try:
                with urllib.request.urlopen(REGRESSIONS_URL % rel, timeout=180) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
            except Exception as e:  # noqa: BLE001 - enrichment is best-effort
                print('warning: could not fetch %s regressions (%s); falling back to opened' % (rel, e), file=sys.stderr)
                continue
            for r in (data if isinstance(data, list) else data.get('regressions', [])):
                live_opened[(rel, r['id'])] = r['opened']
    missing = 0
    for r in recs:
        ro = live_opened.get((r['release'], r['id']))
        if ro is None:
            missing += 1
        r['regression_opened'] = ro or r['opened']
    print('regression_opened: %d/%d resolved from the live API' % (len(recs) - missing, len(recs)))
    return recs


def write(name, recs):
    p = os.path.join(HERE, 'fixtures', name)
    with gzip.GzipFile(p, 'wb', mtime=0) as f:
        f.write(json.dumps(recs, separators=(',', ':')).encode())
    print(name, len(recs), 'records', os.path.getsize(p), 'bytes')


def main():
    live = '--no-live' not in sys.argv[1:]
    os.makedirs(os.path.join(HERE, 'fixtures'), exist_ok=True)
    frozen = []
    for r in json.load(open(FROZEN_SRC))['open_untriaged']:
        views = [v for v in r['duty_views'] if v.endswith('-main')]
        if views:
            frozen.append(slim(r, views))
    write('frozen-2026-10-07.json.gz', enrich_regression_opened(frozen, live=live))

    centers = [datetime.fromisoformat(d + 'T00:00:00+00:00') for d in REPLAY_DAYS]
    byid = {}
    for rel in RELEASES:
        view = '4.%s-main' % rel.split('.')[1]
        data = json.load(open(os.path.join(LIVE_DIR, 'live-%s.json' % view)))
        for comp in data['components'].values():
            for r in (comp.get('open') or []) + (comp.get('closed') or []):
                o = parse(r['opened'])
                # +-36h around the replay date's noon observation time
                if not any(abs((o - (c + timedelta(hours=12))).total_seconds()) <= 36 * 3600 for c in centers):
                    continue
                if r['id'] in byid:
                    byid[r['id']]['duty_views'].append(view)
                else:
                    byid[r['id']] = slim(r, [view])
    write('replay-days.json.gz', enrich_regression_opened(sorted(byid.values(), key=lambda r: r['id']), live=live))


if __name__ == '__main__':
    sys.exit(main())
