#!/usr/bin/env python3

"""
Standalone script to generate a team-to-components mapping from GCS org data.

This script:
1. Downloads org data from GCS to a temp file
2. Extracts team names and their OCPBUGS component mappings
3. Saves the mapping to plugins/component-health/team_component_map.json
4. Deletes the temp file

Usage:
    python3 plugins/component-health/generate_team_component_map.py

Requirements:
    - gsutil installed and authenticated
    - jq (for JSON validation, optional)
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def download_org_data():
    """Download org data from GCS to a temporary file."""
    print("Downloading org data from GCS...", file=sys.stderr)

    # Check if gsutil is available
    try:
        subprocess.run(
            ["gsutil", "--version"],
            check=True,
            capture_output=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: gsutil not found. Please install Google Cloud SDK.", file=sys.stderr)
        print("Installation: https://cloud.google.com/sdk/docs/install", file=sys.stderr)
        sys.exit(1)

    # Create temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".json", prefix="org_data_")
    os.close(temp_fd)  # Close the file descriptor, we'll write to it via gsutil

    try:
        # Download from GCS
        gcs_url = "gs://resolved-org/orgdata/comprehensive_index_dump.json"
        subprocess.run(
            ["gsutil", "cp", gcs_url, temp_path],
            check=True,
            capture_output=True
        )
        print(f"Downloaded to temporary file: {temp_path}", file=sys.stderr)
        return temp_path
    except subprocess.CalledProcessError as e:
        os.unlink(temp_path)  # Clean up temp file
        print(f"Error downloading from GCS: {e}", file=sys.stderr)
        print("Make sure you're authenticated: gcloud auth application-default login", file=sys.stderr)
        sys.exit(1)


def extract_team_component_mapping(org_data_path):
    """Extract team-to-components mapping from org data."""
    print("Parsing org data and extracting team-component mapping...", file=sys.stderr)

    # Load org data
    try:
        with open(org_data_path, 'r') as f:
            org_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    # Get teams and components from lookups
    teams = org_data.get("lookups", {}).get("teams", {})
    components = org_data.get("lookups", {}).get("components", {})

    if not teams:
        print("Error: No teams found in org data", file=sys.stderr)
        sys.exit(1)

    if not components:
        print("Error: No components found in org data", file=sys.stderr)
        sys.exit(1)

    # Build team-to-components mapping
    team_component_map = {}

    for team_name, team_data in teams.items():
        # Get component keys from team's component_list
        component_keys = team_data.get("group", {}).get("component_list", [])

        # Map component keys to OCPBUGS component names
        ocpbugs_components = []

        for comp_key in component_keys:
            if comp_key in components:
                comp_data = components[comp_key]
                jiras = comp_data.get("component", {}).get("jiras", [])

                # Find OCPBUGS entries
                for jira in jiras:
                    if jira.get("project") == "OCPBUGS":
                        component_name = jira.get("component")
                        if component_name and component_name not in ocpbugs_components:
                            ocpbugs_components.append(component_name)

        # Sort components for consistency
        ocpbugs_components.sort()

        # Only include teams with at least one OCPBUGS component
        if ocpbugs_components:
            team_component_map[team_name] = ocpbugs_components

    print(f"Extracted {len(team_component_map)} teams with OCPBUGS components", file=sys.stderr)

    # Count total components
    total_components = sum(len(comps) for comps in team_component_map.values())
    print(f"Total OCPBUGS components across all teams: {total_components}", file=sys.stderr)

    return team_component_map


def save_mapping(team_component_map):
    """Save the mapping to the component-health plugin directory."""
    # Get script directory (should be plugins/component-health/)
    script_dir = Path(__file__).parent
    output_path = script_dir / "team_component_map.json"

    print(f"Saving mapping to: {output_path}", file=sys.stderr)

    # Create output with metadata
    output_data = {
        "metadata": {
            "description": "Mapping of team names to their OCPBUGS components",
            "generated_by": "generate_team_component_map.py",
            "total_teams": len(team_component_map),
            "total_components": sum(len(comps) for comps in team_component_map.values())
        },
        "teams": team_component_map
    }

    # Write to file with pretty formatting
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2, sort_keys=True)

    # Set readable permissions
    os.chmod(output_path, 0o644)

    print(f"Successfully saved mapping to {output_path}", file=sys.stderr)
    return output_path


def cleanup_temp_file(temp_path):
    """Delete the temporary file."""
    if temp_path and os.path.exists(temp_path):
        print(f"Cleaning up temporary file: {temp_path}", file=sys.stderr)
        os.unlink(temp_path)


def main():
    """Main function."""
    temp_path = None

    try:
        # Step 1: Download org data to temp file
        temp_path = download_org_data()

        # Step 2: Extract team-component mapping
        team_component_map = extract_team_component_mapping(temp_path)

        # Step 3: Save mapping to plugin directory
        output_path = save_mapping(team_component_map)

        # Step 4: Clean up temp file
        cleanup_temp_file(temp_path)

        print("\n✓ Successfully generated team-component mapping!", file=sys.stderr)
        print(f"  Location: {output_path}", file=sys.stderr)
        print(f"  Teams: {len(team_component_map)}", file=sys.stderr)
        print(f"  Components: {sum(len(c) for c in team_component_map.values())}", file=sys.stderr)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        cleanup_temp_file(temp_path)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        cleanup_temp_file(temp_path)
        sys.exit(1)


if __name__ == "__main__":
    main()
