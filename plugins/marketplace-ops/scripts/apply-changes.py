#!/usr/bin/env python3
"""
Apply save or drop changes to the working tree.

For saves: restores files from the base branch and adds to .pruneprotect.
For drops: removes files and removes from .pruneprotect if present.
Bumps patch versions for affected plugins.

Usage:
  apply-changes.py --action save --paths p1,p2 --base-branch main --repo-root . --usernames u1,u2
  apply-changes.py --action drop --paths p1,p2 --repo-root .
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path


def git(repo_root, *args):
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"git {' '.join(args)} failed: {result.stderr.strip()}", file=sys.stderr)
    return result.returncode, result.stdout.strip()


def bump_patch_version(plugin_json_path):
    with open(plugin_json_path) as f:
        data = json.load(f)
    version = data.get("version", "0.0.0")
    parts = version.split(".")
    if len(parts) == 3:
        parts[2] = str(int(parts[2]) + 1)
    data["version"] = ".".join(parts)
    with open(plugin_json_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return data["version"]


def plugin_name_from_path(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "plugins":
        return parts[1]
    return None


def is_full_plugin_removal(path):
    parts = path.strip("/").split("/")
    return len(parts) == 2 and parts[0] == "plugins"


def add_to_pruneprotect(repo_root, path, username):
    protect_file = Path(repo_root) / ".pruneprotect"
    today = date.today().isoformat()
    entry = f"\n# Saved by @{username} on {today}\n{path.rstrip('/')}/\n"
    with open(protect_file, "a") as f:
        f.write(entry)


def remove_from_pruneprotect(repo_root, path):
    protect_file = Path(repo_root) / ".pruneprotect"
    if not protect_file.exists():
        return
    lines = protect_file.read_text().splitlines()
    norm = path.rstrip("/") + "/"
    new_lines = []
    skip_comment = False
    for line in lines:
        stripped = line.strip()
        if stripped.rstrip("/") + "/" == norm:
            skip_comment = False
            continue
        if skip_comment and not stripped.startswith("#") and stripped:
            skip_comment = False
        if stripped.startswith("# Saved by") and not skip_comment:
            skip_comment = True
            idx = lines.index(line)
            if idx + 1 < len(lines) and lines[idx + 1].strip().rstrip("/") + "/" == norm:
                continue
            skip_comment = False
        new_lines.append(line)
    protect_file.write_text("\n".join(new_lines) + "\n" if new_lines else "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=["save", "drop"])
    parser.add_argument("--paths", required=True)
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--usernames", default="")
    args = parser.parse_args()

    paths = [p.strip() for p in args.paths.split(",") if p.strip()]
    usernames = [u.strip() for u in args.usernames.split(",") if u.strip()]

    if len(usernames) < len(paths):
        usernames.extend(["unknown"] * (len(paths) - len(usernames)))

    repo_root = args.repo_root
    results = []
    affected_plugins = set()

    for path, username in zip(paths, usernames):
        plugin = plugin_name_from_path(path)

        if args.action == "save":
            rc, _ = git(repo_root, "checkout", f"upstream/{args.base_branch}", "--", path)
            if rc != 0:
                results.append({"path": path, "status": "error", "detail": "git checkout failed"})
                continue
            add_to_pruneprotect(repo_root, path, username)
            results.append({"path": path, "status": "saved", "author": username})

        elif args.action == "drop":
            if os.path.isdir(os.path.join(repo_root, path)):
                rc, _ = git(repo_root, "rm", "-rf", path)
            elif os.path.isfile(os.path.join(repo_root, path)):
                rc, _ = git(repo_root, "rm", path)
            else:
                results.append({"path": path, "status": "error", "detail": "path not found"})
                continue

            if rc != 0:
                results.append({"path": path, "status": "error", "detail": "git rm failed"})
                continue

            remove_from_pruneprotect(repo_root, path)
            results.append({"path": path, "status": "dropped"})

            if plugin and not is_full_plugin_removal(path):
                affected_plugins.add(plugin)

    version_bumps = {}
    for plugin in affected_plugins:
        pj = Path(repo_root) / "plugins" / plugin / ".claude-plugin" / "plugin.json"
        if pj.exists():
            new_version = bump_patch_version(pj)
            version_bumps[plugin] = new_version

    output = {
        "action": args.action,
        "results": results,
        "version_bumps": version_bumps,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
