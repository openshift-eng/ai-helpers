#!/usr/bin/env python3

"""
List all teams from the org data cache.

This script reads the org data cache and extracts all team names.
It depends on the org-data-cache skill to maintain the cache file.
"""

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


def extract_teams(cache_data):
    """Extract team names from cache data."""
    try:
        teams = cache_data.get("lookups", {}).get("teams", {})

        if not teams:
            print(
                "Error: No teams found in cache file.\n"
                "Expected structure: .lookups.teams\n"
                "Cache file may be corrupted or outdated.",
                file=sys.stderr
            )
            sys.exit(1)

        # Get all team keys (team names) and sort them
        team_list = sorted(teams.keys())

        if not team_list:
            print(
                "Warning: No teams found in cache file.\n"
                "This may indicate the cache is outdated or incomplete.",
                file=sys.stderr
            )

        return team_list

    except Exception as e:
        print(f"Error extracting teams: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function."""
    # Read cache
    cache_data = read_cache()

    # Extract teams
    teams = extract_teams(cache_data)

    # Output JSON
    output = {
        "total_teams": len(teams),
        "teams": teams
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
