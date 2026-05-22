#!/usr/bin/env python3
"""Fetch OpenShift CI job reports from the Sippy jobs API.

Returns job metadata including pass rates, run counts, and trend data
for the current and previous reporting periods.
"""

import argparse
import json
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


def build_filter(name: str = None, repo: str = None, exclude_never_stable: bool = True) -> str:
    """Build a Sippy filter JSON string."""
    items = []

    if exclude_never_stable:
        items.append({
            "columnField": "variants",
            "operatorValue": "has entry",
            "value": "never-stable",
            "not": True,
        })

    if name:
        items.append({
            "columnField": "name",
            "operatorValue": "contains",
            "value": name,
        })

    if repo:
        items.append({
            "columnField": "repo",
            "operatorValue": "equals",
            "value": repo,
        })

    if not items:
        return ""

    return json.dumps({"items": items, "linkOperator": "and"})


def fetch_jobs(release: str, filter_str: str = "", sort_field: str = "current_runs",
               sort_dir: str = "desc", period: str = "default", limit: int = 0) -> list:
    """Fetch jobs from the Sippy jobs API."""
    query = {"release": release, "period": period, "sortField": sort_field, "sort": sort_dir}

    if filter_str:
        query["filter"] = filter_str
    if limit > 0:
        query["limit"] = str(limit)

    params = urllib.parse.urlencode(query)
    url = f"{SIPPY_API_BASE}/jobs?{params}"

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


def format_summary(jobs: list) -> str:
    """Format job results as a human-readable summary."""
    if not jobs:
        return "No jobs found matching the given criteria."

    lines = []
    lines.append(f"Found {len(jobs)} jobs:\n")

    for i, j in enumerate(jobs):
        if i > 0:
            lines.append("-" * 70)

        lines.append(f"Job: {j.get('name', 'N/A')}")
        brief = j.get("brief_name", "")
        if brief:
            lines.append(f"  Brief Name:  {brief}")

        org = j.get("org", "")
        repo = j.get("repo", "")
        if org or repo:
            lines.append(f"  Repo:        {org}/{repo}" if org else f"  Repo:        {repo}")

        variants = j.get("variants")
        if variants:
            lines.append(f"  Variants:    {', '.join(variants)}")

        open_bugs = j.get("open_bugs", 0)
        if open_bugs > 0:
            lines.append(f"  Open Bugs:   {open_bugs}")

        lines.append("")
        lines.append(f"  Current Period (last 7 days):")
        lines.append(f"    Runs:       {j.get('current_runs', 0)}")
        lines.append(f"    Pass Rate:  {j.get('current_pass_percentage', 0):.2f}%")
        lines.append(f"    Passes:     {j.get('current_passes', 0)}")
        lines.append(f"    Fails:      {j.get('current_fails', 0)}")
        infra = j.get("current_infra_fails", 0)
        if infra > 0:
            lines.append(f"    Infra Fails: {infra}")

        lines.append("")
        lines.append(f"  Previous Period (7 days before current):")
        lines.append(f"    Runs:       {j.get('previous_runs', 0)}")
        lines.append(f"    Pass Rate:  {j.get('previous_pass_percentage', 0):.2f}%")
        lines.append(f"    Passes:     {j.get('previous_passes', 0)}")
        lines.append(f"    Fails:      {j.get('previous_fails', 0)}")
        prev_infra = j.get("previous_infra_fails", 0)
        if prev_infra > 0:
            lines.append(f"    Infra Fails: {prev_infra}")

        lines.append("")
        net = j.get("net_improvement", 0)
        direction = "improved" if net > 0 else "regressed" if net < 0 else "unchanged"
        lines.append(f"  Trend:  {direction} ({net:+.2f}%)")

        retests = j.get("average_retests_to_merge", 0)
        if retests and retests > 0:
            lines.append(f"  Avg Retests to Merge: {retests:.1f}")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch OpenShift CI job reports from the Sippy jobs API.",
    )
    parser.add_argument(
        "--release",
        default=None,
        help="OpenShift release version (e.g., 4.19) or 'Presubmits' for pull request jobs. "
             "If omitted, the latest release is auto-detected.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Filter jobs by name (substring match).",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Filter presubmit jobs by repository name (e.g., 'origin', 'machine-config-operator').",
    )
    parser.add_argument(
        "--sort-field",
        default="current_runs",
        help="Field to sort by (default: current_runs). Common: current_runs, current_pass_percentage, "
             "net_improvement, name.",
    )
    parser.add_argument(
        "--sort",
        choices=["asc", "desc"],
        default="desc",
        help="Sort direction (default: desc).",
    )
    parser.add_argument(
        "--period",
        choices=["default", "twoDay"],
        default="default",
        help="Reporting period (default: 7-day windows, twoDay: 2-day current vs 7-day previous).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of jobs to return (default: no limit).",
    )
    parser.add_argument(
        "--include-never-stable",
        action="store_true",
        help="Include never-stable jobs (excluded by default).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="Output format (default: json).",
    )

    args = parser.parse_args()

    release = args.release
    if release is None:
        release = get_latest_release()
        print(f"Using latest release: {release}", file=sys.stderr)

    filter_str = build_filter(
        name=args.name,
        repo=args.repo,
        exclude_never_stable=not args.include_never_stable,
    )

    jobs = fetch_jobs(
        release=release,
        filter_str=filter_str,
        sort_field=args.sort_field,
        sort_dir=args.sort,
        period=args.period,
        limit=args.limit,
    )

    if args.format == "json":
        print(json.dumps(jobs, indent=2))
    else:
        print(format_summary(jobs))


if __name__ == "__main__":
    main()
