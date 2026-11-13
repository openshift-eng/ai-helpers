#!/usr/bin/env python3
"""Development triage memory: inventory, own-run group refinement, and early checkpoints.

Uses the shared prior/manifest contract; no write decisions or external writes.
The ordinary duty collector's filters are preserved. Listed own runs are NOT
filtered by test_failed: Sippy's FailedJobRunsFromTestDetails leaves that field
unset even though it selects runs with a nonzero test FailureCount.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blast_radius  # noqa: E402
import clustering  # noqa: E402
import coverage  # noqa: E402
import manifest  # noqa: E402
import prepass  # noqa: E402
import prior  # noqa: E402


def collect(view, components=None, fetch=None):
    """Read the same population as list-regressions, retaining own runs and test ids."""
    spec = importlib.util.spec_from_file_location('duty_list_regressions', prepass.LIST_REGRESSIONS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    raw = (fetch or mod.fetch_regressions)(mod.extract_release_from_view(view))
    if not isinstance(raw, list) or not raw or any(not isinstance(r, dict) or 'id' not in r for r in raw):
        raise ValueError('release inventory unavailable or malformed; not an empty duty board')
    raw = copy.deepcopy(raw)
    for r in raw:
        r.setdefault('regression_opened', r.get('opened'))
    # Verify the view exists before component filtering can legitimately produce zero records.
    raw = mod.filter_by_view(raw, view)
    if not raw:
        raise ValueError('no regressions reference view %s' % view)
    raw = mod.filter_by_components(raw, components)
    raw = mod.simplify_time_fields(raw)
    raw, excluded = mod.exclude_suspected_infra_regressions(raw)
    print('Excluded %d suspected infrastructure regressions' % excluded, file=sys.stderr)
    result = []
    for r in raw:
        slim = prepass.slim(r, view)
        if r.get('test_id'):
            slim['test_id'] = r['test_id']
        result.append(slim)
    return result


def _baseline(baseline, policy, now, run_id):
    if baseline is None:
        return None, 'baseline absent or unreadable'
    if not prior.compatible(baseline, 'devel', policy['scope']):
        return None, 'baseline schema, policy, memory version or scope incompatible'
    errors = manifest.validate(baseline)
    if errors:
        return None, 'baseline invalid: ' + '; '.join(errors[:3])
    try:
        at = clustering.parse_ts(baseline['observation']['time'])
        if at >= now or str(baseline['source_run']['run_id']) == str(run_id):
            return None, 'baseline is not a preceding attempt'
    except (ValueError, TypeError, KeyError, AttributeError):
        return None, 'baseline observation time unavailable'
    return baseline, 'latest preceding compatible attempt'


def _keys(value):
    return coverage.pairs(value) | {(rid, None) for rid in coverage.zero_ids(value)}


def _coverage(keys):
    return sorted(coverage.from_pairs({(rid, run) for rid, run in keys if run is not None}) +
                  [{'regression_id': rid, 'run_ids': []} for rid, run in keys if run is None],
                  key=lambda entry: entry['regression_id'])


def _inventory_keys(records, required=False):
    return {(r['id'], str(j['prowjob_run_id'])) for r in records if not required or r['required'] for j in r['job_runs']} | {
        (r['id'], None) for r in records if not r['job_runs'] and (not required or r['required'])}


def prepare(regs, view, now, baseline=None, components=None, mode='record', run_id='local', source_url=None):
    if mode not in ('record', 'reuse'):
        raise ValueError('memory mode must be record or reuse')
    scope = {'views': [view], 'components': sorted({c.casefold() for c in components}) if components else ['*']}
    policy = {'name': 'devel', 'memory_version': 1, 'memory_mode': mode, 'scope': scope}
    baseline, reason = _baseline(baseline, policy, now, run_id)
    previous_members = {rid for c in (baseline or {}).get('clusters', []) for rid in c['members']['regression_ids']}
    inventory = prepass.as_of([copy.deepcopy(r) for r in regs if prepass.is_open(r)], now)
    for r in inventory:
        r['required'] = not r.get('triages') or r['id'] in previous_members
    inventory.sort(key=lambda r: r['id'])
    doc = {'schema_version': '1.0', 'policy': policy,
           'source_run': {'run_id': str(run_id), 'url': source_url},
           'observation': {'time': prepass.iso(now), 'views': [prepass.view_status(view, regs, now)],
                           'symptom_probe': {'status': 'skipped', 'runs_probed': 0}},
           'baseline_run': {'run_id': baseline['source_run']['run_id'] if baseline else None,
                            'schema_version': baseline['schema_version'] if baseline else None,
                            'manifest_url': baseline['source_run'].get('url') if baseline else None,
                            'compatible': baseline is not None, 'reason': reason},
           'inventory': inventory, 'sweep_candidates': [r['id'] for r in inventory if r.get('triages')],
           'clusters': [], 'unanalysed': []}
    required = _inventory_keys(inventory, required=True)
    groups = []
    assigned = set()
    for c in (baseline or {}).get('clusters', []):
        retained = coverage.pairs(c['members']['coverage']) & required
        if retained:
            groups.append({'coverage': _coverage(retained), 'signature': copy.deepcopy(c['signature'])})
            assigned |= retained
    unassigned = [dict(e, reason='new or unavailable own-run window; analysis not started')
                  for e in _coverage(required - assigned)]
    out = regroup(doc, {'groups': groups, 'unassigned': unassigned}, baseline)
    # Cheap hypotheses only. Final groups may split or merge these, but never lose own-run coverage.
    candidates = prepass.build_clusters([r for r in inventory if r['required']], now)
    out['candidate_groups'] = [{'id': c['id'], 'regression_ids': c['members']['regression_ids'],
                                'fingerprint': c['fingerprint'], 'blast_radius': c['blast_radius']} for c in candidates]
    return out


def regroup(prepared, grouping, baseline=None):
    """Validate an agent's partition and rebuild deterministic groups; current actions never survive."""
    if not isinstance(grouping, dict) or not isinstance(grouping.get('groups'), list):
        raise ValueError('groups must be a JSON list')
    doc = copy.deepcopy(prepared)
    baseline, _ = _baseline(baseline, doc['policy'], clustering.parse_ts(doc['observation']['time']),
                            doc['source_run']['run_id'])
    if doc['baseline_run']['compatible'] and (baseline is None or
            baseline['source_run']['run_id'] != doc['baseline_run']['run_id']):
        raise ValueError('regroup needs the same validated baseline as prepare')
    groups = copy.deepcopy(grouping['groups'])
    unassigned = grouping.get('unassigned', [])
    if not isinstance(unassigned, list):
        raise ValueError('unassigned must be a list')
    for entry in unassigned:
        if not isinstance(entry, dict) or not isinstance(entry.get('reason'), str) or not entry['reason']:
            raise ValueError('unassigned entry requires a reason')
        groups.append({'coverage': [{'regression_id': entry.get('regression_id'), 'run_ids': entry.get('run_ids')}],
                       'signature': {'stage': '', 'discriminator': ''}, 'pending_reason': entry['reason']})
    available = _inventory_keys(doc['inventory'])
    required = _inventory_keys(doc['inventory'], required=True)
    seen = set()
    for g in groups:
        if not isinstance(g, dict) or coverage.problems(g.get('coverage')) or not g['coverage']:
            raise ValueError('group needs nonempty well-formed coverage')
        signature = g.get('signature')
        if not isinstance(signature, dict) or any(not isinstance(signature.get(k), str) for k in ('stage', 'discriminator')):
            raise ValueError('group signature needs stage and discriminator strings')
        g['coverage'] = coverage.normalized(g['coverage'])
        keys = _keys(g['coverage'])
        if keys - available:
            raise ValueError('group names foreign own runs or invalid zero-run placeholders')
        if keys & seen:
            raise ValueError('each regression/run pair must occur in exactly one group')
        seen |= keys
    if required - seen:
        raise ValueError('required own-run windows missing; use unassigned with an exact reason')
    sources = (baseline or {}).get('clusters', [])
    parents = [[s for s in sources if coverage.pairs(s['members']['coverage']) & coverage.pairs(g['coverage'])]
               for g in groups]
    successors = {s['id']: sum(s in ps for ps in parents) for s in sources}
    records = {r['id']: r for r in doc['inventory']}
    now = clustering.parse_ts(doc['observation']['time'])
    # A partition is a hypothesis, not permission to lower a broad current incident's urgency.
    # Include sweep-alarm members explicitly added by regroup, as well as the required population.
    active = {rid for rid, _ in seen}
    candidate_levels = {}
    for candidate in prepass.build_clusters([r for r in doc['inventory'] if r['id'] in active], now):
        for rid in candidate['members']['regression_ids']:
            candidate_levels[rid] = candidate['blast_radius']['level']
    clusters = []
    for g, ps in zip(groups, parents):
        members = []
        for entry in g['coverage']:
            r = copy.deepcopy(records[entry['regression_id']])
            r['job_runs'] = [j for j in r['job_runs'] if str(j['prowjob_run_id']) in entry['run_ids']]
            members.append(r)
        shape = clustering.shape(members, now)
        level, score, reasons = blast_radius.classify(shape)
        candidate_level = min((candidate_levels[r['id']] for r in members), key=prepass.LEVEL_ORDER.get)
        if prepass.LEVEL_ORDER[candidate_level] < prepass.LEVEL_ORDER[level]:
            level = candidate_level
            reasons = reasons + ['urgency floor from current candidate population; group partition does not suppress it']
        stable = len(ps) == 1 and successors[ps[0]['id']] == 1
        digest = hashlib.sha256(json.dumps([g['coverage'], g['signature']], sort_keys=True).encode()).hexdigest()[:16]
        cid = ps[0]['id'] if stable else 'g-' + digest
        old_lineage = ps[0].get('lineage', {}) if stable else {}
        cycles = old_lineage.get('cycles_seen')
        cycles = cycles if isinstance(cycles, int) and not isinstance(cycles, bool) and cycles >= 0 else 0
        clusters.append({'id': cid, 'signature': g['signature'],
                         'pending_reason': g.get('pending_reason', 'analysis or verification not completed'),
                         'lineage': {'first_seen_run': old_lineage.get('first_seen_run') or doc['source_run']['run_id'],
                                     'cycles_seen': cycles + 1,
                                     'supersedes': sorted(s['id'] for s in ps)},
                         'fingerprint': clustering.fingerprint(members),
                         'members': {'regression_ids': [r['id'] for r in members], 'coverage': g['coverage'],
                                     'new_since_baseline': None, 'views': shape['views'], 'components': shape['components']},
                         'shape': shape, 'blast_radius': {'level': level, 'score': score, 'reasons': reasons},
                         'oracle': {'status': 'skipped', 'runs_probed': 0, 'labels': {}, 'label_bugs': {}}})
    prior.attach_priors(clusters, baseline, 'devel', doc['policy']['scope'])
    for c in clusters:
        if c['prior']:
            added = c['prior']['member_delta']['added']
            c['members']['new_since_baseline'] = added
            c['shape']['growth_since_baseline'] = len(added)
    clusters.sort(key=lambda c: (prepass.LEVEL_ORDER[c['blast_radius']['level']],
                                 not prior.unfinished_backlog(c), -c['blast_radius']['score'], c['id']))
    doc['clusters'] = clusters
    doc['unanalysed'] = []
    # Keep only drafts referenced by this generation's priors, including flat history-only sources.
    drafts = copy.deepcopy((baseline or {}).get('proposal_drafts', {}))
    for s in sources:
        proposal = s.get('disposition', {}).get('new_bug_proposal')
        draft = proposal.get('draft') if isinstance(proposal, dict) else None
        if isinstance(draft, str):
            drafts[hashlib.sha256(draft.encode()).hexdigest()] = draft
    referenced = {s['new_bug_proposal'].get('draft_sha256') for c in clusters for s in (c.get('prior') or {}).get('sources', [])
                  if isinstance(s.get('new_bug_proposal'), dict)}
    doc['proposal_drafts'] = {h: text for h, text in drafts.items() if h in referenced}
    errors = manifest.validate(checkpoint(doc))
    if errors:
        raise ValueError('; '.join(errors))
    return doc


def checkpoint(prepared):
    """A real incomplete manifest, with no invented current evidence/actions and all priors preserved."""
    dispositions = {}
    pending = []
    for c in prepared['clusters']:
        reason = c.get('pending_reason', 'analysis or verification not completed')
        dispositions[c['id']] = {'state': 'UNANALYSED',
                                 'analysis': {'depth': 'none', 'confidence': 'low', 'root_cause': reason,
                                              'evidence': [], 'unverified_hypotheses': []},
                                 'proposed_action': {'type': 'none'}}
        pending.append({'cluster_id': c['id'], 'reason': reason, 'blast_radius': c['blast_radius']['level']})
    return manifest.merge(prepared, dispositions, {}, {'unanalysed': pending})


def _load(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _load_baseline(path):
    if path == 'none':
        return None
    try:
        return _load(path)
    except (OSError, ValueError) as exc:
        print('Analysis memory unavailable: %s' % exc, file=sys.stderr)
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--view', required=True)
    p.add_argument('--components', nargs='+')
    p.add_argument('--inventory', help='offline scoped/slim inventory; omit to use the duty collector')
    p.add_argument('--mode', choices=('record', 'reuse'), default='record')
    p.add_argument('--now')
    p.add_argument('--run-id', default='local')
    p.add_argument('--source-url')
    p.add_argument('--baseline', default='none')
    r = commands.add_parser('regroup')
    r.add_argument('--groups', required=True)
    r.add_argument('--baseline', default='none')
    r.add_argument('--prepass', required=True)
    c = commands.add_parser('checkpoint')
    c.add_argument('--prepass', required=True)
    for sub in (p, r, c):
        sub.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            records = _load(args.inventory) if args.inventory else collect(args.view, args.components)
            doc = prepare(records, args.view, clustering.parse_ts(args.now) if args.now else datetime.now(timezone.utc),
                          _load_baseline(args.baseline), args.components, args.mode, args.run_id, args.source_url)
        elif args.command == 'regroup':
            doc = regroup(_load(args.prepass), _load(args.groups), _load_baseline(args.baseline))
        else:
            doc = checkpoint(_load(args.prepass))
            errors = manifest.validate(doc)
            if errors:
                raise ValueError('; '.join(errors))
        # A killed process cannot replace a usable checkpoint with a partial JSON document.
        target = Path(args.out)
        temporary = target.with_name(target.name + '.tmp')
        temporary.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
        temporary.replace(target)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
