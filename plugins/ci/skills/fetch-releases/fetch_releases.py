#!/usr/bin/env python3
"""Fetch OpenShift release information from the Sippy API.

Lists available OCP releases, optionally returning just the latest release version.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

SIPPY_API_URL = "https://sippy.dptools.openshift.org/api/releases"


def fetch_releases() -> dict:
    """Fetch all release data from the Sippy API."""
    try:
        with urllib.request.urlopen(SIPPY_API_URL, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} from Sippy API: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Failed to connect to Sippy API: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def get_ocp_releases(data: dict) -> list:
    """Filter to standard OCP releases (e.g. '4.22', '4.21'), excluding okd, aro, presubmits."""
    releases = data.get("releases", [])
    return [r for r in releases if re.match(r"^\d+\.\d+$", r)]


def main():
    parser = argparse.ArgumentParser(
        description="Fetch OpenShift release information from the Sippy API.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Print only the latest OCP release version (e.g., '4.22')",
    )
    parser.add_argument(
        "--format",
        choices=["json", "list"],
        default="json",
        help="Output format (default: json). 'list' prints one release per line.",
    )

    args = parser.parse_args()

    data = fetch_releases()
    ocp_releases = get_ocp_releases(data)

    if not ocp_releases:
        print("Error: No OCP releases found in Sippy API.", file=sys.stderr)
        sys.exit(1)

    if args.latest:
        print(ocp_releases[0])
        return

    if args.format == "list":
        for r in ocp_releases:
            print(r)
    else:
        ga_dates = data.get("ga_dates", {})
        output = []
        for r in ocp_releases:
            entry = {"release": r}
            if r in ga_dates and ga_dates[r]:
                entry["ga"] = ga_dates[r]
            output.append(entry)
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
