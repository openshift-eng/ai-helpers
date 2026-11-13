#!/usr/bin/env python3
"""Pure helpers for development-memory coverage: which own runs of which regressions a cluster explains.

A coverage is ``[{"regression_id": int, "run_ids": [str, ...]}, ...]``: one entry per regression, run ids
unique non-empty strings. An entry with no runs is a placeholder for a regression that has no listed own run;
it keeps the work visible and is never an ancestry key.

  problems(value)   -> list of shape errors (empty when well-formed); never raises
  pairs(value)      -> {(regression_id, run_id)}; malformed parts are skipped
  zero_ids(value)   -> {regression_id} of the placeholder entries
  regression_ids(value) -> {regression_id} of every well-formed entry
  from_pairs(pairs) -> canonical coverage (sorted by regression id, then run id)
  normalized(value) -> canonical coverage keeping placeholders, or None when malformed

Stdlib only; no I/O.
"""


def _is_rid(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _is_run(x):
    return isinstance(x, str) and x != ''


def problems(value):
    if not isinstance(value, list):
        return ['coverage must be a list of {regression_id, run_ids}']
    errs, seen = [], set()
    for i, e in enumerate(value):
        if not isinstance(e, dict):
            errs.append('coverage[%d]: expected object' % i)
            continue
        rid, runs = e.get('regression_id'), e.get('run_ids')
        if not _is_rid(rid):
            errs.append('coverage[%d]: regression_id must be an integer' % i)
        elif rid in seen:
            errs.append('coverage[%d]: regression %s listed twice' % (i, rid))
        else:
            seen.add(rid)
        if not isinstance(runs, list) or any(not _is_run(r) for r in runs):
            errs.append('coverage[%d]: run_ids must be a list of non-empty strings' % i)
        elif len(set(runs)) != len(runs):
            errs.append('coverage[%d]: run_ids must not repeat' % i)
    return errs


def _entries(value):
    for e in value if isinstance(value, list) else []:
        if isinstance(e, dict) and _is_rid(e.get('regression_id')) and isinstance(e.get('run_ids'), list):
            yield e['regression_id'], [r for r in e['run_ids'] if _is_run(r)]


def pairs(value):
    return {(rid, run) for rid, runs in _entries(value) for run in runs}


def zero_ids(value):
    return {rid for rid, runs in _entries(value) if not runs}


def regression_ids(value):
    return {rid for rid, _ in _entries(value)}


def from_pairs(pair_set):
    by = {}
    for rid, run in pair_set:
        by.setdefault(rid, set()).add(run)
    return [{'regression_id': rid, 'run_ids': sorted(by[rid])} for rid in sorted(by)]


def normalized(value):
    if problems(value):
        return None
    return [{'regression_id': rid, 'run_ids': sorted(runs)} for rid, runs in sorted(_entries(value))]
