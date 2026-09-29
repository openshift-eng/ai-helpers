#!/usr/bin/env python3
"""Validate evidence contracts and export independently reviewed reliability issues.

Mechanical validation checks integrity, not truth. The independent reviewer must
actually inspect the cited evidence and challenge the proposed causal repair.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sys

VERDICTS = {'PROVEN_FIX', 'UNRESOLVED', 'ALREADY_FIXED', 'REJECTED'}
ROLES = {'failure', 'mechanism', 'current_source', 'control'}
FAILED_RESULTS = {'F', 'N', 'n', 'A', 'failure', 'error', 'aborted'}
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return value


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field}: nonempty text required')
    return value


def safe_file(workspace, name):
    if not isinstance(name, str) or Path(name).is_absolute():
        raise ValueError('evidence path must be workspace-relative')
    path = (workspace / name).resolve()
    if not path.is_relative_to(workspace.resolve()) or not path.is_file():
        raise ValueError(f'evidence missing or outside workspace: {name}')
    return path


def evidence(workspace, item):
    for key in ('id', 'role', 'path', 'sha256', 'source_url'):
        text(item.get(key), f'evidence.{key}')
    if item['role'] not in ROLES:
        raise ValueError(f'unknown evidence role: {item["role"]}')
    if not item['source_url'].startswith('https://'):
        raise ValueError('evidence source_url must use HTTPS')
    path = safe_file(workspace, item['path'])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError(f'evidence hash mismatch: {item["path"]}')
    lines = raw.decode('utf-8').splitlines()
    first, last = item.get('line_start'), item.get('line_end')
    if type(first) is not int or type(last) is not int or not 1 <= first <= last <= len(lines):
        raise ValueError(f'invalid evidence line range: {item["path"]}')
    return '\n'.join(lines[first - 1:last])


def validate_candidate(workspace, candidate):
    for key in ('id', 'defect_key', 'title', 'investigator', 'owner', 'summary',
                'mechanism', 'current_state', 'proposed_change', 'validation', 'limitations'):
        text(candidate.get(key), key)
    if not SLUG.fullmatch(candidate['id']) or not SLUG.fullmatch(candidate['defect_key']):
        raise ValueError('id and defect_key must be kebab-case')
    if type(candidate.get('priority')) is not int or candidate['priority'] < 1:
        raise ValueError('priority must be a positive integer; lower sorts first')
    if candidate.get('verdict') not in VERDICTS:
        raise ValueError('invalid investigator verdict')
    if not isinstance(candidate.get('runs'), list) or not candidate['runs']:
        raise ValueError('at least one affected run is required')
    for run in candidate['runs']:
        for key in ('run_id', 'job', 'url', 'result'):
            text(run.get(key), f'run.{key}')
        if not run['url'].startswith('https://'):
            raise ValueError('run URL must use HTTPS')
        if type(run.get('blocking_failure')) is not bool:
            raise ValueError('blocking_failure must be a boolean, supported by JUnit/step evidence')
    items = candidate.get('evidence')
    if not isinstance(items, list) or not items:
        raise ValueError('candidate needs evidence')
    snippets, roles = {}, set()
    for item in items:
        snippet = evidence(workspace, item)
        if item['id'] in snippets:
            raise ValueError('duplicate evidence ID')
        snippets[item['id']] = snippet
        roles.add(item['role'])
    if candidate['verdict'] == 'PROVEN_FIX':
        if not ROLES <= roles:
            raise ValueError('proven fix needs failure, mechanism, current_source and control evidence')
        if not any(r['blocking_failure'] and r['result'] in FAILED_RESULTS for r in candidate['runs']):
            raise ValueError('proven fix needs an actual blocking failed run')
        if candidate.get('currently_unfixed') is not True:
            raise ValueError('proven fix must be currently unfixed')
    return snippets


def validate_review(candidate, review):
    if review.get('candidate_id') != candidate['id'] or review.get('candidate_sha256') != digest(candidate):
        raise ValueError('review does not match the exact current candidate')
    text(review.get('reviewer'), 'reviewer')
    if review['reviewer'] == candidate['investigator']:
        raise ValueError('investigator cannot independently review their own candidate')
    if review.get('verdict') not in VERDICTS:
        raise ValueError('invalid review verdict')
    for key in ('reasoning', 'counterargument', 'repair_scope'):
        text(review.get(key), f'review.{key}')
    checked = review.get('checked_evidence_ids')
    if not isinstance(checked, list) or not checked or len(set(checked)) != len(checked):
        raise ValueError('review needs unique inspected evidence IDs')
    ids = {e['id'] for e in candidate['evidence']}
    if not set(checked) <= ids:
        raise ValueError('review references unknown evidence')
    if review['verdict'] == 'PROVEN_FIX' and set(checked) != ids:
        raise ValueError('proven review must inspect every cited evidence item')


def load(workspace):
    config = read(workspace / 'config.json')
    candidates = []
    seen = set()
    files = sorted((workspace / 'candidates').glob('*.json'))
    if len(files) > config['max_candidates']:
        raise ValueError('candidate budget exceeded; narrow or explicitly revise the run budget')
    for path in files:
        candidate = read(path)
        snippets = validate_candidate(workspace, candidate)
        if candidate['id'] in seen:
            raise ValueError('duplicate candidate ID')
        seen.add(candidate['id'])
        review_path = workspace / 'reviews' / (candidate['id'] + '.json')
        review = read(review_path) if review_path.exists() else None
        if review is not None:
            validate_review(candidate, review)
        accepted = bool(review and candidate['verdict'] == review['verdict'] == 'PROVEN_FIX')
        candidates.append((candidate, review, snippets, accepted))
    return config, candidates


def md(value):
    # Agent-authored text is rendered as literal prose, not executable HTML or links.
    value = html.escape(str(value), quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', value)


def handoff(candidate, review, snippets, paths):
    c = candidate
    result = [f'# {md(c["title"])}', '', '**Category: Reliability · Independently validated current defect**', '',
              '## Summary', '', md(c['summary']), '', '## Impact and affected runs', '']
    for run in c['runs']:
        result.append(f'- {md(run["job"])} / {md(run["run_id"])}: {md(run["result"])}; blocking failure: {run["blocking_failure"]}. {md(run["url"])}')
    for heading, value in [('Root cause / demonstrated mechanism', c['mechanism']),
                           ('Current source and fix status', c['current_state']),
                           ('Suggested fix and owner', c['owner'] + '\n\n' + c['proposed_change']),
                           ('Validation and acceptance', c['validation']),
                           ('Limits and unresolved cofailures', c['limitations']),
                           ('Independent review', review['reasoning'] + '\n\nCounterargument: ' + review['counterargument'] + '\n\nRepair scope: ' + review['repair_scope'])]:
        result += ['', '## ' + heading, '', md(value)]
    result += ['', '## Evidence', '']
    for e in c['evidence']:
        result += [f'### {md(e["id"])} — {e["role"]}', '',
                   f'[Retained evidence]({paths[e["id"]]}) · lines {e["line_start"]}–{e["line_end"]}', '',
                   md(e['source_url']), '', 'SHA256: `' + e['sha256'] + '`', '',
                   '\n'.join('> ' + md(line) for line in snippets[e['id']].splitlines()), '']
    return '\n'.join(result) + '\n'


def publish(workspace, output):
    config, rows = load(workspace)
    # A fresh output is an immutable handoff snapshot; stale approvals cannot linger.
    if output.exists():
        raise ValueError('output already exists; choose a new snapshot directory (never overwrite hand-edited issues)')
    selected, excluded, keys = [], [], set()
    for row in sorted(rows, key=lambda r: (r[0]['priority'], r[0]['id'])):
        c, review, _, accepted = row
        reason = None
        if not accepted:
            reason = review['verdict'] if review else 'UNREVIEWED'
            if c['verdict'] != 'PROVEN_FIX':
                reason = c['verdict']
        elif c['defect_key'] in keys:
            reason = 'DUPLICATE_MECHANISM'
        elif len(selected) >= config['max_issues']:
            reason = 'VALIDATED_OVER_LIMIT'
        if reason:
            excluded.append({'id': c['id'], 'reason': reason, 'candidate': c, 'review': review})
        else:
            keys.add(c['defect_key'])
            selected.append(row)
    output.mkdir(parents=True)
    try:
        (output / 'issues').mkdir()
        index = []
        for c, review, snippets, _ in selected:
            target = output / 'issues' / c['id']
            (target / 'evidence').mkdir(parents=True)
            paths = {}
            for n, item in enumerate(c['evidence']):
                filename = f'{n:03d}.txt'
                shutil.copyfile(safe_file(workspace, item['path']), target / 'evidence' / filename)
                paths[item['id']] = 'evidence/' + filename
                if hashlib.sha256((target / paths[item['id']]).read_bytes()).hexdigest() != item['sha256']:
                    raise ValueError('evidence changed while exporting')
            (target / 'README.md').write_text(handoff(c, review, snippets, paths))
            portable = dict(c, evidence=[dict(e, path=paths[e['id']]) for e in c['evidence']])
            write(target / 'finding.json', portable)
            write(target / 'review.json', dict(review, exported_candidate_sha256=digest(portable)))
            index.append({'id': c['id'], 'title': c['title'], 'defect_key': c['defect_key'], 'priority': c['priority'], 'path': f'issues/{c["id"]}/README.md'})
        write(output / 'unresolved.json', excluded)
        write(output / 'manifest.json', {'config': config, 'validated_issues': index, 'excluded_records': len(excluded), 'validation_scope': 'Evidence integrity and independent attestation; no automatic proof of causality.'})
        links = ''.join(f'<li><a href="{html.escape(r["path"], quote=True)}">{html.escape(r["title"])}</a></li>' for r in index)
        (output / 'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Validated CI reliability issues</title><h1>Validated CI reliability issues</h1><p>Independent review applies to each stated defect, not guaranteed whole-job recovery.</p><ol>' + links + '</ol><p><a href="unresolved.json">Excluded, unresolved and already-fixed records</a></p></html>')
        (output / 'README.md').write_text('# Validated CI reliability issues\n\n' + '\n'.join(f'- [{md(r["title"])}]({r["path"]})' for r in index) + '\n\nSee manifest.json for limits and unresolved.json for excluded records. Counts are not predicted recoveries.\n')
    except Exception:
        # Only remove the fresh directory owned by this invocation.
        shutil.rmtree(output)
        raise
    return {'validated_issues': len(index), 'excluded': len(excluded), 'output': str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--workspace', type=Path, required=True)
    init.add_argument('--max-issues', type=positive, default=10)
    init.add_argument('--max-candidates', type=positive, default=100)
    init.add_argument('--time-budget-minutes', type=positive, default=120)
    init.add_argument('--max-agents', type=positive, default=4)
    for name in ('validate', 'publish'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--workspace', type=Path, required=True)
        if name == 'publish':
            cmd.add_argument('--output', type=Path, required=True)
    stamp = sub.add_parser('candidate-digest')
    stamp.add_argument('candidate', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            if args.max_candidates < args.max_issues:
                raise ValueError('max-candidates must be at least max-issues')
            args.workspace.mkdir(parents=True, exist_ok=True)
            config = args.workspace / 'config.json'
            if config.exists():
                raise ValueError('workspace already initialized; preserve its frozen configuration')
            for name in ('candidates', 'reviews', 'evidence'):
                (args.workspace / name).mkdir(exist_ok=True)
            write(config, {'schema_version': 1, 'max_issues': args.max_issues, 'max_candidates': args.max_candidates,
                           'time_budget_minutes': args.time_budget_minutes, 'max_agents': args.max_agents,
                           'started_at': dt.datetime.now(dt.timezone.utc).isoformat()})
            print(config)
        elif args.command == 'candidate-digest':
            print(digest(read(args.candidate)))
        elif args.command == 'validate':
            _, rows = load(args.workspace)
            print(json.dumps({'candidates': len(rows), 'dual_approved': sum(r[3] for r in rows), 'note': 'Structural validation does not establish causality.'}))
        else:
            print(json.dumps(publish(args.workspace, args.output)))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
