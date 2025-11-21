#!/usr/bin/env python3
"""
fetch-rhcos-metadata.py - Fetch RHCOS metadata from OpenShift installer repository

This script fetches the rhcos.json metadata file from the openshift/installer
GitHub repository for a specific OpenShift version and extracts the OVA download URL.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def parse_version(version):
    """Parse OpenShift version to extract major.minor"""
    # Remove 'latest-' or 'stable-' prefix if present
    version = version.replace('latest-', '').replace('stable-', '').replace('fast-', '').replace('candidate-', '')

    # Extract major.minor from version like "4.20.1" -> "4.20"
    parts = version.split('.')
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"

    return version


def fetch_rhcos_metadata(version):
    """
    Fetch RHCOS metadata from openshift/installer GitHub repository

    Args:
        version: OpenShift version (e.g., "4.20", "4.19", "latest-4.20")

    Returns:
        dict: RHCOS metadata

    Raises:
        Exception: If metadata cannot be fetched
    """
    major_minor = parse_version(version)
    branch = f"release-{major_minor}"
    url = f"https://raw.githubusercontent.com/openshift/installer/refs/heads/{branch}/data/data/coreos/rhcos.json"

    print(f"Fetching RHCOS metadata for OpenShift {major_minor}", file=sys.stderr)
    print(f"URL: {url}", file=sys.stderr)

    try:
        with urllib.request.urlopen(url) as response:
            data = response.read()
            return json.loads(data)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise Exception(f"RHCOS metadata not found for version {major_minor}. Branch '{branch}' may not exist yet.")
        raise Exception(f"HTTP error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise Exception(f"Network error: {e.reason}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON in RHCOS metadata: {e}")


def extract_ova_info(metadata):
    """
    Extract OVA download URL and related information from RHCOS metadata

    Args:
        metadata: RHCOS metadata dictionary

    Returns:
        dict: OVA information including URL, SHA256, version
    """
    try:
        # Navigate to the OVA information (x86_64 architecture)
        vmware_artifacts = metadata['architectures']['x86_64']['artifacts']['vmware']
        ova_format = vmware_artifacts['formats']['ova']
        disk_info = ova_format['disk']

        return {
            'url': disk_info['location'],
            'sha256': disk_info.get('sha256', ''),
            'uncompressed_sha256': disk_info.get('uncompressed-sha256', ''),
            'rhcos_version': metadata.get('oscontainer', {}).get('version', 'unknown'),
            'openshift_version': metadata.get('buildid', 'unknown')
        }
    except KeyError as e:
        raise Exception(f"Missing key in RHCOS metadata: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Fetch RHCOS OVA metadata from openshift/installer repository',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch metadata for OpenShift 4.20
  %(prog)s 4.20

  # Fetch metadata for OpenShift 4.19 (works with various formats)
  %(prog)s latest-4.19
  %(prog)s stable-4.19
  %(prog)s 4.19.0

Output format (JSON):
  {
    "url": "https://...",
    "sha256": "...",
    "rhcos_version": "420.94.202501071309-0",
    "openshift_version": "..."
  }
        """
    )

    parser.add_argument(
        'version',
        help='OpenShift version (e.g., 4.20, latest-4.19, stable-4.18)'
    )

    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print JSON output'
    )

    args = parser.parse_args()

    try:
        # Fetch metadata
        metadata = fetch_rhcos_metadata(args.version)

        # Extract OVA info
        ova_info = extract_ova_info(metadata)

        # Output JSON
        if args.pretty:
            print(json.dumps(ova_info, indent=2))
        else:
            print(json.dumps(ova_info))

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
