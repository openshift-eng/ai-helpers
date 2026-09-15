#!/usr/bin/env python3
"""
Parse and validate Prow job URLs from prow or gcsweb.
Extracts build_id, prowjob name, and GCS paths.
"""

import re
import sys
import json


# Prow: /view/gs/<bucket>/...  gcsweb: /gcs/<bucket>/...
_GCS_PATH = re.compile(r"/(?:gs|gcs)/([^/]+)/(.+)$")
PUBLIC_BUCKET = "test-platform-results-public"
LEGACY_BUCKET = "test-platform-results"


def parse_prowjob_url(url):
    """
    Parse a Prow job URL and extract relevant information.

    Args:
        url: prow or gcsweb URL containing /gs/<bucket>/ or /gcs/<bucket>/.
            A legacy test-platform-results URL is remapped to the public bucket
            for GCS paths; that bucket is not publicly readable.

    Returns:
        dict with keys: bucket, bucket_path, build_id, prowjob_name, gcs_base_path

    Raises:
        ValueError: if URL format is invalid
    """
    match = _GCS_PATH.search(url.rstrip("/"))
    if not match:
        raise ValueError(
            "URL must contain '/gs/<bucket>/' or '/gcs/<bucket>/'.\n"
            "Example: https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/"
            "test-platform-results-public/pr-logs/pull/30393/"
            "pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn/1978913325970362368/"
        )

    parsed_bucket = match.group(1)
    bucket = PUBLIC_BUCKET if parsed_bucket == LEGACY_BUCKET else parsed_bucket
    bucket_path = match.group(2).rstrip("/")

    # Find build_id: at least 10 consecutive decimal digits delimited by /
    build_id_pattern = r"/(\d{10,})(?:/|$)"
    id_match = re.search(build_id_pattern, bucket_path)

    if not id_match:
        raise ValueError(
            f"Could not find build ID (10+ decimal digits) in URL path.\n"
            f"Bucket path: {bucket_path}\n"
            f"Expected pattern: /NNNNNNNNNN/ where N is a digit"
        )

    build_id = id_match.group(1)

    # Extract prowjob name: path segment immediately before build_id
    path_segments = bucket_path.split("/")

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

    gcs_base_path = f"gs://{bucket}/{bucket_path}/"

    return {
        "bucket": bucket,
        "bucket_path": bucket_path,
        "build_id": build_id,
        "prowjob_name": prowjob_name,
        "gcs_base_path": gcs_base_path,
        "original_url": url,
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


if __name__ == "__main__":
    sys.exit(main())
