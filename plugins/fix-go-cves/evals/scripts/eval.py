#!/usr/bin/env python3
"""Prepare pinned checkouts and verify replay or live harness trials."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time

EVAL_ROOT = Path(__file__).resolve().parents[1]
INFRA = ('.claude', '.replay', '.staged-plugins', 'hooks', 'subagents', 'output')
AUDITS = ('scan-regression', 'existing-entries', 'fix-availability', 'yaml-integrity')


def repository_identity(url):
    match = re.fullmatch(r'https://github[.]com/([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9_.-]+)', url)
    if not match or match[2].removesuffix('.git') in ('', '.', '..'):
        raise ValueError('Fixture repository must be an explicit GitHub HTTPS repository URL')
    return match[1], match[2].removesuffix('.git')


def freeze_run(raw, dataset_root, run_dir, case_ids, project_root):
    """Write a selected, self-contained dataset and the config stock stages use."""
    import yaml

    case_ids = list(case_ids)
    if (not case_ids or len(set(case_ids)) != len(case_ids)
            or any(not re.fullmatch(r'case-[0-9]{3}', name) for name in case_ids)):
        raise ValueError('Select distinct case-NNN identifiers')
    dataset_root, run_dir = Path(dataset_root).resolve(), Path(run_dir).resolve()
    for name in case_ids:
        source = dataset_root / name
        if (source.is_symlink() or not source.is_dir()
                or any(path.is_symlink() for path in source.rglob('*'))):
            raise ValueError(f'Missing or linked fixture: {name}')
        for filename in ('input.yaml', 'annotations.yaml'):
            if not isinstance(yaml.safe_load((source / filename).read_text()), dict):
                raise ValueError(f'{name}/{filename} must contain a mapping')
    provenance = run_dir / 'provenance'
    provenance.mkdir(parents=True)  # Never replace the inputs of an existing run.
    for name in case_ids:
        shutil.copytree(dataset_root / name, provenance / 'cases' / name)
    raw['dataset']['path'] = 'cases'
    config = provenance / 'eval.yaml'
    config.write_text(yaml.safe_dump(raw, sort_keys=False))
    files = {str(path.relative_to(provenance)): digest(path)
             for path in sorted(provenance.rglob('*')) if path.is_file()}
    write_json(provenance / 'manifest.json', {
        'selected_cases': case_ids, 'project_root': str(Path(project_root).resolve()),
        'helper_sha256': digest(Path(__file__)),
        'files': files})
    return config


def snapshot(config_path, run_dir, case_ids, model=None):
    # Use the harness's loader and path rules, including any config overlays.
    from agent_eval.config import EvalConfig, load_raw, resolve_plugin_dir

    config = EvalConfig.from_yaml(config_path)
    raw, _ = load_raw(Path(config_path))
    raw.setdefault('runner', {})['plugin_dirs'] = [
        str(resolve_plugin_dir(config, path)) for path in config.runner.plugin_dirs]
    # Freeze explicit nonsecret paths without copying provider credentials.
    environment = raw['runner'].get('env', {})
    for name in ('DOCKER_HOST', 'GRYPE_DB_CACHE_DIR', 'GOMODCACHE', 'GOOGLE_APPLICATION_CREDENTIALS'):
        value = environment.get(name)
        if isinstance(value, str) and value.startswith('$'):
            environment[name] = os.environ.get(value[1:])
    if model:
        raw.setdefault('models', {})['skill'] = model
    judge_model = config.models.judge or os.environ.get('EVAL_JUDGE_MODEL')
    if judge_model:
        raw.setdefault('models', {})['judge'] = judge_model
    return freeze_run(raw, config.resolve_path(config.dataset.path), run_dir,
                      case_ids, config.project_root)


def frozen_inputs(run_dir):
    import yaml

    provenance = Path(run_dir).resolve() / 'provenance'
    manifest = read_json(provenance / 'manifest.json')
    cases = manifest['selected_cases']
    if (not isinstance(cases, list) or not cases or len(set(cases)) != len(cases)
            or any(not isinstance(name, str) or not re.fullmatch(r'case-[0-9]{3}', name)
                   for name in cases)):
        raise ValueError('Invalid frozen case selection')
    files = manifest['files']
    required = {'eval.yaml', *(f'cases/{case}/{name}' for case in cases
                              for name in ('input.yaml', 'annotations.yaml'))}
    if not isinstance(files, dict) or not required.issubset(files):
        raise ValueError('Incomplete frozen inputs')
    for name, expected in files.items():
        path = provenance / name
        if (path.is_symlink() or not path.resolve().is_relative_to(provenance)
                or digest(path) != expected):
            raise ValueError(f'Frozen input changed: {name}')
    config = yaml.safe_load((provenance / 'eval.yaml').read_text())
    return provenance, manifest, config


def check_reserved_paths(workspace):
    collisions = {PurePosixPath(name).parts[0]
                  for name in git(workspace, 'ls-files', '-z').split('\0') if name
                  and PurePosixPath(name).parts[0] in INFRA}
    if collisions:
        raise ValueError(f'Repository uses reserved eval paths: {sorted(collisions)}')


def run(*args, cwd=None, env=None):
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True,
                          check=True, timeout=600).stdout.strip()


def git(repo, *args):
    return run('git', '-C', str(repo), *args)


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plugin_hashes(plugin):
    return {str(p.relative_to(plugin)): digest(p) for p in sorted(plugin.rglob('*'))
            if p.is_file() and not p.is_symlink() and p.relative_to(plugin).parts[0] != 'bin'}


def unpack_plugin(archive, destination):
    allowed = {'.claude-plugin', 'skills', 'scripts', 'subagents', 'README.md'}
    with tarfile.open(archive) as tar:
        seen = set()
        for member in tar.getmembers():
            name = PurePosixPath(member.name)
            if (name.is_absolute() or '..' in name.parts or not name.parts
                    or name.parts[0] not in allowed or member.name in seen
                    or not (member.isfile() or member.isdir())):
                raise ValueError(f'Unsafe plugin archive entry: {member.name}')
            seen.add(member.name)
        tar.extractall(destination, filter='data')
    manifest = read_json(destination / '.claude-plugin/plugin.json')
    if set(manifest) != {'name', 'description', 'version', 'author'}:
        raise ValueError('Recorded plugin manifest may not enable hooks or servers')
    for audit in AUDITS:
        if not (destination / f'subagents/{audit}.sh').is_file():
            raise ValueError(f'Recorded plugin lacks audit: {audit}')


def case_data(source):
    import yaml

    data = yaml.safe_load((source / 'input.yaml').read_text())
    expected = yaml.safe_load((source / 'annotations.yaml').read_text())
    for field in ('base_commit', 'default_commit'):
        if not re.fullmatch('[0-9a-f]{40}', data[field]):
            raise ValueError(f'Invalid pin: {field}')
    live = data.get('mode') == 'live'
    if not live and not re.fullmatch('[0-9a-f]{40}', expected['result_commit']):
        raise ValueError('Invalid result commit')
    repository_identity(data['repository'])
    for branch in (data['base_branch'], data['default_branch'], data['original_branch'],
                   *([] if live else [expected['fix_branch']])):
        run('git', 'check-ref-format', '--branch', branch)
    return data, expected


def prepare(workspace, source):
    """Called by before_each, before the agent sees any fixture answers."""
    workspace, source = Path(workspace).resolve(), Path(source).resolve()
    if (workspace / 'go.mod').exists() or (workspace / '.replay').exists():
        raise ValueError('Refusing to overwrite an existing or already prepared checkout')
    data, expected = case_data(source)
    workspace.mkdir(parents=True, exist_ok=True)
    for child in workspace.iterdir():
        if child.is_symlink():
            child.unlink()  # Harness links into the answer-bearing project.
        elif child.name == '.git':
            shutil.rmtree(child)
        elif child.name == 'input.yaml':
            child.unlink()  # Args were resolved before before_each.
        elif child.name not in INFRA:
            raise ValueError(f'Unexpected harness workspace entry: {child.name}')
    settings = workspace / '.claude'
    if settings.exists():
        for child in settings.iterdir():
            if child.is_symlink():
                child.unlink()
    private = workspace / '.replay'
    private.mkdir(mode=0o700)
    (private / 'bin').mkdir()
    owner, repository = repository_identity(data['repository'])
    upstream = private / 'remotes' / owner / f'{repository}.git'
    upstream.parent.mkdir(parents=True)
    run('git', 'init', '--bare', str(upstream))
    for branch, commit in ((data['base_branch'], data['base_commit']),
                           (data['default_branch'], data['default_commit'])):
        # Only pinned history, no tags or later branch tips. Setup alone fetches.
        run('git', '-c', 'protocol.https.allow=always', '-C', str(upstream),
            'fetch', '--no-tags', data['repository'], f'{commit}:refs/heads/{branch}')
    git(upstream, 'symbolic-ref', 'HEAD', f'refs/heads/{data["default_branch"]}')
    fork = private / 'remotes/fork' / f'{repository}.git'
    fork.parent.mkdir(parents=True)
    run('git', 'clone', '--bare', '--no-local', str(upstream), str(fork))
    git(workspace, 'init')
    git(workspace, 'remote', 'add', 'origin', str(upstream))
    git(workspace, 'remote', 'add', 'fork', str(fork))
    git(workspace, 'fetch', '--no-tags', 'origin')
    git(workspace, 'checkout', '-b', data['original_branch'],
        f'origin/{data["default_branch"]}')
    check_reserved_paths(workspace)
    git(workspace, 'config', 'user.name', 'Eval')
    git(workspace, 'config', 'user.email', 'eval@example.invalid')
    control = workspace.parent.parent / 'control' / workspace.name
    runtime = control / 'runtime'
    for name in ('home', 'tmp'):
        (runtime / name).mkdir(parents=True)
    live = data.get('mode') == 'live'
    if not live:
        shutil.copy2(source / 'result.bundle', private / 'result.bundle')
        git(workspace, 'bundle', 'verify', str(private / 'result.bundle'))
        heads = git(workspace, 'bundle', 'list-heads', str(private / 'result.bundle')).splitlines()
        matching = [line.split()[1] for line in heads
                    if line.split()[0] == expected['result_commit']]
        if len(matching) != 1:
            raise ValueError('Bundle must advertise the one recorded result')
        git(workspace, 'fetch', str(private / 'result.bundle'), matching[0])
        if git(workspace, 'rev-parse', f'{expected["result_commit"]}^') != data['base_commit']:
            raise ValueError('Pilot result must have the pinned base as its sole parent')
    (workspace / '.git/info/exclude').write_text(
        '\n'.join(f'/{name}/' for name in INFRA) + '\n/.hook-outputs.json\n')
    plugin = workspace / '.staged-plugins/fix-go-cves'
    plugin.mkdir(parents=True)
    if live:
        for name in ('.claude-plugin', 'skills', 'scripts', 'subagents'):
            shutil.copytree(EVAL_ROOT.parent / name, plugin / name)
        shutil.copy2(EVAL_ROOT.parent / 'README.md', plugin / 'README.md')
    else:
        unpack_plugin(source / 'plugin.tar.gz', plugin)
    shutil.copy2(EVAL_ROOT.parent / 'skills/fix-go-cves/SKILL.md',
                 plugin / 'skills/fix-go-cves/SKILL.md')
    shutil.copy2(__file__, private / 'driver.py')
    fix_all = plugin / 'scripts/fix-all.sh'
    original = fix_all.read_text()
    if live:
        # The real runtime may download its own scanner into plugin/bin. Keep
        # tools and caches outside the checkout so scans cover application artifacts.
        shutil.copytree(plugin, runtime / 'plugin')
    fix_all.write_text('#!/usr/bin/env bash\nexec ' + shlex.quote(sys.executable)
                       + ' ' + shlex.quote(str(private / 'driver.py'))
                       + ' replay "$@"\n\n# Recorded implementation follows.\n' + original)
    fix_all.chmod(0o755)
    if not live:
        log = gzip.decompress((source / 'run.log.gz').read_bytes()).decode()
        log = log.replace('{{REPO}}', str(workspace)).replace('{{HOME}}', str(runtime / 'home'))
        (private / 'run.log').write_text(log)
    shim = private / 'bin/gh'
    shim.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(private / 'gh.log')
                    + '"\nexit 97\n')
    shim.chmod(0o755)
    meta = dict(data)
    meta['runtime_dir'] = str(runtime)
    if not live:
        meta.update(result_commit=expected['result_commit'], fix_branch=expected['fix_branch'],
                    exit_code=expected['exit_code'])
    write_json(private / 'meta.json', meta)
    baseline = {'workspace': str(workspace), 'source': str(source), 'runtime_dir': str(runtime),
                'plugin_hashes': plugin_hashes(plugin), 'meta': meta,
                'refs': {str(p): git(p, 'show-ref') for p in (upstream, fork)}}
    if live:
        baseline['runtime_plugin_hashes'] = plugin_hashes(runtime / 'plugin')
    # Outside the agent workspace: capture compares against trusted setup state.
    write_json(control / 'baseline.json', baseline)
    hook_env = {'HOME': str(runtime / 'home'), 'TMPDIR': str(runtime / 'tmp'),
                'PATH': str(private / 'bin') + ':' + os.environ['PATH']}
    write_json(workspace / '.hook-outputs.json', {'env': hook_env,
               'data': {'workspace': str(workspace), 'case_source': str(source),
                        'plugin_hashes': baseline['plugin_hashes']}})
    print(f'Prepared {workspace.name}: pinned real checkout, {"live runtime" if live else "recorded replay"}')
    return baseline


def replay(arguments):
    workspace = Path(__file__).resolve().parent.parent
    meta = read_json(workspace / '.replay/meta.json')
    witnesses = Path(meta['runtime_dir']) if meta.get('mode') == 'live' else workspace / '.replay'
    calls = witnesses / 'invocations.jsonl'
    previous = calls.read_text().splitlines() if calls.exists() else []
    with calls.open('a') as stream:
        stream.write(json.dumps({'arguments': arguments, 'time': time.time()}) + '\n')
    if previous or not requested_arguments(arguments, meta, workspace):
        raise ValueError('Script must run once with the requested branch')
    if (git(workspace, 'rev-parse', 'HEAD') != meta['default_commit']
            or git(workspace, 'status', '--porcelain')):
        raise ValueError('Checkout changed before invocation')
    if meta.get('mode') == 'live':
        return live_run(workspace, arguments)
    git(workspace, 'checkout', '-b', meta['fix_branch'], meta['result_commit'])
    print((workspace / '.replay/run.log').read_text(), end='')
    return meta['exit_code']


def live_run(workspace, arguments):
    """Tee the actual runtime output; never substitute a recorded result."""
    runtime = Path(read_json(workspace / '.replay/meta.json')['runtime_dir'])
    script = runtime / 'plugin/scripts/fix-all.sh'
    with (runtime / 'run.log').open('w') as log:
        with subprocess.Popen(['bash', str(script), *arguments], cwd=workspace,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, bufsize=1) as process:
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end='', flush=True)
            status = process.wait()
    write_json(runtime / 'status.json', {
        'exit_code': status, 'head': git(workspace, 'rev-parse', 'HEAD'),
        'branch': git(workspace, 'branch', '--show-current'),
        'ignored_snapshot': ignored_snapshot(workspace)})
    return status


def requested_arguments(arguments, meta, workspace):
    arguments = list(arguments)
    for index, value in enumerate(arguments):
        candidate = Path(value) if value.startswith('/') else workspace / value
        if (value == '.' or value.startswith('/')) and candidate.resolve() == workspace:
            del arguments[index]
            break
    return arguments in (meta['arguments'], [meta['base_branch']])


def ignored_snapshot(workspace):
    """Fingerprint native ignored outputs at the runtime/agent boundary."""
    snapshot = {}
    for name in git(workspace, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z').split('\0'):
        if not name or PurePosixPath(name).parts[0] in INFRA:
            continue
        path = workspace / name
        if path.is_symlink():
            snapshot[name] = 'symlink:' + os.readlink(path)
        elif path.is_file():
            snapshot[name] = digest(path)
        else:
            raise ValueError(f'Cannot fingerprint ignored output: {name}')
    return snapshot


def capture(workspace):
    workspace = Path(workspace).resolve()
    baseline = read_json(workspace.parent.parent / 'control' / workspace.name / 'baseline.json')
    private = workspace / '.replay'
    witnesses = Path(baseline['runtime_dir']) if baseline['meta'].get('mode') == 'live' else private
    calls = witnesses / 'invocations.jsonl'
    ignored = ignored_snapshot(workspace)
    refs_unchanged = True
    for path, refs in baseline['refs'].items():
        try:
            refs_unchanged = git(Path(path), 'show-ref') == refs and refs_unchanged
        except subprocess.CalledProcessError:
            refs_unchanged = False  # Deleted/damaged remotes are a contract failure.
    state = {'head': git(workspace, 'rev-parse', 'HEAD'),
             'branch': git(workspace, 'branch', '--show-current'),
             'dirty': git(workspace, 'status', '--porcelain', '--untracked-files=all'),
             'unexpected_ignored': list(ignored),
             'invocations': [json.loads(line) for line in calls.read_text().splitlines()]
                            if calls.exists() else [],
             'gh_calls': (private / 'gh.log').read_text() if (private / 'gh.log').exists() else '',
             'plugin_unchanged': plugin_hashes(workspace / '.staged-plugins/fix-go-cves')
                                 == baseline['plugin_hashes'],
             'refs_unchanged': refs_unchanged,
             'expected': baseline['meta'], 'workspace': str(workspace)}
    if state['expected'].get('mode') == 'live':
        status = witnesses / 'status.json'
        completion = read_json(status) if status.exists() else {}
        state['runtime_exit'] = completion.get('exit_code')
        state['runtime_head'] = completion.get('head')
        state['runtime_branch'] = completion.get('branch')
        state['runtime_ignored_snapshot'] = completion.get('ignored_snapshot')
        state['ignored_snapshot'] = ignored
        state['runtime_plugin_unchanged'] = plugin_hashes(Path(baseline['runtime_dir']) / 'plugin') == baseline['runtime_plugin_hashes']
        original = state['branch'] == state['expected']['original_branch'] and state['head'] == state['expected']['default_commit']
        state['changed_files'] = [] if original else git(workspace, 'diff', '--name-only',
                                                       state['expected']['base_commit'], 'HEAD').splitlines()
        log_path = witnesses / 'run.log'
        log = log_path.read_text() if log_path.exists() else ''
        (workspace / 'output').mkdir(exist_ok=True)
        shutil.copy2(log_path, workspace / 'output/run.log') if log else None
        # Keep diagnostic context while dropping repetitive scanner progress.
        lines = log.splitlines()
        selected = set()
        pattern = r'^(--- |Fix branch:|Fixed:|FIXED:|IGNORED:|NEEDS_REVIEW:|ERROR:|TIMEOUT:|WARNING:|NOT READY|POLICY|Clean:|No CVEs|PR command|[0-9a-f]{7,40} )|\.go:[0-9]+:|FAIL|failed|timed out|not detected'
        for index, line in enumerate(lines):
            if re.search(pattern, line):
                selected.update(range(max(0, index - 2), min(len(lines), index + 4)))
        evidence = (f'Runtime exit: {state["runtime_exit"]}\n'
                    f'Runtime HEAD: {state["runtime_head"]}\n'
                    f'Runtime branch: {state["runtime_branch"]}\n'
                    f'Captured HEAD: {state["head"]}\n'
                    f'Captured branch: {state["branch"]}\n\n'
                    + '\n'.join(lines[index] for index in sorted(selected)))
        (workspace / 'output/evidence.txt').write_text(evidence + '\n')
        state['runtime_summary'] = '--- Summary:' in log or 'No CVEs found.' in log
    write_json(workspace / 'output/state.json', state)


def events(path):
    result = []
    for line in path.read_text().splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(value)
    return result


def final_reply(stream):
    results = [event for event in stream if event.get('type') == 'result']
    if not results or results[-1].get('is_error') or not results[-1].get('result', '').strip():
        raise ValueError('Missing or errored final completed response')
    return results[-1]['result']


def trace_violations(stream, workspace):
    # Only case-owned runtime files are readable outside the checkout. The
    # trusted baseline and neighboring cases remain outside this allowance.
    runtime = workspace.parent.parent / 'control' / workspace.name / 'runtime'
    allowed = (workspace.resolve(), runtime.resolve())
    violations = []
    for event in stream:
        for item in event.get('message', {}).get('content', []):
            if not isinstance(item, dict) or item.get('type') != 'tool_use':
                continue
            name, value = item.get('name', ''), item.get('input', {})
            command = value.get('command', '')
            if name in ('Agent', 'Task', 'WebFetch', 'WebSearch') or name.startswith('mcp__'):
                violations.append(f'Out-of-scope tool: {name}')
            lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()')
            lexer.whitespace_split = True
            try:
                tokens = list(lexer)
            except ValueError:
                tokens = []
            forbidden = 'gh' in tokens
            for index, token in enumerate(tokens):
                if token != 'git':
                    continue
                index += 1
                while index < len(tokens) and tokens[index].startswith('-'):
                    index += 2 if tokens[index] in ('-C', '-c', '--git-dir', '--work-tree') else 1
                if index < len(tokens) and tokens[index] in ('push', 'stash', 'clean'):
                    forbidden = True
            if forbidden:
                violations.append('Attempted publication or destructive git operation')
            path = value.get('file_path', value.get('path', ''))
            if name == 'Read' and path:
                candidate = Path(path)
                if not candidate.is_absolute():
                    candidate = workspace / candidate
                if not any(candidate.resolve().is_relative_to(root) for root in allowed):
                    violations.append('Read outside the case workspace')
            # Detect ordinary direct reads of the answer-bearing checkout and
            # trusted eval controls, even when another argument is permitted.
            for prefix, reason in (
                    (str(EVAL_ROOT.parents[2]), 'Command accesses the source checkout'),
                    (str(runtime.parent.parent), 'Command accesses protected eval control files')):
                for path in re.findall(re.escape(prefix) + r'''[^\s'";|<>]*''', command):
                    if not any(Path(path).resolve().is_relative_to(root) for root in allowed):
                        violations.append(reason)
    return violations


def extract(run_dir):
    cases = sorted((Path(run_dir) / 'cases').glob('case-*'))
    if not cases:
        raise ValueError('No completed case outputs')
    for case in cases:
        stream = events(case / 'stdout.log')
        output = case / 'output'
        state = read_json(output / 'state.json')
        result = read_json(case / 'run_result.json')
        if result.get('error') or result.get('exit_code') != 0:
            raise ValueError(f'{case.name}: agent did not complete successfully')
        state['trace_violations'] = trace_violations(stream, Path(state['workspace']))
        state['permission_denials'] = result.get('permission_denials', [])
        write_json(output / 'state.json', state)
        (output / 'reply.md').write_text(final_reply(stream) + '\n')


def check(case_dir, live=False):
    import yaml

    case = Path(case_dir)
    state = read_json(case / 'output/state.json')
    reply = (case / 'output/reply.md').read_text()
    expected = state['expected']
    blocks = '\n'.join(re.findall(r'(?ms)^```[^\n]*\n(.*?)^```', reply))
    conditions = {
        'clean checkout': not state['dirty'] and not state['unexpected_ignored'],
        'one requested invocation': len(state['invocations']) == 1 and
            requested_arguments(state['invocations'][0]['arguments'], expected,
                                Path(state.get('workspace', '/unused-workspace'))),
        'remotes and plugin unchanged': state['refs_unchanged'] and state['plugin_unchanged'],
        'no forbidden operations': not state['gh_calls'] and not state['trace_violations']
                                   and not state['permission_denials'],
        'no invented publication command': not re.search(r'\bgh\s+pr\s+create\b|\bgit\s+push\b', blocks),
    }
    if live:
        # Native builds/tests legitimately create ignored files. Require the
        # exact completed runtime state rather than a filename allowance.
        conditions['clean checkout'] = not state['dirty']
        recorded_ignored = state.get('runtime_ignored_snapshot')
        conditions['runtime ignored-output measurement recorded'] = isinstance(recorded_ignored, dict)
        if isinstance(recorded_ignored, dict):
            conditions['runtime ignored outputs retained'] = state['ignored_snapshot'] == recorded_ignored
        conditions['actual runtime completed'] = state['runtime_exit'] in (0, 2) and state['runtime_summary']
        conditions['runtime result retained'] = state['head'] == state['runtime_head'] and state['branch'] == state['runtime_branch']
        conditions['runtime plugin unchanged'] = state['runtime_plugin_unchanged']
        conditions['dependency-only changes'] = all(re.search(
            r'(^|/)(go\.(mod|sum)|\.grype\.yaml)$|^go\.work(\.sum)?$|(^|/)vendor/', name)
            for name in state['changed_files'])
    else:
        conditions['recorded result/branch'] = state['head'] == expected['result_commit'] and state['branch'] == expected['fix_branch']
    provenance, manifest, _ = frozen_inputs(case.parent.parent)
    if case.name not in manifest['selected_cases']:
        raise ValueError(f'Unselected case: {case.name}')
    source = provenance / 'cases' / case.name
    data = yaml.safe_load((source / 'input.yaml').read_text())
    if (data.get('mode') == 'live') != live:
        raise ValueError(f'{case.name}: wrong evaluation track')
    annotation = yaml.safe_load((source / 'annotations.yaml').read_text())
    hashes = re.findall(r'\b[0-9a-f]{7,40}\b', reply)
    for commit in annotation.get('required_commits', []):
        conditions[f'commit {commit[:7]} reported'] = any(commit.startswith(value) for value in hashes)
    failures = [name for name, ok in conditions.items() if not ok]
    return {'passed': not failures, 'reason': '; '.join(failures) if failures else 'Contract satisfied'}


def verify(run_dir, live=False):
    import yaml

    _, manifest, config = frozen_inputs(run_dir)
    summary = yaml.safe_load((Path(run_dir) / 'summary.yaml').read_text())
    per_case = summary.get('per_case', {})
    if not isinstance(per_case, dict) or set(per_case) != set(manifest['selected_cases']):
        raise ValueError('Judge results do not match the selected cases')
    expected = {}
    for judge in config['judges']:
        name = judge['name']
        if name in expected:
            raise ValueError(f'Duplicate configured judge: {name}')
        stochastic = any(judge.get(key) for key in ('prompt', 'prompt_file', 'llm_rubric', 'agent'))
        expected[name] = max(1, judge.get('samples', 1)) if stochastic else 1
    if not expected:
        raise ValueError('No configured judges')
    for case, judges in per_case.items():
        if not isinstance(judges, dict) or set(judges) != set(expected):
            raise ValueError(f'{case}: judge results do not match the configured judges')
        for name, samples in expected.items():
            result = judges[name]
            if not isinstance(result, dict) or type(result.get('value')) is not bool or result.get('error'):
                raise ValueError(f'{case}/{name}: missing or errored verdict')
            if samples > 1:
                stability = result.get('stability', {})
                if not isinstance(stability, dict):
                    raise ValueError(f'{case}/{name}: malformed judge samples')
                values = stability.get('values', [])
                if (type(stability.get('samples')) is not int or stability['samples'] != samples
                        or type(stability.get('error_count')) is not int or stability['error_count'] != 0
                        or not isinstance(values, list) or len(values) != samples
                        or any(type(value) is not bool for value in values)
                        or result['value'] != (sum(values) * 2 > samples)):
                    raise ValueError(f'{case}/{name}: incomplete judge samples')
    print('All requested judge results and samples completed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('snapshot', 'prepare', 'replay', 'capture', 'extract', 'check', 'verify', 'dry-run'))
    parser.add_argument('--config', type=Path)
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--model')
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--case-source', type=Path, default=EVAL_ROOT / 'cases/case-005')
    parser.add_argument('--case-dir', type=Path)
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--live', action='store_true')
    args, extra = parser.parse_known_args()
    if args.command == 'replay':
        return replay(extra)
    if extra:
        parser.error(f'Unexpected arguments: {extra}')
    if args.command == 'snapshot':
        print(snapshot(args.config, args.run_dir, args.cases or [], args.model))
    elif args.command == 'prepare':
        prepare(os.environ['CASE_WORKSPACE'], os.environ['CASE_SOURCE_DIR'])
    elif args.command == 'capture':
        capture(os.environ['CASE_WORKSPACE'])
    elif args.command == 'extract':
        extract(args.run_dir)
    elif args.command == 'check':
        print(json.dumps(check(args.case_dir, args.live)))
    elif args.command == 'verify':
        verify(args.run_dir, args.live)
    else:
        if not args.prepare_only and case_data(args.case_source)[0].get('mode') == 'live':
            raise ValueError('A model-free dry-run may replay recordings only; use --prepare-only for live cases')
        workspace = args.workspace.resolve()
        case = workspace / 'cases' / args.case_source.name
        prepare(case, args.case_source)
        if not args.prepare_only:
            hook_env = read_json(case / '.hook-outputs.json')['env']
            (case / '.hook-outputs.json').unlink()
            meta = read_json(case / '.replay/meta.json')
            command = ['bash', str(case / '.staged-plugins/fix-go-cves/scripts/fix-all.sh'),
                       *meta['arguments']]
            result = subprocess.run(command, cwd=case, env={**os.environ, **hook_env},
                                    capture_output=True, text=True)
            expected = meta['exit_code']
            if result.returncode != expected:
                raise ValueError(f'Replay exited {result.returncode}, expected {expected}: {result.stderr}')
            capture(case)
            state = read_json(case / 'output/state.json')
            if (state['head'] != state['expected']['result_commit'] or state['dirty']
                    or state['unexpected_ignored'] or len(state['invocations']) != 1
                    or not state['plugin_unchanged'] or not state['refs_unchanged']):
                raise ValueError('Model-free replay did not preserve the expected repository state')
            print(f'Model-free replay retained {git(case, "rev-parse", "--short", "HEAD")} (exit {expected})')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
