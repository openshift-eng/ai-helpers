#!/usr/bin/env python3
"""
Fetch OpenShift release dates from Sippy API.

This script fetches release information including GA dates and development start dates
for OpenShift releases from the Sippy API.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def fetch_release_dates():
    """
    Fetch all release dates from Sippy API.
    
    Returns:
        Dictionary containing release information
        
    Raises:
        Exception: If the API request fails
    """
    url = "https://sippy.dptools.openshift.org/api/releases"
    
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP Error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise Exception(f"URL Error: {e.reason}")
    except Exception as e:
        raise Exception(f"Failed to fetch release dates: {str(e)}")


def get_release_info(data: dict, release: str) -> dict:
    """
    Extract information for a specific release.
    
    Args:
        data: Full API response containing all release data
        release: Release identifier (e.g., "4.21", "4.20")
    
    Returns:
        Dictionary containing release-specific information
        
    Note:
        If 'ga' and 'ga_date' fields are null/missing, the release is still 
        in development and has not reached General Availability yet.
    """
    result = {
        "release": release,
        "found": False
    }
    
    # Check if release exists in the releases list
    if release in data.get("releases", []):
        result["found"] = True
        
        # Get detailed dates (GA and development start)
        dates = data.get("dates", {})
        if release in dates:
            release_dates = dates[release]
            result["ga"] = release_dates.get("ga")
            result["development_start"] = release_dates.get("development_start")
        
        # Get release attributes if available
        release_attrs = data.get("release_attrs", {})
        if release in release_attrs:
            attrs = release_attrs[release]
            result["previous_release"] = attrs.get("previous_release", "")
    
    return result


def format_output(data: dict) -> str:
    """
    Format the release data for output.
    
    Args:
        data: Dictionary containing release information
    
    Returns:
        Formatted JSON string
    """
    return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch OpenShift release dates from Sippy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get dates for release 4.21
  python3 get_release_dates.py --release 4.21
  
  # Get dates for release 4.20
  python3 get_release_dates.py --release 4.20
"""
    )
    
    parser.add_argument(
        '--release',
        type=str,
        required=True,
        help='Release version (e.g., "4.21", "4.20")'
    )
    
    args = parser.parse_args()
    
    try:
        # Fetch all release data
        data = fetch_release_dates()
        
        # Extract info for the specific release
        release_info = get_release_info(data, args.release)
        
        # Format and print output
        output = format_output(release_info)
        print(output)
        
        # Return exit code based on whether release was found
        return 0 if release_info["found"] else 1
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

