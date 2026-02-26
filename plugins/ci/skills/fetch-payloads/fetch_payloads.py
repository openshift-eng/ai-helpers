#!/usr/bin/env python3
"""Fetch recent release payloads from the OpenShift release controller.

Lists release payloads for a given architecture, version, and stream,
showing their tag name, phase (Accepted/Rejected/Ready), and a link
to the release controller page for more details.

For rejected payloads, fetches release details and reports which
blocking jobs failed with their Prow links.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

# Architectures that have their own release controller domain.
KNOWN_ARCHITECTURES = ["amd64", "arm64", "ppc64le", "s390x", "multi"]

SIPPY_API_URL = "https://sippy.dptools.openshift.org/api/releases"


def rc_domain(architecture: str) -> str:
    """Return the release controller domain for the given architecture."""
    return f"{architecture}.ocp.releases.ci.openshift.org"


def release_stream_name(version: str, stream: str, architecture: str) -> str:
    """Build the release stream identifier used by the release controller.

    Mirrors the logic in sippy's OCPProject.FullReleaseStream:
      - amd64:  4.18.0-0.nightly
      - others: 4.18.0-0.nightly-arm64
      - ci stream is only available on amd64
    """
    if stream == "ci" and architecture != "amd64":
        print(
            "Error: The 'ci' stream is only available for amd64.",
            file=sys.stderr,
        )
        sys.exit(1)

    name = f"{version}.0-0.{stream}"
    if architecture != "amd64":
        name += f"-{architecture}"
    return name


def fetch_json(url: str, timeout: int = 30) -> dict:
    """Fetch JSON from a URL."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} from {url}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Failed to connect: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def fetch_tags(architecture: str, version: str, stream: str) -> list:
    """Fetch release tags from the release controller API."""
    domain = rc_domain(architecture)
    stream_name = release_stream_name(version, stream, architecture)
    url = f"https://{domain}/api/v1/releasestream/{stream_name}/tags"
    data = fetch_json(url)
    return data.get("tags", [])


def fetch_release_details(architecture: str, stream_name: str, tag_name: str) -> dict:
    """Fetch details for a specific release tag."""
    domain = rc_domain(architecture)
    url = f"https://{domain}/api/v1/releasestream/{stream_name}/release/{tag_name}"
    return fetch_json(url)


def release_page_url(architecture: str, stream_name: str, tag_name: str) -> str:
    """Build the URL to the release controller page for a specific tag."""
    domain = rc_domain(architecture)
    return f"https://{domain}/releasestream/{stream_name}/release/{tag_name}"


def parse_timestamp(tag_name: str) -> str:
    """Extract a human-readable timestamp from a payload tag name.

    Tags contain a YYYY-MM-DD-HHMMSS suffix, e.g.:
      4.18.0-0.nightly-2026-02-26-105306 -> 2026-02-26 10:53:06
    """
    m = re.search(r"(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})(\d{2})$", tag_name)
    if m:
        return f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}"
    return "unknown"


def format_payload(tag: dict, details: dict, architecture: str, stream_name: str) -> str:
    """Format a single payload's output."""
    name = tag.get("name", "")
    phase = tag.get("phase", "Unknown")
    timestamp = parse_timestamp(name)
    url = release_page_url(architecture, stream_name, name)

    lines = [f"{name}  ({phase})  {timestamp}  {url}"]

    results = details.get("results", {})
    blocking = results.get("blockingJobs", {})

    if not blocking:
        return "\n".join(lines)

    if phase == "Rejected":
        failed = {k: v for k, v in blocking.items() if v.get("state") == "Failed"}
        succeeded = len([v for v in blocking.values() if v.get("state") == "Succeeded"])
        if failed:
            lines.append(f"  Blocking: {succeeded}/{len(blocking)} succeeded, {len(failed)} failed:")
            for job_name, info in sorted(failed.items()):
                retries = info.get("retries", 0)
                retry_str = f" ({retries} retries)" if retries else ""
                prow_url = info.get("url", "")
                lines.append(f"    FAILED  {job_name}{retry_str}")
                if prow_url:
                    lines.append(f"            {prow_url}")
    elif phase == "Ready":
        pending_jobs = {k: v for k, v in blocking.items() if v.get("state") == "Pending"}
        succeeded_jobs = {k: v for k, v in blocking.items() if v.get("state") == "Succeeded"}
        failed_jobs = {k: v for k, v in blocking.items() if v.get("state") == "Failed"}
        parts = []
        if succeeded_jobs:
            parts.append(f"{len(succeeded_jobs)} succeeded")
        if pending_jobs:
            parts.append(f"{len(pending_jobs)} pending")
        if failed_jobs:
            parts.append(f"{len(failed_jobs)} failed")
        lines.append(f"  Blocking: {', '.join(parts)} (of {len(blocking)})")
        if failed_jobs:
            lines.append(f"  Failed blocking jobs:")
            for job_name, info in sorted(failed_jobs.items()):
                retries = info.get("retries", 0)
                retry_str = f" ({retries} retries)" if retries else ""
                prow_url = info.get("url", "")
                lines.append(f"    FAILED  {job_name}{retry_str}")
                if prow_url:
                    lines.append(f"            {prow_url}")
    else:
        # Accepted - brief summary
        lines.append(f"  Blocking: {len(blocking)}/{len(blocking)} succeeded")

    return "\n".join(lines)


def get_latest_version() -> str:
    """Fetch the latest OCP version from the Sippy API."""
    try:
        with urllib.request.urlopen(SIPPY_API_URL, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error: Could not fetch releases from Sippy: {e}", file=sys.stderr)
        sys.exit(1)

    releases = data.get("releases", [])
    ocp_releases = [r for r in releases if re.match(r"^\d+\.\d+$", r)]
    if not ocp_releases:
        print("Error: No OCP releases found in Sippy API.", file=sys.stderr)
        sys.exit(1)

    return ocp_releases[0]


def main():
    parser = argparse.ArgumentParser(
        description="Fetch recent release payloads from the OpenShift release controller.",
    )
    parser.add_argument(
        "architecture",
        nargs="?",
        default="amd64",
        help="CPU architecture (default: amd64). Options: amd64, arm64, ppc64le, s390x, multi",
    )
    parser.add_argument(
        "version",
        nargs="?",
        default=None,
        help="OCP version, e.g. 4.18 (default: latest from Sippy API)",
    )
    parser.add_argument(
        "stream",
        nargs="?",
        default="nightly",
        help="Release stream (default: nightly). Options: nightly, ci",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of tags to show (default: 5, 0 = all)",
    )
    parser.add_argument(
        "--phase",
        choices=["Accepted", "Rejected", "Ready"],
        default=None,
        help="Filter by phase",
    )

    args = parser.parse_args()

    architecture = args.architecture
    if architecture not in KNOWN_ARCHITECTURES:
        print(
            f"Error: Unknown architecture '{architecture}'. "
            f"Known architectures: {', '.join(KNOWN_ARCHITECTURES)}",
            file=sys.stderr,
        )
        sys.exit(1)

    version = args.version
    if version is None:
        version = get_latest_version()

    stream = args.stream
    stream_name = release_stream_name(version, stream, architecture)

    tags = fetch_tags(architecture, version, stream)

    if args.phase:
        tags = [t for t in tags if t.get("phase") == args.phase]

    if args.limit > 0:
        tags = tags[: args.limit]

    if not tags:
        print("No payloads found.", file=sys.stderr)
        sys.exit(1)

    print(f"Release stream: {stream_name} ({architecture})", file=sys.stderr)
    print(f"Fetching details for {len(tags)} payloads...", file=sys.stderr)

    for i, tag in enumerate(tags):
        name = tag.get("name", "")
        details = fetch_release_details(architecture, stream_name, name)
        print(format_payload(tag, details, architecture, stream_name))
        if i < len(tags) - 1:
            print()


if __name__ == "__main__":
    main()
