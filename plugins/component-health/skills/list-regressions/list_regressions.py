#!/usr/bin/env python3
"""
Script to fetch regression data for OpenShift components.

Usage:
    python3 list_regressions.py --release <release> [--opened <true|false>]

Example:
    python3 list_regressions.py --release 4.17 --opened true
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from typing import Optional


def fetch_regressions(release: str, opened: Optional[bool] = None) -> dict:
    """
    Fetch regression data from the component health API.
    
    Args:
        release: The release version (e.g., "4.17", "4.16")
        opened: Optional boolean to filter by open/closed status
    
    Returns:
        Dictionary containing the regression data
    
    Raises:
        urllib.error.URLError: If the request fails
    """
    # Construct the base URL - update this with the actual endpoint
    base_url = f"https://sippy.dptools.openshift.org/api/component_readiness/regressions"
    
    # Build query parameters
    params = [f"release={release}"]
    if opened is not None:
        params.append(f"opened={'true' if opened else 'false'}")
    
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


def format_output(data: dict) -> str:
    """
    Format the regression data for output.
    
    Args:
        data: Dictionary containing regression data
    
    Returns:
        Formatted string output
    """
    return json.dumps(data, indent=2)


def parse_bool(value: str) -> bool:
    """
    Parse a boolean string value.
    
    Args:
        value: String value ("true", "false", "1", "0", etc.)
    
    Returns:
        Boolean value
    """
    value_lower = value.lower()
    if value_lower in ('true', '1', 'yes', 'y'):
        return True
    elif value_lower in ('false', '0', 'no', 'n'):
        return False
    else:
        raise ValueError(f"Invalid boolean value: {value}")


def main():
    parser = argparse.ArgumentParser(
        description='Fetch regression data for OpenShift components',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all regressions for release 4.17
  %(prog)s --release 4.17
  
  # List only open regressions for release 4.16
  %(prog)s --release 4.16 --opened true
  
  # List closed regressions for release 4.15
  %(prog)s --release 4.15 --opened false
  
  # Filter by specific components
  %(prog)s --release 4.21 --components Monitoring "kube-apiserver"
        """
    )
    
    parser.add_argument(
        '--release',
        type=str,
        required=True,
        help='Release version (e.g., "4.17", "4.16")'
    )
    
    parser.add_argument(
        '--opened',
        type=str,
        choices=['true', 'false'],
        default=None,
        help='Filter by opened status (true for open, false for closed)'
    )
    
    parser.add_argument(
        '--components',
        type=str,
        nargs='+',
        default=None,
        help='Filter by component names (space-separated list, case-insensitive)'
    )
    
    args = parser.parse_args()
    
    # Parse the opened flag
    opened = None
    if args.opened is not None:
        opened = parse_bool(args.opened)
    
    try:
        # Fetch regressions
        regressions = fetch_regressions(args.release, opened)
        
        # Filter by components if specified
        if args.components and isinstance(regressions, list):
            regressions = filter_by_components(regressions, args.components)
        
        # Simplify time field structures (closed, last_failure)
        if isinstance(regressions, list):
            regressions = simplify_time_fields(regressions)
        
        # Reconstruct the data structure if it was originally a dict
        filtered_data = regressions
        
        # Format and print output
        output = format_output(filtered_data)
        print(output)
        
        return 0
    
    except Exception as e:
        print(f"Failed to fetch regressions: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

