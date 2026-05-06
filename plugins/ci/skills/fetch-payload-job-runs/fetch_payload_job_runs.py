#!/usr/bin/env python3
"""Fetch job runs for a specific payload tag from the Sippy API.

Returns job run details including state, kind, upgrade info, and Prow URLs.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


SIPPY_API_URL = "https://sippy.dptools.openshift.org/api/releases/job_runs"


def extract_release(tag: str) -> str:
    """Extract the release version (e.g. '4.19') from a payload tag."""
    match = re.match(r"^(\d+\.\d+)", tag)
    if not match:
        print(f"Error: Cannot extract release version from tag '{tag}'", file=sys.stderr)
        sys.exit(1)
    return match.group(1)


def fetch_job_runs(tag: str, upgrade_only: bool = False) -> list:
    """Fetch job runs for the given payload tag from Sippy."""
    release = extract_release(tag)

    filter_items = [
        {
            "columnField": "release_tag",
            "operatorValue": "=",
            "value": tag,
        },
    ]
    if upgrade_only:
        filter_items.append({
            "columnField": "upgrade",
            "operatorValue": "=",
            "value": "true",
        })

    params = urllib.parse.urlencode({
        "release": release,
        "filter": json.dumps({"items": filter_items}),
    })
    url = f"{SIPPY_API_URL}?{params}"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} from {url}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Failed to connect: {e.reason}", file=sys.stderr)
        sys.exit(1)


def format_text(job_runs: list, tag: str, upgrade_only: bool) -> str:
    """Format job runs as human/AI-readable text."""
    lines = []
    lines.append(f"Payload: {tag}")
    lines.append(f"Filter: {'upgrade jobs only' if upgrade_only else 'all jobs'}")
    lines.append(f"Total job runs: {len(job_runs)}")
    lines.append("")

    # Group by kind
    by_kind = {}
    for run in job_runs:
        kind = run.get("kind", "Unknown")
        by_kind.setdefault(kind, []).append(run)

    for kind in sorted(by_kind.keys()):
        runs = by_kind[kind]
        succeeded = sum(1 for r in runs if r.get("state") == "Succeeded")
        failed = sum(1 for r in runs if r.get("state") == "Failed")
        other = len(runs) - succeeded - failed
        lines.append(f"## {kind} Jobs ({len(runs)} total, {succeeded} succeeded, {failed} failed)")
        lines.append("")

        for run in sorted(runs, key=lambda r: r.get("state", "")):
            state = run.get("state", "Unknown")
            job_name = run.get("job_name", "unknown")
            url = run.get("url", "")
            retries = run.get("retries", 0)

            state_icon = "PASS" if state == "Succeeded" else "FAIL" if state == "Failed" else state
            line = f"  [{state_icon}] {job_name}"
            if retries > 0:
                line += f" (retries: {retries})"
            lines.append(line)

            if run.get("upgrade"):
                upgrades_from = run.get("upgrades_from", "")
                upgrades_to = run.get("upgrades_to", "")
                if upgrades_from:
                    lines.append(f"         upgrade: {upgrades_from} -> {upgrades_to}")

            if url:
                lines.append(f"         {url}")
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch job runs for a payload tag from Sippy.",
    )
    parser.add_argument(
        "tag",
        help="Payload tag (e.g. 4.19.0-0.nightly-2026-04-02-000704)",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        default=False,
        help="Show only upgrade jobs",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

    job_runs = fetch_job_runs(args.tag, upgrade_only=args.upgrade)

    if not job_runs:
        print(f"No job runs found for tag '{args.tag}'.", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        print(json.dumps(job_runs, indent=2))
    else:
        print(format_text(job_runs, args.tag, args.upgrade))


if __name__ == "__main__":
    main()
