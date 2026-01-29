#!/usr/bin/env python3

"""
List all OCPBUGS components from the team component mapping.

This script reads the team_component_map.json file and extracts OCPBUGS component names.
Optionally filters by team using the --team argument.
"""

import argparse
import json
import os
import sys
from pathlib import Path


def get_mapping_path():
    """Get the absolute path to the team component mapping file."""
    # Get the script's directory (should be plugins/teams/skills/list-components/)
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


def extract_components(mapping_data, team_name=None):
    """Extract OCPBUGS component names from mapping data, optionally filtered by team."""
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

        # If team filter is specified, return that team's components
        if team_name:
            if team_name not in teams:
                print(
                    f"Error: Team '{team_name}' not found in mapping.\n"
                    f"Use list-teams to see available teams.",
                    file=sys.stderr
                )
                sys.exit(1)

            components = teams[team_name]

            if not components:
                print(
                    f"Warning: No OCPBUGS components found for team '{team_name}'.\n"
                    f"The team may not have any OCPBUGS components assigned.",
                    file=sys.stderr
                )

            return sorted(components)

        # If no team filter, return all unique components across all teams
        all_components = set()
        for team_components in teams.values():
            all_components.update(team_components)

        if not all_components:
            print(
                "Warning: No OCPBUGS components found in mapping file.\n"
                "This may indicate the mapping is empty or outdated.",
                file=sys.stderr
            )

        return sorted(all_components)

    except Exception as e:
        print(f"Error extracting components: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="List OCPBUGS components from team component mapping"
    )
    parser.add_argument(
        "--team",
        type=str,
        help="Filter components by team name (use list-teams to see available teams)"
    )
    args = parser.parse_args()

    # Read mapping
    mapping_data = read_mapping()

    # Extract components (optionally filtered by team)
    components = extract_components(mapping_data, team_name=args.team)

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
