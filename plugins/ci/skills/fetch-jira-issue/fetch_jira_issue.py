#!/usr/bin/env python3
"""
Fetch JIRA issue details from the Red Hat JIRA REST API.
Retrieves status, assignee, priority, resolution, comments, and linked PRs.
Classifies issue progress as ACTIVE, STALLED, or NEEDS_ATTENTION.
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


class JiraIssueFetcher:
    """Fetches and parses JIRA issue data from the Red Hat JIRA REST API."""

    BASE_URL = "https://issues.redhat.com/rest/api/2/issue"

    # Fields to request from the API
    FIELDS = [
        "summary",
        "description",
        "status",
        "assignee",
        "reporter",
        "priority",
        "resolution",
        "components",
        "labels",
        "fixVersions",
        "updated",
        "created",
        "comment",
    ]

    # Statuses considered "active work in progress"
    ACTIVE_STATUSES = {
        "assigned",
        "in progress",
        "code review",
        "modified",
        "on_qa",
        "post",
    }

    # Statuses considered "not yet started"
    NEW_STATUSES = {
        "new",
        "open",
        "untriaged",
        "to do",
    }

    # Days thresholds for staleness classification
    STALE_DAYS = 14
    RECENT_DAYS = 7

    def __init__(self, jira_key: str, token: Optional[str] = None):
        """
        Initialize fetcher with JIRA issue key.

        Args:
            jira_key: JIRA issue key (e.g., OCPBUGS-74401)
            token: JIRA API token. If not provided, reads from JIRA_TOKEN env var.

        Raises:
            ValueError: If no token is available
        """
        self.jira_key = jira_key.upper().strip()
        self.token = token or os.environ.get("JIRA_TOKEN", "")
        if not self.token:
            raise ValueError(
                "JIRA API token required.\n"
                "Set JIRA_TOKEN environment variable or pass --token.\n"
                "Obtain from: https://issues.redhat.com (Profile > Personal Access Tokens)"
            )
        self.api_url = f"{self.BASE_URL}/{self.jira_key}"

    def fetch(self) -> Dict[str, Any]:
        """
        Fetch issue data from JIRA REST API.

        Returns:
            dict: Raw JSON response from JIRA API

        Raises:
            ValueError: If issue not found or API error occurs
        """
        fields_param = ",".join(self.FIELDS)
        url = f"{self.api_url}?fields={fields_param}"

        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ValueError(
                    "Authentication failed. Check that JIRA_TOKEN is valid.\n"
                    "Obtain from: https://issues.redhat.com (Profile > Personal Access Tokens)"
                )
            elif e.code == 403:
                raise ValueError(
                    f"Access denied for {self.jira_key}. "
                    "Your token may lack permissions for this project."
                )
            elif e.code == 404:
                raise ValueError(
                    f"Issue {self.jira_key} not found. "
                    "Verify the issue key is correct."
                )
            else:
                raise ValueError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise ValueError(
                f"Failed to connect to JIRA API: {e.reason}\n"
                "Check network connectivity and VPN settings."
            )

    def parse(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw JIRA API response into structured issue data.

        Args:
            raw_data: Raw JSON response from JIRA API

        Returns:
            dict: Structured issue data
        """
        fields = raw_data.get("fields", {})

        issue = {
            "key": raw_data.get("key", self.jira_key),
            "url": f"https://issues.redhat.com/browse/{raw_data.get('key', self.jira_key)}",
            "summary": fields.get("summary", ""),
            "status": self._parse_named_field(fields.get("status")),
            "resolution": self._parse_named_field(fields.get("resolution")),
            "priority": self._parse_named_field(fields.get("priority")),
            "assignee": self._parse_user(fields.get("assignee")),
            "reporter": self._parse_user(fields.get("reporter")),
            "components": [
                c.get("name", "") for c in (fields.get("components") or [])
            ],
            "labels": fields.get("labels", []),
            "fix_versions": [
                v.get("name", "") for v in (fields.get("fixVersions") or [])
            ],
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
        }

        # Parse comments
        comment_data = fields.get("comment", {})
        comments = comment_data.get("comments", [])
        issue["comment_count"] = len(comments)
        issue["comments"] = self._parse_comments(comments)

        # Extract PR links from comments
        issue["linked_prs"] = self._extract_pr_links(comments)

        # Classify progress
        issue["progress"] = self._classify_progress(issue)

        return issue

    def _parse_named_field(self, field: Optional[Dict]) -> Optional[str]:
        """Extract name from a JIRA field with a name property."""
        if field and isinstance(field, dict):
            return field.get("name")
        return None

    def _parse_user(self, user: Optional[Dict]) -> Optional[Dict[str, str]]:
        """Parse a JIRA user field into name and email."""
        if not user or not isinstance(user, dict):
            return None
        return {
            "display_name": user.get("displayName", ""),
            "email": user.get("emailAddress", ""),
        }

    def _parse_comments(self, comments: List[Dict]) -> List[Dict[str, Any]]:
        """
        Parse comment list, returning all comments with metadata.

        Args:
            comments: Raw comment list from JIRA API

        Returns:
            list: Parsed comments with author, date, and body
        """
        parsed = []
        for comment in comments:
            author = comment.get("author", {})
            parsed.append({
                "author": author.get("displayName", "unknown"),
                "created": comment.get("created", ""),
                "body": comment.get("body", ""),
            })
        return parsed

    def _extract_pr_links(self, comments: List[Dict]) -> List[str]:
        """
        Extract GitHub PR URLs from comment bodies.

        Args:
            comments: Raw comment list from JIRA API

        Returns:
            list: Unique GitHub PR URLs found in comments
        """
        pr_pattern = re.compile(
            r"https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/pull/\d+"
        )
        prs = set()
        for comment in comments:
            body = comment.get("body", "")
            prs.update(pr_pattern.findall(body))
        return sorted(prs)

    def _classify_progress(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify issue progress as ACTIVE, STALLED, or NEEDS_ATTENTION.

        Args:
            issue: Parsed issue data

        Returns:
            dict: Progress classification with level, label, and reason
        """
        status = (issue.get("status") or "").lower()
        assignee = issue.get("assignee")
        updated = issue.get("updated", "")
        comments = issue.get("comments", [])
        linked_prs = issue.get("linked_prs", [])

        days_since_update = self._days_since(updated)
        days_since_comment = None
        if comments:
            last_comment_date = comments[-1].get("created", "")
            days_since_comment = self._days_since(last_comment_date)

        # Determine progress level
        if status in self.ACTIVE_STATUSES:
            if days_since_update is not None and days_since_update > self.STALE_DAYS:
                level = "STALLED"
                reason = (
                    f"Status is '{issue['status']}' but no activity "
                    f"in {days_since_update} days"
                )
            elif linked_prs:
                level = "ACTIVE"
                reason = f"PR in progress ({len(linked_prs)} linked)"
            elif days_since_comment is not None and days_since_comment <= self.RECENT_DAYS:
                level = "ACTIVE"
                reason = f"Recent comment activity ({days_since_comment} days ago)"
            elif days_since_update is not None and days_since_update <= self.RECENT_DAYS:
                level = "ACTIVE"
                reason = f"Recently updated ({days_since_update} days ago)"
            else:
                level = "ACTIVE"
                reason = f"Status is '{issue['status']}'"
        elif status in self.NEW_STATUSES:
            if not assignee:
                level = "NEEDS_ATTENTION"
                reason = f"Status is '{issue['status']}' with no assignee"
            elif days_since_update is not None and days_since_update > self.STALE_DAYS:
                level = "NEEDS_ATTENTION"
                reason = (
                    f"Status is '{issue['status']}' with no progress "
                    f"in {days_since_update} days"
                )
            else:
                level = "NEEDS_ATTENTION"
                reason = f"Status is '{issue['status']}'"
        elif status in ("closed", "verified"):
            level = "RESOLVED"
            resolution = issue.get("resolution")
            if resolution:
                reason = f"Status '{issue['status']}', resolution '{resolution}'"
            else:
                reason = f"Status '{issue['status']}'"
        else:
            # Unknown status - check activity
            if days_since_update is not None and days_since_update > self.STALE_DAYS:
                level = "STALLED"
                reason = (
                    f"Status is '{issue['status']}' with no activity "
                    f"in {days_since_update} days"
                )
            else:
                level = "ACTIVE"
                reason = f"Status is '{issue['status']}'"

        emoji = {
            "ACTIVE": "ACTIVE",
            "STALLED": "STALLED",
            "NEEDS_ATTENTION": "NEEDS_ATTENTION",
            "RESOLVED": "RESOLVED",
        }.get(level, level)

        return {
            "level": level,
            "label": emoji,
            "reason": reason,
            "days_since_update": days_since_update,
            "days_since_last_comment": days_since_comment,
        }

    def _days_since(self, date_str: str) -> Optional[int]:
        """
        Calculate days between a date string and now.

        Args:
            date_str: ISO format date string from JIRA

        Returns:
            int or None: Days since the date, or None if unparseable
        """
        if not date_str:
            return None
        try:
            # JIRA dates look like: 2026-02-03T13:02:37.700+0000
            # Normalize timezone format
            clean = re.sub(r"(\d{2})(\d{2})$", r"\1:\2", date_str)
            dt = datetime.fromisoformat(clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - dt).days
        except (ValueError, TypeError):
            return None

    def fetch_and_parse(self) -> Dict[str, Any]:
        """
        Fetch and parse JIRA issue in one call.

        Returns:
            dict: Structured issue data with progress classification

        Raises:
            ValueError: If fetch or parse fails
        """
        raw_data = self.fetch()
        return self.parse(raw_data)


def format_summary(issue: Dict[str, Any]) -> str:
    """
    Format issue data as a human-readable summary.

    Args:
        issue: Parsed issue data

    Returns:
        str: Formatted summary text
    """
    lines = []
    lines.append(f"JIRA Issue: {issue['key']}")
    lines.append("=" * 60)
    lines.append("")

    # Basic info
    lines.append(f"Summary: {issue['summary']}")
    lines.append(f"URL: {issue['url']}")
    lines.append(f"Status: {issue['status']}")
    if issue["resolution"]:
        lines.append(f"Resolution: {issue['resolution']}")
    lines.append(f"Priority: {issue['priority']}")
    lines.append("")

    # People
    if issue["assignee"]:
        lines.append(f"Assignee: {issue['assignee']['display_name']}")
    else:
        lines.append("Assignee: Unassigned")
    if issue["reporter"]:
        lines.append(f"Reporter: {issue['reporter']['display_name']}")
    lines.append("")

    # Classification
    if issue["components"]:
        lines.append(f"Components: {', '.join(issue['components'])}")
    if issue["labels"]:
        lines.append(f"Labels: {', '.join(issue['labels'])}")
    if issue["fix_versions"]:
        lines.append(f"Fix Versions: {', '.join(issue['fix_versions'])}")
    lines.append("")

    # Dates
    created_date = issue["created"][:10] if issue["created"] else "unknown"
    updated_date = issue["updated"][:10] if issue["updated"] else "unknown"
    lines.append(f"Created: {created_date}")
    lines.append(f"Updated: {updated_date}")
    lines.append("")

    # Progress classification
    progress = issue.get("progress", {})
    level = progress.get("level", "UNKNOWN")
    emoji_map = {
        "ACTIVE": "\U0001f7e2",
        "STALLED": "\U0001f7e1",
        "NEEDS_ATTENTION": "\U0001f534",
        "RESOLVED": "\u2705",
    }
    emoji = emoji_map.get(level, "\u2753")
    lines.append(f"Progress: {emoji} {level} - {progress.get('reason', '')}")
    if progress.get("days_since_update") is not None:
        lines.append(f"  Days since update: {progress['days_since_update']}")
    if progress.get("days_since_last_comment") is not None:
        lines.append(
            f"  Days since last comment: {progress['days_since_last_comment']}"
        )
    lines.append("")

    # Linked PRs
    if issue["linked_prs"]:
        lines.append(f"Linked PRs ({len(issue['linked_prs'])}):")
        for pr in issue["linked_prs"]:
            lines.append(f"  - {pr}")
        lines.append("")

    # Recent comments (last 3)
    comments = issue.get("comments", [])
    if comments:
        recent = comments[-3:]
        lines.append(f"Recent Comments ({len(recent)} of {len(comments)} total):")
        for comment in recent:
            author = comment["author"]
            created = comment["created"][:10] if comment["created"] else "unknown"
            body = comment["body"]
            # Truncate long comments
            if len(body) > 300:
                body = body[:300] + "..."
            lines.append(f"  [{created}] {author}:")
            for body_line in body.split("\n")[:5]:
                lines.append(f"    {body_line}")
            lines.append("")
    else:
        lines.append("Comments: None")
        lines.append("")

    return "\n".join(lines)


def main():
    """Fetch JIRA issue details from command line and output results."""
    if len(sys.argv) < 2:
        print(
            "Usage: fetch_jira_issue.py <jira_key> [--format json|summary] [--token TOKEN]",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  fetch_jira_issue.py OCPBUGS-74401", file=sys.stderr)
        print("  fetch_jira_issue.py OCPBUGS-74401 --format json", file=sys.stderr)
        print("  fetch_jira_issue.py OCPBUGS-74401 --format summary", file=sys.stderr)
        print("", file=sys.stderr)
        print("Environment:", file=sys.stderr)
        print("  JIRA_TOKEN: API token for issues.redhat.com (required)", file=sys.stderr)
        sys.exit(1)

    jira_key = sys.argv[1]

    # Parse optional arguments
    output_format = "json"
    token = None

    for i, arg in enumerate(sys.argv):
        if arg == "--format" and i + 1 < len(sys.argv):
            output_format = sys.argv[i + 1]
            if output_format not in ("json", "summary"):
                print(
                    f"Error: Invalid format '{output_format}'. Use 'json' or 'summary'",
                    file=sys.stderr,
                )
                sys.exit(1)
        elif arg == "--token" and i + 1 < len(sys.argv):
            token = sys.argv[i + 1]

    try:
        fetcher = JiraIssueFetcher(jira_key, token=token)
        issue = fetcher.fetch_and_parse()

        if output_format == "json":
            print(json.dumps(issue, indent=2))
        else:
            print(format_summary(issue))

        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
