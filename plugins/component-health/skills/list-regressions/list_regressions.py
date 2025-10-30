#!/usr/bin/env python3
"""
Script to fetch regression data for OpenShift components.

Usage:
    python3 list_regressions.py --release <release> [--components comp1 comp2 ...]

Example:
    python3 list_regressions.py --release 4.17
    python3 list_regressions.py --release 4.21 --components Monitoring etcd
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def fetch_regressions(release: str) -> dict:
    """
    Fetch regression data from the component health API.
    
    Args:
        release: The release version (e.g., "4.17", "4.16")
    
    Returns:
        Dictionary containing the regression data
    
    Raises:
        urllib.error.URLError: If the request fails
    """
    # Construct the base URL
    base_url = f"https://sippy.dptools.openshift.org/api/component_readiness/regressions"
    
    # Build query parameters
    params = [f"release={release}"]
    
    url = f"{base_url}?{'&'.join(params)}"
    
    print(f"Fetching regressions from: {url}", file=sys.stderr)
    
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data
            else:
                raise Exception(f"HTTP {response.status}: {response.reason}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise


def filter_by_components(data: list, components: list = None) -> list:
    """
    Filter regression data by component names.
    
    Args:
        data: List of regression dictionaries
        components: Optional list of component names to filter by
    
    Returns:
        Filtered list of regressions matching the specified components
    """
    # Always filter out regressions with empty component names
    # These are legacy prior to a code change to ensure it is always set.
    filtered = [
        regression for regression in data
        if regression.get('component', '') != ''
    ]
    
    # If no specific components requested, return all non-empty components
    if not components:
        return filtered
    
    # Convert components to lowercase for case-insensitive comparison
    components_lower = [c.lower() for c in components]
    
    # Further filter by specified components
    filtered = [
        regression for regression in filtered
        if regression.get('component', '').lower() in components_lower
    ]
    
    print(f"Filtered to {len(filtered)} regressions for components: {', '.join(components)}", 
          file=sys.stderr)
    
    return filtered


def simplify_time_fields(data: list) -> list:
    """
    Simplify time fields in regression data.
    
    Converts time fields from a nested structure like:
      {"Time": "2025-09-27T12:04:24.966914Z", "Valid": true}
    to either:
      - The timestamp string if Valid is true
      - null if Valid is false
    
    This applies to fields: 'closed', 'last_failure'
    
    Args:
        data: List of regression dictionaries
    
    Returns:
        List of regressions with simplified time fields
    """
    time_fields = ['closed', 'last_failure']
    
    for regression in data:
        for field in time_fields:
            if field in regression:
                value = regression[field]
                # Check if the field is a dict with Valid and Time fields
                if isinstance(value, dict):
                    if value.get('Valid') is True:
                        # Replace with just the timestamp string
                        regression[field] = value.get('Time')
                    else:
                        # Replace with null if not valid
                        regression[field] = None
    
    return data


def group_by_component(data: list) -> dict:
    """
    Group regressions by component name and split into open/closed.
    
    Args:
        data: List of regression dictionaries
    
    Returns:
        Dictionary mapping component names to objects containing open and closed regression lists
    """
    components = {}
    
    for regression in data:
        component = regression.get('component', 'Unknown')
        if component not in components:
            components[component] = {
                "open": [],
                "closed": []
            }
        
        # Split based on whether closed field is null
        if regression.get('closed') is None:
            components[component]["open"].append(regression)
        else:
            components[component]["closed"].append(regression)
    
    # Sort component names for consistent output
    return dict(sorted(components.items()))


def calculate_summary(regressions: list) -> dict:
    """
    Calculate summary statistics for a list of regressions.
    
    Args:
        regressions: List of regression dictionaries
    
    Returns:
        Dictionary containing summary statistics with nested open/closed totals and triaged counts
    """
    total = len(regressions)
    
    # Split into open and closed
    open_regressions = [r for r in regressions if r.get('closed') is None]
    closed_regressions = [r for r in regressions if r.get('closed') is not None]
    
    # Count triaged regressions (those with non-empty triages list)
    open_triaged = len([r for r in open_regressions if r.get('triages', [])])
    closed_triaged = len([r for r in closed_regressions if r.get('triages', [])])
    
    return {
        "total": total,
        "open": {
            "total": len(open_regressions),
            "triaged": open_triaged
        },
        "closed": {
            "total": len(closed_regressions),
            "triaged": closed_triaged
        }
    }


def add_component_summaries(components: dict) -> dict:
    """
    Add summary statistics to each component object.
    
    Args:
        components: Dictionary mapping component names to objects containing open and closed regression lists
    
    Returns:
        Dictionary with summaries added to each component
    """
    for component, component_data in components.items():
        # Combine open and closed to get all regressions for this component
        all_regressions = component_data["open"] + component_data["closed"]
        component_data["summary"] = calculate_summary(all_regressions)
    
    return components


def format_output(data: dict) -> str:
    """
    Format the regression data for output.

    Args:
        data: Dictionary containing regression data with keys:
            - 'summary': Overall statistics (total, open, closed)
            - 'components': Dictionary mapping component names to objects with:
                - 'summary': Per-component statistics
                - 'open': List of open regression objects
                - 'closed': List of closed regression objects

    Returns:
        Formatted JSON string output
    """
    return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch regression data for OpenShift components',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all regressions for release 4.17
  %(prog)s --release 4.17
  
  # Filter by specific components
  %(prog)s --release 4.21 --components Monitoring "kube-apiserver"
  
  # Filter by multiple components
  %(prog)s --release 4.21 --components Monitoring etcd "kube-apiserver"
        """
    )
    
    parser.add_argument(
        '--release',
        type=str,
        required=True,
        help='Release version (e.g., "4.17", "4.16")'
    )
    
    parser.add_argument(
        '--components',
        type=str,
        nargs='+',
        default=None,
        help='Filter by component names (space-separated list, case-insensitive)'
    )
    
    args = parser.parse_args()
    
    try:
        # Fetch regressions
        regressions = fetch_regressions(args.release)

        # Filter by components (always called to remove empty component names)
        if isinstance(regressions, list):
            regressions = filter_by_components(regressions, args.components)

        # Simplify time field structures (closed, last_failure)
        if isinstance(regressions, list):
            regressions = simplify_time_fields(regressions)

        # Group regressions by component
        if isinstance(regressions, list):
            components = group_by_component(regressions)
        else:
            components = {}

        # Add summaries to each component
        if isinstance(components, dict):
            components = add_component_summaries(components)

        # Calculate overall summary statistics from all regressions
        all_regressions = []
        for comp_data in components.values():
            all_regressions.extend(comp_data["open"])
            all_regressions.extend(comp_data["closed"])
        
        overall_summary = calculate_summary(all_regressions)

        # Construct output with summary and components
        output_data = {
            "summary": overall_summary,
            "components": components
        }

        # Format and print output
        output = format_output(output_data)
        print(output)

        return 0
    
    except Exception as e:
        print(f"Failed to fetch regressions: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

