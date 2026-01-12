#!/usr/bin/env python3
"""
Sync plugin versions from individual plugin.json files to marketplace.json.

This script reads the version from each plugin's .claude-plugin/plugin.json
and updates the corresponding entry in .claude-plugin/marketplace.json.
"""

import json
import sys
from pathlib import Path
from typing import Optional


def get_plugin_version(plugins_dir: Path, plugin_name: str) -> Optional[str]:
    """Get the version from a plugin's plugin.json file."""
    plugin_json_path = plugins_dir / plugin_name / '.claude-plugin' / 'plugin.json'
    if not plugin_json_path.exists():
        return None

    with open(plugin_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('version')


def sync_marketplace_versions(repo_root: Path) -> bool:
    """
    Sync versions from plugin.json files to marketplace.json.

    Returns True if changes were made, False otherwise.
    """
    marketplace_path = repo_root / '.claude-plugin' / 'marketplace.json'
    plugins_dir = repo_root / 'plugins'

    if not marketplace_path.exists():
        print(f"Error: Marketplace file not found: {marketplace_path}", file=sys.stderr)
        sys.exit(1)

    with open(marketplace_path, 'r', encoding='utf-8') as f:
        marketplace = json.load(f)

    changes_made = False

    for plugin in marketplace.get('plugins', []):
        plugin_name = plugin.get('name')
        if not plugin_name:
            continue

        version = get_plugin_version(plugins_dir, plugin_name)
        if version is None:
            print(f"Warning: No plugin.json found for {plugin_name}")
            continue

        current_version = plugin.get('version')
        if current_version != version:
            print(f"Updating {plugin_name}: {current_version} -> {version}")
            plugin['version'] = version
            changes_made = True
        else:
            print(f"OK: {plugin_name} @ {version}")

    if changes_made:
        with open(marketplace_path, 'w', encoding='utf-8') as f:
            json.dump(marketplace, f, indent=2)
            f.write('\n')
        print(f"\n✓ Updated {marketplace_path}")
    else:
        print("\n✓ All versions already in sync")

    return changes_made


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    print("Syncing plugin versions to marketplace.json...")
    sync_marketplace_versions(repo_root)


if __name__ == '__main__':
    main()
