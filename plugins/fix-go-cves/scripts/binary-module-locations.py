#!/usr/bin/env python3
"""Locate findings in freshly generated binaries for remediation dispatch.

Raw Grype reports stay unchanged. Only binaries recorded by this run and whose
main module uniquely identifies a tracked go.mod can acquire a source scope.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys


def normalized(path):
    return "/" + path.removeprefix("/src/").lstrip("/")


def module_locations(repo):
    result = {}
    files = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--", "go.mod", "*/go.mod"],
        capture_output=True, check=True,
    ).stdout.decode().split("\0")
    for relative in filter(None, files):
        path = repo / relative
        if "vendor" in path.relative_to(repo).parts or not path.resolve().is_relative_to(repo):
            continue
        match = re.search(r"^module[ \t]+(\"(?:[^\"\\]|\\.)*\"|\S+)", path.read_text(), re.M)
        if not match:
            continue
        name = match[1]
        if name.startswith('"'):
            try:
                name = json.loads(name)
            except ValueError:
                continue
        result.setdefault(name, []).append("/" + relative)
    return {name: paths[0] for name, paths in result.items() if len(paths) == 1}


def binary_locations(repo, manifest, scan):
    if not manifest.is_file():
        return {}
    modules = module_locations(repo)
    needed = {
        normalized(location["path"])
        for match in scan["matches"]
        for location in match["artifact"].get("locations", [])
    }
    mapped = {}
    for entry in manifest.read_text().splitlines():
        binary = Path(entry).resolve()
        if not binary.is_relative_to(repo) or not binary.is_file():
            continue
        location = "/" + str(binary.relative_to(repo))
        if location not in needed:
            continue
        try:
            info = subprocess.run(
                ["go", "version", "-m", str(binary)], capture_output=True, text=True,
                timeout=15, env={**os.environ, "GOTOOLCHAIN": "local", "GOWORK": "off"},
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if info.returncode:
            continue
        main = re.search(r"^[ \t]+mod[ \t]+(\S+)[ \t]", info.stdout, re.M)
        if main and main[1] in modules:
            mapped[location] = modules[main[1]]
    return mapped


def dispatch_scan(repo, manifest, scan):
    mapped = binary_locations(repo, manifest, scan)
    for match in scan["matches"]:
        if match["artifact"].get("type") != "go-module" or match["artifact"].get("name") == "stdlib":
            continue
        for location in match["artifact"].get("locations", []):
            scope = mapped.get(normalized(location["path"]))
            if scope:
                location["path"] = scope
    return scan


def filter_duplicates(repo, manifest, scan):
    """Retain raw duplicate evidence while applying proven source coverage."""
    mapped = binary_locations(repo, manifest, scan)

    def key(match):
        return (match["vulnerability"]["id"], match["artifact"]["name"],
                match["artifact"].get("version"),
                match["vulnerability"].get("fix", {}).get("state") or "unknown")

    def nofix(match):
        return (match["artifact"].get("type") == "go-module"
                and bool(match["artifact"].get("version"))
                and not match["vulnerability"].get("fix", {}).get("versions"))

    handled = {
        (key(match), normalized(location["path"]))
        for match in scan.get("ignoredMatches", []) if nofix(match)
        for location in match["artifact"].get("locations", [])
        if normalized(location["path"]).endswith("/go.mod")
    }
    retained, duplicates = [], []
    for match in scan["matches"]:
        locations = match["artifact"].get("locations", [])
        covered = nofix(match) and locations and all(
            (key(match), mapped.get(normalized(location["path"]))) in handled
            for location in locations
        )
        (duplicates if covered else retained).append(match)
    scan["matches"] = retained
    if duplicates:
        scan.setdefault("generatedBinaryDuplicates", []).extend(duplicates)
    return scan


if __name__ == "__main__":
    operation = {"--location-map": binary_locations, "--filter-duplicates": filter_duplicates}.get(
        sys.argv[3] if len(sys.argv) > 3 else "", dispatch_scan)
    json.dump(operation(Path(sys.argv[1]).resolve(), Path(sys.argv[2]), json.load(sys.stdin)), sys.stdout)
    print()
