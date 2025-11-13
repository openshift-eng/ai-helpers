#!/usr/bin/env python3
"""
Script to fetch component names from Sippy component readiness API.

Usage:
    python3 list_components.py --release <release>

Example:
    python3 list_components.py --release 4.21
    python3 list_components.py --release 4.20
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def fetch_components(release: str) -> list:
    """
    Fetch component names from the component readiness API.

    Args:
        release: The release version (e.g., "4.21", "4.20")

    Returns:
        List of unique component names

    Raises:
        urllib.error.URLError: If the request fails
    """
    # Construct the view parameter (e.g., "4.21-main")
    view = f"{release}-main"

    # Construct the URL
    url = f"https://sippy.dptools.openshift.org/api/component_readiness?view={view}"

    print(f"Fetching components from: {url}", file=sys.stderr)

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))

                # Extract component names from rows
                components = []
                if 'rows' in data:
                    for row in data['rows']:
                        if 'component' in row and row['component']:
                            components.append(row['component'])

                # Return unique components, sorted alphabetically
                unique_components = sorted(set(components))

                print(f"Found {len(unique_components)} unique components", file=sys.stderr)

                return unique_components
            else:
                raise Exception(f"HTTP {response.status}: {response.reason}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        if e.code == 404:
            print(f"View '{view}' not found. Please check the release version.", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Fetch component names from Sippy component readiness API'
    )

    parser.add_argument(
        '--release',
        type=str,
        required=True,
        help='Release version (e.g., "4.21", "4.20")'
    )

    args = parser.parse_args()

    try:
        # Fetch components
        components = fetch_components(args.release)

        # Output as JSON array
        output = {
            "release": args.release,
            "view": f"{args.release}-main",
            "component_count": len(components),
            "components": components
        }

        print(json.dumps(output, indent=2))

    except Exception as e:
        print(f"Failed to fetch components: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
