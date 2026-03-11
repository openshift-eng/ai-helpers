#!/usr/bin/env python3
"""Fetch recent release payloads from the OpenShift release controller.

Outputs JSON with each payload's tag, phase, release controller URL,
and full API details (blocking jobs, async jobs, retries, Prow URLs).
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

KNOWN_ARCHITECTURES = ["amd64", "arm64", "ppc64le", "s390x", "multi"]
SIPPY_API_URL = "https://sippy.dptools.openshift.org/api/releases"


def rc_domain(architecture: str) -> str:
    return f"{architecture}.ocp.releases.ci.openshift.org"


def release_stream_name(version: str, stream: str, architecture: str) -> str:
    if stream == "ci" and architecture != "amd64":
        print("Error: The 'ci' stream is only available for amd64.", file=sys.stderr)
        sys.exit(1)
    name = f"{version}.0-0.{stream}"
    if architecture != "amd64":
        name += f"-{architecture}"
    return name


def fetch_json(url: str, timeout: int = 30) -> dict:
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
    domain = rc_domain(architecture)
    stream_name = release_stream_name(version, stream, architecture)
    url = f"https://{domain}/api/v1/releasestream/{stream_name}/tags"
    data = fetch_json(url)
    return data.get("tags", [])


def fetch_release_details(architecture: str, stream_name: str, tag_name: str) -> dict:
    domain = rc_domain(architecture)
    url = f"https://{domain}/api/v1/releasestream/{stream_name}/release/{tag_name}"
    return fetch_json(url)


def release_page_url(architecture: str, stream_name: str, tag_name: str) -> str:
    domain = rc_domain(architecture)
    return f"https://{domain}/releasestream/{stream_name}/release/{tag_name}"


def get_latest_version() -> str:
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
        "architecture", nargs="?", default="amd64",
        help="CPU architecture (default: amd64). Options: amd64, arm64, ppc64le, s390x, multi",
    )
    parser.add_argument(
        "version", nargs="?", default=None,
        help="OCP version, e.g. 4.18 (default: latest from Sippy API)",
    )
    parser.add_argument(
        "stream", nargs="?", default="nightly",
        help="Release stream (default: nightly). Options: nightly, ci",
    )
    parser.add_argument(
        "--limit", type=int, default=5,
        help="Maximum number of tags to show (default: 5, 0 = all)",
    )
    parser.add_argument(
        "--phase", choices=["Accepted", "Rejected", "Ready"], default=None,
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

    payloads = []
    for tag in tags:
        name = tag.get("name", "")
        details = fetch_release_details(architecture, stream_name, name)
        payloads.append({
            "tag": name,
            "phase": tag.get("phase", "Unknown"),
            "url": release_page_url(architecture, stream_name, name),
            "results": details.get("results", {}),
        })

    print(json.dumps(payloads, indent=2))


if __name__ == "__main__":
    main()
