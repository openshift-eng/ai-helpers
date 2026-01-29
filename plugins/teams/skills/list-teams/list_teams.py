#!/usr/bin/env python3

"""
List all teams from the team component mapping.

This script reads the team_component_map.json file and extracts all team names.
"""

import json
import os
import sys
from pathlib import Path


def get_mapping_path():
    """Get the absolute path to the team component mapping file."""
    # Get the script's directory (should be plugins/teams/skills/list-teams/)
    script_dir = Path(__file__).parent
    # Go up two levels to plugins/teams/
    plugin_dir = script_dir.parent.parent
    return plugin_dir / "team_component_map.json"


def read_mapping():
    """Read and parse the team component mapping file."""
    mapping_path = get_mapping_path()

    if not mapping_path.exists():
        print(
            f"Error: Team component mapping file not found at {mapping_path}\n"
            "This file should be in the repository. Please check your installation.",
            file=sys.stderr
        )
        sys.exit(1)

    try:
        with open(mapping_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(
            f"Error: Failed to parse mapping file. File may be corrupted.\n"
            f"Details: {e}\n"
            f"Try regenerating with: python3 plugins/teams/generate_team_component_map.py",
            file=sys.stderr
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error reading mapping file: {e}", file=sys.stderr)
        sys.exit(1)


def extract_teams(mapping_data):
    """Extract team names from mapping data."""
    try:
        teams = mapping_data.get("teams", {})

        if not teams:
            print(
                "Error: No teams found in mapping file.\n"
                "Expected structure: {teams: {...}}\n"
                "Mapping file may be corrupted.",
                file=sys.stderr
            )
            sys.exit(1)

        # Get all team keys (team names) and sort them
        team_list = sorted(teams.keys())

        if not team_list:
            print(
                "Warning: No teams found in mapping file.\n"
                "This may indicate the mapping is empty or outdated.",
                file=sys.stderr
            )

        return team_list

    except Exception as e:
        print(f"Error extracting teams: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function."""
    # Read mapping
    mapping_data = read_mapping()

    # Extract teams
    teams = extract_teams(mapping_data)

    # Output JSON
    output = {
        "total_teams": len(teams),
        "teams": teams
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
