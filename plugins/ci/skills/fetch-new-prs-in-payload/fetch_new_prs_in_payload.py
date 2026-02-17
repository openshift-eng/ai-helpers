#!/usr/bin/env python3
"""Fetch new pull requests included in an OpenShift payload that were not in the previous one.

Uses the Sippy payload diff API to retrieve PRs that are new in a given payload tag.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List

SIPPY_API_BASE = "https://sippy.dptools.openshift.org/api"


def fetch_new_prs(payload_tag: str) -> list:
    """Fetch new PRs in the given payload tag compared to its predecessor."""
    url = f"{SIPPY_API_BASE}/payloads/diff?toPayload={urllib.parse.quote(payload_tag)}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(
                f"Error: Payload '{payload_tag}' not found.",
                file=sys.stderr,
            )
            print(
                "Verify the payload tag exists (e.g., 4.22.0-0.ci-2026-02-06-195709).",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print(f"Error: HTTP {e.code} from Sippy API: {e.reason}", file=sys.stderr)
            sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Failed to connect to Sippy API: {e.reason}", file=sys.stderr)
        print("Check network connectivity.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("Error: Unexpected API response format (expected a JSON array).", file=sys.stderr)
        sys.exit(1)

    # Transform the response into a cleaner structure
    prs = []
    for entry in data:
        pr = {
            "url": entry.get("url", ""),
            "pull_request_id": entry.get("pull_request_id", ""),
            "component": entry.get("name", ""),
            "description": entry.get("description", ""),
            "bug_url": entry.get("bug_url", ""),
        }
        prs.append(pr)

    return prs


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
