#!/usr/bin/env python3

"""
List all components from the org data cache.

This script reads the org data cache and extracts all component names.
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


def extract_components(cache_data):
    """Extract OCPBUGS component names from cache data."""
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

        # Extract component names from jiras where project == "OCPBUGS"
        ocpbugs_components = set()

        for key, value in components.items():
            # Check if this component has jiras defined
            jiras = value.get("component", {}).get("jiras", [])

            # Look for OCPBUGS project entries
            for jira in jiras:
                if jira.get("project") == "OCPBUGS":
                    component_name = jira.get("component")
                    if component_name:
                        ocpbugs_components.add(component_name)

        if not ocpbugs_components:
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
    # Read cache
    cache_data = read_cache()

    # Extract components
    components = extract_components(cache_data)

    # Output JSON
    output = {
        "total_components": len(components),
        "components": components
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
