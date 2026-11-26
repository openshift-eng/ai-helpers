#!/usr/bin/env python3
"""Retain accepted workflow evidence and detect edits after a cached PASS."""

import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def files(root):
    scratch = root / ".rebase-tmp"
    paths = [scratch / name for name in (
        "state.json", "base-commit", "branch-name", ".session-active", "status/INCOMPLETE")]
    for suffix in ("report", "evidence", "crash"):
        paths.extend((scratch / "gates").glob("*." + suffix))
    return {str(path.relative_to(root)): path.read_bytes()
            for path in sorted(set(paths)) if path.is_file()}


def hashes(contents):
    return {name: digest(raw) for name, raw in contents.items()}


def newer_versions(record_path, record):
    """Require a newer same-repository launch receipt before releasing live proof."""
    prefix = record["version"] + "_"
    started = record.get("started_at")
    if not record_path.name.startswith(prefix) or type(started) is not int:
        return set()
    key = record_path.name[len(prefix):]
    versions = set()
    for path in record_path.parent.glob("*.json"):
        try:
            candidate = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(candidate, dict):
            continue
        version, base = candidate.get("version"), candidate.get("base_ref")
        if (isinstance(version, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
                and version != record["version"] and path.name == version + "_" + key
                and candidate.get("repo") == record["repo"]
                and type(candidate.get("started_at")) is int and candidate["started_at"] > started
                and isinstance(base, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", base)):
            versions.add(version)
    return versions


def other_version(root, owners):
    """A declared target needs an independent launch receipt, not just a label."""
    try:
        state = json.loads((root / ".rebase-tmp/state.json").read_text())
    except (OSError, ValueError):
        return False
    actual = state.get("version") if isinstance(state, dict) else None
    return isinstance(actual, str) and actual in owners


def capture(destination, roots):
    destination.mkdir(parents=True, exist_ok=True)
    archive = Path(tempfile.mkdtemp(prefix="accepted-", dir=destination))
    records = []
    for index, root in enumerate(dict.fromkeys(roots)):
        contents = files(root)
        for name, raw in contents.items():
            target = archive / str(index) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        records.append({"source": str(root), "files": hashes(contents)})
    if not records:
        raise ValueError("no accepted evidence to retain")
    manifest = archive / "manifest.json"
    manifest.write_text(json.dumps(records, indent=2) + "\n")
    print(manifest)


def check(record_path, live_roots):
    record = json.loads(record_path.read_text())
    owners = newer_versions(record_path, record)
    manifest = Path(record["evidence_manifest"])
    raw = manifest.read_bytes()
    if digest(raw) != record["evidence_sha256"]:
        raise ValueError("accepted evidence manifest changed")
    records = json.loads(raw)
    if not records:
        raise ValueError("no accepted evidence")
    sources = set()
    for index, item in enumerate(records):
        root = Path(item["source"])
        sources.add(root)
        if hashes(files(manifest.parent / str(index))) != item["files"]:
            raise ValueError("retained evidence changed or disappeared")
        # Court cleanup removes whole worktrees. Their accepted evidence must
        # remain usable; deleting reports in an existing checkout is different.
        # cmd_run removes main scratch before a subsequent worktree launch.
        # Missing individual files in a surviving scratch remain invalid.
        released = bool(owners) and not (root / ".rebase-tmp").exists()
        if (root.exists() and not released and not other_version(root, owners)
                and hashes(files(root)) != item["files"]):
            raise ValueError("live evidence changed since the accepted run")
    relevant_roots = {root for root in live_roots if not other_version(root, owners)}
    if not relevant_roots.issubset(sources):
        raise ValueError("new evidence workspace requires a fresh result")


if __name__ == "__main__":
    try:
        action, target, *roots = sys.argv[1:]
        roots = [Path(root).resolve() for root in roots]
        if action == "capture":
            capture(Path(target), roots)
        elif action == "check":
            check(Path(target), roots)
        elif action == "other-version" and len(roots) == 1:
            record_path = Path(target)
            record = json.loads(record_path.read_text())
            sys.exit(0 if other_version(roots[0], newer_versions(record_path, record)) else 1)
        else:
            raise ValueError("expected capture, check, or other-version")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: run evidence is unverified: {error}", file=sys.stderr)
        sys.exit(1)
