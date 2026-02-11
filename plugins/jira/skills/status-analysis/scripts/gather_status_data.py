#!/usr/bin/env python3
"""
Status Data Gatherer for Weekly Status Updates

This script uses asyncio to efficiently gather Jira issue data and GitHub PR data
for the weekly status update workflow. It fetches data in parallel with proper
rate limiting and outputs structured JSON files for LLM processing.

Environment Variables:
    JIRA_URL: Base URL for JIRA instance (default: https://issues.redhat.com)
    JIRA_PERSONAL_TOKEN: Your JIRA API bearer token (required)
    GITHUB_TOKEN: GitHub personal access token with repo scope (required)

Usage:
    python3 gather_status_data.py --project OCPSTRAT --component "Control Plane"
    python3 gather_status_data.py --project OCPSTRAT --days 7 --verbose
    python3 gather_status_data.py --project OCPSTRAT --output-dir .work/weekly-status --debug

Output:
    Creates a directory with:
    - manifest.json: Processing config and issue list
    - issues/OCPSTRAT-1234.json: Per-issue data with descendants and PRs
"""

import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from urllib.parse import urlencode

# Configure logging
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configure logging with appropriate level and format."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # Configure handler for stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    # Reduce noise from aiohttp/urllib3
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# Try to import aiohttp, fall back to requests if not available
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    logger.warning("aiohttp not available. Install with: pip install aiohttp")
    logger.warning("Falling back to synchronous requests (slower)")
    try:
        import requests
    except ImportError:
        logger.error("Either aiohttp or requests is required")
        sys.exit(1)


# =============================================================================
# Constants
# =============================================================================

# Jira rate limiting (conservative for Red Hat Jira)
JIRA_REQUEST_DELAY_SECONDS = 0.3  # 300ms between requests (increased from 200ms)
JIRA_MAX_CONCURRENT_REQUESTS = 2  # Max 2 parallel requests (reduced from 3)
JIRA_BATCH_SIZE = 40  # Max tickets per JQL query
JIRA_CHANGELOG_DELAY_SECONDS = 0.5  # Extra delay for changelog API (more rate-limited)

# GitHub rate limiting
GITHUB_MAX_CONCURRENT_REQUESTS = 5  # Reduced from 10
GITHUB_GRAPHQL_BATCH_SIZE = 30  # Reduced from 50 to avoid timeouts
GITHUB_RETRY_ATTEMPTS = 3  # Number of retries for transient errors
GITHUB_RETRY_DELAY_SECONDS = 5  # Delay between retries


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class DateRange:
    start: date
    end: date

    def contains(self, dt: datetime) -> bool:
        """Check if a datetime falls within this range."""
        if dt is None:
            return False
        d = dt.date() if isinstance(dt, datetime) else dt
        return self.start <= d <= self.end

    def to_dict(self) -> Dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


@dataclass
class GatherConfig:
    project: str
    jira_url: str
    jira_token: str
    github_token: str
    output_dir: Path
    date_range: DateRange
    component: Optional[str] = None
    label: Optional[str] = None
    status_summary_field: str = "customfield_12320841"
    assignees: List[str] = field(default_factory=list)
    excluded_assignees: List[str] = field(default_factory=list)


@dataclass
class PRRef:
    """Reference to a GitHub PR extracted from Jira."""
    owner: str
    repo: str
    number: int
    url: str
    found_in_issues: Set[str] = field(default_factory=set)

    @classmethod
    def from_url(cls, url: str) -> Optional["PRRef"]:
        """Parse a GitHub PR URL into a PRRef."""
        match = re.match(
            r"https?://github\.com/([^/]+)/([^/]+)/pull[s]?/(\d+)",
            url
        )
        if match:
            return cls(
                owner=match.group(1),
                repo=match.group(2),
                number=int(match.group(3)),
                url=url
            )
        return None


# =============================================================================
# Jira Client
# =============================================================================

class JiraClient:
    """Async Jira REST API client with batch support and rate limiting."""

    # Fields to fetch for status analysis
    ISSUE_FIELDS = (
        "summary,status,assignee,description,comment,updated,created,"
        "issuetype,priority,labels,issuelinks"
    )

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(JIRA_MAX_CONCURRENT_REQUESTS)
        self.request_count = 0

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON with rate limiting and error handling."""
        async with self.semaphore:
            await asyncio.sleep(JIRA_REQUEST_DELAY_SECONDS)
            self.request_count += 1

            # Log the request at debug level
            logger.debug(f"Jira request #{self.request_count}: {url[:100]}...")

            if HAS_AIOHTTP and self.session:
                try:
                    async with self.session.get(url, headers=self._get_headers()) as resp:
                        if resp.status == 200:
                            logger.debug(f"Jira request #{self.request_count} succeeded")
                            return await resp.json()
                        elif resp.status == 401:
                            logger.error("Jira authentication failed (401). Check JIRA_PERSONAL_TOKEN.")
                            return None
                        elif resp.status == 404:
                            logger.debug(f"Jira request #{self.request_count} returned 404")
                            return None
                        elif resp.status == 429:
                            logger.warning("Rate limited by Jira! Waiting 30 seconds...")
                            await asyncio.sleep(30)
                            return await self._fetch_json(url)  # Retry
                        else:
                            text = await resp.text()
                            logger.warning(f"Jira API returned {resp.status}: {text[:200]}")
                            return None
                except Exception as e:
                    logger.error(f"Error fetching {url}: {e}")
                    return None
            else:
                # Synchronous fallback
                try:
                    response = requests.get(url, headers=self._get_headers(), timeout=30)
                    if response.status_code == 200:
                        logger.debug(f"Jira request #{self.request_count} succeeded")
                        return response.json()
                    elif response.status_code == 429:
                        logger.warning("Rate limited by Jira! Waiting 30 seconds...")
                        await asyncio.sleep(30)
                        return await self._fetch_json(url)
                    else:
                        logger.warning(f"Jira API returned {response.status_code}")
                        return None
                except Exception as e:
                    logger.error(f"Error fetching {url}: {e}")
                    return None

    async def search_issues(
        self,
        jql: str,
        fields: str,
        expand: Optional[str] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for issues using JQL."""
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields,
        }
        if expand:
            params["expand"] = expand

        url = f"{self.base_url}/rest/api/2/search?{urlencode(params)}"
        result = await self._fetch_json(url)
        return result.get("issues", []) if result else []

    async def fetch_issues_batch(
        self,
        issue_keys: List[str],
        fields: str,
        expand: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch multiple issues using batch JQL: key in (KEY1, KEY2, ...)"""
        if not issue_keys:
            logger.debug("No issue keys to fetch")
            return {}

        results = {}
        total_batches = (len(issue_keys) + JIRA_BATCH_SIZE - 1) // JIRA_BATCH_SIZE
        logger.info(f"Fetching {len(issue_keys)} issues in {total_batches} batch(es)")

        # Process in batches
        for i in range(0, len(issue_keys), JIRA_BATCH_SIZE):
            batch = issue_keys[i : i + JIRA_BATCH_SIZE]
            batch_num = i // JIRA_BATCH_SIZE + 1

            logger.info(f"  Batch {batch_num}/{total_batches}: {len(batch)} issues")
            logger.debug(f"  Batch keys: {batch[:5]}{'...' if len(batch) > 5 else ''}")

            # Build batch JQL
            keys_str = ",".join(batch)
            jql = f"key in ({keys_str})"

            issues = await self.search_issues(jql, fields, expand, max_results=len(batch) + 10)
            logger.debug(f"  Batch {batch_num} returned {len(issues)} issues")

            for issue in issues:
                results[issue["key"]] = issue

        logger.info(f"Fetched {len(results)} issues total")
        return results

    async def get_issue_changelog(
        self, issue_key: str, max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Get changelog for an issue."""
        # Extra delay for changelog API which is more rate-limited
        await asyncio.sleep(JIRA_CHANGELOG_DELAY_SECONDS)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/changelog?maxResults={max_results}"
        result = await self._fetch_json(url)
        return result.get("values", []) if result else []

    async def fetch_changelogs_batch(
        self, issue_keys: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch changelogs for multiple issues."""
        if not issue_keys:
            logger.debug("No issue keys for changelog fetch")
            return {}

        results = {}
        total_batches = (len(issue_keys) + JIRA_BATCH_SIZE - 1) // JIRA_BATCH_SIZE
        logger.info(f"Fetching changelogs for {len(issue_keys)} issues in {total_batches} batch(es)")

        # Create tasks for all changelogs
        async def fetch_one(key: str):
            changelog = await self.get_issue_changelog(key)
            logger.debug(f"  Changelog for {key}: {len(changelog)} entries")
            return key, changelog

        # Process in batches to respect rate limits
        for i in range(0, len(issue_keys), JIRA_BATCH_SIZE):
            batch = issue_keys[i : i + JIRA_BATCH_SIZE]
            batch_num = i // JIRA_BATCH_SIZE + 1

            logger.info(f"  Changelog batch {batch_num}/{total_batches}: {len(batch)} issues")

            tasks = [fetch_one(key) for key in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = 0
            for result in batch_results:
                if isinstance(result, tuple):
                    key, changelog = result
                    results[key] = changelog
                    success_count += 1
                elif isinstance(result, Exception):
                    logger.warning(f"  Changelog fetch failed: {result}")

            logger.debug(f"  Batch {batch_num} completed: {success_count}/{len(batch)} succeeded")

        logger.info(f"Fetched changelogs for {len(results)} issues")
        return results

    async def get_issue_remote_links(self, issue_key: str) -> List[Dict[str, Any]]:
        """Get remote links (external links like GitHub PRs) for an issue."""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/remotelink"
        result = await self._fetch_json(url)
        return result if isinstance(result, list) else []

    async def fetch_remote_links_batch(
        self, issue_keys: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch remote links for multiple issues (typically root issues only)."""
        if not issue_keys:
            logger.debug("No issue keys for remote links fetch")
            return {}

        results = {}
        logger.info(f"Fetching remote links for {len(issue_keys)} root issues")

        async def fetch_one(key: str):
            links = await self.get_issue_remote_links(key)
            if links:
                logger.debug(f"  Remote links for {key}: {len(links)} links")
            return key, links

        tasks = [fetch_one(key) for key in issue_keys]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in batch_results:
            if isinstance(result, tuple):
                key, links = result
                results[key] = links
            elif isinstance(result, Exception):
                logger.warning(f"  Remote links fetch failed: {result}")

        links_found = sum(len(v) for v in results.values())
        logger.info(f"Fetched {links_found} remote links from {len(results)} issues")
        return results


# =============================================================================
# GitHub GraphQL Client
# =============================================================================

class GitHubClient:
    """Async GitHub GraphQL API client for fetching PR data."""

    GRAPHQL_URL = "https://api.github.com/graphql"

    def __init__(self, token: str):
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(GITHUB_MAX_CONCURRENT_REQUESTS)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _escape_graphql_string(self, s: str) -> str:
        """Escape a string for use in GraphQL query."""
        # Escape backslashes first, then quotes
        return s.replace("\\", "\\\\").replace('"', '\\"')

    def _build_pr_query(self, pr_refs: List[PRRef]) -> str:
        """Build a GraphQL query to fetch multiple PRs."""
        query_parts = []
        for i, ref in enumerate(pr_refs):
            owner = self._escape_graphql_string(ref.owner)
            repo = self._escape_graphql_string(ref.repo)
            query_parts.append(f"""
                pr{i}: repository(owner: "{owner}", name: "{repo}") {{
                    pullRequest(number: {ref.number}) {{
                        number
                        title
                        state
                        isDraft
                        url
                        createdAt
                        updatedAt
                        mergedAt
                        additions
                        deletions
                        changedFiles
                        reviewDecision
                        reviews(last: 30) {{
                            nodes {{
                                author {{ login }}
                                state
                                body
                                submittedAt
                            }}
                        }}
                        reviewThreads(last: 50) {{
                            nodes {{
                                isResolved
                                comments(first: 5) {{
                                    nodes {{
                                        author {{ login }}
                                        body
                                        createdAt
                                        path
                                        line
                                    }}
                                }}
                            }}
                        }}
                        commits(last: 30) {{
                            nodes {{
                                commit {{
                                    oid
                                    messageHeadline
                                    committedDate
                                    author {{ email }}
                                }}
                            }}
                        }}
                        files(first: 50) {{
                            nodes {{
                                path
                                additions
                                deletions
                            }}
                        }}
                    }}
                }}
            """)

        return "query { " + " ".join(query_parts) + " }"

    async def get_prs_batch(
        self, session: aiohttp.ClientSession, pr_refs: List[PRRef]
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch multiple PRs using GraphQL batching with retry logic."""
        if not pr_refs:
            logger.debug("No PR refs to fetch")
            return {}

        results = {}
        total_batches = (len(pr_refs) + GITHUB_GRAPHQL_BATCH_SIZE - 1) // GITHUB_GRAPHQL_BATCH_SIZE
        logger.info(f"Fetching {len(pr_refs)} PRs in {total_batches} GraphQL batch(es)")

        # Process in batches
        for batch_start in range(0, len(pr_refs), GITHUB_GRAPHQL_BATCH_SIZE):
            batch = pr_refs[batch_start : batch_start + GITHUB_GRAPHQL_BATCH_SIZE]
            batch_num = batch_start // GITHUB_GRAPHQL_BATCH_SIZE + 1

            logger.info(f"  GitHub batch {batch_num}/{total_batches}: {len(batch)} PRs")
            logger.debug(f"  PR URLs: {[r.url for r in batch[:3]]}{'...' if len(batch) > 3 else ''}")

            query = self._build_pr_query(batch)
            logger.debug(f"  GraphQL query length: {len(query)} chars")

            # Retry loop for transient errors
            data = None
            last_error = None
            for attempt in range(1, GITHUB_RETRY_ATTEMPTS + 1):
                async with self.semaphore:
                    try:
                        if HAS_AIOHTTP:
                            async with session.post(
                                self.GRAPHQL_URL,
                                headers=self._get_headers(),
                                json={"query": query},
                                timeout=aiohttp.ClientTimeout(total=60),
                            ) as resp:
                                # Check for transient errors that should be retried
                                if resp.status in (502, 503, 504):
                                    last_error = f"GitHub API error {resp.status}"
                                    if attempt < GITHUB_RETRY_ATTEMPTS:
                                        delay = GITHUB_RETRY_DELAY_SECONDS * attempt
                                        logger.warning(f"  {last_error}, retrying in {delay}s (attempt {attempt}/{GITHUB_RETRY_ATTEMPTS})")
                                        await asyncio.sleep(delay)
                                        continue
                                    else:
                                        logger.error(f"  {last_error}, giving up after {GITHUB_RETRY_ATTEMPTS} attempts")
                                        break
                                elif resp.status != 200:
                                    text = await resp.text()
                                    logger.error(f"GitHub API error {resp.status}: {text[:500]}")
                                    break
                                data = await resp.json()
                        else:
                            response = requests.post(
                                self.GRAPHQL_URL,
                                headers=self._get_headers(),
                                json={"query": query},
                                timeout=60,
                            )
                            if response.status_code in (502, 503, 504):
                                last_error = f"GitHub API error {response.status_code}"
                                if attempt < GITHUB_RETRY_ATTEMPTS:
                                    delay = GITHUB_RETRY_DELAY_SECONDS * attempt
                                    logger.warning(f"  {last_error}, retrying in {delay}s (attempt {attempt}/{GITHUB_RETRY_ATTEMPTS})")
                                    await asyncio.sleep(delay)
                                    continue
                                else:
                                    logger.error(f"  {last_error}, giving up after {GITHUB_RETRY_ATTEMPTS} attempts")
                                    break
                            elif response.status_code != 200:
                                logger.error(f"GitHub API error {response.status_code}")
                                break
                            data = response.json()

                        # Success - exit retry loop
                        break

                    except asyncio.TimeoutError:
                        last_error = "Request timeout"
                        if attempt < GITHUB_RETRY_ATTEMPTS:
                            delay = GITHUB_RETRY_DELAY_SECONDS * attempt
                            logger.warning(f"  {last_error}, retrying in {delay}s (attempt {attempt}/{GITHUB_RETRY_ATTEMPTS})")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error(f"  {last_error}, giving up after {GITHUB_RETRY_ATTEMPTS} attempts")
                            break
                    except Exception as e:
                        logger.error(f"Error fetching PR batch: {e}")
                        break

            # Process response if we got data
            if data is None:
                continue

            if "errors" in data:
                logger.warning(f"GraphQL errors: {data['errors'][:2]}")

            if "data" not in data:
                logger.warning("No 'data' in GraphQL response")
                continue

            batch_success = 0
            for i, ref in enumerate(batch):
                key = f"pr{i}"
                if key in data["data"] and data["data"][key]:
                    pr_data = data["data"][key].get("pullRequest")
                    if pr_data:
                        results[ref.url] = pr_data
                        batch_success += 1
                        logger.debug(f"    PR #{ref.number}: {pr_data.get('state')} - {pr_data.get('title', '')[:50]}")
                    else:
                        logger.debug(f"    PR #{ref.number}: not found (possibly deleted)")
                else:
                    logger.debug(f"    PR #{ref.number}: repo not found or no access")

            logger.debug(f"  Batch {batch_num} completed: {batch_success}/{len(batch)} PRs fetched")

        logger.info(f"Fetched {len(results)} PRs total")
        return results


# =============================================================================
# Data Gatherer
# =============================================================================

class StatusDataGatherer:
    """Orchestrates data gathering from Jira and GitHub."""

    # GitHub PR URL pattern
    PR_PATTERN = re.compile(r"https?://github\.com/[^/]+/[^/]+/pull[s]?/\d+")

    def __init__(self, config: GatherConfig):
        self.config = config
        self.jira = JiraClient(config.jira_url, config.jira_token)
        self.github = GitHubClient(config.github_token)

    def _build_root_jql(self) -> str:
        """Build JQL to find root issues."""
        parts = [
            f'project = "{self.config.project}"',
            "status != Closed",
            'status != "Release Pending"',
        ]

        if self.config.component:
            parts.append(f'component = "{self.config.component}"')

        if self.config.label:
            parts.append(f'labels = "{self.config.label}"')

        if self.config.assignees:
            assignee_list = ", ".join(f'"{a}"' for a in self.config.assignees)
            parts.append(f"assignee IN ({assignee_list})")

        if self.config.excluded_assignees:
            excluded_list = ", ".join(f'"{a}"' for a in self.config.excluded_assignees)
            parts.append(f"assignee NOT IN ({excluded_list})")

        return " AND ".join(parts) + " ORDER BY rank ASC"

    def _extract_pr_urls(self, text: Optional[str]) -> Set[str]:
        """Extract GitHub PR URLs from text."""
        if not text:
            return set()
        return set(self.PR_PATTERN.findall(text))

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def _filter_changelog_to_range(
        self, changelog: List[Dict], date_range: DateRange
    ) -> List[Dict]:
        """Filter changelog entries to date range."""
        filtered = []
        for entry in changelog:
            created = self._parse_datetime(entry.get("created"))
            if created and date_range.contains(created):
                filtered.append({
                    "date": entry.get("created"),
                    "author": entry.get("author", {}).get("emailAddress"),
                    "items": [
                        {
                            "field": item.get("field"),
                            "from": item.get("fromString"),
                            "to": item.get("toString"),
                        }
                        for item in entry.get("items", [])
                    ],
                })
        return filtered

    def _filter_comments_to_range(
        self, comments: List[Dict], date_range: DateRange
    ) -> List[Dict]:
        """Filter comments to date range and mark bots."""
        filtered = []
        bot_patterns = ["automation", "bot", "github", "jenkins", "jira"]

        for comment in comments:
            created = self._parse_datetime(comment.get("created"))
            if not created or not date_range.contains(created):
                continue

            author = comment.get("author", {})
            author_name = (author.get("displayName", "") or "").lower()
            author_email = (author.get("emailAddress", "") or "").lower()

            is_bot = any(p in author_name or p in author_email for p in bot_patterns)
            if "noreply" in author_email:
                is_bot = True

            filtered.append({
                "author": author.get("emailAddress") or author.get("displayName", "Unknown"),
                "author_name": author.get("displayName", "Unknown"),
                "date": comment.get("created"),
                "body": comment.get("body", ""),
                "is_bot": is_bot,
            })

        return filtered

    def _filter_pr_to_range(
        self, pr_data: Dict[str, Any], date_range: DateRange
    ) -> Dict[str, Any]:
        """Filter PR data to date range and add activity summary."""
        # Filter reviews
        reviews_in_range = []
        for review in (pr_data.get("reviews", {}).get("nodes") or []):
            submitted = self._parse_datetime(review.get("submittedAt"))
            if submitted and date_range.contains(submitted):
                reviews_in_range.append({
                    "author": (review.get("author") or {}).get("login", "Unknown"),
                    "state": review.get("state"),
                    "body": (review.get("body") or "")[:500],
                    "submitted_at": review.get("submittedAt"),
                })

        # Filter commits
        commits_in_range = []
        for node in (pr_data.get("commits", {}).get("nodes") or []):
            commit = node.get("commit", {})
            committed = self._parse_datetime(commit.get("committedDate"))
            if committed and date_range.contains(committed):
                commits_in_range.append({
                    "sha": (commit.get("oid") or "")[:7],
                    "message": commit.get("messageHeadline", ""),
                    "date": commit.get("committedDate"),
                    "author": (commit.get("author") or {}).get("email", "Unknown"),
                })

        # Filter review comments
        review_comments_in_range = []
        for thread in (pr_data.get("reviewThreads", {}).get("nodes") or []):
            for comment in (thread.get("comments", {}).get("nodes") or []):
                created = self._parse_datetime(comment.get("createdAt"))
                if created and date_range.contains(created):
                    review_comments_in_range.append({
                        "author": (comment.get("author") or {}).get("login", "Unknown"),
                        "path": comment.get("path"),
                        "line": comment.get("line"),
                        "body": (comment.get("body") or "")[:300],
                        "created_at": comment.get("createdAt"),
                    })

        # Files changed summary
        files = pr_data.get("files", {}).get("nodes") or []
        files_changed = {
            "total": pr_data.get("changedFiles", len(files)),
            "additions": pr_data.get("additions", 0),
            "deletions": pr_data.get("deletions", 0),
            "files": [
                {
                    "path": f.get("path", ""),
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                }
                for f in files[:20]
            ],
        }

        return {
            "url": pr_data.get("url"),
            "number": pr_data.get("number"),
            "title": pr_data.get("title"),
            "state": pr_data.get("state"),
            "is_draft": pr_data.get("isDraft", False),
            "review_decision": pr_data.get("reviewDecision"),
            "dates": {
                "created_at": pr_data.get("createdAt"),
                "updated_at": pr_data.get("updatedAt"),
                "merged_at": pr_data.get("mergedAt"),
            },
            "files_changed": files_changed,
            "reviews_in_range": reviews_in_range,
            "commits_in_range": commits_in_range,
            "review_comments_in_range": review_comments_in_range,
            "activity_summary": {
                "commits_in_range": len(commits_in_range),
                "reviews_in_range": len(reviews_in_range),
                "review_comments_in_range": len(review_comments_in_range),
            },
        }

    async def gather(self) -> Dict[str, Any]:
        """Main gathering method."""
        start_time = datetime.now()
        logger.info(f"Starting data gather at {start_time.isoformat()}")
        logger.debug(f"Config: project={self.config.project}, component={self.config.component}")
        logger.debug(f"Date range: {self.config.date_range.start} to {self.config.date_range.end}")

        if HAS_AIOHTTP:
            logger.debug("Using aiohttp for async HTTP requests")
            async with aiohttp.ClientSession() as session:
                self.jira.session = session
                return await self._gather_internal(session)
        else:
            logger.debug("Using requests for sync HTTP requests")
            return await self._gather_internal(None)

    async def _gather_internal(self, session: Optional[aiohttp.ClientSession]) -> Dict[str, Any]:
        """Internal gathering logic."""
        start_time = datetime.now()

        # Step 1: Find root issues
        logger.info("Step 1/7: Fetching root issues")
        jql = self._build_root_jql()
        logger.debug(f"JQL query: {jql}")

        root_issues = await self.jira.search_issues(
            jql=jql,
            fields=f"{self.jira.ISSUE_FIELDS},{self.config.status_summary_field}",
            max_results=100,
        )
        logger.info(f"  Found {len(root_issues)} root issues")
        for issue in root_issues:
            logger.debug(f"    {issue['key']}: {issue.get('fields', {}).get('summary', '')[:60]}")

        if not root_issues:
            logger.warning("No root issues found. Check JQL query and permissions.")
            return self._build_manifest([], {}, {}, {}, start_time)

        # Step 2: Get descendants for all root issues
        logger.info("Step 2/7: Fetching descendants")
        all_descendant_keys: Dict[str, List[str]] = {}

        for issue in root_issues:
            issue_key = issue["key"]
            child_jql = f"issue in childIssuesOf({issue_key})"
            logger.debug(f"  Fetching descendants of {issue_key}")
            children = await self.jira.search_issues(
                jql=child_jql,
                fields="key",
                max_results=200,
            )
            all_descendant_keys[issue_key] = [c["key"] for c in children]
            logger.debug(f"    {issue_key} has {len(children)} descendants")

        total_descendants = sum(len(v) for v in all_descendant_keys.values())
        logger.info(f"  Found {total_descendants} total descendants across {len(root_issues)} root issues")

        # Step 3: Batch fetch all descendant details
        logger.info("Step 3/7: Fetching descendant details")
        all_keys = []
        for keys in all_descendant_keys.values():
            all_keys.extend(keys)
        unique_keys = list(set(all_keys))
        logger.debug(f"  {len(unique_keys)} unique descendant keys to fetch")

        descendant_data = await self.jira.fetch_issues_batch(
            unique_keys,
            fields=self.jira.ISSUE_FIELDS,
        )

        # Step 4: Fetch changelogs for root Jira issues
        logger.info("Step 4/8: Fetching changelogs for root Jira issues")
        root_keys = [issue["key"] for issue in root_issues]
        changelogs = await self.jira.fetch_changelogs_batch(root_keys)

        # Step 5: Fetch remote links for root Jira issues (PRs roll up to parent)
        logger.info("Step 5/8: Fetching remote links for root Jira issues")
        remote_links = await self.jira.fetch_remote_links_batch(root_keys)

        # Step 6: Extract PR URLs from all issues, comments, and remote links
        logger.info("Step 6/8: Extracting PR URLs from issues, comments, and remote links")
        pr_refs_map: Dict[str, PRRef] = {}

        for issue in root_issues:
            issue_key = issue["key"]
            fields = issue.get("fields", {})

            # From description
            desc_urls = self._extract_pr_urls(fields.get("description", ""))
            for url in desc_urls:
                if url not in pr_refs_map:
                    ref = PRRef.from_url(url)
                    if ref:
                        pr_refs_map[url] = ref
                        logger.debug(f"    Found PR in {issue_key} description: {url}")
                if url in pr_refs_map:
                    pr_refs_map[url].found_in_issues.add(issue_key)

            # From comments
            comments = fields.get("comment", {}).get("comments", [])
            for comment in comments:
                comment_urls = self._extract_pr_urls(comment.get("body", ""))
                for url in comment_urls:
                    if url not in pr_refs_map:
                        ref = PRRef.from_url(url)
                        if ref:
                            pr_refs_map[url] = ref
                            logger.debug(f"    Found PR in {issue_key} comment: {url}")
                    if url in pr_refs_map:
                        pr_refs_map[url].found_in_issues.add(issue_key)

        # From descendants
        desc_pr_count = 0
        for parent_key, child_keys in all_descendant_keys.items():
            for child_key in child_keys:
                if child_key not in descendant_data:
                    continue
                child = descendant_data[child_key]
                child_fields = child.get("fields", {})

                for url in self._extract_pr_urls(child_fields.get("description", "")):
                    if url not in pr_refs_map:
                        ref = PRRef.from_url(url)
                        if ref:
                            pr_refs_map[url] = ref
                            desc_pr_count += 1
                    if url in pr_refs_map:
                        pr_refs_map[url].found_in_issues.add(parent_key)

                for comment in child_fields.get("comment", {}).get("comments", []):
                    for url in self._extract_pr_urls(comment.get("body", "")):
                        if url not in pr_refs_map:
                            ref = PRRef.from_url(url)
                            if ref:
                                pr_refs_map[url] = ref
                                desc_pr_count += 1
                        if url in pr_refs_map:
                            pr_refs_map[url].found_in_issues.add(parent_key)

        # From remote links (only PRs that reference a descendant issue key)
        remote_link_pr_count = 0
        for issue_key, links in remote_links.items():
            # Get descendant keys for this root issue
            desc_keys = set(all_descendant_keys.get(issue_key, []))
            for link in links:
                obj = link.get("object", {})
                url = obj.get("url", "")
                title = obj.get("title", "")
                if url and "github.com" in url and "/pull" in url:
                    # Check if the PR title references a descendant issue
                    references_descendant = any(desc_key in title for desc_key in desc_keys)
                    if references_descendant:
                        if url not in pr_refs_map:
                            ref = PRRef.from_url(url)
                            if ref:
                                pr_refs_map[url] = ref
                                remote_link_pr_count += 1
                                logger.debug(f"    Found PR in {issue_key} remote link: {url}")
                        if url in pr_refs_map:
                            pr_refs_map[url].found_in_issues.add(issue_key)

        logger.info(f"  Found {len(pr_refs_map)} unique PR URLs ({desc_pr_count} from descendants, {remote_link_pr_count} from remote links)")

        # Step 7: Fetch PR data from GitHub
        logger.info("Step 7/8: Fetching PR data from GitHub")
        if session and pr_refs_map:
            pr_data_map = await self.github.get_prs_batch(session, list(pr_refs_map.values()))
        else:
            pr_data_map = {}
            if not session:
                logger.warning("  No aiohttp session - skipping GitHub PR fetch")
            elif not pr_refs_map:
                logger.debug("  No PR URLs found - nothing to fetch")
        logger.info(f"  Fetched data for {len(pr_data_map)} PRs")

        # Step 8: Build output
        logger.info("Step 8/8: Building output files")
        manifest = self._build_manifest(
            root_issues,
            all_descendant_keys,
            descendant_data,
            changelogs,
            start_time,
            pr_refs_map,
            pr_data_map,
        )

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Data gathering complete in {duration:.1f}s")
        logger.info(f"Total Jira API requests: {self.jira.request_count}")

        return manifest

    def _build_manifest(
        self,
        root_issues: List[Dict],
        all_descendant_keys: Dict[str, List[str]],
        descendant_data: Dict[str, Dict],
        changelogs: Dict[str, List[Dict]],
        start_time: datetime,
        pr_refs_map: Optional[Dict[str, PRRef]] = None,
        pr_data_map: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, Any]:
        """Build manifest and per-issue files."""
        pr_refs_map = pr_refs_map or {}
        pr_data_map = pr_data_map or {}

        output_dir = self.config.output_dir
        issues_dir = output_dir / "issues"
        logger.debug(f"Creating output directory: {output_dir}")
        issues_dir.mkdir(parents=True, exist_ok=True)

        issue_entries = []
        total_prs = 0

        for issue in root_issues:
            issue_key = issue["key"]
            fields = issue.get("fields", {})

            # Get descendant keys for this issue
            desc_keys = all_descendant_keys.get(issue_key, [])

            # Process descendants
            descendants_data = {
                "total": len(desc_keys),
                "by_status": {},
                "updated_in_range": [],
            }

            for desc_key in desc_keys:
                if desc_key not in descendant_data:
                    continue
                desc = descendant_data[desc_key]
                desc_fields = desc.get("fields", {})
                status = desc_fields.get("status", {}).get("name", "Unknown")
                descendants_data["by_status"][status] = descendants_data["by_status"].get(status, 0) + 1

                # Check if updated in range
                updated = self._parse_datetime(desc_fields.get("updated"))
                if updated and self.config.date_range.contains(updated):
                    descendants_data["updated_in_range"].append({
                        "key": desc_key,
                        "summary": desc_fields.get("summary", ""),
                        "status": status,
                        "updated": desc_fields.get("updated"),
                    })

            # Calculate completion
            completed_statuses = {"Done", "Closed", "Resolved", "Release Pending", "Verified"}
            completed = sum(
                count for status, count in descendants_data["by_status"].items()
                if status in completed_statuses
            )
            if descendants_data["total"] > 0:
                descendants_data["completion_pct"] = round(
                    100 * completed / descendants_data["total"], 1
                )
            else:
                descendants_data["completion_pct"] = 0

            # Filter changelog to range
            issue_changelog = changelogs.get(issue_key, [])
            changelog_in_range = self._filter_changelog_to_range(
                issue_changelog, self.config.date_range
            )

            # Find last status summary update
            last_status_update = None
            for entry in reversed(issue_changelog):
                for item in entry.get("items", []):
                    field_name = (item.get("field") or "").lower()
                    if "status" in field_name and "summary" in field_name:
                        last_status_update = entry.get("created")
                        break
                if last_status_update:
                    break

            # Filter comments
            comments = fields.get("comment", {}).get("comments", [])
            comments_in_range = self._filter_comments_to_range(
                comments, self.config.date_range
            )

            # Get PRs for this issue
            issue_prs = []
            for url, ref in pr_refs_map.items():
                if issue_key in ref.found_in_issues:
                    if url in pr_data_map:
                        filtered_pr = self._filter_pr_to_range(
                            pr_data_map[url], self.config.date_range
                        )
                        filtered_pr["found_in_descendants"] = [
                            k for k in ref.found_in_issues if k != issue_key
                        ]
                        issue_prs.append(filtered_pr)
                        total_prs += 1

            # Build issue data
            assignee = fields.get("assignee") or {}
            issue_data = {
                "issue": {
                    "key": issue_key,
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", "Unknown"),
                    "assignee": {
                        "email": assignee.get("emailAddress"),
                        "name": assignee.get("displayName"),
                    },
                    "current_status_summary": fields.get(self.config.status_summary_field),
                    "last_status_summary_update": last_status_update,
                },
                "descendants": descendants_data,
                "changelog_in_range": changelog_in_range,
                "comments_in_range": comments_in_range,
                "prs": issue_prs,
            }

            # Write issue file
            issue_file = issues_dir / f"{issue_key}.json"
            with open(issue_file, "w") as f:
                json.dump(issue_data, f, indent=2)
            logger.debug(f"  Wrote {issue_file}")

            issue_entries.append({
                "key": issue_key,
                "summary": fields.get("summary", ""),
                "assignee": assignee.get("emailAddress"),
                "status": fields.get("status", {}).get("name", "Unknown"),
                "descendants_count": len(desc_keys),
                "prs_count": len(issue_prs),
            })
            logger.debug(f"  {issue_key}: {len(desc_keys)} descendants, {len(issue_prs)} PRs, {len(changelog_in_range)} changelog entries, {len(comments_in_range)} comments")

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Build manifest
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "config": {
                "project": self.config.project,
                "component": self.config.component,
                "label": self.config.label,
                "date_range": self.config.date_range.to_dict(),
                "status_summary_field": self.config.status_summary_field,
            },
            "issues": issue_entries,
            "stats": {
                "total_issues": len(root_issues),
                "total_descendants": sum(len(v) for v in all_descendant_keys.values()),
                "total_prs": total_prs,
                "jira_requests": self.jira.request_count,
                "fetch_duration_seconds": round(duration, 2),
            },
        }

        # Write manifest
        manifest_file = output_dir / "manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)
        logger.debug(f"Wrote manifest to {manifest_file}")
        logger.info(f"Output: {len(issue_entries)} issue files + manifest.json")

        return manifest


# =============================================================================
# CLI
# =============================================================================

def get_env_var(name: str, default: Optional[str] = None, required: bool = True, alternatives: Optional[List[str]] = None) -> Optional[str]:
    """Get environment variable, with optional alternative names."""
    value = os.environ.get(name, default)

    # Try alternatives if primary not found
    if not value and alternatives:
        for alt in alternatives:
            value = os.environ.get(alt)
            if value:
                logger.debug(f"Using {alt} instead of {name}")
                break

    if required and not value:
        alt_msg = f" (or {', '.join(alternatives)})" if alternatives else ""
        print(f"Error: Environment variable {name}{alt_msg} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def get_github_token() -> str:
    """Get GitHub token from environment or gh CLI."""
    # Try environment first
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        logger.debug("Using GITHUB_TOKEN from environment")
        return token

    # Fall back to gh CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
        token = result.stdout.strip()
        if token:
            logger.debug("Using token from 'gh auth token'")
            return token
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to get token from gh CLI: {e}")
    except FileNotFoundError:
        logger.warning("gh CLI not found")

    print("Error: GITHUB_TOKEN not set and 'gh auth token' failed", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Gather Jira and GitHub data for weekly status updates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --project OCPSTRAT
  %(prog)s --project OCPSTRAT --component "Control Plane" --verbose
  %(prog)s --project OCPSTRAT --days 14 --output-dir .work/status --debug

Environment Variables:
  JIRA_URL              Jira server URL (default: https://issues.redhat.com)
  JIRA_PERSONAL_TOKEN   Jira API bearer token (required)
  GITHUB_TOKEN          GitHub personal access token (required)
        """,
    )

    parser.add_argument("--project", required=True, help="Jira project key (e.g., OCPSTRAT)")
    parser.add_argument("--component", help="Filter by component name")
    parser.add_argument("--label", help="Filter by label")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back (default: 7)")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD), overrides --days")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--output-dir", default=".work/weekly-status", help="Output directory")
    parser.add_argument("--status-field", default="customfield_12320841", help="Status Summary field ID")
    parser.add_argument("--assignee", action="append", dest="assignees", help="Filter by assignee")
    parser.add_argument("--exclude-assignee", action="append", dest="excluded_assignees", help="Exclude assignee")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output (INFO level)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output (DEBUG level)")

    args = parser.parse_args()

    # Setup logging based on verbosity flags
    setup_logging(verbose=args.verbose, debug=args.debug)

    # Calculate date range
    if args.end_date:
        end_date = date.fromisoformat(args.end_date)
    else:
        end_date = date.today()

    if args.start_date:
        start_date = date.fromisoformat(args.start_date)
    else:
        start_date = end_date - timedelta(days=args.days)

    # Build output directory with date
    output_dir = Path(args.output_dir) / end_date.isoformat()

    # Get credentials
    jira_url = get_env_var("JIRA_URL", default="https://issues.redhat.com", required=False)
    jira_token = get_env_var("JIRA_PERSONAL_TOKEN", alternatives=["JIRA_TOKEN"])
    github_token = get_github_token()

    config = GatherConfig(
        project=args.project,
        component=args.component,
        label=args.label,
        jira_url=jira_url,
        jira_token=jira_token,
        github_token=github_token,
        output_dir=output_dir,
        date_range=DateRange(start=start_date, end=end_date),
        status_summary_field=args.status_field,
        assignees=args.assignees or [],
        excluded_assignees=args.excluded_assignees or [],
    )

    # Always print header to stderr (regardless of log level)
    print("=" * 60, file=sys.stderr)
    print("Status Data Gatherer", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Project: {config.project}", file=sys.stderr)
    print(f"Component: {config.component or 'All'}", file=sys.stderr)
    print(f"Date range: {start_date} to {end_date}", file=sys.stderr)
    print(f"Output: {output_dir}", file=sys.stderr)
    print(f"Mode: {'async (aiohttp)' if HAS_AIOHTTP else 'sync (requests)'}", file=sys.stderr)
    print(f"Log level: {'DEBUG' if args.debug else 'INFO' if args.verbose else 'WARNING'}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("", file=sys.stderr)

    logger.debug(f"Full config: project={config.project}, component={config.component}, "
                 f"label={config.label}, assignees={config.assignees}, "
                 f"excluded={config.excluded_assignees}")

    gatherer = StatusDataGatherer(config)
    manifest = asyncio.run(gatherer.gather())

    # Always print summary to stderr
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("Summary", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Issues: {manifest['stats']['total_issues']}", file=sys.stderr)
    print(f"Descendants: {manifest['stats']['total_descendants']}", file=sys.stderr)
    print(f"PRs: {manifest['stats']['total_prs']}", file=sys.stderr)
    print(f"Jira requests: {manifest['stats']['jira_requests']}", file=sys.stderr)
    print(f"Duration: {manifest['stats']['fetch_duration_seconds']}s", file=sys.stderr)
    print(f"Output: {output_dir}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Output manifest to stdout for piping
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
