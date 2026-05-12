#!/usr/bin/env python3
"""
Add a Component Readiness triage record link to a JIRA issue description.

Appends a section to the issue description with a link to the triage record UI
so that anyone viewing the bug can monitor the on-going status of all
regressions triaged to it.

Usage:
    python3 add_jira_triage_link.py OCPBUGS-12345 --triage-id 456

Requires JIRA_API_TOKEN and JIRA_USERNAME environment variables.
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any, Dict, List

JIRA_BASE_URL = "https://redhat.atlassian.net"
TRIAGE_UI_BASE = "https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/triages"


def _get_auth_header(username: str, token: str) -> str:
    credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
    return f"Basic {credentials}"


def _fetch_description(issue_key: str, auth: str) -> Dict[str, Any]:
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}?fields=description"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", auth)
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _description_contains_triage_link(description: Any, triage_url: str) -> bool:
    if description is None:
        return False
    text = json.dumps(description)
    return triage_url in text


def _build_triage_section(triage_id: int) -> List[Dict[str, Any]]:
    triage_url = f"{TRIAGE_UI_BASE}/{triage_id}"
    return [
        {
            "type": "rule",
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Component Readiness Triage Record",
                    "marks": [{"type": "strong"}],
                },
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Monitor the on-going status of all regressions triaged to this bug: ",
                },
                {
                    "type": "text",
                    "text": triage_url,
                    "marks": [
                        {
                            "type": "link",
                            "attrs": {"href": triage_url},
                        }
                    ],
                },
            ],
        },
    ]


def add_triage_link(issue_key: str, triage_id: int, token: str, username: str) -> dict:
    auth = _get_auth_header(username, token)
    triage_url = f"{TRIAGE_UI_BASE}/{triage_id}"

    try:
        issue_data = _fetch_description(issue_key, auth)
    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "error": f"Failed to fetch issue: HTTP {e.code}",
            "issue_key": issue_key,
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"Failed to fetch issue: {e.reason}",
            "issue_key": issue_key,
        }

    description = issue_data.get("fields", {}).get("description")

    if _description_contains_triage_link(description, triage_url):
        return {
            "success": True,
            "issue_key": issue_key,
            "triage_url": triage_url,
            "already_present": True,
        }

    if description is None:
        description = {"type": "doc", "version": 1, "content": []}

    triage_nodes = _build_triage_section(triage_id)
    description["content"].extend(triage_nodes)

    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"
    payload = json.dumps({"fields": {"description": description}}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="PUT")
    req.add_header("Authorization", auth)
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            pass
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return {
            "success": False,
            "error": f"Failed to update description: HTTP {e.code}: {error_body}",
            "issue_key": issue_key,
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"Failed to update description: {e.reason}",
            "issue_key": issue_key,
        }

    return {
        "success": True,
        "issue_key": issue_key,
        "triage_url": triage_url,
        "already_present": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Add a Component Readiness triage record link to a JIRA issue description",
    )
    parser.add_argument("issue_key", help="JIRA issue key (e.g., OCPBUGS-12345)")
    parser.add_argument(
        "--triage-id",
        type=int,
        required=True,
        help="Triage record ID from Component Readiness",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    token = os.environ.get("JIRA_API_TOKEN")
    if not token:
        print("Error: JIRA_API_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    username = os.environ.get("JIRA_USERNAME")
    if not username:
        print("Error: JIRA_USERNAME environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    result = add_triage_link(args.issue_key, args.triage_id, token, username)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            if result.get("already_present"):
                print(f"Triage link already present in {result['issue_key']}")
            else:
                print(f"Triage link added to {result['issue_key']}")
            print(f"  {result['triage_url']}")
        else:
            print(f"Failed to add triage link to {result['issue_key']}")
            print(f"  Error: {result['error']}")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
