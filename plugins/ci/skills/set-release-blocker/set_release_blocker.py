#!/usr/bin/env python3
"""
Set the Release Blocker field on a JIRA issue.

Usage:
    python3 set_release_blocker.py <issue_key> [--value Approved|Rejected|""]

Examples:
    python3 set_release_blocker.py OCPBUGS-76523
    python3 set_release_blocker.py OCPBUGS-76523 --value Approved
    python3 set_release_blocker.py OCPBUGS-76523 --value Rejected
    python3 set_release_blocker.py OCPBUGS-76523 --value ""  # Clear the field

Requires JIRA_TOKEN environment variable to be set.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

JIRA_BASE_URL = "https://issues.redhat.com"
RELEASE_BLOCKER_FIELD = "customfield_12319743"

# Option IDs for the Release Blocker select field
RELEASE_BLOCKER_OPTIONS = {
    "Approved": "25755",
    "Rejected": "25756",
}


def set_release_blocker(issue_key: str, value: str, token: str) -> dict:
    """Set the Release Blocker field on a JIRA issue.

    Args:
        issue_key: JIRA issue key (e.g., OCPBUGS-76523)
        value: "Approved", "Rejected", or "" to clear
        token: JIRA API token

    Returns:
        dict with success status, issue key, and value set
    """
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}"

    if value == "":
        payload = {"fields": {RELEASE_BLOCKER_FIELD: None}}
    else:
        option_id = RELEASE_BLOCKER_OPTIONS.get(value)
        if option_id is None:
            return {
                "success": False,
                "error": f"Invalid value '{value}'. Must be one of: {', '.join(RELEASE_BLOCKER_OPTIONS.keys())} or empty string to clear.",
                "issue_key": issue_key,
            }
        payload = {"fields": {RELEASE_BLOCKER_FIELD: {"id": option_id}}}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            # PUT returns 204 No Content on success
            pass
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return {
            "success": False,
            "error": f"HTTP {e.code}: {error_body}",
            "issue_key": issue_key,
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"URL error: {e.reason}",
            "issue_key": issue_key,
        }

    # Verify the update
    verify_req = urllib.request.Request(
        f"{url}?fields={RELEASE_BLOCKER_FIELD}", method="GET"
    )
    verify_req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(verify_req, timeout=30) as response:
            verify_data = json.loads(response.read().decode("utf-8"))
            current_value = verify_data.get("fields", {}).get(RELEASE_BLOCKER_FIELD)
            if current_value:
                current_value = current_value.get("value", None)

            return {
                "success": True,
                "issue_key": issue_key,
                "value": current_value,
                "url": f"{JIRA_BASE_URL}/browse/{issue_key}",
            }
    except Exception:
        # Update succeeded but verification failed — still report success
        return {
            "success": True,
            "issue_key": issue_key,
            "value": value if value else None,
            "url": f"{JIRA_BASE_URL}/browse/{issue_key}",
            "note": "Update succeeded but verification could not be completed",
        }


def main():
    parser = argparse.ArgumentParser(
        description="Set the Release Blocker field on a JIRA issue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s OCPBUGS-76523
  %(prog)s OCPBUGS-76523 --value Approved
  %(prog)s OCPBUGS-76523 --value Rejected
  %(prog)s OCPBUGS-76523 --value ""
""",
    )

    parser.add_argument("issue_key", help="JIRA issue key (e.g., OCPBUGS-76523)")
    parser.add_argument(
        "--value",
        default="Approved",
        help='Value to set: "Approved" (default), "Rejected", or "" to clear',
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

    token = os.environ.get("JIRA_TOKEN")
    if not token:
        print("Error: JIRA_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    result = set_release_blocker(args.issue_key, args.value, token)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print(
                f"Release Blocker set to '{result['value']}' on {result['issue_key']}"
            )
            print(f"  {result['url']}")
        else:
            print(f"Failed to set Release Blocker on {result['issue_key']}")
            print(f"  Error: {result['error']}")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
