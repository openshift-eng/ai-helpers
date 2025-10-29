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
    
    args = parser.parse_args()
    
    # Parse the opened flag
    opened = None
    if args.opened is not None:
        opened = parse_bool(args.opened)
    
    try:
        # Fetch regressions
        data = fetch_regressions(args.release, opened)
        
        # Format and print output
        output = format_output(data)
        print(output)
        
        return 0
    
    except Exception as e:
        print(f"Failed to fetch regressions: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

