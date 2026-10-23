#!/usr/bin/env python3
"""Remove only unchanged, untracked build outputs previously recorded by this run."""

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def identity(repo, name):
    path = Path(name)
    try:
        relative = path.relative_to(repo)
        if not path.is_absolute() or '..' in relative.parts or '.git' in relative.parts:
            return None
        current = repo
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                return None
            if current != path and ((current / '.git').exists() or (current / '.git').is_symlink()):
                return None
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not path.resolve().is_relative_to(repo):
            return None
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        return {'kind': 'file', 'sha256': digest.hexdigest(), 'mode': stat.S_IMODE(info.st_mode)}
    except (OSError, ValueError):
        return None


def inventory(repo):
    """Keep all pre-build paths; only regular executable files can be outputs."""
    paths, executable = set(), []
    for directory, dirs, files in os.walk(repo, followlinks=False):
        dirs[:] = [name for name in dirs if name != '.git']
        for name in dirs + files:
            path = Path(directory) / name
            if name == '.git' or '\n' in str(path) or '\r' in str(path):
                continue  # Plain native-build witnesses cannot represent these names.
            paths.add(str(path))
            if not path.is_symlink() and path.is_file() and path.stat().st_mode & stat.S_IXUSR:
                executable.append(path)
    return paths, executable


def tracked_paths(repo):
    result = subprocess.run(['git', '-C', str(repo), 'ls-files', '-z'], capture_output=True)
    return set(filter(None, os.fsdecode(result.stdout).split('\0'))) if result.returncode == 0 else None


def metadata_file(path):
    if path.is_symlink():
        return False
    try:
        info = path.stat()
    except FileNotFoundError:
        return True
    return stat.S_ISREG(info.st_mode) and info.st_nlink == 1


def claims(path):
    try:
        if not path or not metadata_file(path):
            return {}
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}  # Legacy pathname-only or malformed claims establish no ownership.


def write(path, text):
    if not metadata_file(path):
        raise ValueError(f'Unowned artifact metadata: {path}')
    path.write_text(text)


def write_claims(path, value):
    write(path, json.dumps(value, sort_keys=True) + '\n')


def cleanup(repo, records, tracked, baseline=()):
    if tracked is None:
        return
    for name, expected in records.items():
        if (name in baseline or not isinstance(expected, dict)
                or set(expected) != {'kind', 'sha256', 'mode'}
                or type(expected['mode']) is not int or not expected['mode'] & stat.S_IXUSR):
            continue
        current = identity(repo, name)
        if current is None or current != expected:
            continue
        path = Path(name)
        if str(path.relative_to(repo)) in tracked:
            continue
        try:
            path.unlink()
        except OSError as error:
            print(f'WARNING: preserving build output {path}: {error}', file=sys.stderr)


def update_previous(previous, records):
    if previous:
        try:
            write_claims(previous, records)
        except (OSError, ValueError) as error:
            print(f'WARNING: cannot persist build-output ownership: {error}', file=sys.stderr)


def main(operation, repo, state, previous):
    repo = Path(repo).resolve()
    manifest = Path(state + '.generated-artifacts')
    baseline = Path(state + '.baseline-artifacts')
    built = Path(state + '.built-artifacts')
    previous = Path(previous) if previous else None
    tracked = tracked_paths(repo)
    if not metadata_file(baseline):
        raise ValueError(f'Unowned artifact metadata: {baseline}')
    if operation == 'prepare':
        first = not baseline.exists()
        old_paths = set(baseline.read_text().splitlines()) if not first else set()
        stamp = baseline.stat().st_mtime_ns if not first else None
        if first:
            cleanup(repo, claims(previous), tracked)
            update_previous(previous, {})
        cleanup(repo, claims(manifest), tracked, old_paths)
        # Unclaimed/preserved paths already exist before this build. Do not adopt
        # a replacement as a newly generated file during a later build phase.
        paths, _ = inventory(repo)
        write(baseline, ''.join(name + '\n' for name in sorted(old_paths | paths)))
        if stamp is not None:
            os.utime(baseline, ns=(baseline.stat().st_atime_ns, stamp))
        write_claims(manifest, {})
    elif operation == 'record':
        old_paths = set(baseline.read_text().splitlines())
        _, executable = inventory(repo)
        records = {}
        for path in executable:
            name = str(path)
            if name not in old_paths and tracked is not None and str(path.relative_to(repo)) not in tracked:
                current = identity(repo, name)
                if current:
                    records[name] = current
        write_claims(manifest, records)
        update_previous(previous, records)
        # Preserve the existing plain-path interface used by native proof and
        # binary-to-module mapping, including in-place rebuilds of baseline files.
        stamp = baseline.stat().st_mtime_ns
        write(built, ''.join(str(path) + '\n' for path in sorted(executable)
                            if path.stat().st_mtime_ns > stamp and identity(repo, str(path))))
    else:
        raise ValueError('Expected prepare or record')


if __name__ == '__main__':
    try:
        main(*sys.argv[1:])
    except (OSError, ValueError) as error:
        print(f'ERROR: artifact ownership could not be established: {error}', file=sys.stderr)
        sys.exit(1)
