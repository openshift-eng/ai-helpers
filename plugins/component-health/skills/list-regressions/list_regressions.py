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


def filter_by_components(data: list, components: list) -> list:
    """
    Filter regression data by component names.
    
    Args:
        data: List of regression dictionaries
        components: List of component names to filter by
    
    Returns:
        Filtered list of regressions matching the specified components
    """
    if not components:
        return data
    
    # Convert components to lowercase for case-insensitive comparison
    components_lower = [c.lower() for c in components]
    
    filtered = [
        regression for regression in data
        if regression.get('component', '').lower() in components_lower
    ]
    
    print(f"Filtered from {len(data)} to {len(filtered)} regressions for components: {', '.join(components)}", 
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


def calculate_summary(regressions: list) -> dict:
    """
    Calculate summary statistics for regressions.

    Args:
        regressions: List of regression dictionaries

    Returns:
        Dictionary containing summary statistics
    """
    total = len(regressions)
    open_count = len([r for r in regressions if r.get('closed') is None])
    closed_count = len([r for r in regressions if r.get('closed') is not None])

    return {
        "total": total,
        "open": open_count,
        "closed": closed_count
    }


def format_output(data: dict) -> str:
    """
    Format the regression data for output.

    Args:
        data: Dictionary containing regression data (should have 'summary' and 'regressions' keys)

    Returns:
        Formatted string output
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

        # Filter by components if specified
        if args.components and isinstance(regressions, list):
            regressions = filter_by_components(regressions, args.components)

        # Simplify time field structures (closed, last_failure)
        if isinstance(regressions, list):
            regressions = simplify_time_fields(regressions)

        # Calculate summary statistics
        summary = calculate_summary(regressions) if isinstance(regressions, list) else {}

        # Construct output with summary and regressions
        output_data = {
            "summary": summary,
            "regressions": regressions
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

