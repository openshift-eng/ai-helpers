#!/usr/bin/env python3
"""Fetch new pull requests included in an OpenShift payload that were not in the previous one.

Uses the Sippy payload diff API to retrieve PRs that are new in a given payload tag,
falling back to the release controller API when Sippy has not yet ingested the payload.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

SIPPY_API_BASE = "https://sippy.dptools.openshift.org/api"
RELEASE_CONTROLLER_BASE = "https://amd64.ocp.releases.ci.openshift.org/api/v1"


def _http_get_json(url: str, timeout: int = 30) -> dict:
    """Fetch JSON from a URL. Raises on HTTP or connection errors."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_stream(payload_tag: str) -> Optional[str]:
    """Extract the release stream from a payload tag.

    Examples:
        4.21.0-0.ci-2026-02-27-125225 -> 4.21.0-0.ci
        4.22.0-0.nightly-2026-01-15-114134 -> 4.22.0-0.nightly
    """
    m = re.match(r"^(.+)-\d{4}-\d{2}-\d{2}-\d{6}$", payload_tag)
    return m.group(1) if m else None


def _find_previous_tag(stream: str, payload_tag: str) -> Optional[str]:
    """Find the payload immediately before payload_tag in the stream."""
    url = f"{RELEASE_CONTROLLER_BASE}/releasestream/{urllib.parse.quote(stream)}/tags"
    data = _http_get_json(url)
    tags = [t["name"] for t in data.get("tags", [])]
    try:
        idx = tags.index(payload_tag)
    except ValueError:
        return None
    if idx + 1 >= len(tags):
        return None
    return tags[idx + 1]


def fetch_from_sippy(payload_tag: str) -> Optional[list]:
    """Try fetching PR diff from Sippy. Returns None if the payload is not available."""
    url = f"{SIPPY_API_BASE}/payloads/diff?toPayload={urllib.parse.quote(payload_tag)}"
    try:
        data = _http_get_json(url)
    except urllib.error.HTTPError:
        return None
    except urllib.error.URLError:
        return None

    if not isinstance(data, list):
        return None

    prs = []
    for entry in data:
        prs.append({
            "url": entry.get("url", ""),
            "pull_request_id": entry.get("pull_request_id", ""),
            "component": entry.get("name", ""),
            "description": entry.get("description", ""),
            "bug_url": entry.get("bug_url", ""),
        })
    return prs


def fetch_from_release_controller(payload_tag: str) -> list:
    """Fetch PR diff from the release controller API."""
    stream = _parse_stream(payload_tag)
    if not stream:
        print(
            f"Error: Cannot parse release stream from tag '{payload_tag}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    prev_tag = _find_previous_tag(stream, payload_tag)
    if not prev_tag:
        print(
            f"Error: Cannot find previous payload for '{payload_tag}' in stream '{stream}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    url = (
        f"{RELEASE_CONTROLLER_BASE}/releasestream/{urllib.parse.quote(stream)}"
        f"/release/{urllib.parse.quote(payload_tag)}"
        f"?from={urllib.parse.quote(prev_tag)}"
    )

    try:
        data = _http_get_json(url, timeout=60)
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} from release controller: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Failed to connect to release controller: {e.reason}", file=sys.stderr)
        sys.exit(1)

    changelog = data.get("changeLogJson", {})
    updated_images = changelog.get("updatedImages", []) or []

    prs = []
    for image in updated_images:
        component = image.get("name", "")
        for commit in image.get("commits", []):
            pull_url = commit.get("pullURL", "")
            pull_id = str(commit.get("pullID", ""))
            description = commit.get("subject", "")
            issues = commit.get("issues", {}) or {}
            bug_url = next(iter(issues.values()), "")
            prs.append({
                "url": pull_url,
                "pull_request_id": pull_id,
                "component": component,
                "description": description,
                "bug_url": bug_url,
            })

    return prs


def fetch_new_prs(payload_tag: str) -> list:
    """Fetch new PRs, trying Sippy first then falling back to the release controller."""
    prs = fetch_from_sippy(payload_tag)
    if prs is not None:
        return prs

    print(
        f"Sippy does not have payload '{payload_tag}', "
        "falling back to release controller.",
        file=sys.stderr,
    )
    return fetch_from_release_controller(payload_tag)


def format_summary(prs: list, payload_tag: str) -> str:
    """Format PRs as a human-readable summary."""
    lines = []
    lines.append(f"New PRs in payload {payload_tag}")
    lines.append("=" * 60)
    lines.append(f"Total: {len(prs)} new pull requests")
    lines.append("")

    # Group by component
    by_component: Dict[str, List] = {}
    for pr in prs:
        component = pr["component"] or "(unknown)"
        by_component.setdefault(component, []).append(pr)

    for component in sorted(by_component.keys()):
        component_prs = by_component[component]
        lines.append(f"  {component} ({len(component_prs)} PRs):")
        for pr in component_prs:
            bug = f" [{pr['bug_url']}]" if pr["bug_url"] else ""
            lines.append(f"    - {pr['description']}{bug}")
            lines.append(f"      {pr['url']}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch new PRs in an OpenShift payload compared to its predecessor.",
    )
    parser.add_argument(
        "payload_tag",
        help="The payload tag (e.g., 4.22.0-0.ci-2026-02-06-195709)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="Output format (default: json)",
    )

    args = parser.parse_args()

    prs = fetch_new_prs(args.payload_tag)

    if args.format == "json":
        output = {
            "payload_tag": args.payload_tag,
            "total_prs": len(prs),
            "pull_requests": prs,
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_summary(prs, args.payload_tag))


if __name__ == "__main__":
    main()
