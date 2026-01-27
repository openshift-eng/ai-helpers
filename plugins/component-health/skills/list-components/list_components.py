#!/usr/bin/env python3

"""
List all OCPBUGS components from the org data cache.

This script reads the org data cache and extracts OCPBUGS component names.
Optionally filters by team using the --team argument.
It depends on the org-data-cache skill to maintain the cache file.
"""

import argparse
import json
import os
import sys
from pathlib import Path


def get_cache_path():
    """Get the absolute path to the cache file."""
    return Path.home() / ".cache" / "ai-helpers" / "org_data.json"


def read_cache():
    """Read and parse the org data cache file."""
    cache_path = get_cache_path()

    if not cache_path.exists():
        print(
            f"Error: Cache file not found at {cache_path}\n"
            "Please run the org-data-cache skill first to create the cache:\n"
            "  python3 plugins/component-health/skills/org-data-cache/org_data_cache.py",
            file=sys.stderr
        )
        sys.exit(1)

    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(
            f"Error: Failed to parse cache file. Cache may be corrupted.\n"
            f"Details: {e}\n"
            f"Try deleting {cache_path} and re-running org-data-cache skill.",
            file=sys.stderr
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error reading cache file: {e}", file=sys.stderr)
        sys.exit(1)


def get_team_component_keys(cache_data, team_name):
    """Get component keys for a specific team."""
    teams = cache_data.get("lookups", {}).get("teams", {})

    if team_name not in teams:
        print(
            f"Error: Team '{team_name}' not found in cache.\n"
            f"Use list-teams to see available teams.",
            file=sys.stderr
        )
        sys.exit(1)

    team_data = teams[team_name]
    component_keys = team_data.get("group", {}).get("component_list", [])

    return set(component_keys)


def extract_components(cache_data, team_name=None):
    """Extract OCPBUGS component names from cache data, optionally filtered by team."""
    try:
        components = cache_data.get("lookups", {}).get("components", {})

        if not components:
            print(
                "Error: No components found in cache file.\n"
                "Expected structure: .lookups.components\n"
                "Cache file may be corrupted or outdated.",
                file=sys.stderr
            )
            sys.exit(1)

        # If team filter is specified, get the team's component keys
        team_component_keys = None
        if team_name:
            team_component_keys = get_team_component_keys(cache_data, team_name)

        # Extract component names from jiras where project == "OCPBUGS"
        ocpbugs_components = set()

        for key, value in components.items():
            # If filtering by team, only process components in the team's component_list
            if team_component_keys is not None and key not in team_component_keys:
                continue

            # Check if this component has jiras defined
            jiras = value.get("component", {}).get("jiras", [])

            # Look for OCPBUGS project entries
            for jira in jiras:
                if jira.get("project") == "OCPBUGS":
                    component_name = jira.get("component")
                    if component_name:
                        ocpbugs_components.add(component_name)

        if not ocpbugs_components:
            if team_name:
                print(
                    f"Warning: No OCPBUGS components found for team '{team_name}'.\n"
                    f"The team may not have any OCPBUGS components assigned.",
                    file=sys.stderr
                )
            else:
                print(
                    "Warning: No OCPBUGS components found in cache file.\n"
                    "This may indicate the cache is outdated or incomplete.",
                    file=sys.stderr
                )

        # Sort and return as list
        component_list = sorted(ocpbugs_components)

        return component_list

    except Exception as e:
        print(f"Error extracting components: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="List OCPBUGS components from org data cache"
    )
    parser.add_argument(
        "--team",
        type=str,
        help="Filter components by team name (use list-teams to see available teams)"
    )
    args = parser.parse_args()

    # Read cache
    cache_data = read_cache()

    # Extract components (optionally filtered by team)
    components = extract_components(cache_data, team_name=args.team)

    # Output JSON
    output = {
        "total_components": len(components),
        "components": components
    }

    # Add team info if filtering by team
    if args.team:
        output["team"] = args.team

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
