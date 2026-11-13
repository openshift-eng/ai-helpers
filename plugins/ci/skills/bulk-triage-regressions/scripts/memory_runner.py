#!/usr/bin/env python3
"""Artifact transport for development triage memory: pick the preceding attempt's manifest, publish this one.

  memory_runner.py select  --job J --build-id N [--pull-number P --repo-owner O --repo-name R]
                           [--bucket B] [--mode record|reuse] --dest baseline.json --out memory-selection.json
  memory_runner.py publish --initial inventory-prepass.json --checkpoint checkpoint-manifest.json
                           --final triage-manifest.json --workdir DIR --artifact-dir DIR

select prints the local baseline path, or `none`, and always exits 0 when it could write its record: an
unavailable baseline is a reported cold start, never an error and never "nothing changed". Only the latest
attempt strictly preceding this build, in this job's own history (a rehearsal's history is its pull request's),
is ever consulted; an older attempt is never substituted. The manifest is exposed at --dest only after
exactly one object matched, the download finished and it parsed as a JSON object.

publish promotes at most one validated manifest to <artifact-dir>/triage-manifest.json: the agent's final
one when it validates and kept the runner's deterministic fields, else the runner's early checkpoint. A
rejected final manifest is kept as triage-manifest.invalid.json. It prints the status and exits 0 for
`final` or `final-with-gaps` (explicitly exhausted zero-run lookups, never inherited analysis).

Stdlib only. The only external call is `gcloud storage ls|cp`, behind an injectable run(argv) boundary.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_BUCKET = 'test-platform-results-public'
STEP_NAME = 'openshift-claude-bulk-triage'
MANIFEST_NAME = 'triage-manifest.json'
GCLOUD_TIMEOUT = 300
DETAIL_LIMIT = 600
PROTECTED = ('schema_version', 'policy', 'source_run', 'observation', 'baseline_run', 'inventory')
WORKING_DOCUMENTS = ('prepass.json', 'groups.json', 'dispositions.json', 'actions.json', 'extra.json')
_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
_NUMBER = re.compile(r'^[0-9]+$')


def default_run(argv):
    """Run a command; (return code, stdout, stderr). A command that cannot start or times out is a failure."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=GCLOUD_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, '', '%s: %s' % (argv[0], e)
    return p.returncode, p.stdout, p.stderr


def _name(x):
    return isinstance(x, str) and bool(_NAME.match(x))


def _number(x):
    return isinstance(x, str) and bool(_NUMBER.match(x))


def history_path(job, pull_number=None, repo_owner=None, repo_name=None, bucket=DEFAULT_BUCKET):
    """'<bucket>/<prefix>/<job>' holding this job's runs, or None when the identity is incomplete or unsafe.

    A periodic's runs live under logs/<job>; a rehearsal's under pr-logs/pull/<org>_<repo>/<pr>/<job>. A
    pull number without its repository is incomplete: the history is never guessed."""
    if not (_name(job) and _name(bucket)):
        return None
    if pull_number:
        if not (_number(pull_number) and _name(repo_owner) and _name(repo_name)):
            return None
        return '%s/pr-logs/pull/%s_%s/%s/%s' % (bucket, repo_owner, repo_name, pull_number, job)
    return '%s/logs/%s' % (bucket, job)


def history_prefix(job, **identity):
    path = history_path(job, **identity)
    return 'gs://' + path if path else None


def parse_run_ids(listing, prefix):
    """Sorted integer run ids among the direct children `<prefix>/<digits>/` of a listing."""
    head = prefix.rstrip('/') + '/'
    ids = set()
    for line in listing.splitlines():
        line = line.strip()
        if line.startswith(head) and line.endswith('/') and _number(line[len(head):-1]):
            ids.add(int(line[len(head):-1]))
    return sorted(ids)


def _detail(text):
    return (text or '').strip()[:DETAIL_LIMIT] or None


def _discard(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def select(job, build_id, dest, pull_number=None, repo_owner=None, repo_name=None, bucket=DEFAULT_BUCKET,
           mode=None, run=default_run):
    """Resolve the baseline for this attempt; returns the selection record (see module docstring).

    status: selected | no-preceding-attempt | history-unreadable | manifest-unavailable |
    manifest-ambiguous | manifest-unreadable | metadata-missing. Anything but `selected` leaves no file
    at `dest` and baseline_path null."""
    path = history_path(job, pull_number or None, repo_owner, repo_name, bucket)
    known = path is not None and _number(build_id)
    sel = {'mode': mode, 'status': None, 'reason': None, 'detail': None,
           'job': job or None, 'current_build_id': build_id or None, 'pull_number': pull_number or None,
           'history_url': 'gs://' + path if path else None,
           'current_run_url': 'https://prow.ci.openshift.org/view/gs/%s/%s' % (path, build_id) if known else None,
           'preceding_run_id': None, 'manifest_url': None, 'baseline_path': None}
    _discard(dest)

    def done(status, reason, detail=None):
        sel.update(status=status, reason=reason, detail=_detail(detail))
        return sel

    if not known:
        return done('metadata-missing', 'job name, numeric build id or pull-request identity missing; '
                                        'no history can be attributed to this run')
    prefix = sel['history_url']
    code, out, err = run(['gcloud', 'storage', 'ls', prefix + '/'])
    if code != 0:
        # partial output of a failed listing must never select a run
        return done('history-unreadable', 'job history could not be listed; preceding attempt unknown', err)
    preceding = [i for i in parse_run_ids(out, prefix) if i < int(build_id)]
    if not preceding:
        return done('no-preceding-attempt', 'no attempt precedes this build in the job history')
    latest = str(max(preceding))
    sel['preceding_run_id'] = latest
    pattern = '%s/%s/artifacts/*/%s/artifacts/%s' % (prefix, latest, STEP_NAME, MANIFEST_NAME)
    code, out, err = run(['gcloud', 'storage', 'ls', pattern])
    if code != 0:
        return done('manifest-unavailable', 'the latest preceding attempt has no readable manifest '
                                            '(absent or listing failed); older attempts are not used', err)
    found = sorted({line.strip() for line in out.splitlines()
                    if line.strip().startswith(prefix + '/' + latest + '/') and line.strip().endswith('/' + MANIFEST_NAME)})
    if len(found) != 1:
        return done('manifest-ambiguous' if found else 'manifest-unavailable',
                    'expected exactly one manifest in the latest preceding attempt, found %d' % len(found),
                    '\n'.join(found))
    sel['manifest_url'] = found[0]
    partial = dest + '.download'
    _discard(partial)
    code, _, err = run(['gcloud', 'storage', 'cp', found[0], partial])
    try:
        if code != 0:
            return done('manifest-unreadable', 'the manifest could not be downloaded', err)
        try:
            with open(partial, encoding='utf-8') as f:
                doc = json.load(f)
        except (OSError, ValueError) as e:
            return done('manifest-unreadable', 'the downloaded manifest is not readable JSON', str(e))
        if not isinstance(doc, dict):
            return done('manifest-unreadable', 'the downloaded manifest is not a JSON object')
        os.replace(partial, dest)
    finally:
        _discard(partial)
    sel['baseline_path'] = dest
    return done('selected', 'latest preceding attempt')


def _write_json(path, doc):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def _read(path):
    """(document, error): a JSON object or the reason it is unavailable."""
    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
    except FileNotFoundError:
        return None, 'absent'
    except (OSError, ValueError) as e:
        return None, 'unreadable: %s' % e
    if not isinstance(doc, dict):
        return None, 'not a JSON object'
    return doc, None


def _problems(doc, initial, validate, baseline=None):
    errs = ['%s differs from the runner\'s initial snapshot' % k for k in PROTECTED if doc.get(k) != initial.get(k)]
    errs += list(validate(doc))
    if errs:
        return errs
    import devel
    try:
        regenerated = devel.regroup(initial, {'groups': [
            {'coverage': c['members']['coverage'], 'signature': c['signature']} for c in doc['clusters']]}, baseline)
        actual = {c['id']: c for c in doc['clusters']}
        expected = {c['id']: c for c in regenerated['clusters']}
        if actual.keys() != expected.keys():
            return ['cluster ids differ from deterministic regroup']
        for cid, c in expected.items():
            for key in ('prior', 'signature', 'lineage', 'fingerprint', 'shape', 'blast_radius'):
                if actual[cid].get(key) != c.get(key):
                    errs.append('cluster %s %s differs from deterministic regroup' % (cid, key))
            for key, value in c['members'].items():
                if actual[cid]['members'].get(key) != value:
                    errs.append('cluster %s members.%s differs from deterministic regroup' % (cid, key))
        if doc.get('proposal_drafts', {}) != regenerated.get('proposal_drafts', {}):
            errs.append('proposal_drafts differs from referenced baseline drafts')
    except (ValueError, KeyError, TypeError) as exc:
        errs.append('cannot reproduce final groups: %s' % exc)
    return errs


def publish(initial, checkpoint, final, workdir, artifact_dir, validate=None, baseline=None):
    """Export the working documents and promote at most one trustworthy manifest; returns the status record.

    status: final (complete analysis promoted) | partial (valid progress promoted, investigation unfinished) |
    checkpoint (no agent manifest beyond the runner's
    checkpoint; the checkpoint was promoted) | invalid-final (the agent's manifest was rejected; the
    checkpoint was promoted and the rejected file kept as a diagnostic) | none (nothing trustworthy)."""
    import manifest
    if validate is None:
        validate = manifest.validate
    out = os.path.join(artifact_dir, MANIFEST_NAME)
    invalid = os.path.join(artifact_dir, 'triage-manifest.invalid.json')
    for path in (out, invalid):
        _discard(path)
    for name in WORKING_DOCUMENTS:
        src = os.path.join(workdir, name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(artifact_dir, name))
    if os.path.isfile(initial):
        shutil.copyfile(initial, os.path.join(artifact_dir, 'inventory-prepass.json'))

    status = {'status': 'none', 'promoted': None, 'errors': [], 'final': None, 'checkpoint': None,
              'clusters': None, 'unanalysed': None, 'sweep_pending': None}
    base, base_err = _read(initial)
    final_doc, final_err = _read(final)
    check_doc, check_err = _read(checkpoint)
    status['final'], status['checkpoint'] = final_err or 'read', check_err or 'read'
    final_errs = check_errs = None
    if base is None:
        status['errors'].append('runner snapshot %s; no manifest can be verified' % base_err)
    else:
        if final_doc is not None:
            final_errs = _problems(final_doc, base, validate, baseline)
        if check_doc is not None:
            check_errs = _problems(check_doc, base, validate, baseline)
    checkpoint_ok = check_errs == []
    rejected = final_err != 'absent' and (final_doc is None or final_errs != [])
    if rejected:
        if os.path.isfile(final):
            shutil.copyfile(final, invalid)
        status['errors'] += (['final manifest %s' % final_err] if final_doc is None else final_errs or [])[:40]
    chosen = None
    if final_errs == [] and final_doc != check_doc:
        status['status'], status['promoted'], chosen = 'final', 'final', final_doc
    elif checkpoint_ok:
        status['status'] = 'invalid-final' if rejected else 'checkpoint'
        status['promoted'], chosen = 'checkpoint', check_doc
    elif final_errs == []:
        # the agent's manifest equals a checkpoint we can no longer read back: still only a checkpoint
        status['status'], status['promoted'], chosen = 'checkpoint', 'checkpoint', final_doc
    if chosen is not None:
        clusters = chosen.get('clusters') or []
        status['clusters'] = len(clusters)
        status['unanalysed'] = sum(1 for c in clusters
                                   if isinstance(c, dict) and (c.get('disposition') or {}).get('state') == 'UNANALYSED')
        if status['status'] == 'final' and (status['unanalysed'] or chosen.get('unanalysed')):
            pending = [c for c in clusters if c.get('disposition', {}).get('state') == 'UNANALYSED']
            exhausted = {c['id'] for c in pending if c['disposition'].get('analysis', {}).get('evidence_unavailable')}
            listed = {e.get('cluster_id') for e in chosen.get('unanalysed', []) if isinstance(e, dict)}
            status['status'] = ('final-with-gaps' if pending and len(exhausted) == len(pending) and listed <= exhausted
                                else 'partial')
        status['sweep_pending'] = manifest.pending_sweep(chosen, base['inventory'])
        if status['status'] in ('final', 'final-with-gaps') and status['sweep_pending']:
            status['status'] = 'partial'
        _write_json(out, chosen)
    _write_json(os.path.join(artifact_dir, 'memory-publication.json'), status)
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('select')
    s.add_argument('--job', default='')
    s.add_argument('--build-id', default='')
    s.add_argument('--pull-number', default='')
    s.add_argument('--repo-owner', default='')
    s.add_argument('--repo-name', default='')
    s.add_argument('--bucket', default=DEFAULT_BUCKET)
    s.add_argument('--mode', choices=('record', 'reuse'))
    s.add_argument('--dest', required=True)
    s.add_argument('--out', required=True)
    p = sub.add_parser('publish')
    p.add_argument('--baseline', default='none')
    for k in ('initial', 'checkpoint', 'final', 'workdir', 'artifact-dir'):
        p.add_argument('--' + k, required=True)
    args = ap.parse_args(argv)
    try:
        if args.cmd == 'select':
            sel = select(args.job, args.build_id, args.dest, args.pull_number, args.repo_owner, args.repo_name,
                         args.bucket or DEFAULT_BUCKET, args.mode)
            _write_json(args.out, sel)
            print('Analysis memory baseline: %s (%s)%s' % (sel['status'], sel['reason'],
                                                         ': ' + sel['detail'] if sel['detail'] else ''), file=sys.stderr)
            print(sel['baseline_path'] or 'none')
            return 0
        baseline = None
        if args.baseline != 'none':
            baseline, error = _read(args.baseline)
            if error:
                print('baseline unavailable for publication verification: %s' % error, file=sys.stderr)
        status = publish(args.initial, args.checkpoint, args.final, args.workdir, args.artifact_dir, baseline=baseline)
    except OSError as e:
        print('error: %s' % e, file=sys.stderr)
        return 2
    for e in status['errors']:
        print(e, file=sys.stderr)
    print(status['status'])
    return 0 if status['status'] in ('final', 'final-with-gaps') else 1


if __name__ == '__main__':
    sys.exit(main())
