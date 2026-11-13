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

Policies form compatibility families: ``post-ga`` and ``ga`` are one family, ``devel``
is another, and memory never crosses a family. Under ``devel`` a cluster is one
signature/window group whose ``members.coverage`` names the own runs it explains; ancestry
is then shared (regression, run) pairs only -- never a cluster id, a lineage entry or a
shared regression id -- and each source additionally carries its coverage, signature, the
metadata of a new-bug proposal (the draft's hash and length, never its text) and symptom
proposals, with ``prior.run_delta`` giving the pairs added and removed.

Stdlib only; no network, no I/O, no write decisions. Historical JSON is copied
opaquely (bounded root-cause prose aside); the agent and the manifest validator
decide what a current carry may rely on.
"""
import copy
import hashlib
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import coverage as cov  # noqa: E402

SCHEMA_VERSION = '1.0'
POLICY = 'post-ga'
FAMILIES = {'post-ga': 'ga', 'ga': 'ga', 'devel': 'devel'}
DEVEL = 'devel'
MEMORY_VERSION = 1
SUMMARY_LIMIT = 500
PROPOSAL_KEYS = ('status', 'summary', 'component', 'triage_type', 'release_blocker', 'regression_ids')
DEVEL_SOURCE_KEYS = ('coverage', 'signature', 'new_bug_proposal', 'symptom_proposals')
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


def family(name):
    """'ga', 'devel' or None for an unknown policy name."""
    return FAMILIES.get(name) if isinstance(name, str) else None


def normalize_scope(scope):
    """(sorted views, sorted components) for a {views, components} scope of strings, else None."""
    if not isinstance(scope, dict):
        return None
    out = []
    for k in ('views', 'components'):
        v = scope.get(k)
        if not isinstance(v, list) or any(not isinstance(x, str) or not x for x in v):
            return None
        out.append(tuple(sorted(set(v))))
    return tuple(out) if out[0] else None


def compatible(baseline, policy=POLICY, scope=None):
    """Whether `baseline` may serve as memory for a run under `policy`: schema 1.0, a cluster list and a
    policy of the same family. A devel baseline additionally needs memory_version 1 and a well-formed
    scope; when `scope` is given it must equal the baseline's (order and duplicates ignored)."""
    fam = family(policy)
    if not (fam and isinstance(baseline, dict) and baseline.get('schema_version') == SCHEMA_VERSION
            and isinstance(baseline.get('policy'), dict) and family(baseline['policy'].get('name')) == fam
            and isinstance(baseline.get('clusters'), list)):
        return False
    if fam != DEVEL:
        return True
    pol = baseline['policy']
    version = pol.get('memory_version')
    if isinstance(version, bool) or version != MEMORY_VERSION:
        return False
    own = normalize_scope(pol.get('scope'))
    return own is not None and (scope is None or normalize_scope(scope) == own)


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
    """The views the baseline run fetched completely (None when it recorded none): a partial fetch of one
    view leaves the memory of clusters in other views complete."""
    obs = _dict(baseline.get('observation')) or {}
    views = obs.get('views')
    if not isinstance(views, list) or not views:
        return None
    return {v.get('view') for v in views
            if isinstance(v, dict) and v.get('fetch') == 'complete' and isinstance(v.get('view'), str)}


def _source_views(cluster):
    """The views a source cluster's members were observed in; None when unknown or malformed."""
    mem = _dict(cluster.get('members')) or {}
    views = mem.get('views')
    if not isinstance(views, list) or not views or any(not isinstance(v, str) or not v for v in views):
        return None
    return set(views)


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


def _matching(items, cluster_id, ids=None):
    """Top-level entries about this source: by cluster id, or (watch list only) by member id; [] when the list
    has none, None when unreadable."""
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
    unanalysed = _matching(baseline.get('unanalysed'), cid)
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


def _project_proposal(value):
    """Metadata of a new-bug proposal: the draft stays in the baseline manifest, identified by hash and length."""
    p = _dict(value)
    if not p:
        return None
    out = {k: copy.deepcopy(p.get(k)) for k in PROPOSAL_KEYS}
    if isinstance(out['summary'], str):
        out['summary'] = out['summary'][:SUMMARY_LIMIT]
    draft = p.get('draft')
    readable = isinstance(draft, str) and draft != ''
    try:
        encoded = draft.encode('utf-8') if readable else None
    except UnicodeError:
        encoded, readable = None, False
    out['draft_sha256'] = hashlib.sha256(encoded).hexdigest() if readable else None
    out['draft_chars'] = len(draft) if readable else None
    return out


def _devel_fields(source):
    """The devel additions to a projected immediate source."""
    disp = _dict(source.get('disposition')) or {}
    mem = _dict(source.get('members')) or {}
    symptoms = disp.get('symptom_proposals')
    return {'coverage': cov.normalized(mem.get('coverage')),
            'signature': copy.deepcopy(_dict(source.get('signature'))),
            'new_bug_proposal': _project_proposal(disp.get('new_bug_proposal')),
            'symptom_proposals': copy.deepcopy(symptoms) if isinstance(symptoms, list) else None}


def _retained_devel_fields(snap):
    """The devel additions of a retained snapshot, re-projected: already metadata, never a draft."""
    proposal = _dict(snap.get('new_bug_proposal'))
    if proposal:
        proposal = {k: copy.deepcopy(v) for k, v in proposal.items() if k != 'draft'}
    symptoms = snap.get('symptom_proposals')
    return {'coverage': cov.normalized(snap.get('coverage')),
            'signature': copy.deepcopy(_dict(snap.get('signature'))),
            'new_bug_proposal': proposal or None,
            'symptom_proposals': copy.deepcopy(symptoms) if isinstance(symptoms, list) else None}


def _retained_sources(source, current_ids, devel=False):
    """Flat history-only context behind an unfinished immediate source (Decision 7).

    `source` is an already projected immediate source whose baseline cluster carried its own
    ``prior``; the finished snapshots of that prior that have a cluster id and an analysis container
    are re-projected once through the envelope contract, marked ``history_only``, with their original
    run/time (null when unknown) and basis. Nothing nested, nothing recursive.
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
        if not isinstance(snap, dict) or snap.get('unfinished') is not False:
            continue
        analysis = _dict(snap.get('analysis'))
        cid = _text(snap.get('cluster_id'))
        if analysis is None or not cid:
            continue
        # unknown run/time or unreadable metadata disqualify inheritance (no basis) but not retention as context
        key = (_text(snap.get('run_id')), _iso(snap.get('observed_at')), cid)
        if key in seen:
            continue
        seen.add(key)
        kept = _normalize_snapshot(snap, analysis, cid, current)
        kept['run_id'], kept['observed_at'] = key[0], key[1]
        if devel:
            kept.update(_retained_devel_fields(snap))
        out.append(kept)
    return out


def _normalize_snapshot(snap, analysis, cid, current):
    """Re-project a retained snapshot through the same envelope contract as an immediate source: only the
    projection keys, bounded prose, well-shaped evidence locators, a validated basis, containers or null."""
    root = analysis.get('root_cause')
    truncated = analysis.get('root_cause_truncated') is True or (isinstance(root, str) and len(root) > ROOT_CAUSE_LIMIT)
    refs = []
    for r in analysis.get('evidence_refs') if isinstance(analysis.get('evidence_refs'), list) else []:
        if not isinstance(r, dict) or not _text(r.get('prowjob_run_id')):
            continue
        sup = r.get('supports_regression_ids')
        if not isinstance(sup, list) or not sup or not all(is_id(i) for i in sup):
            continue
        refs.append({'prowjob_run_id': r['prowjob_run_id'], 'supports_regression_ids': sort_ids(sup),
                     'artifact': _text(r.get('artifact'))})
    kept = {k: None for k in SOURCE_KEYS}
    kept.update({
        'cluster_id': cid, 'history_only': True, 'unfinished': False,
        'member_ids': sort_ids(i for i in snap['member_ids'] if is_id(i)) if isinstance(snap.get('member_ids'), list) else [],
        'state': snap.get('state') if isinstance(snap.get('state'), str) else None,
        'analysis': {'depth': analysis.get('depth'), 'confidence': analysis.get('confidence'),
                     'owning_component': analysis.get('owning_component'), 'triage_type': analysis.get('triage_type'),
                     'unverified_hypotheses': copy.deepcopy(analysis.get('unverified_hypotheses')),
                     'root_cause': root[:ROOT_CAUSE_LIMIT] if isinstance(root, str) else None,
                     'root_cause_truncated': truncated, 'evidence_refs': refs,
                     'basis': _basis_from(analysis.get('basis'))},
    })
    kept['matched_member_ids'] = sort_ids(i for i in kept['member_ids'] if i in current)
    for k in ('fingerprint', 'shape', 'blast_radius', 'oracle', 'bug_search', 'proposed_action', 'escalation'):
        kept[k] = copy.deepcopy(_dict(snap.get(k)))
    for k in ('actions', 'unlinked', 'watch_list', 'unanalysed'):
        kept[k] = copy.deepcopy(snap[k]) if isinstance(snap.get(k), list) else None
    return kept


def _pairs(cluster):
    mem = cluster.get('members') if isinstance(cluster, dict) else None
    return cov.pairs(mem.get('coverage')) if isinstance(mem, dict) else set()


def attach_priors(clusters, baseline, policy=POLICY, scope=None):
    """Set ``prior`` on every current cluster (None without usable memory); never mutates the baseline.

    `policy` is the current run's policy; a baseline of another family (or, for devel, another memory
    version or -- when `scope` is given -- another scope) attaches nothing. Under devel the ancestry key
    is the (regression, run) pair from ``members.coverage``; zero-run placeholders match nothing."""
    if not compatible(baseline, policy, scope):
        for c in clusters:
            c['prior'] = None
        return
    devel = family(policy) == DEVEL
    keys = _pairs if devel else member_ids
    base = {b['id']: b for b in baseline['clusters'] if isinstance(b, dict) and isinstance(b.get('id'), str)}
    by_member = {}
    for bid, b in base.items():
        for rid in keys(b):
            by_member.setdefault(rid, set()).add(bid)
    identity = _identity(baseline)
    complete = _complete_views(baseline)

    def supersedes_of(c):
        lineage = _dict(c.get('lineage')) or {}
        sup = lineage.get('supersedes')
        return [sid for sid in sup if isinstance(sid, str)] if isinstance(sup, list) else []

    def immediate_ids(c):
        found = set()
        if not devel:
            if c['id'] in base:
                found.add(c['id'])
            for sid in supersedes_of(c):
                if sid in base:
                    found.add(sid)
        for rid in keys(c):
            found |= by_member.get(rid, set())
        return sorted(found)

    plans = [(c, immediate_ids(c)) for c in clusters]
    # a split needs several current clusters that actually share members with the source; an identity-only
    # match (a same-id replacement population) is not one of its children
    successors = {}
    for c, ids in plans:
        shared = set(keys(c))
        for sid in ids:
            if shared & set(keys(base[sid])):
                successors[sid] = successors.get(sid, 0) + 1

    for c, source_ids in plans:
        if not source_ids:
            c['prior'] = None
            continue
        current_ids = member_ids(c)
        if len(source_ids) > 1:
            relationship = 'merge'
        elif successors.get(source_ids[0], 0) > 1 and set(keys(c)) & set(keys(base[source_ids[0]])):
            relationship = 'split'
        elif source_ids[0] == c['id']:
            relationship = 'same-id'
        elif not devel and source_ids[0] in supersedes_of(c):
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
            if devel:
                projected.update(_devel_fields(b))
            sources.append(projected)
        retained = []
        for s in sources:
            retained += _retained_sources(s, current_ids, devel)
            del s['_embedded_prior']
        seen = set()
        for s in list(retained):
            key = (s['run_id'], s['observed_at'], s['cluster_id'])
            if key in seen:
                retained.remove(s)
            seen.add(key)
        scopes = [_source_views(base[s['cluster_id']]) for s in sources]
        c['prior'] = {
            'run_id': identity['run_id'], 'observed_at': identity['observed_at'],
            'source_url': identity['source_url'], 'write_mode': identity['write_mode'],
            'observation_complete': (complete is not None and all(v is not None and v <= complete for v in scopes)),
            'relationship': relationship,
            'sources': sources + retained,
            'member_delta': {'added': sort_ids(i for i in current_ids if i not in union),
                             'removed': sort_ids(i for i in union if i not in set(current_ids))},
        }
        if devel:
            now, was = _pairs(c), set().union(*(_pairs(base[sid]) for sid in source_ids))
            c['prior']['run_delta'] = {'added': cov.from_pairs(now - was), 'removed': cov.from_pairs(was - now)}


def unfinished_backlog(cluster):
    """True when an immediate source sharing members was left unfinished (backlog priority within urgency)."""
    pr = _dict(cluster.get('prior'))
    if not pr:
        return False
    return any(isinstance(s, dict) and not s.get('history_only') and s.get('unfinished') and s.get('matched_member_ids')
               for s in pr.get('sources') or [])
