#!/usr/bin/env python3
"""One-off generator for the pre-pass backtest fixtures (kept for provenance). See fixtures/README.md."""
import gzip
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN_SRC = '/root/OPNET-595-BGP/tmp-opencode/bulk-existing-triage-4.16-4.22-2026-10-07/inventory.json'
LIVE_DIR = '/root/OPNET-595-BGP/tmp-opencode/chaibot-design'
RELEASES = ['4.16', '4.17', '4.18', '4.19', '4.20', '4.21', '4.22']
REPLAY_DAYS = ['2026-08-30', '2026-09-20', '2026-09-24', '2026-09-25']


def parse(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00').split('.')[0] + '+00:00')


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


def write(name, recs):
    p = os.path.join(HERE, 'fixtures', name)
    with gzip.GzipFile(p, 'wb', mtime=0) as f:
        f.write(json.dumps(recs, separators=(',', ':')).encode())
    print(name, len(recs), 'records', os.path.getsize(p), 'bytes')


def main():
    os.makedirs(os.path.join(HERE, 'fixtures'), exist_ok=True)
    frozen = []
    for r in json.load(open(FROZEN_SRC))['open_untriaged']:
        views = [v for v in r['duty_views'] if v.endswith('-main')]
        if views:
            frozen.append(slim(r, views))
    write('frozen-2026-10-07.json.gz', frozen)

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
    write('replay-days.json.gz', sorted(byid.values(), key=lambda r: r['id']))


if __name__ == '__main__':
    sys.exit(main())
