#!/usr/bin/env python3
"""
Gather Jira activity for catch-me-up triage.

Fetches recent activity (changelogs + comments) on issues where the user is
assignee or watcher. Dumps raw events as JSON for inspection.

Requires: pip install aiohttp

Environment:
    JIRA_URL          Jira instance URL (default: https://redhat.atlassian.net)
    JIRA_API_TOKEN    Atlassian API token
    JIRA_USERNAME     Atlassian account email
"""

import argparse
import asyncio
import base64
import json
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)

# Stored lowercase — is_bot() lowercases before comparison.
BOT_ACCOUNTS = {
    "openshift jira links copy bot",     # 766 events
    "pme-bot service account",           # 487
    "osi db",                            # 204
    "rh-internal-custom-fields",         # 101
    "scriptrunner for jira",             # 75
    "art bot",                           # 64
    "openshift jira bot",                # 64
    "automation for jira",               # 58
    "openshift prow bot",                # 42
    "scriptrunner service account",      # 28
    "konflux release team",              # 27
    "dptp bot",                          # 23
    "openshift release-controller bot",  # 16
    "jira-sd-elements-integration bot",  # 14
    "cucushift bot",                     # 11
    "openshift jira automation bot",     # 9
}


def is_bot(display_name: str) -> bool:
    """Check display name against the known bot accounts list."""
    return (display_name or "").lower().strip() in BOT_ACCOUNTS


JIRA_REQUEST_DELAY = 0.05


@dataclass
class Config:
    jira_url: str
    jira_token: str
    jira_username: str
    days: int
    output_dir: Path


def parse_datetime(date_str: str | None) -> datetime | None:
    """Parse an ISO datetime string, handling Jira's Z suffix."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def in_range(dt: datetime | None, start: date, end: date) -> bool:
    """Return True if dt falls within [start, end] inclusive."""
    if dt is None:
        return False
    d = dt.date() if isinstance(dt, datetime) else dt
    return start <= d <= end


def adf_to_text(node: Any) -> str:
    """Convert Atlassian Document Format to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return str(node)

    parts: list[str] = []
    node_type = node.get("type")

    if node_type == "text":
        text = node.get("text", "")
        for mark in node.get("marks", []):
            if mark.get("type") == "link":
                href = mark.get("attrs", {}).get("href", "")
                if href and href != text:
                    text = f"{text} ({href})"
        parts.append(text)
    elif node_type in ("inlineCard", "blockCard", "embedCard"):
        url = node.get("attrs", {}).get("url", "")
        if url:
            parts.append(url)
    elif node_type == "mention":
        parts.append(f"@{node.get('attrs', {}).get('text', '')}")

    for child in node.get("content", []):
        parts.append(adf_to_text(child))

    block_types = ("doc", "paragraph", "heading", "bulletList",
                   "orderedList", "listItem", "blockquote")
    sep = "\n" if node_type in block_types else ""
    return sep.join(parts)


class JiraClient:
    ISSUE_FIELDS = "summary,status,assignee,comment,updated,created,issuetype,priority,labels"

    def __init__(self, config: Config):
        self.base_url = config.jira_url.rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https":
            raise ValueError("JIRA_URL must be https")
        credentials = base64.b64encode(
            f"{config.jira_username}:{config.jira_token}".encode()
        ).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.request_count = 0

    async def fetch_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        method: str = "GET",
        json_body: dict | None = None,
        retries: int = 3,
    ) -> dict | list | None:
        """Make a rate-limited, retrying HTTP request to Jira."""
        await asyncio.sleep(JIRA_REQUEST_DELAY)
        self.request_count += 1
        logger.debug("Request #%d: %s %s", self.request_count, method, url[:100])

        if method == "POST":
            req = session.post(url, headers=self.headers, json=json_body)
        else:
            req = session.get(url, headers=self.headers)

        async with req as resp:
            if resp.status == 200:
                return await resp.json()
            if resp.status == 401:
                raise ValueError("Jira auth failed (401). Check JIRA_API_TOKEN and JIRA_USERNAME.")
            if resp.status == 429:
                if retries <= 0:
                    logger.error("Rate limited, no retries left: %s", url[:100])
                    return None
                logger.warning("Rate limited, waiting 30s (%d retries left)", retries)
                await asyncio.sleep(30)
                return await self.fetch_json(session, url, method, json_body, retries - 1)
            text = await resp.text()
            logger.warning("Jira %d: %s", resp.status, text[:200])
            return None

    async def search(
        self,
        session: aiohttp.ClientSession,
        jql: str,
        fields: str = ISSUE_FIELDS,
        max_results: int = 500,
    ) -> list[dict]:
        """Run a paginated JQL search and return all matching issues."""
        all_issues: list[dict] = []
        next_page_token: str | None = None

        while len(all_issues) < max_results:
            body: dict[str, Any] = {
                "jql": jql,
                "maxResults": min(100, max_results - len(all_issues)),
                "fields": [f.strip() for f in fields.split(",")],
            }
            if next_page_token:
                body["nextPageToken"] = next_page_token

            url = f"{self.base_url}/rest/api/3/search/jql"
            result = await self.fetch_json(session, url, method="POST", json_body=body)
            if not result or not isinstance(result, dict):
                break

            issues = result.get("issues", [])
            if not issues:
                break
            all_issues.extend(issues)

            next_page_token = result.get("nextPageToken")
            if not next_page_token:
                break

        if len(all_issues) >= max_results:
            logger.warning("Hit %d-issue search limit — results may be incomplete", max_results)
        return all_issues

    async def get_changelog(
        self, session: aiohttp.ClientSession, issue_key: str
    ) -> list[dict]:
        """Fetch the full paginated changelog for an issue."""
        all_values: list[dict] = []
        start_at = 0
        while True:
            url = (f"{self.base_url}/rest/api/3/issue/{issue_key}/changelog"
                   f"?maxResults=100&startAt={start_at}")
            result = await self.fetch_json(session, url)
            if not isinstance(result, dict):
                break
            values = result.get("values", [])
            if not values:
                break
            all_values.extend(values)
            if start_at + len(values) >= result.get("total", 0):
                break
            start_at += len(values)
        return all_values



async def gather(config: Config) -> dict:
    """Fetch changelogs and comments for all watched/assigned issues, emit events JSON."""
    start_time = datetime.now()
    start_date = date.today() - timedelta(days=config.days)
    end_date = date.today()

    client = JiraClient(config)

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        jql = (
            f'(assignee = "{config.jira_username}" OR watcher = "{config.jira_username}") '
            f"AND updated >= -{config.days}d "
            f"ORDER BY updated DESC"
        )
        logger.info("JQL: %s", jql)
        issues = await client.search(session, jql)
        logger.info("Found %d issues", len(issues))

        issues_by_key: dict[str, dict] = {}
        for issue in issues:
            issues_by_key[issue["key"]] = issue

        total = len(issues_by_key)
        completed = 0

        print(f"Fetching changelogs for {total} issues...", file=sys.stderr)
        changelogs: dict[str, list[dict]] = {}
        for i, key in enumerate(issues_by_key, 1):
            changelogs[key] = await client.get_changelog(session, key)
            if i % 20 == 0 or i == total:
                print(f"  Changelogs: {i}/{total}", file=sys.stderr)

    all_events: list[dict] = []

    for key, issue in issues_by_key.items():
        fields = issue.get("fields", {})
        assignee = fields.get("assignee") or {}
        issue_meta = {
            "key": key,
            "summary": fields.get("summary", ""),
            "status": (fields.get("status") or {}).get("name", "Unknown"),
            "assignee": assignee.get("displayName"),
        }

        for entry in changelogs.get(key, []):
            created = parse_datetime(entry.get("created"))
            if not in_range(created, start_date, end_date):
                continue

            author = entry.get("author", {})
            author_name = author.get("displayName", "Unknown")
            if (author.get("emailAddress") or "").lower() == config.jira_username.lower():
                continue
            if is_bot(author_name):
                continue
            for item in entry.get("items", []):
                all_events.append({
                    "type": "field_change",
                    "issue": issue_meta,
                    "date": entry.get("created"),
                    "author": author.get("displayName", "Unknown"),
                    "field": item.get("field", ""),
                    "from": item.get("fromString"),
                    "to": item.get("toString"),
                })

        comments = fields.get("comment", {}).get("comments", [])
        for comment in comments:
            created = parse_datetime(comment.get("created"))
            if not in_range(created, start_date, end_date):
                continue

            author = comment.get("author", {})
            author_name = author.get("displayName", "Unknown")
            if (author.get("emailAddress") or "").lower() == config.jira_username.lower():
                continue
            if is_bot(author_name):
                continue
            body = adf_to_text(comment.get("body", ""))

            all_events.append({
                "type": "comment",
                "issue": issue_meta,
                "date": comment.get("created"),
                "author": author.get("displayName", "Unknown"),
                "body": body,
            })

    all_events.sort(key=lambda e: e.get("date", ""), reverse=True)

    duration = (datetime.now() - start_time).total_seconds()

    output = {
        "generated_at": datetime.now().isoformat(),
        "config": {
            "jira_username": config.jira_username,
            "days": config.days,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
        },
        "stats": {
            "total_issues": len(issues_by_key),
            "total_events": len(all_events),
            "jira_requests": client.request_count,
            "duration_seconds": round(duration, 2),
        },
        "events": all_events,
    }

    output_dir = config.output_dir / f"{end_date.isoformat()}-{config.days}d"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "events.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    return output


def main():
    """CLI entry point: parse args, configure, and run the gather loop."""
    import os

    parser = argparse.ArgumentParser(description="Gather Jira activity for catch-me-up triage")
    parser.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    parser.add_argument("--output-dir", default=".work/catch-me-up/runs", help="Output directory")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached results and re-fetch")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    jira_url = os.environ.get("JIRA_URL", "https://redhat.atlassian.net")
    jira_token = os.environ.get("JIRA_API_TOKEN")
    jira_username = os.environ.get("JIRA_USERNAME")

    if not jira_token:
        print("Error: JIRA_API_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    if not jira_username:
        print("Error: JIRA_USERNAME not set", file=sys.stderr)
        sys.exit(1)

    config = Config(
        jira_url=jira_url,
        jira_token=jira_token,
        jira_username=jira_username,
        days=args.days,
        output_dir=Path(args.output_dir),
    )

    # Check cache — keyed by date AND days parameter
    cache_file = config.output_dir / f"{date.today().isoformat()}-{config.days}d" / "events.json"
    if cache_file.exists() and not args.no_cache:
        print(f"Using cached results from {cache_file}", file=sys.stderr)
        with open(cache_file) as f:
            result = json.load(f)
        print(f"Events: {result['stats']['total_events']}", file=sys.stderr)
        return

    print(f"Gathering Jira activity for {jira_username}", file=sys.stderr)
    print(f"Looking back {config.days} days", file=sys.stderr)

    result = asyncio.run(gather(config))

    print(f"\nDone in {result['stats']['duration_seconds']}s", file=sys.stderr)
    print(f"Issues: {result['stats']['total_issues']}", file=sys.stderr)
    print(f"Events: {result['stats']['total_events']}", file=sys.stderr)
    print(f"Jira requests: {result['stats']['jira_requests']}", file=sys.stderr)
    print(f"Output: {config.output_dir / f'{date.today().isoformat()}-{config.days}d' / 'events.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
