#!/usr/bin/env python3
"""
Auto-bump patch versions for plugins that changed since a base ref.

Accepts an optional base ref argument (e.g. a commit SHA). When run in
GitHub Actions, pass ${{ github.event.before }} to correctly handle
multi-commit merges (rebase, squash, or merge commit). Falls back to
HEAD~1 when no argument is provided.
"""

import json
import subprocess
import sys
from pathlib import Path


def get_changed_plugins(repo_root: Path, base_ref: str) -> set[str]:
    """Find plugins with code changes since base_ref."""
    result = subprocess.run(
        ["git", "diff", "--name-only", base_ref, "HEAD", "--", "plugins/"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        print(f"Error running git diff: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    plugins = set()
    for path in result.stdout.strip().splitlines():
        if not path:
            continue
        # Skip documentation-only changes
        if path.endswith("README.md") or path.endswith("SKILL.md"):
            continue
        # Extract plugin name (plugins/{name}/...)
        parts = path.split("/")
        if len(parts) >= 2:
            plugins.add(parts[1])

    return plugins


def bump_patch_version(version: str) -> str:
    """Bump the patch component of a semver string."""
    parts = version.split(".")
    if len(parts) != 3:
        print(f"Warning: unexpected version format '{version}', skipping")
        return version
    parts[2] = str(int(parts[2]) + 1)
    return ".".join(parts)


def main():
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    base_ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1"
    print(f"Comparing against base ref: {base_ref}")

    changed = get_changed_plugins(repo_root, base_ref)
    if not changed:
        print("No plugin code changes detected")
        return

    bumped = 0
    for plugin_name in sorted(changed):
        plugin_json_path = (
            repo_root / "plugins" / plugin_name / ".claude-plugin" / "plugin.json"
        )
        if not plugin_json_path.exists():
            print(f"SKIP: {plugin_name} - no plugin.json")
            continue

        with open(plugin_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        old_version = data.get("version", "0.0.0")
        new_version = bump_patch_version(old_version)
        if new_version == old_version:
            continue

        data["version"] = new_version
        with open(plugin_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

        print(f"Bumped {plugin_name}: {old_version} -> {new_version}")
        bumped += 1

    if bumped:
        print(f"\n{bumped} plugin(s) bumped")
    else:
        print("No plugins needed bumping")


if __name__ == "__main__":
    main()
