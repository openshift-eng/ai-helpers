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
import stat
import subprocess
import sys
import tarfile
import textwrap
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
    plugin = provenance / 'fix-go-cves'
    for name in ('.claude-plugin', 'skills', 'scripts', 'subagents'):
        source = EVAL_ROOT.parent / name
        # Copies must not silently follow a changed source link.
        if source.is_symlink() or any(path.is_symlink() for path in source.rglob('*') if not source_cache(path.relative_to(source))):
            raise ValueError(f'Linked plugin source: {source}')
        shutil.copytree(source, plugin / name, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '*.pyc'))
    if (EVAL_ROOT.parent / 'README.md').is_symlink():
        raise ValueError('Linked plugin README')
    shutil.copy2(EVAL_ROOT.parent / 'README.md', plugin / 'README.md')
    helper = plugin / 'evals/scripts/eval.py'
    helper.parent.mkdir(parents=True)
    shutil.copy2(__file__, helper)
    interpreter = os.environ.get('CVE_EVAL_PYTHON', sys.executable)
    if not Path(interpreter).is_absolute() or not os.access(interpreter, os.X_OK):
        raise ValueError('CVE_EVAL_PYTHON must name an absolute executable interpreter')
    # Keep the venv entrypoint: resolving its symlink would lose its packages.
    interpreter = str(Path(interpreter).absolute())
    for hooks in raw.get('hooks', {}).values():
        for hook in hooks:
            command = hook['command']
            match = re.search(r'python3\s+[^\n]+?/evals/scripts/eval[.]py[\"\']?', command)
            if not match:
                raise ValueError('Unrecognized eval lifecycle hook')
            hook['command'] = command[:match.start()] + shlex.join([interpreter, str(helper)]) + command[match.end():]
    for judge in raw.get('judges', []):
        if 'check' in judge:
            judge['check'], replacements = re.subn(
                r'helper = pathlib[.]Path[.]cwd\(\) / [\"\']plugins/fix-go-cves/evals/scripts/eval[.]py[\"\']',
                'helper = pathlib.Path(' + repr(str(helper)) + ')', judge['check'])
            if 'eval.py' in judge['check'] and replacements != 1:
                raise ValueError('Unrecognized deterministic eval helper')
            judge['check'] = judge['check'].replace('[sys.executable, str(helper)',
                                                  '[' + repr(interpreter) + ', str(helper)')
    if 'runner' in raw:
        raw['runner']['plugin_dirs'] = [str(plugin)]
    raw['dataset']['path'] = 'cases'
    config = provenance / 'eval.yaml'
    config.write_text(yaml.safe_dump(raw, sort_keys=False))
    files = {str(path.relative_to(provenance)): file_identity(path)
             for path in sorted(provenance.rglob('*')) if path.is_file() and not source_cache(path.relative_to(provenance))}
    write_json(provenance / 'manifest.json', {
        'selected_cases': case_ids, 'project_root': str(Path(project_root).resolve()),
        'helper_sha256': digest(Path(__file__)),
        'interpreter': interpreter_identity(interpreter),
        'files': files})
    return config


def snapshot(config_path, run_dir, case_ids, model=None, live=False):
    # Use the harness's loader and path rules, including any config overlays.
    from agent_eval.config import EvalConfig, load_raw, resolve_plugin_dir
    from agent_eval import config as harness_config

    config = EvalConfig.from_yaml(config_path)
    raw, _ = load_raw(Path(config_path))
    contract = 'live_contract' if live else 'replay_contract'
    if contract not in {judge.get('name') for judge in raw.get('judges', [])}:
        raise ValueError('Selected profile does not match the evaluation track')
    import yaml
    for name in case_ids:
        if not re.fullmatch(r'case-[0-9]{3}', name):
            raise ValueError('Select case-NNN identifiers')
        data = yaml.safe_load((config.resolve_path(config.dataset.path) / name / 'input.yaml').read_text())
        if (data.get('mode') == 'live') != live:
            raise ValueError(f'{name}: case does not match the evaluation track')
    plugins = [Path(resolve_plugin_dir(config, path)).resolve()
               for path in config.runner.plugin_dirs]
    if plugins != [EVAL_ROOT.parent.resolve()]:
        raise ValueError('The eval requires exactly the current fix-go-cves plugin')
    raw.setdefault('runner', {})['plugin_dirs'] = list(map(str, plugins))
    # Freeze explicit nonsecret settings without copying provider credentials.
    environment = raw['runner'].get('env', {})
    for name in ('DOCKER_HOST', 'GRYPE_DB_CACHE_DIR', 'GOMODCACHE', 'GOOGLE_APPLICATION_CREDENTIALS', 'GOMAXPROCS', 'DAPPER_ENV', 'DAPPER_ARGS', 'CVE_FIX_TEST_CMD', 'CVE_FIX_GO_MINOR_GUARD', 'CVE_FIX_K8S_VERSION_GUARD', 'CVE_FIX_GRYPE_VERSION'):
        value = environment.get(name)
        if isinstance(value, str) and value.startswith('$'):
            environment[name] = os.environ.get(value[1:])
    if model:
        raw.setdefault('models', {})['skill'] = model
    judge_model = config.models.judge or os.environ.get('EVAL_JUDGE_MODEL')
    if judge_model:
        raw.setdefault('models', {})['judge'] = judge_model
    frozen = freeze_run(raw, config.resolve_path(config.dataset.path), run_dir,
                        case_ids, config.project_root)
    manifest = read_json(frozen.parent / 'manifest.json')
    manifest['source_revision'] = git(config.project_root, 'rev-parse', 'HEAD')
    manifest['source_status'] = git(config.project_root, 'status', '--porcelain')
    if getattr(harness_config, '__file__', None):
        harness = Path(git(Path(harness_config.__file__).parent, 'rev-parse', '--show-toplevel'))
        manifest['harness'] = {
            'root': str(harness), 'revision': git(harness, 'rev-parse', 'HEAD'),
            'status': git(harness, 'status', '--porcelain'),
            'diff_sha256': hashlib.sha256(git(harness, 'diff', '--binary', 'HEAD').encode()).hexdigest(),
            'code': harness_files(harness)}
    write_json(frozen.parent / 'manifest.json', manifest)
    return frozen


def frozen_inputs(run_dir):
    import yaml

    provenance = Path(run_dir).resolve() / 'provenance'
    if provenance.is_symlink() or (provenance / 'manifest.json').is_symlink():
        raise ValueError('Linked frozen inputs')
    manifest = read_json(provenance / 'manifest.json')
    cases = manifest['selected_cases']
    if (not isinstance(cases, list) or not cases or len(set(cases)) != len(cases)
            or any(not isinstance(name, str) or not re.fullmatch(r'case-[0-9]{3}', name)
                   for name in cases)):
        raise ValueError('Invalid frozen case selection')
    if manifest.get('helper_sha256') != digest(__file__):
        raise ValueError('Scoring helper changed since inputs were frozen')
    if manifest.get('interpreter') != interpreter_identity(manifest['interpreter']['entrypoint']):
        raise ValueError('Selected interpreter changed since inputs were frozen')
    if 'harness' in manifest:
        harness = manifest['harness']
        if harness_files(Path(harness['root'])) != harness['code']:
            raise ValueError('Selected harness changed since inputs were frozen')
    files = manifest['files']
    required = {'eval.yaml', *(f'cases/{case}/{name}' for case in cases
                              for name in ('input.yaml', 'annotations.yaml'))}
    if not isinstance(files, dict) or not required.issubset(files):
        raise ValueError('Incomplete frozen inputs')
    current = {}
    for path in sorted(provenance.rglob('*')):
        if path == provenance / 'manifest.json' or source_cache(path.relative_to(provenance)):
            continue
        if path.is_symlink():
            raise ValueError(f'Frozen input changed: {path.relative_to(provenance)}')
        if path.is_file():
            current[str(path.relative_to(provenance))] = file_identity(path)
    if current != files:
        changed = next(name for name in sorted(current.keys() | files.keys())
                       if current.get(name) != files.get(name))
        raise ValueError(f'Frozen input changed: {changed}')
    config = yaml.safe_load((provenance / 'eval.yaml').read_text())
    return provenance, manifest, config


def frozen_expectations(case, source=None):
    """Use the original case, never collected runtime state, as grading authority."""
    import yaml

    case = Path(case)
    run_dir = Path(source).parent.parent.parent if source is not None else case.parent.parent
    provenance, manifest, _ = frozen_inputs(run_dir)
    if case.name not in manifest['selected_cases']:
        raise ValueError(f'Unselected case: {case.name}')
    source = provenance / 'cases' / case.name
    expected = yaml.safe_load((source / 'input.yaml').read_text())
    if expected.get('mode') != 'live':
        annotations = yaml.safe_load((source / 'annotations.yaml').read_text())
        expected.update({key: annotations[key] for key in ('result_commit', 'fix_branch', 'exit_code')})
    return expected


def expectations_match(collected, expected):
    # Runtime paths describe where to collect facts, not what those facts must mean.
    return (isinstance(collected, dict)
            and {key: value for key, value in collected.items() if key != 'runtime_dir'} == expected)


def check_reserved_paths(workspace, ref=None):
    paths = (git(workspace, 'ls-tree', '-rz', '--name-only', ref) if ref
             else git(workspace, 'ls-files', '-z'))
    collisions = {PurePosixPath(name).parts[0]
                  for name in paths.split('\0') if name
                  and PurePosixPath(name).parts[0] in INFRA}
    if collisions:
        pin = f' at {ref}' if ref else ''
        raise ValueError(f'Repository uses reserved eval paths{pin}: {sorted(collisions)}')


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


def harness_files(root):
    return {str(path.relative_to(root)): file_identity(path)
            for base in ('agent_eval', 'skills/eval-run/scripts')
            for path in sorted((root / base).rglob('*.py'))}


def interpreter_identity(path):
    script = ('import importlib.metadata,json,platform; import yaml; '
              'assert yaml.CSafeLoader; '
              'print(json.dumps({"version":platform.python_version(),"packages":'
              'sorted(set((d.metadata["Name"],d.version) for d in importlib.metadata.distributions()))}))')
    return {'entrypoint': str(path), 'executable': str(Path(path).resolve()),
            'sha256': digest(path), **json.loads(run(str(path), '-c', script))}


def file_identity(path):
    path = Path(path)
    if path.is_symlink():
        return {'kind': 'symlink', 'target': os.readlink(path)}
    if not path.is_file():
        raise ValueError(f'Not a regular file: {path}')
    return {'kind': 'file', 'sha256': digest(path), 'mode': stat.S_IMODE(path.stat().st_mode)}


def source_cache(path):
    return bool({'__pycache__', '.pytest_cache'}.intersection(Path(path).parts)) or Path(path).suffix == '.pyc'


def plugin_hashes(plugin):
    result = {}
    for path in sorted(Path(plugin).rglob('*')):
        if path.relative_to(plugin).parts[0] == 'bin' or source_cache(path.relative_to(plugin)):
            continue
        if path.is_symlink():
            raise ValueError(f'Linked plugin source: {path}')
        if path.is_file():
            result[str(path.relative_to(plugin))] = file_identity(path)
    return result


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
    provenance, manifest, _ = frozen_inputs(source.parent.parent.parent)
    if (source != provenance / 'cases' / source.name
            or source.name not in manifest['selected_cases'] or workspace.name != source.name):
        raise ValueError('Preparation must use the selected frozen case')
    frozen_plugin = provenance / 'fix-go-cves'
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
    upstream = private / 'remotes/upstream' / owner / f'{repository}.git'
    upstream.parent.mkdir(parents=True)
    run('git', 'init', '--bare', str(upstream))
    for branch, commit in ((data['base_branch'], data['base_commit']),
                           (data['default_branch'], data['default_commit'])):
        # Only pinned history, no tags or later branch tips. Setup alone fetches.
        run('git', '-c', 'protocol.https.allow=always', '-C', str(upstream),
            'fetch', '--no-tags', data['repository'], f'{commit}:refs/heads/{branch}')
    for commit in dict.fromkeys((data['base_commit'], data['default_commit'])):
        check_reserved_paths(upstream, commit)
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
            shutil.copytree(frozen_plugin / name, plugin / name)
        shutil.copy2(frozen_plugin / 'README.md', plugin / 'README.md')
    else:
        unpack_plugin(source / 'plugin.tar.gz', plugin)
    if not live:
        # Replay the historical engine with the complete current invoking skill.
        current_skill = plugin / 'skills/fix-go-cves'
        if current_skill.exists():
            shutil.rmtree(current_skill)
        shutil.copytree(frozen_plugin / 'skills/fix-go-cves', current_skill)
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


def without_recorded_exit(log, exit_code):
    """The recording's capture status belongs to the invoking wrapper, not stdout."""
    if type(exit_code) is int:
        return re.sub(rf'(?m)^exit={exit_code}\n?\Z', '', log)
    return log


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
    print(without_recorded_exit((workspace / '.replay/run.log').read_text(), meta['exit_code']), end='')
    return meta['exit_code']


def file_hashes(directory):
    hashes = {}
    for path in sorted(Path(directory).rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Linked runtime evidence: {path}')
        if path.is_file():
            hashes[str(path.relative_to(directory))] = digest(path)
    return hashes


def runtime_environment():
    """Observe tool identities without serializing the process environment."""
    scanner = shutil.which('grype')
    result = {'docker_host': os.environ.get('DOCKER_HOST'),
              'gomaxprocs': os.environ.get('GOMAXPROCS'), 'dapper_env': os.environ.get('DAPPER_ENV'),
              'scanner_path': scanner, 'scanner_sha256': digest(scanner) if scanner else None}
    for name, command in (
            ('scanner_version', ['grype', 'version', '-o', 'json']),
            ('builder_images', ['docker', 'image', 'ls', '--no-trunc', '--digests',
                                '--format', '{{json .}}'])):
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=30)
            result[name] = {'exit_code': process.returncode, 'stdout': process.stdout}
        except (OSError, subprocess.TimeoutExpired) as exc:
            result[name] = {'error': type(exc).__name__}
    return result


def live_run(workspace, arguments):
    """Tee the actual runtime output; never substitute a recorded result."""
    runtime = Path(read_json(workspace / '.replay/meta.json')['runtime_dir'])
    script = runtime / 'plugin/scripts/fix-all.sh'
    before = runtime_environment()
    environment = dict(os.environ, CVE_FIX_EVIDENCE_DIR=str(runtime / 'evidence'))
    with (runtime / 'run.log').open('w') as log:
        with subprocess.Popen(['bash', str(script), *arguments], cwd=workspace, env=environment,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, bufsize=1) as process:
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end='', flush=True)
            status = process.wait()
    write_json(runtime / 'evidence/environment.json', {'before': before, 'after': runtime_environment()})
    write_json(runtime / 'status.json', {
        'exit_code': status, 'head': git(workspace, 'rev-parse', 'HEAD'),
        'branch': git(workspace, 'branch', '--show-current'),
        'run_log_sha256': digest(runtime / 'run.log'),
        'evidence_hashes': file_hashes(runtime / 'evidence'),
        'ignored_snapshot': ignored_snapshot(workspace)})
    return status


def archive_live_evidence(workspace, baseline, completion, restored_original):
    runtime = Path(baseline['runtime_dir'])
    output = workspace / 'output'
    output.mkdir(exist_ok=True)
    evidence = runtime / 'evidence'
    hashes = file_hashes(evidence)
    target = output / 'runtime'
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    if evidence.is_dir():
        shutil.copytree(evidence, target)
    patch = '' if restored_original else git(workspace, 'diff', '--binary', baseline['meta']['base_commit'], 'HEAD')
    (output / 'change.patch').write_text(patch + ('\n' if patch else ''))
    write_json(output / 'runtime-identity.json', {
        'repository': baseline['meta']['repository'],
        'base_commit': baseline['meta']['base_commit'],
        'default_commit': baseline['meta']['default_commit'],
        'runtime_plugin_hashes': baseline['runtime_plugin_hashes'],
        'driver_sha256': digest(workspace / '.replay/driver.py')
                          if (workspace / '.replay/driver.py').is_file() else None,
        'run_log_sha256': completion.get('run_log_sha256'),
        'evidence_hashes': completion.get('evidence_hashes'),
        'change_sha256': digest(output / 'change.patch')})
    return hashes == file_hashes(target) == completion.get('evidence_hashes')


def scan_usable(status):
    return (type(status.get('exit_code')) is int and status['exit_code'] == 0
            and all(status.get(name) is False for name in (
                'build_failed', 'coverage_unknown', 'scanner_degraded', 'scan_transient'))
            and status.get('build_status') in ('not_configured', 'not_recorded', 'skipped', 'completed')
            and (status['build_status'] != 'completed' or status.get('build_exit_code') == 0))


def grype_document(path):
    value = read_json(path)
    if (not isinstance(value, dict) or not isinstance(value.get('matches'), list)
            or not isinstance(value.get('ignoredMatches', []), list)
            or not isinstance(value.get('source'), dict)
            or not isinstance(value.get('descriptor'), dict)):
        raise ValueError(f'Invalid archived Grype document: {path.name}')
    for match in value['matches'] + value.get('ignoredMatches', []):
        artifact, vulnerability = match.get('artifact', {}), match.get('vulnerability', {})
        if (not isinstance(artifact.get('type'), str) or not artifact['type']
                or (artifact['type'] == 'go-module' and
                    (not artifact.get('name') or not vulnerability.get('id')
                     or not isinstance(artifact.get('locations', []), list)))):
            raise ValueError(f'Malformed archived Grype match: {path.name}')
    return value


def test_attempts(root):
    attempts = []
    for path in (root / 'tests').glob('*.json'):
        run, attempt = map(int, re.fullmatch(r'([1-9][0-9]*)-([1-9][0-9]*)', path.stem).groups())
        attempts.append((run, attempt, read_json(path)))
    return sorted(attempts, key=lambda item: item[:2])


def native_scan_proof(case, state, phase, head, retained=False):
    """Share Subctl's archived native witnesses between coverage checks and judges."""
    root = case / 'output/runtime'
    directories = [path for path in (root / 'scans').glob(phase + '.*') if path.is_dir()]
    checks = {'one authoritative binary scan recorded': len(directories) == 1}
    proof = {'checks': checks, 'binaries': []}
    if len(directories) != 1:
        return proof
    directory = directories[0]
    scan = read_json(directory / 'status.json')
    catalog = read_json(directory / 'catalog.cdx.json')
    native = [record for record in events(directory / 'binaries.jsonl') if re.fullmatch(
        r'cmd/bin/subctl-.+-linux-amd64', os.path.normpath(record.get('path', '')))]
    paths = [os.path.normpath(record['path']) for record in native]
    checks['native binary paths unique'] = len(paths) == len(set(paths))
    if not checks['native binary paths unique']:
        return proof
    checks['native build from scan tree completed'] = (bool(head) and scan.get('head') == head
        and scan.get('phase') == phase
        and scan_usable(scan) and scan.get('build_status') == 'completed' and bool(native))
    for binary in native:
        path = os.path.normpath(binary['path'])
        info = binary.get('build_info', '')
        revisions = re.findall(r'(?m)^[ \t]*build[ \t]+vcs\.revision=([^\s]+)[ \t]*$', info)
        modified = re.findall(r'(?m)^[ \t]*build[ \t]+vcs\.modified=([^\s]+)[ \t]*$', info)
        props = [component.get('properties', []) for component in catalog.get('components', [])
                 if component.get('name') == 'stdlib']
        covered = any(
            any(prop.get('name') == 'syft:package:foundBy'
                and prop.get('value') == 'go-module-binary-cataloger' for prop in properties)
            and any(re.fullmatch(r'syft:location:[0-9]+:path', prop.get('name', ''))
                    and prop.get('value', '').removeprefix('/src').lstrip('/') == path
                    for prop in properties) for properties in props)
        catalog_hash = any(component.get('type') == 'file'
            and component.get('name') in ('/' + path, '/src/' + path, state['workspace'] + '/' + path)
            and any(item.get('alg') == 'SHA-256' and item.get('content') == binary.get('sha256')
                    for item in component.get('hashes', [])) for component in catalog.get('components', []))
        checks[f'native binary {path} positively cataloged' + (' and retained' if retained else '')] = (
            binary.get('recorded_build_artifact') is True and revisions == [head] and modified == ['false']
            and covered and catalog_hash
            and (not retained or state['ignored_snapshot'].get(path, {}).get('sha256') == binary.get('sha256')))
        # Full build_info includes every dependency; only these existing lines are useful here.
        lines = info.splitlines()
        proof['binaries'].append({
            'path': path, 'sha256': binary.get('sha256'),
            'recorded_build_artifact': binary.get('recorded_build_artifact'),
            'build_info': lines[:1] + [line for line in lines[1:] if re.match(
                r'^[ \t]*build[ \t]+(?:vcs\.revision|vcs\.modified|GOOS|GOARCH|CGO_ENABLED)=', line)],
            'stdlib_binary_catalog_location': covered, 'catalog_sha256_matches': catalog_hash})
    return proof


def runtime_scan_head(case, state, result):
    """Distinguish scanned source from a witnessed no-commit checkout restoration."""
    expected = state['expected']
    original = expected.get('default_commit')
    branch = expected.get('original_branch')
    if (original and branch and state['runtime_head'] == original
            and state.get('runtime_branch') == result.get('branch') == branch
            and result.get('head') == original and state.get('changed_files') == []
            and result.get('base_commit') == expected.get('base_commit')
            and type(result.get('exit_code')) is int and result['exit_code'] in (0, 2)):
        log = case / 'output/run.log'
        text = log.read_text() if log.is_file() else ''
        if (re.search(r'(?m)^No commits; removed the empty fix branch\.$', text)
                or (result['exit_code'] == 0
                    and re.search(r'(?m)^No CVEs found\. [^\r\n]+ is clean\.$', text))):
            return expected['base_commit']
    return state['runtime_head']


def runtime_evidence(case, state):
    """Project existing receipts into the factual judges' single evidence input."""
    root = case / 'output/runtime'
    result_path = root / 'run.json'
    if not result_path.is_file():
        return 'Archived engine completion receipt (run.json): unavailable\n'
    text = 'Archived engine completion receipt (run.json):\n' + result_path.read_text().strip() + '\n'
    try:
        result = read_json(result_path)
        phases = result.get('phases', {})
        attempts = test_attempts(root)
    except (OSError, ValueError, TypeError, AttributeError):
        return text + 'Archived completion or test receipts unavailable or invalid\n'
    for run, attempt, _ in attempts:
        path = root / 'tests' / f'{run}-{attempt}.json'
        text += f'Archived test receipt (tests/{path.name}):\n' + path.read_text().strip() + '\n'
    if state['expected'].get('repository', '').rstrip('/').rsplit('/', 1)[-1] != 'subctl.git':
        return text + 'Subctl native proof: not applicable\n'
    for phase, name, head in (('initial', 'initial_scan', state['expected'].get('base_commit')),
                              ('final-gate', 'final_gate', runtime_scan_head(case, state, result))):
        if phases.get(name) != 'completed':
            continue
        try:
            proof = native_scan_proof(case, state, phase, head, retained=phase == 'final-gate')
            text += f'Subctl native proof ({phase}):\n' + json.dumps(proof, indent=2) + '\n'
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            text += f'Subctl native proof ({phase}): unavailable or invalid\n'
    return text


def runtime_scenario(case, state):
    """Judge engine coverage from archived evidence, independently of final prose."""
    expected = state['expected']
    expectation = expected.get('runtime_expectation', 'observed')
    if expectation not in ('observed', 'repair', 'binary'):
        raise ValueError(f'Unknown runtime expectation: {expectation}')
    root = case / 'output/runtime'
    if not (root / 'run.json').exists():
        return {'runtime scenario evidence available': False}
    result = read_json(root / 'run.json')
    same_head = result.get('head') == state['runtime_head']
    conditions = {'engine completion agrees with captured result': same_head and
                  result.get('exit_code') == state['runtime_exit']}
    for guard in ('go_minor_guard', 'k8s_version_guard'):
        if expected.get(guard) is True:
            conditions[f'{guard} enabled'] = (root / 'state.env').is_file() and bool(re.search(
                rf'(?m)^{guard.upper()}=true$', (root / 'state.env').read_text()))
    for name, command in expected.get('canonical_commands', {}).items():
        if name != 'license' or result.get('phases', {}).get('license') != 'not_reached':
            conditions[f'canonical {name} command used'] = result.get(name + '_command') == command
    try:
        phases = result.get('phases', {})
        scan_head = runtime_scan_head(case, state, result)
        if phases.get('tests') == 'completed':
            attempts = test_attempts(root)
            conditions['canonical test receipts and logs retained'] = (bool(attempts)
                and {path.stem for path in (root / 'tests').glob('*.json')}
                    == {path.stem for path in (root / 'tests').glob('*.log') if path.is_file()}
                and all(record.get('command') == result.get('test_command')
                        and bool(record.get('head')) and type(record.get('exit_code')) is int
                        for _, _, record in attempts)
                and sorted({run for run, _, _ in attempts}) == list(range(1, attempts[-1][0] + 1))
                and all([attempt for run, attempt, _ in attempts if run == number]
                        == list(range(1, 1 + sum(run == number for run, _, _ in attempts)))
                        for number in {run for run, _, _ in attempts}))
            conditions['last canonical test agrees with completion'] = (bool(attempts)
                and attempts[-1][2].get('head') == result.get('tested_head')
                and attempts[-1][2].get('exit_code') == result.get('test_exit_code'))
        if phases.get('verification') == 'completed' and result.get('verification_exit_code') == 0:
            for name in AUDITS:
                path = root / 'audits' / f'{name}.evidence'
                text = path.read_text() if path.exists() else ''
                counters = ('NEW_CVES', 'UNRESOLVED') if name == 'scan-regression' else ('NEW_ISSUES',)
                conditions[f'{name} audit complete and clean'] = (bool(text.strip())
                    and not re.search(r'(?m)^SKIP:|SCAN_FAILED=|BUILD_FAILED=', text)
                    and all(re.findall(rf'\b{counter}=([^\s]+)', text) == ['0'] for counter in counters))
        if phases.get('license') == 'completed':
            conditions['canonical license evidence retained'] = (root / 'license.log').is_file()
        for name, phase, head in (('initial-scan', 'initial', expected.get('base_commit')),
                                  ('final-gate', 'final-gate', scan_head)):
            if phases.get('initial_scan' if phase == 'initial' else 'final_gate') == 'completed':
                status = read_json(root / f'{name}-status.json')
                conditions[f'{name} receipt agrees with completed phase'] = (
                    status.get('phase') == phase and status.get('head') == head
                    and type(status.get('exit_code')) is int)
                if status.get('exit_code') == 0:
                    grype_document(root / f'{name}.json')
        if expectation == 'observed':
            return conditions
        initial = grype_document(root / 'initial-scan.json')
        initial_status = read_json(root / 'initial-scan-status.json')
        conditions['required initial scan completed at pinned base'] = (
            phases.get('initial_scan') == 'completed'
            and initial_status.get('phase') == 'initial'
            and initial_status.get('head') == expected.get('base_commit')
            and type(initial_status.get('exit_code')) is int
            and initial_status['exit_code'] == 0)
        phase = 'final-gate'
        if result.get('phases', {}).get('final_gate') == 'completed':
            final = grype_document(root / 'final-gate.json')
            gate = read_json(root / 'final-gate-status.json')
        elif (expectation == 'binary' and state['runtime_exit'] == 0 and not initial['matches']
              and scan_head == expected['base_commit']):
            # A real clean fast path needs its initial native catalog, not an invented final gate.
            final, gate, phase = initial, initial_status, 'initial'
        else:
            conditions['required scan phases reached'] = False
            return conditions
        conditions['authoritative scan coverage confirmed'] = scan_usable(gate)
        if phase != 'initial':
            phases = result.get('phases', {})
            conditions['canonical verification gates passed on retained tree'] = (
                phases.get('tests') == 'completed' and result.get('test_exit_code') == 0
                and result.get('tested_head') == scan_head
                and phases.get('verification') == 'completed' and result.get('verification_exit_code') == 0
                and ((phases.get('license') == 'not_configured'
                      and 'license' not in expected.get('canonical_commands', {}))
                     or (phases.get('license') == 'completed' and result.get('license_exit_code') == 0)))
        if expectation == 'repair':
            conditions['initial scan coverage confirmed'] = scan_usable(initial_status)
            repairable = {(m['vulnerability']['id'], m['artifact']['name'])
                          for m in initial['matches'] if m['artifact']['type'] == 'go-module'
                          and usable_fix(m)}
            remaining = {(m['vulnerability']['id'], m['artifact']['name'])
                         for m in final['matches'] + final.get('ignoredMatches', [])
                         + final.get('generatedBinaryDuplicates', [])
                         if m['artifact']['type'] == 'go-module'}
            conditions['initial fixable finding actually cleared'] = bool(repairable - remaining)
            conditions['dependency repair retained'] = (state['runtime_head'] != expected['base_commit']
                and any(re.search(r'(^|/)go\.(mod|sum)$|(^|/)vendor/', path) for path in state['changed_files']))
            conditions['runtime completed successfully'] = state['runtime_exit'] == 0
            conditions['authoritative scan has no actionable findings'] = not final['matches']
            return conditions
        if phase != 'initial':
            conditions.update({'initial ' + key: value for key, value in
                native_scan_proof(case, state, 'initial', expected['base_commit'])['checks'].items()})
        conditions.update(native_scan_proof(case, state, phase, scan_head,
                                            retained=True)['checks'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        conditions['required runtime evidence valid'] = False
    return conditions


def usable_fix(match):
    """A published usable threshold is coverage, not upgrade-policy approval."""
    versions = match['vulnerability'].get('fix', {}).get('versions', [])
    if not isinstance(versions, list):
        return False
    stdlib = match['artifact']['name'] == 'stdlib'
    for version in versions:
        if not isinstance(version, str):
            continue
        if stdlib:
            if re.fullmatch(r'v?(?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)', version):
                return True
        elif re.fullmatch(
                r'v?(?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)[.](?:0|[1-9][0-9]*)'
                r'(?:-(?:0[.]|[0-9A-Za-z-]+(?:[.][0-9A-Za-z-]+)*[.]0[.])?'
                r'[0-9]{14}-[0-9a-f]{12})?(?:[+]incompatible)?', version):
            return True
    return False


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
        if path.is_symlink() or path.is_file():
            snapshot[name] = file_identity(path)
        else:
            raise ValueError(f'Cannot fingerprint ignored output: {name}')
    return snapshot


def capture(workspace):
    workspace = Path(workspace).resolve()
    baseline = read_json(workspace.parent.parent / 'control' / workspace.name / 'baseline.json')
    expected = frozen_expectations(workspace, baseline['source'])
    if not expectations_match(baseline['meta'], expected):
        raise ValueError('Prepared expectations differ from frozen case')
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
        original = state['branch'] == state['expected']['original_branch'] and state['head'] == state['expected']['default_commit']
        state['runtime_evidence_unchanged'] = archive_live_evidence(workspace, baseline, completion, original)
        state['ignored_snapshot'] = ignored
        state['runtime_plugin_unchanged'] = plugin_hashes(Path(baseline['runtime_dir']) / 'plugin') == baseline['runtime_plugin_hashes']
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
        recipe = printed_pr_recipe(log)
        if recipe:
            start = lines.index('PR command:')
            selected.update(range(start, start + len(recipe.splitlines()) + 1))
        evidence = (f'Runtime exit: {state["runtime_exit"]}\n'
                    f'Runtime HEAD: {state["runtime_head"]}\n'
                    f'Runtime branch: {state["runtime_branch"]}\n'
                    f'Captured HEAD: {state["head"]}\n'
                    f'Captured branch: {state["branch"]}\n\n'
                    + runtime_evidence(workspace, state) + '\n'
                    + '\n'.join(lines[index] for index in sorted(selected))
                    + '\n\nRetained dependency diff:\n' + (workspace / 'output/change.patch').read_text())
        (workspace / 'output/evidence.txt').write_text(evidence + '\n')
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


def message_blocks(event):
    message = event.get('message')
    content = message.get('content') if isinstance(message, dict) else None
    return content if isinstance(content, list) else []


def terminal_exit_observed(stream, status):
    """Require a matched native log observation before the final response.

    This is evidence of observation, not authentication of an exact log path.
    """
    if type(status) is not int:
        return False
    observed, before_response = False, False
    observations = set()
    for event in stream:
        if event.get('type') == 'assistant':
            before_response = observed
            for item in message_blocks(event):
                if not isinstance(item, dict) or item.get('type') != 'tool_use':
                    continue
                name, value = item.get('name'), item.get('input', {})
                eligible = name == 'Read' and Path(value.get('file_path', '')).suffix == '.log'
                if name == 'Bash':
                    command = value.get('command', '')
                    try:
                        tokens = shlex.split(command)
                    except ValueError:
                        tokens = []
                    launch = any(Path(token).name in ('bash', 'sh')
                                 and Path(tokens[index + 1]).name == 'fix-all.sh'
                                 for index, token in enumerate(tokens[:-1]))
                    reader = any(Path(token).name in ('tail', 'head', 'cat', 'grep', 'sed', 'awk')
                                 for token in tokens)
                    eligible = launch or (reader and re.search(r'\$LOG\b|\$\{LOG\}|[.]log\b', command))
                if eligible and item.get('id'):
                    observations.add(item.get('id'))
        elif event.get('type') == 'user':
            for item in message_blocks(event):
                if (not isinstance(item, dict) or item.get('type') != 'tool_result'
                        or item.get('is_error') or item.get('tool_use_id') not in observations):
                    continue
                content = item.get('content', '')
                if isinstance(content, list):
                    content = '\n'.join(block.get('text', '') for block in content
                                        if isinstance(block, dict) and block.get('type') == 'text')
                if isinstance(content, str):
                    observed = observed or any(int(code) == status for code in re.findall(
                        r'(?m)^(?:[ \t]*[0-9]+[\t:→][ \t]*)?exit=([0-9]+)[ \t]*$', content))
    return before_response


def independent_runtime_commands(tokens):
    """Catch direct extra scans/builds/tests; this is not a shell sandbox."""
    commands, current = [], []
    for token in [*tokens, ';']:
        if token and all(char in ';&|()\n' for char in token):
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    for command in commands:
        if command[0] == 'env':
            command = command[1:]
        while command and re.match(r'[A-Za-z_][A-Za-z0-9_]*=', command[0]):
            command = command[1:]
        if not command:
            continue
        executable = Path(command[0]).name
        if executable in ('bash', 'sh') and len(command) > 1:
            executable = Path(command[1]).name
        if executable in ('scan.sh', 'report.sh'):
            return True
        if executable in ('grype', '$GRYPE_BIN', '${GRYPE_BIN}'):
            if len(command) == 1 or command[1] not in ('version', 'help', '--version', '--help', '-h'):
                return True
        if executable == 'make' and not any(
                option in ('-v', '--version', '-h', '--help')
                for option in command[1:]):
            return True
        if executable == 'go' and len(command) > 1 and command[1] in ('build', 'test'):
            return True
    return False


def benign_inventory(command):
    # Raw forms preserve shell quoting/redirection semantics that shlex discards.
    return isinstance(command, str) and command.strip(' \t') in (
        'git stash list', 'git stash list 2>&1',
        'git status --short && echo "---" && git stash list 2>&1')


def benign_inventory_denial(denial):
    return (isinstance(denial, dict) and denial.get('tool_name') == 'Bash'
            and isinstance(denial.get('tool_input'), dict)
            and benign_inventory(denial['tool_input'].get('command')))


def trace_violations(stream, workspace, protected_roots=None):
    # Only case-owned runtime files are readable outside the checkout. The
    # trusted baseline and neighboring cases remain outside this allowance.
    runtime = workspace.parent.parent / 'control' / workspace.name / 'runtime'
    allowed = (workspace.resolve(), runtime.resolve())
    violations = []
    for event in stream:
        for item in message_blocks(event):
            if not isinstance(item, dict) or item.get('type') != 'tool_use':
                continue
            name, value = item.get('name', ''), item.get('input', {})
            command = value.get('command', '')
            if name in ('Agent', 'Task', 'WebFetch', 'WebSearch') or name.startswith('mcp__'):
                violations.append(f'Out-of-scope tool: {name}')
            lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()\n')
            lexer.whitespace = ' \t\r'
            lexer.whitespace_split = True
            try:
                tokens = list(lexer)
            except ValueError:
                tokens = []
            if independent_runtime_commands(tokens):
                violations.append('Independent scan, build or test outside the requested script')
            forbidden = 'gh' in tokens
            for index, token in enumerate(tokens):
                if token != 'git':
                    continue
                index += 1
                while index < len(tokens) and tokens[index].startswith('-'):
                    index += 2 if tokens[index] in ('-C', '-c', '--git-dir', '--work-tree') else 1
                if index >= len(tokens):
                    continue
                subcommand = tokens[index]
                if subcommand in ('push', 'clean') or (subcommand == 'stash' and not benign_inventory(command)):
                    forbidden = True
                arguments = []
                for argument in tokens[index + 1:]:
                    if argument and all(char in ';&|()\n' for char in argument):
                        break
                    arguments.append(argument)
                if (subcommand in ('add', 'am', 'checkout', 'cherry-pick', 'commit',
                                   'merge', 'mv', 'pull', 'rebase', 'reset', 'restore',
                                   'revert', 'rm', 'switch')
                        or (subcommand == 'apply' and
                            ('--check' not in arguments or '--apply' in arguments))):
                    violations.append(f'Git mutation outside the requested script: {subcommand}')
            if forbidden:
                violations.append('Attempted publication or disallowed git operation')
            path = value.get('file_path', value.get('path', ''))
            if name == 'Read' and path:
                candidate = Path(path)
                if not candidate.is_absolute():
                    candidate = workspace / candidate
                if not any(candidate.resolve().is_relative_to(root) for root in allowed):
                    violations.append('Read outside the case workspace')
            # Detect ordinary direct reads of the answer-bearing checkout and
            # trusted eval controls, even when another argument is permitted.
            roots = protected_roots or (EVAL_ROOT.parents[2], runtime.parent.parent)
            for prefix in map(str, roots):
                reason = 'Command accesses protected source or eval control files'
                for path in re.findall(re.escape(prefix) + r'''[^\s'";|<>]*''', command):
                    if not any(Path(path).resolve().is_relative_to(root) for root in allowed):
                        violations.append(reason)
    return violations


def extract(run_dir):
    provenance, manifest, _ = frozen_inputs(run_dir)
    cases = sorted(path for path in (Path(run_dir) / 'cases').iterdir() if path.is_dir())
    if {path.name for path in cases} != set(manifest['selected_cases']):
        raise ValueError('Case outputs do not match the selected cases')
    for case in cases:
        stream = events(case / 'stdout.log')
        output = case / 'output'
        state = read_json(output / 'state.json')
        result = read_json(case / 'run_result.json')
        if result.get('error') or result.get('exit_code') != 0:
            raise ValueError(f'{case.name}: agent did not complete successfully')
        expected = frozen_expectations(case)
        if not expectations_match(state.get('expected'), expected):
            raise ValueError(f'{case.name}: collected expectations differ from frozen case')
        state['trace_violations'] = trace_violations(stream, Path(state['workspace']),
            (manifest['project_root'], provenance, Path(state['workspace']).parent.parent / 'control'))
        state['permission_denials'] = result.get('permission_denials', [])
        if expected.get('mode') == 'live':
            state['runtime_exit_observed'] = terminal_exit_observed(stream, state['runtime_exit'])
        write_json(output / 'state.json', state)
        (output / 'reply.md').write_text(final_reply(stream) + '\n')


def printed_pr_recipe(log):
    """Read the engine's emitted continuation block without interpreting shell."""
    lines = log.splitlines()
    starts = [index for index, line in enumerate(lines) if line == 'PR command:']
    if len(starts) != 1:
        return None
    block = []
    for line in lines[starts[0] + 1:]:
        block.append(line)
        if not line.endswith('\\'):
            break
    if (len(block) < 3 or not block[0].startswith('git push ')
            or not block[0].endswith(' && \\') or block[1] != 'gh pr create \\'
            or block[-1] != '  --assignee "@me"'):
        return None
    return '\n'.join(block)


def markdown_code_blocks(reply):
    """Decode CommonMark code containers and exclude their source from prose checks."""
    from markdown_it import MarkdownIt

    lines = reply.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    blocks = []
    for token in MarkdownIt('commonmark').parse(reply):
        if token.type in ('fence', 'code_block'):
            blocks.append(token.content)
            start, end = token.map
            lines[start:end] = [''] * (end - start)
    return blocks, '\n'.join(lines)


def publication_relay_allowed(reply, log, exit_code):
    """Check fenced, inline argument-bearing and command-leading publication.

    This recognizes command syntax, not the meaning of free-form advice.
    """
    command = r'(?:gh\s+pr\s+create|git\s+push)\b'
    blocks, outside = markdown_code_blocks(reply)
    inline = re.compile(r'`([^`\n]+)`')
    # Inline bare command names are also ordinary mentions (for example, no
    # `gh pr create` command was printed). Arguments distinguish these spans.
    blocks.extend(match[1] for match in inline.finditer(outside)
                  if re.match(command + r'[ \t]+\S', match[1].lstrip()))
    lines = inline.sub('', outside).splitlines()
    start = re.compile(r'^[ \t]*(?:(?:[-*+>]|[0-9]+[.)])[ \t]+)?'
                       r'(?:\$[ \t]+)?(' + command + r'.*)$')
    index = 0
    while index < len(lines):
        match = start.match(lines[index])
        if match:
            block = [match[1]]
            while block[-1].endswith('\\') and index + 1 < len(lines):
                index += 1
                block.append(lines[index])
            blocks.append('\n'.join(block))
        index += 1
    publication = [textwrap.dedent(block).strip() for block in blocks
                   if re.search(r'\b' + command, block)]
    if not publication:
        return True
    recipe = printed_pr_recipe(log) if log is not None else None
    if not recipe or len(publication) != 1:
        return False
    return publication[0] == recipe or (publication[0].startswith('--- Summary:')
        and summary_relay_allowed(publication, log, exit_code))


def summary_relay_allowed(blocks, log, exit_code):
    """Require the complete witnessed Summary, without inventing one on clean paths."""
    if log is None:
        return False
    relayed = [textwrap.dedent(block).strip() for block in blocks
               if re.search(r'(?m)^[ \t]*--- Summary:', block)]
    summary = re.search(r'(?m)^--- Summary:', log)
    if not summary:
        return not relayed
    tail = without_recorded_exit(log, exit_code)[summary.start():].strip()
    allowed = {tail}
    if type(exit_code) is int and not re.search(r'(?m)^exit=[0-9]+$', tail):
        allowed.add(tail + f'\nexit={exit_code}')
    return len(relayed) == 1 and relayed[0] in allowed


def check(case_dir, live=False):
    import yaml

    case = Path(case_dir)
    state = read_json(case / 'output/state.json')
    reply = (case / 'output/reply.md').read_text()
    expected = frozen_expectations(case)
    expectations_unchanged = expectations_match(state.get('expected'), expected)
    state = {**state, 'expected': expected}
    provenance, manifest, _ = frozen_inputs(case.parent.parent)
    if case.name not in manifest['selected_cases']:
        raise ValueError(f'Unselected case: {case.name}')
    source = provenance / 'cases' / case.name
    data = yaml.safe_load((source / 'input.yaml').read_text())
    if (data.get('mode') == 'live') != live:
        raise ValueError(f'{case.name}: wrong evaluation track')
    blocks, _ = markdown_code_blocks(reply)
    log = None
    try:
        if live:
            path = case / 'output/run.log'
            identity = read_json(case / 'output/runtime-identity.json')
            if (path.is_file() and not path.is_symlink()
                    and identity.get('run_log_sha256') == digest(path)):
                log = path.read_text()
        elif f'cases/{case.name}/run.log.gz' in manifest['files']:
            log = gzip.decompress((source / 'run.log.gz').read_bytes()).decode()
    except (OSError, ValueError, AttributeError):
        pass  # Missing or invalid completion witnesses cannot authorize a reply.
    exit_code = state.get('runtime_exit') if live else expected.get('exit_code')
    conditions = {
        'frozen expectations unchanged': expectations_unchanged,
        'clean checkout': not state['dirty'] and not state['unexpected_ignored'],
        'one requested invocation': len(state['invocations']) == 1 and
            requested_arguments(state['invocations'][0]['arguments'], expected,
                                Path(state.get('workspace', '/unused-workspace'))),
        'remotes and plugin unchanged': state['refs_unchanged'] and state['plugin_unchanged'],
        'no forbidden operations': not state['gh_calls'] and not state['trace_violations']
                                   and all(benign_inventory_denial(denial) for denial in state['permission_denials']),
        'no invented publication command': publication_relay_allowed(
            reply, log, exit_code),
        'literal runtime Summary': summary_relay_allowed(blocks, log, exit_code),
    }
    if live:
        # Native builds/tests legitimately create ignored files. Require the
        # exact completed runtime state rather than a filename allowance.
        conditions['clean checkout'] = not state['dirty']
        recorded_ignored = state.get('runtime_ignored_snapshot')
        conditions['runtime ignored-output measurement recorded'] = isinstance(recorded_ignored, dict)
        if isinstance(recorded_ignored, dict):
            conditions['runtime ignored outputs retained'] = state['ignored_snapshot'] == recorded_ignored
        conditions['actual runtime completed'] = type(state['runtime_exit']) is int and state['runtime_exit'] in (0, 2)
        conditions['runtime exit observed before final response'] = state.get('runtime_exit_observed') is True
        conditions['runtime result retained'] = state['head'] == state['runtime_head'] and state['branch'] == state['runtime_branch']
        conditions['runtime plugin unchanged'] = state['runtime_plugin_unchanged']
        conditions['runtime evidence retained'] = state.get('runtime_evidence_unchanged') is True
        try:
            hashes = read_json(case / 'output/runtime-identity.json').get('evidence_hashes')
            archive = case / 'output/runtime'
            conditions['archived runtime evidence intact'] = (archive.is_dir() and not archive.is_symlink()
                and isinstance(hashes, dict) and file_hashes(archive) == hashes)
        except (OSError, ValueError, AttributeError):
            conditions['archived runtime evidence intact'] = False
        if conditions['archived runtime evidence intact']:
            conditions.update(runtime_scenario(case, state))
        conditions['dependency-only changes'] = all(re.search(
            r'(^|/)(go\.(mod|sum)|\.grype\.yaml)$|^go\.work(\.sum)?$|(^|/)vendor/', name)
            for name in state['changed_files'])
    else:
        conditions['recorded result/branch'] = state['head'] == expected['result_commit'] and state['branch'] == expected['fix_branch']
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
        print(snapshot(args.config, args.run_dir, args.cases or [], args.model, args.live))
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
        source = args.case_source.resolve()
        if source.parent.parent.name != 'provenance':
            freeze_run({'dataset': {'path': str(source.parent)}}, source.parent,
                       workspace, [source.name], EVAL_ROOT.parents[2])
            source = workspace / 'provenance/cases' / source.name
        case = workspace / 'cases' / source.name
        prepare(case, source)
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
