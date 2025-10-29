#!/usr/bin/env python3
"""
Extract MicroShift version from Prow CI build logs.

This script fetches the build log from a Prow CI job and extracts the
exact MicroShift version being tested, along with determining the build type.

Usage:
    python3 extract_microshift_version.py <job_id> <version> <job_type>

Arguments:
    job_id: The Prow CI job ID (e.g., "1982281180531134464")
    version: The release version (e.g., "4.20")
    job_type: The job type (e.g., "e2e-aws-tests-bootc-release-periodic" or "e2e-aws-tests-release-periodic")
Output:
    JSON object with:
    {
        "version": "4.20.0-0.nightly-2025-10-15-110252-20251024164401-7d3263467",
        "build_type": "nightly",
        "success": true,
        "error": null
    }
"""

import sys
import json
import re
import urllib.request
import urllib.error
import ssl


def construct_build_log_url(version, job_id, job_type):
    """Construct the URL to the build log for a given job."""
    base_url = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"
    job_name = f"periodic-ci-openshift-microshift-release-{version}-periodics-{job_type}"
    artifact_path = f"artifacts/{job_type}/openshift-microshift-e2e-metal-tests/artifacts/scenario-info/el96-lrel@standard1/rf-debug.log"
    
    return f"{base_url}/{job_name}/{job_id}/{artifact_path}"


def fetch_build_log(url):
    """Fetch the build log content from the given URL."""
    try:
        # Create SSL context that doesn't verify certificates
        # This is needed for some environments where SSL cert chain is incomplete
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(url, timeout=30, context=ssl_context) as response:
            content = response.read().decode('utf-8')
            return content, None
    except urllib.error.URLError as e:
        return None, f"Failed to fetch build log: {e}"
    except Exception as e:
        return None, f"Error reading build log: {e}"


def extract_version_from_log(log_content):
    """
    Extract MicroShift version from build log content.
    
    Looks for patterns like:
    - ${version_string_raw} = 4.20.0-202510161342.p0.g17d1d9a.assembly.4.20.0.el9.x86_64
    """
    # Look for the version string pattern in the log
    # Pattern: ${version_string_raw} = 4.20.0-202510161342.p0.g17d1d9a.assembly.4.20.0.el9.x86_64
    pattern = r'\$\{version_string_raw\}\s*=\s*(.+?)(?:\s|$)'
    
    match = re.search(pattern, log_content)
    if match:
        version_string = match.group(1).strip()
        return version_string, None
    
    return None, "Could not find version string in build log"


def determine_build_type(version_string):
    """
    Determine the build type from the version string.
    
    Returns one of: "nightly", "ec", "rc", "zstream"
    """
    if "nightly" in version_string.lower():
        return "nightly"
    elif "-ec." in version_string:
        return "ec"
    elif "-rc." in version_string:
        return "rc"
    else:
       return "zstream"


def main():
    """Main entry point."""
    if len(sys.argv) != 4:
        print(json.dumps({
            "success": False,
            "error": "Usage: extract_microshift_version.py <job_id> <version> <job_type>"
        }))
        sys.exit(1)
    
    job_id = sys.argv[1]
    version = sys.argv[2]
    job_type = sys.argv[3]

    # Construct build log URL
    url = construct_build_log_url(version, job_id, job_type)
    
    # Fetch build log
    log_content, error = fetch_build_log(url)
    if error:
        print(json.dumps({
            "success": False,
            "error": error,
            "url": url
        }))
        sys.exit(1)
    
    # Extract version
    microshift_version, error = extract_version_from_log(log_content)
    if error:
        print(json.dumps({
            "success": False,
            "error": error,
            "url": url
        }))
        sys.exit(1)
    
    # Determine build type
    build_type = determine_build_type(microshift_version)
    
    # Output result
    result = {
        "success": True,
        "version": microshift_version,
        "build_type": build_type,
        "url": url,
        "error": None
    }
    
    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
