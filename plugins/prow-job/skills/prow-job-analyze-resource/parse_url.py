#!/usr/bin/env python3
"""
Parse and validate Prow job URLs from gcsweb.
Extracts build_id, prowjob name, and GCS paths.
"""

import re
import sys
import json
from urllib.parse import urlparse


def parse_prowjob_url(url):
    """
    Parse a Prow job URL and extract relevant information.

    Args:
        url: gcsweb URL containing test-platform-results

    Returns:
        dict with keys: bucket_path, build_id, prowjob_name, gcs_base_path

    Raises:
        ValueError: if URL format is invalid
    """
    # Find test-platform-results in URL
    if 'test-platform-results/' not in url:
        raise ValueError(
            "URL must contain 'test-platform-results/' substring.\n"
            "Example: https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/"
            "test-platform-results/pr-logs/pull/30393/pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn/1978913325970362368/"
        )

    # Extract path after test-platform-results/
    bucket_path = url.split('test-platform-results/')[1]

    # Remove trailing slash if present
    bucket_path = bucket_path.rstrip('/')

    # Find build_id: at least 10 consecutive decimal digits delimited by /
    build_id_pattern = r'/(\d{10,})(?:/|$)'
    match = re.search(build_id_pattern, bucket_path)

    if not match:
        raise ValueError(
            f"Could not find build ID (10+ decimal digits) in URL path.\n"
            f"Bucket path: {bucket_path}\n"
            f"Expected pattern: /NNNNNNNNNN/ where N is a digit"
        )

    build_id = match.group(1)

    # Extract prowjob name: path segment immediately before build_id
    # Split bucket_path by / and find segment before build_id
    path_segments = bucket_path.split('/')

    try:
        build_id_index = path_segments.index(build_id)
        if build_id_index == 0:
            raise ValueError("Build ID cannot be the first path segment")
        prowjob_name = path_segments[build_id_index - 1]
    except (ValueError, IndexError):
        raise ValueError(
            f"Could not extract prowjob name from path.\n"
            f"Build ID: {build_id}\n"
            f"Path segments: {path_segments}"
        )

    # Construct GCS base path
    gcs_base_path = f"gs://test-platform-results/{bucket_path}/"

    return {
        'bucket_path': bucket_path,
        'build_id': build_id,
        'prowjob_name': prowjob_name,
        'gcs_base_path': gcs_base_path,
        'original_url': url
    }


def main():
    """Parse URL from command line argument and output JSON."""
    if len(sys.argv) != 2:
        print("Usage: parse_url.py <prowjob-url>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]

    try:
        result = parse_prowjob_url(url)
        print(json.dumps(result, indent=2))
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
