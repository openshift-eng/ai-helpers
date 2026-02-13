#!/usr/bin/env python3
"""Look up an OpenShift CI test by name using the Sippy tests API.

Returns test metadata including pass rates, test ID, Jira component, and run counts
for the current and previous reporting periods.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SIPPY_API_BASE = "https://sippy.dptools.openshift.org/api"
SIPPY_RELEASES_URL = "https://sippy.dptools.openshift.org/api/releases"


def get_latest_release() -> str:
    """Fetch the latest OCP release version from the Sippy releases API."""
    try:
        with urllib.request.urlopen(SIPPY_RELEASES_URL, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error: Could not fetch releases from Sippy API: {e}", file=sys.stderr)
        sys.exit(1)

    releases = data.get("releases", [])
    ocp_releases = [r for r in releases if re.match(r"^\d+\.\d+$", r)]
    if not ocp_releases:
        print("Error: No OCP releases found in Sippy API.", file=sys.stderr)
        sys.exit(1)

    return ocp_releases[0]


def lookup_test(test_name: str, release: str, collapse: bool = True) -> list:
    """Look up a test by name in the Sippy tests API."""
    filter_param = json.dumps({
        "items": [
            {
                "columnField": "name",
                "operatorValue": "equals",
                "value": test_name,
            }
        ],
    })
    query = {
        "release": release,
        "filter": filter_param,
    }
    if not collapse:
        query["collapse"] = "false"
    params = urllib.parse.urlencode(query)
    url = f"{SIPPY_API_BASE}/tests/v2?{params}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} from Sippy API: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Failed to connect to Sippy API: {e.reason}", file=sys.stderr)
        print("Check network connectivity to sippy.dptools.openshift.org.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("Error: Unexpected API response format (expected a JSON array).", file=sys.stderr)
        sys.exit(1)

    return data


def format_summary(tests: list) -> str:
    """Format test results as a human-readable summary."""
    if not tests:
        return "No tests found matching the given name."

    lines = []
    for i, t in enumerate(tests):
        if i > 0:
            lines.append("-" * 60)
        lines.append(f"Test: {t.get('name', 'N/A')}")
        lines.append(f"  Test ID:         {t.get('test_id', 'N/A')}")
        lines.append(f"  Suite:           {t.get('suite_name', '') or 'N/A'}")
        lines.append(f"  Jira Component:  {t.get('jira_component', 'N/A')}")

        variants = t.get("variants")
        if variants:
            lines.append(f"  Variants:        {', '.join(variants)}")

        open_bugs = t.get("open_bugs", 0)
        if open_bugs > 0:
            lines.append(f"  Open Bugs:       {open_bugs} (bugs filed mentioning this test)")
        else:
            lines.append(f"  Open Bugs:       0")

        lines.append("")
        lines.append(f"  Current Period (last 7 days):")
        lines.append(f"    Runs:       {t.get('current_runs', 0)}")
        lines.append(f"    Pass Rate:  {t.get('current_pass_percentage', 0):.2f}%")
        lines.append(f"    Failures:   {t.get('current_failures', 0)} ({t.get('current_failure_percentage', 0):.2f}%)")
        lines.append(f"    Flakes:     {t.get('current_flakes', 0)} ({t.get('current_flake_percentage', 0):.2f}%)")
        lines.append("")
        lines.append(f"  Previous Period (7 days before current):")
        lines.append(f"    Runs:       {t.get('previous_runs', 0)}")
        lines.append(f"    Pass Rate:  {t.get('previous_pass_percentage', 0):.2f}%")
        lines.append(f"    Failures:   {t.get('previous_failures', 0)} ({t.get('previous_failure_percentage', 0):.2f}%)")
        lines.append(f"    Flakes:     {t.get('previous_flakes', 0)} ({t.get('previous_flake_percentage', 0):.2f}%)")
        lines.append("")
        net = t.get("net_working_improvement", 0)
        direction = "improved" if net > 0 else "regressed" if net < 0 else "unchanged"
        lines.append(f"  Trend:  {direction} ({net:+.2f}%)")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Look up an OpenShift CI test by name using the Sippy API.",
    )
    parser.add_argument(
        "test_name",
        help='The full test name (e.g., "[sig-api-machinery] Discovery should validate PreferredVersion ...")',
    )
    parser.add_argument(
        "--release",
        default=None,
        help="OpenShift release version (e.g., 4.22). If omitted, the latest release is auto-detected.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--no-collapse",
        action="store_true",
        help="Show per-variant breakdown instead of collapsing all variants into one row",
    )

    args = parser.parse_args()

    release = args.release
    if release is None:
        release = get_latest_release()
        print(f"Using latest release: {release}", file=sys.stderr)

    tests = lookup_test(args.test_name, release, collapse=not args.no_collapse)

    if args.format == "json":
        print(json.dumps(tests, indent=2))
    else:
        print(format_summary(tests))


if __name__ == "__main__":
    main()
