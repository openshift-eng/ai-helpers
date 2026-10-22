#!/usr/bin/env python3
"""Flat prior memory for the weekly post-GA pre-pass.

Projects the preceding weekly ``triage-manifest.json`` (the ``--baseline``) onto
the current clusters as one ``prior`` block per cluster: which previous clusters
the current one descends from (same id, lineage, shared regression ids), what
the previous run concluded about them (state, analysis summary, bug candidates,
actions, escalation, watch/unanalysed status) and how the membership moved.
History is one flat generation: when the latest attempt left a cluster
unfinished, the useful snapshots it had itself inherited are retained as
``history_only`` context, never nested and never accumulated.

Stdlib only; no network, no I/O, no write decisions. Historical JSON is copied
opaquely (bounded root-cause prose aside); the agent and the manifest validator
decide what a current carry may rely on.
"""
import copy
import re
from datetime import datetime

SCHEMA_VERSION = '1.0'
POLICY = 'post-ga'
ROOT_CAUSE_LIMIT = 2000
RELATIONSHIPS = ('same-id', 'supersedes', 'split', 'merge', 'overlap')
UNFINISHED_STATE = 'UNANALYSED'
BASIS_DEPTHS = ('deep-dive', 'oracle')
WRITE_MODES = ('report', 'auto')
ACTION_KEYS = ('type', 'status', 'triage_id', 'jira', 'regression_ids', 'result_url', 'error')
ESCALATION_KEYS = ('required', 'reason', 'first_escalated_run', 're_notify', 're_notify_reasons')
ORACLE_KEYS = ('status', 'runs_probed', 'labels', 'label_bugs')
SOURCE_KEYS = ('run_id', 'observed_at', 'cluster_id', 'history_only', 'unfinished', 'member_ids',
               'matched_member_ids', 'fingerprint', 'shape', 'blast_radius', 'oracle', 'state', 'analysis',
               'bug_search', 'proposed_action', 'actions', 'escalation', 'unlinked', 'watch_list', 'unanalysed')
_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$')


def compatible(baseline):
    """The same meaning as prepass.diff_baseline: schema 1.0, post-ga policy, a cluster list."""
    return (isinstance(baseline, dict) and baseline.get('schema_version') == SCHEMA_VERSION
            and isinstance(baseline.get('policy'), dict) and baseline['policy'].get('name') == POLICY
            and isinstance(baseline.get('clusters'), list))


def is_id(x):
    return (isinstance(x, int) and not isinstance(x, bool)) or (isinstance(x, str) and x != '')


def sort_ids(ids):
    """Deduplicated ids, integers numerically first, then strings lexically."""
    ids = list(ids)
    ints = sorted({i for i in ids if isinstance(i, int) and not isinstance(i, bool)})
    strs = sorted({i for i in ids if isinstance(i, str)})
    return ints + strs


def member_ids(cluster):
    mem = cluster.get('members') if isinstance(cluster, dict) else None
    ids = mem.get('regression_ids') if isinstance(mem, dict) else None
    return sort_ids(i for i in ids if is_id(i)) if isinstance(ids, list) else []


def _text(x):
    return x if isinstance(x, str) and x else None


def _iso(x):
    """An ISO instant with an explicit offset, else None (unknown)."""
    if not isinstance(x, str) or not _ISO.match(x.strip()):
        return None
    try:
        datetime.fromisoformat(x.strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    return x.strip()


def _dict(x):
    return x if isinstance(x, dict) else None


def _identity(baseline):
    src = _dict(baseline.get('source_run')) or {}
    obs = _dict(baseline.get('observation')) or {}
    pol = _dict(baseline.get('policy')) or {}
    run_id = src.get('run_id')
    run_id = str(run_id) if is_id(run_id) else None
    mode = pol.get('write_mode')
    return {'run_id': run_id, 'observed_at': _iso(obs.get('time')), 'source_url': _text(src.get('url')),
            'write_mode': mode if mode in WRITE_MODES else None}


def _complete_views(baseline):
    obs = _dict(baseline.get('observation')) or {}
    views = obs.get('views')
    if not isinstance(views, list) or not views:
        return None
    if any(not isinstance(v, dict) or v.get('fetch') != 'complete' for v in views):
        return None
    return {v.get('view') for v in views}


def _evidence_refs(analysis):
    refs = []
    for e in analysis.get('evidence') if isinstance(analysis.get('evidence'), list) else []:
        if not isinstance(e, dict) or not is_id(e.get('prowjob_run_id')):
            continue
        sup = e.get('supports_regression_ids')
        if not isinstance(sup, list) or not sup or not all(is_id(i) for i in sup):
            continue
        refs.append({'prowjob_run_id': str(e['prowjob_run_id']), 'supports_regression_ids': sort_ids(sup),
                     'artifact': _text(e.get('artifact'))})
    return refs


def _basis_from(value):
    b = _dict(value)
    if not b:
        return None
    run_id, cid, at = _text(b.get('run_id')), _text(b.get('cluster_id')), _iso(b.get('observed_at'))
    if run_id and cid and at and b.get('depth') in BASIS_DEPTHS:
        return {'run_id': run_id, 'cluster_id': cid, 'observed_at': at, 'depth': b['depth']}
    return None


def _project_analysis(analysis, identity, cluster_id, unfinished):
    """PriorAnalysis: bounded summary, well-shaped evidence locators and the original qualifying basis."""
    root = analysis.get('root_cause')
    truncated = isinstance(root, str) and len(root) > ROOT_CAUSE_LIMIT
    refs = _evidence_refs(analysis)
    depth, confidence = analysis.get('depth'), analysis.get('confidence')
    basis = None
    if not unfinished and confidence == 'high' and refs:
        if depth in BASIS_DEPTHS and identity['run_id'] and identity['observed_at']:
            basis = {'run_id': identity['run_id'], 'cluster_id': cluster_id, 'observed_at': identity['observed_at'],
                     'depth': depth}
        elif depth == 'carried-forward':
            rev = _dict(analysis.get('reverification')) or {}
            if rev.get('outcome') == 'carried':
                basis = _basis_from(rev.get('basis'))
    return {'depth': depth, 'confidence': confidence, 'owning_component': analysis.get('owning_component'),
            'triage_type': analysis.get('triage_type'),
            'unverified_hypotheses': copy.deepcopy(analysis.get('unverified_hypotheses')),
            'root_cause': root[:ROOT_CAUSE_LIMIT] if isinstance(root, str) else None,
            'root_cause_truncated': truncated, 'evidence_refs': refs, 'basis': basis}


def _matching(items, cluster_id, ids):
    """Top-level watch/unanalysed entries about this source; [] when the list has none, None when unreadable."""
    if not isinstance(items, list):
        return None
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get('cluster_id') == cluster_id or (ids and is_id(it.get('regression_id')) and it['regression_id'] in ids):
            out.append(copy.deepcopy(it))
    return out


def _project_source(source, baseline, matched_member_ids):
    """Project one baseline cluster as an immediate source of a current cluster."""
    identity = _identity(baseline)
    cid = source['id']
    ids = member_ids(source)
    disp = _dict(source.get('disposition'))
    analysis = _dict(disp.get('analysis')) if disp else None
    state = disp.get('state') if disp else None
    state = state if isinstance(state, str) else None
    unanalysed = _matching(baseline.get('unanalysed'), cid, ids)
    rev = _dict(analysis.get('reverification')) if analysis else None
    unfinished = (disp is None or analysis is None or state == UNFINISHED_STATE or bool(unanalysed)
                  or (rev or {}).get('outcome') == 'incomplete')
    bug_search = _dict(disp.get('bug_search')) if disp else None
    oracle = _dict(source.get('oracle'))
    esc = _dict(source.get('escalation'))
    acts = source.get('actions')
    mem = _dict(source.get('members')) or {}
    return {
        'run_id': identity['run_id'], 'observed_at': identity['observed_at'], 'cluster_id': cid,
        'history_only': False, 'unfinished': unfinished,
        'member_ids': ids, 'matched_member_ids': sort_ids(matched_member_ids),
        'fingerprint': copy.deepcopy(_dict(source.get('fingerprint'))),
        'shape': copy.deepcopy(_dict(source.get('shape'))),
        'blast_radius': copy.deepcopy(_dict(source.get('blast_radius'))),
        'oracle': {k: copy.deepcopy(oracle.get(k)) for k in ORACLE_KEYS} if oracle else None,
        'state': state,
        'analysis': _project_analysis(analysis, identity, cid, unfinished) if analysis else None,
        'bug_search': ({'candidates': copy.deepcopy(bug_search.get('candidates')),
                        'newer_release_fix': copy.deepcopy(bug_search.get('newer_release_fix'))}
                       if bug_search else None),
        'proposed_action': copy.deepcopy(_dict(disp.get('proposed_action'))) if disp else None,
        'actions': ([{k: copy.deepcopy(a[k]) for k in ACTION_KEYS if k in a} if isinstance(a, dict) else copy.deepcopy(a)
                     for a in acts] if isinstance(acts, list) else None),
        'escalation': {k: copy.deepcopy(esc[k]) for k in ESCALATION_KEYS if k in esc} if esc else None,
        'unlinked': copy.deepcopy(mem.get('unlinked')) if isinstance(mem.get('unlinked'), list) else None,
        'watch_list': _matching(baseline.get('watch_list'), cid, ids),
        'unanalysed': unanalysed,
    }


def _retained_sources(source, current_ids):
    """Flat history-only context behind an unfinished immediate source (Decision 7).

    `source` is an already projected immediate source whose baseline cluster carried its own
    ``prior``; the finished, readable snapshots of that prior are copied once, marked
    ``history_only``, with their original run/time and basis. Nothing nested, nothing recursive.
    """
    if not source.get('unfinished'):
        return []
    embedded = _dict(source.get('_embedded_prior'))
    snapshots = embedded.get('sources') if embedded else None
    if not isinstance(snapshots, list):
        return []
    out, seen = [], set()
    current = set(current_ids)
    for snap in snapshots:
        if not isinstance(snap, dict) or snap.get('unfinished') is not False or not _dict(snap.get('analysis')):
            continue
        key = (snap.get('run_id'), snap.get('observed_at'), snap.get('cluster_id'))
        if key in seen or not isinstance(snap.get('cluster_id'), str):
            continue
        seen.add(key)
        kept = {k: copy.deepcopy(snap.get(k)) for k in SOURCE_KEYS}
        kept['run_id'] = _text(snap.get('run_id'))
        kept['observed_at'] = _iso(snap.get('observed_at'))
        kept['history_only'] = True
        kept['unfinished'] = False
        kept['member_ids'] = sort_ids(i for i in (snap.get('member_ids') or []) if is_id(i)) \
            if isinstance(snap.get('member_ids'), list) else []
        kept['matched_member_ids'] = sort_ids(i for i in kept['member_ids'] if i in current)
        analysis = kept['analysis']
        analysis['basis'] = _basis_from(analysis.get('basis'))
        if not isinstance(analysis.get('evidence_refs'), list):
            analysis['evidence_refs'] = []
        out.append(kept)
    return out


def attach_priors(clusters, baseline):
    """Set ``prior`` on every current cluster (None without usable memory); never mutates the baseline."""
    if not compatible(baseline):
        for c in clusters:
            c['prior'] = None
        return
    base = {b['id']: b for b in baseline['clusters'] if isinstance(b, dict) and isinstance(b.get('id'), str)}
    by_member = {}
    for bid, b in base.items():
        for rid in member_ids(b):
            by_member.setdefault(rid, set()).add(bid)
    identity = _identity(baseline)
    complete = _complete_views(baseline)

    def immediate_ids(c):
        found = set()
        if c['id'] in base:
            found.add(c['id'])
        lineage = _dict(c.get('lineage')) or {}
        for sid in lineage.get('supersedes') or []:
            if sid in base:
                found.add(sid)
        for rid in member_ids(c):
            found |= by_member.get(rid, set())
        return sorted(found)

    plans = [(c, immediate_ids(c)) for c in clusters]
    successors = {}
    for c, ids in plans:
        for sid in ids:
            successors[sid] = successors.get(sid, 0) + 1

    for c, source_ids in plans:
        if not source_ids:
            c['prior'] = None
            continue
        current_ids = member_ids(c)
        lineage = _dict(c.get('lineage')) or {}
        if len(source_ids) > 1:
            relationship = 'merge'
        elif successors[source_ids[0]] > 1:
            relationship = 'split'
        elif source_ids[0] == c['id']:
            relationship = 'same-id'
        elif source_ids[0] in (lineage.get('supersedes') or []):
            relationship = 'supersedes'
        else:
            relationship = 'overlap'
        sources, union = [], set()
        for sid in source_ids:
            b = base[sid]
            ids = member_ids(b)
            union |= set(ids)
            projected = _project_source(b, baseline, [i for i in ids if i in set(current_ids)])
            projected['_embedded_prior'] = b.get('prior')
            sources.append(projected)
        retained = []
        for s in sources:
            retained += _retained_sources(s, current_ids)
            del s['_embedded_prior']
        seen = set()
        for s in list(retained):
            key = (s['run_id'], s['observed_at'], s['cluster_id'])
            if key in seen:
                retained.remove(s)
            seen.add(key)
        views = set()
        for s in sources:
            mem = _dict(base[s['cluster_id']].get('members')) or {}
            views |= {v for v in (mem.get('views') or []) if isinstance(v, str)} if isinstance(mem.get('views'), list) else set()
        c['prior'] = {
            'run_id': identity['run_id'], 'observed_at': identity['observed_at'],
            'source_url': identity['source_url'], 'write_mode': identity['write_mode'],
            'observation_complete': complete is not None and views <= complete,
            'relationship': relationship,
            'sources': sources + retained,
            'member_delta': {'added': sort_ids(i for i in current_ids if i not in union),
                             'removed': sort_ids(i for i in union if i not in set(current_ids))},
        }


def unfinished_backlog(cluster):
    """True when an immediate source sharing members was left unfinished (backlog priority within urgency)."""
    pr = _dict(cluster.get('prior'))
    if not pr:
        return False
    return any(isinstance(s, dict) and not s.get('history_only') and s.get('unfinished') and s.get('matched_member_ids')
               for s in pr.get('sources') or [])
