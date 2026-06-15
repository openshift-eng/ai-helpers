#!/usr/bin/env python3
"""
JIRA Reader Script for Claude Code Skill

This script provides read-only access to JIRA issues on Red Hat Issue Tracker.
It fetches issue details, comments, custom fields, related Git links, and
traverses the ticket graph (parent, children, siblings, issue links, web links).

Uses Atlassian REST API v3. Description and comment fields are returned in
Atlassian Document Format (ADF) and automatically converted to plain text.

Usage:
    python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --issue INFERENG-5233
    python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --issue INFERENG-5233 --include-comments
    python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --jql "project=INFERENG AND fixVersion='3.4'"
    python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --graph INFERENG-5233
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

import urllib3
from ratelimit import limits, sleep_and_retry

try:
    from jira import JIRA
except ImportError:
    print(json.dumps({"error": "jira package not installed. Run: python3 -m pip install jira"}))
    sys.exit(1)


def _deep_to_dict(obj):
    """Recursively convert JIRA PropertyHolder trees to plain dicts."""
    if isinstance(obj, dict):
        return {k: _deep_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_to_dict(item) for item in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    try:
        return {k: _deep_to_dict(v) for k, v in vars(obj).items()}
    except TypeError:
        return obj


def adf_to_text(node):
    """
    Convert an Atlassian Document Format (ADF) node to plain text.

    API v3 returns description and comment body fields as ADF JSON (a nested
    document structure) instead of wiki markup. This function recursively
    extracts readable text, preserving paragraph breaks, list structure, and
    code block formatting.

    Args:
        node: An ADF node (dict with 'type' and optional 'content'),
              a plain string (returned as-is), or None.

    Returns:
        Plain text representation of the ADF content.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node

    if not isinstance(node, dict):
        node = _deep_to_dict(node)
        if not isinstance(node, dict):
            return str(node) if node else ""

    node_type = node.get("type", "")
    content = node.get("content", [])

    if node_type == "text":
        text = node.get("text", "")
        for mark in node.get("marks", []):
            if mark.get("type") == "link":
                href = mark.get("attrs", {}).get("href", "")
                if href and href != text:
                    return f"{text} ({href})"
        return text

    if node_type == "hardBreak":
        return "\n"

    if node_type == "mention":
        return node.get("attrs", {}).get("text", "")

    if node_type == "emoji":
        return node.get("attrs", {}).get("shortName", "")

    if node_type == "codeBlock":
        code_text = "".join(adf_to_text(child) for child in content)
        return f"\n```\n{code_text}\n```\n"

    if node_type in ("bulletList", "orderedList"):
        lines = []
        for i, item in enumerate(content):
            prefix = "- " if node_type == "bulletList" else f"{i + 1}. "
            item_text = adf_to_text(item).strip()
            lines.append(f"{prefix}{item_text}")
        return "\n".join(lines) + "\n"

    if node_type == "listItem":
        return "".join(adf_to_text(child) for child in content)

    if node_type in ("heading", "paragraph"):
        text = "".join(adf_to_text(child) for child in content)
        return text + "\n"

    if node_type == "blockquote":
        inner = "".join(adf_to_text(child) for child in content).strip()
        return "> " + inner.replace("\n", "\n> ") + "\n"

    if node_type == "rule":
        return "\n---\n"

    if node_type == "table":
        rows = []
        for row_node in content:
            cells = []
            for cell_node in row_node.get("content", []):
                cell_text = "".join(
                    adf_to_text(child) for child in cell_node.get("content", [])
                ).strip()
                cells.append(cell_text)
            rows.append(" | ".join(cells))
        return "\n".join(rows) + "\n"

    if node_type == "inlineCard":
        return node.get("attrs", {}).get("url", "")

    # doc, panel, expand, mediaSingle, etc.: recurse into children
    parts = [adf_to_text(child) for child in content]
    return "".join(parts)


def load_env_file():
    """Load environment variables from .env files.

    Loads ./.env first (local settings), then ~/.env (global defaults).
    Pre-existing environment variables are never overwritten.
    Surrounding quotes on values are stripped.
    """
    for env_path in [".env", os.path.expanduser("~/.env")]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        value = value.strip()
                        if (value.startswith('"') and value.endswith('"')) or (
                            value.startswith("'") and value.endswith("'")
                        ):
                            value = value[1:-1]
                        os.environ.setdefault(key.strip(), value)


_DECISION_KEYWORDS = re.compile(
    r"\b(?:decided|agreed|requirement|must|blocked|changed|approved|rejected|architecture|design)\b",
    re.IGNORECASE,
)


def generate_comments_brief(comments_json_path, max_bytes=30720, recent_days=30):
    """Produce a comments-brief.md digest from a previously saved comments.json."""
    with open(comments_json_path) as f:
        data = json.load(f)

    comments = data.get("comments", [])
    if not comments:
        brief_path = os.path.join(os.path.dirname(comments_json_path), "comments-brief.md")
        with open(brief_path, "w") as f:
            f.write("# Comments Brief\n\nNo comments found.\n")
        return {
            "brief_file": brief_path,
            "brief_bytes": 0,
            "recent_count": 0,
            "decision_count": 0,
            "omitted_count": 0,
        }

    cutoff = datetime.now() - timedelta(days=recent_days)

    recent = []
    older_decision = []
    older_omitted = 0

    for c in comments:
        try:
            created = datetime.strptime(c["created"], "%Y-%m-%d %H:%M")
        except (ValueError, KeyError):
            created = datetime.min
        if created >= cutoff:
            recent.append(c)
        elif _DECISION_KEYWORDS.search(c["body"]):
            older_decision.append(c)
        else:
            older_omitted += 1

    date_range = data.get("date_range", {})
    total = len(comments)

    def _render_brief(recent, older_decision, older_omitted):
        shown = len(recent) + len(older_decision)
        lines = [
            "# Comments Brief",
            "",
            f"Total comments: {total} | Showing: {shown} | Omitted: {older_omitted}",
            f"Date range: {date_range.get('earliest', 'N/A')} to {date_range.get('latest', 'N/A')}",
        ]
        if recent:
            lines.append("")
            lines.append(f"## Recent comments (last {recent_days} days)")
            for c in recent:
                lines.append("")
                lines.append(f"### [{c['author']}] — {c['created']}")
                lines.append("")
                lines.append(c["body"])
        if older_decision:
            lines.append("")
            lines.append("## Decision-relevant older comments")
            for c in older_decision:
                lines.append("")
                lines.append(f"### [{c['author']}] — {c['created']}")
                lines.append("")
                lines.append(c["body"])
        if older_omitted:
            lines.append("")
            lines.append("---")
            lines.append(f"{older_omitted} older comments omitted (no decision keywords found).")
            lines.append(f"Full comments: {os.path.basename(comments_json_path)}")
        return "\n".join(lines) + "\n"

    content = _render_brief(recent, older_decision, older_omitted)

    while len(content.encode("utf-8")) > max_bytes and older_decision:
        older_decision.pop(0)
        older_omitted += 1
        content = _render_brief(recent, older_decision, older_omitted)

    brief_path = os.path.join(os.path.dirname(comments_json_path), "comments-brief.md")
    os.makedirs(os.path.dirname(brief_path) or ".", exist_ok=True)
    with open(brief_path, "w") as f:
        f.write(content)

    return {
        "brief_file": brief_path,
        "brief_bytes": len(content.encode("utf-8")),
        "recent_count": len(recent),
        "decision_count": len(older_decision),
        "omitted_count": older_omitted,
    }


class JiraReader:
    """Read-only JIRA client for fetching, analyzing, and traversing issues."""

    def __init__(self, server=None):
        """Initialize JIRA connection with appropriate authentication."""
        load_env_file()

        token = os.environ.get("JIRA_API_TOKEN") or os.environ.get("JIRA_AUTH_TOKEN")
        if not token:
            raise ValueError(
                "JIRA_API_TOKEN (or JIRA_AUTH_TOKEN) not set. Add it to .env or ~/.env"
            )

        server = server or os.environ.get("JIRA_URL", "https://redhat.atlassian.net")

        if "atlassian.net" in server:
            options = {"rest_api_version": "3"}
            email = os.environ.get("JIRA_EMAIL")
            if not email:
                raise ValueError(
                    "JIRA_EMAIL environment variable not set. "
                    "Required for Atlassian Cloud. Add it to .env or ~/.env"
                )
            self.jira = JIRA(server=server, basic_auth=(email, token), options=options)
        else:
            self.jira = JIRA(server=server, token_auth=token)

        self.server = server
        self._epic_link_field = None
        self._parent_link_field = None
        self._custom_fields_discovered = False

    def process_comments(self, comments):
        """
        Process JIRA comments into anonymized threaded format.

        Args:
            comments: List of JIRA comment objects

        Returns:
            List of dictionaries with anonymized comment data
        """
        if not comments:
            return []

        # Create user mapping for anonymization
        user_mapping = {}
        participant_counter = 0

        # Sort comments by creation date
        sorted_comments = sorted(comments, key=lambda x: x.created)

        processed_comments = []

        for comment in sorted_comments:
            # Get or create anonymous participant label
            author_key = (
                comment.author.key if hasattr(comment.author, "key") else str(comment.author)
            )
            if author_key not in user_mapping:
                participant_counter += 1
                user_mapping[author_key] = (
                    f"Participant {chr(64 + participant_counter)}"  # A, B, C, etc.
                )

            participant = user_mapping[author_key]

            # Format timestamp
            try:
                timestamp = datetime.strptime(comment.created[:19], "%Y-%m-%dT%H:%M:%S")
                formatted_time = timestamp.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                formatted_time = comment.created[:16].replace("T", " ")

            # Clean comment body (v3 API returns ADF; v2 returns plain text)
            raw_body = comment.body if comment.body else ""
            comment_body = adf_to_text(raw_body).strip()

            if comment_body:
                processed_comments.append(
                    {"participant": participant, "timestamp": formatted_time, "body": comment_body}
                )

        return processed_comments

    def extract_git_links(self, links, git_link_types="all"):
        """
        Extract Git-related links (GitHub/GitLab) from JIRA remote links.

        Args:
            links: List of JIRA remote link objects
            git_link_types: Filter for "github", "gitlab", or "all"

        Returns:
            List of Git URLs
        """
        links_list = []

        if git_link_types == "github":
            prefix = ("github", "www.github")
        elif git_link_types == "gitlab":
            prefix = ("gitlab",)
        else:
            prefix = ("github", "www.github", "gitlab")

        for link in links:
            try:
                host = urllib3.util.parse_url(link.object.url).host
                if host and host.startswith(prefix):
                    links_list.append(link.object.url)
            except Exception:  # noqa: S112
                continue

        return links_list

    def categorize_issue_type(self, issue_type):
        """
        Categorize issue type into standard categories.

        Args:
            issue_type: JIRA issue type string

        Returns:
            Standardized category
        """
        issue_type_lower = issue_type.lower()

        if issue_type_lower == "bug":
            return "Bug"
        elif issue_type_lower == "vulnerability":
            return "CVE"
        elif issue_type_lower in ["story", "feature"]:
            return "Feature/Story"
        elif issue_type_lower == "epic":
            return "Epic"
        elif issue_type_lower == "task":
            return "Task"
        else:
            return issue_type

    @sleep_and_retry
    @limits(calls=2, period=5)
    def get_issue_data(self, jira_id, include_comments=False, git_link_types="all"):
        """
        Fetch comprehensive data for a JIRA issue.

        Args:
            jira_id: JIRA issue key (e.g., "INFERENG-5233")
            include_comments: Whether to fetch and process comments
            git_link_types: Filter for Git links ("github", "gitlab", or "all")

        Returns:
            Dictionary with issue data
        """
        try:
            issue = self.jira.issue(jira_id)
            links = self.jira.remote_links(jira_id)

            # Get comments if requested
            comments_data = []
            if include_comments:
                comments = self.jira.comments(jira_id)
                comments_data = self.process_comments(comments)

            # Extract Git links
            git_links = self.extract_git_links(links, git_link_types)

            # Extract custom fields
            custom_fields = {}

            # Release Note Type (customfield_10785)
            if hasattr(issue.fields, "customfield_10785") and issue.fields.customfield_10785:
                release_note_type = issue.fields.customfield_10785.value
                # Normalize "Feature" to "Enhancement"
                release_note_type = (
                    "Enhancement" if release_note_type == "Feature" else release_note_type
                )
                custom_fields["release_note_type"] = release_note_type

            # Fix Versions
            if issue.fields.fixVersions:
                custom_fields["fix_versions"] = [v.name for v in issue.fields.fixVersions]

            # Extract assignee safely
            assignee = None
            if issue.fields.assignee:
                assignee = (
                    issue.fields.assignee.displayName
                    if hasattr(issue.fields.assignee, "displayName")
                    else str(issue.fields.assignee)
                )

            # Build response
            return {
                "issue_key": issue.key,
                "issue_type": str(issue.fields.issuetype),
                "issue_category": self.categorize_issue_type(str(issue.fields.issuetype)),
                "priority": str(issue.fields.priority) if issue.fields.priority else "Undefined",
                "status": str(issue.fields.status),
                "assignee": assignee,
                "summary": issue.fields.summary,
                "description": adf_to_text(issue.fields.description),
                "created": issue.fields.created,
                "updated": issue.fields.updated,
                "comments": comments_data,
                "custom_fields": custom_fields,
                "git_links": git_links,
                "url": f"{self.server}/browse/{issue.key}",
            }

        except Exception as e:
            return {"error": f"Failed to fetch issue {jira_id}: {str(e)}", "issue_key": jira_id}

    @sleep_and_retry
    @limits(calls=2, period=5)
    def search_issues(self, jql, max_results=50, fetch_details=False):
        """
        Search JIRA issues using JQL (JIRA Query Language).

        Args:
            jql: JQL query string
            max_results: Maximum number of results to return
            fetch_details: If True, return issue keys for detailed
                fetching; if False, return summary info

        Returns:
            List of issue keys (if fetch_details=True) or list of
            issue summaries (if fetch_details=False)
        """
        try:
            issues = self.jira.search_issues(jql, maxResults=max_results)

            if not fetch_details:
                # Return basic info from search results without additional API calls (FAST)
                summaries = []
                for issue in issues:
                    assignee = None
                    if issue.fields.assignee:
                        assignee = (
                            issue.fields.assignee.displayName
                            if hasattr(issue.fields.assignee, "displayName")
                            else str(issue.fields.assignee)
                        )

                    # Extract fix versions
                    fix_versions = []
                    if issue.fields.fixVersions:
                        fix_versions = [v.name for v in issue.fields.fixVersions]

                    summaries.append(
                        {
                            "issue_key": issue.key,
                            "issue_type": str(issue.fields.issuetype),
                            "issue_category": self.categorize_issue_type(
                                str(issue.fields.issuetype)
                            ),
                            "priority": str(issue.fields.priority)
                            if issue.fields.priority
                            else "Undefined",
                            "status": str(issue.fields.status),
                            "assignee": assignee,
                            "summary": issue.fields.summary,
                            "fix_versions": fix_versions,
                            "url": f"{self.server}/browse/{issue.key}",
                        }
                    )
                return summaries
            else:
                # Return issue keys for detailed fetching (SLOW but comprehensive)
                return [issue.key for issue in issues]
        except Exception as e:
            return {"error": f"JQL search failed: {str(e)}"}

    # --- Ticket graph traversal methods ---

    def _discover_custom_fields(self):
        """Discover custom field IDs for 'Epic Link' and 'Parent Link'."""
        if self._custom_fields_discovered:
            return

        try:
            fields = self.jira.fields()
            for field in fields:
                name = field.get("name", "")
                if name == "Epic Link":
                    self._epic_link_field = field["id"]
                elif name == "Parent Link":
                    self._parent_link_field = field["id"]
        except Exception:  # noqa: S110
            pass

        self._custom_fields_discovered = True

    def _detect_parent(self, issue):
        """
        Detect the parent ticket key from an issue.

        Returns:
            Tuple of (parent_key, source) where source describes how parent was found.
        """
        # Check standard parent field
        if hasattr(issue.fields, "parent") and issue.fields.parent:
            return issue.fields.parent.key, "parent_field"

        # Check Parent Link custom field
        if self._parent_link_field:
            parent_link = getattr(issue.fields, self._parent_link_field, None)
            if parent_link:
                if isinstance(parent_link, str):
                    return parent_link, "parent_link_custom_field"
                elif hasattr(parent_link, "key"):
                    return parent_link.key, "parent_link_custom_field"

        return None, None

    @sleep_and_retry
    @limits(calls=2, period=5)
    def _fetch_issue_summary(self, jira_id):
        """Fetch basic summary fields for an issue."""
        try:
            issue = self.jira.issue(
                jira_id, fields="summary,status,issuetype,description,priority,assignee"
            )
            fields = issue.fields
            return {
                "key": issue.key,
                "summary": fields.summary,
                "status": str(fields.status) if fields.status else None,
                "issuetype": str(fields.issuetype) if fields.issuetype else None,
                "priority": str(fields.priority) if fields.priority else None,
                "assignee": fields.assignee.displayName
                if fields.assignee and hasattr(fields.assignee, "displayName")
                else None,
                "description": adf_to_text(fields.description),
            }
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                return {
                    "key": jira_id,
                    "summary": None,
                    "status": None,
                    "issuetype": None,
                    "error": "exists but not accessible (HTTP 403)",
                }
            return {"key": jira_id, "error": str(e)}

    @sleep_and_retry
    @limits(calls=2, period=5)
    def _fetch_issue(self, jira_id):
        """Rate-limited full issue fetch (returns the JIRA issue object)."""
        return self.jira.issue(jira_id)

    def _fetch_ancestor_chain(self, issue, max_depth=2):
        """
        Walk the parent chain from an issue, returning a list of ancestors.

        Each ancestor includes summary fields plus a 'source' indicating how
        the parent link was detected. Stops when no parent is found, an error
        occurs, or max_depth is reached.

        Returns:
            Tuple of (ancestors_list, errors_list). ancestors_list is ordered
            from immediate parent to most distant ancestor.
        """
        ancestors = []
        errors = []
        current_issue = issue
        seen_keys = {issue.key}

        for _ in range(max_depth):
            parent_key, parent_source = self._detect_parent(current_issue)
            if not parent_key:
                break
            if parent_key in seen_keys:
                errors.append(f"Cycle detected in ancestor chain: {parent_key} already visited")
                break

            seen_keys.add(parent_key)

            try:
                parent_issue = self._fetch_issue(parent_key)
            except Exception as e:
                if "403" in str(e) or "Forbidden" in str(e):
                    ancestors.append(
                        {
                            "key": parent_key,
                            "summary": None,
                            "status": None,
                            "issuetype": None,
                            "priority": None,
                            "assignee": None,
                            "description": None,
                            "source": parent_source,
                            "error": "exists but not accessible (HTTP 403)",
                        }
                    )
                else:
                    errors.append(f"Ancestor fetch for {parent_key}: {e}")
                break

            f = parent_issue.fields
            ancestors.append(
                {
                    "key": parent_issue.key,
                    "summary": f.summary,
                    "status": str(f.status) if f.status else None,
                    "issuetype": str(f.issuetype) if f.issuetype else None,
                    "priority": str(f.priority) if f.priority else None,
                    "assignee": f.assignee.displayName
                    if f.assignee and hasattr(f.assignee, "displayName")
                    else None,
                    "description": adf_to_text(f.description),
                    "source": parent_source,
                }
            )

            current_issue = parent_issue

        return ancestors, errors

    def _build_child_info(self, issue):
        """Build the metadata dict for a child/sibling issue."""
        f = issue.fields
        return {
            "key": issue.key,
            "summary": f.summary,
            "status": str(f.status) if f.status else None,
            "issuetype": str(f.issuetype) if f.issuetype else None,
            "priority": str(f.priority) if f.priority else None,
            "assignee": f.assignee.displayName
            if f.assignee and hasattr(f.assignee, "displayName")
            else None,
        }

    def _enrich_with_remote_links(self, issues, errors):
        """Fetch remote links, adding git_links and auto_discovered_urls."""
        for item in issues:
            web_links, auto_discovered, link_errors = self._fetch_remote_links(item["key"])
            item["git_links"] = []
            for link in web_links.get("links", []):
                url = link.get("url", "")
                try:
                    host = urllib3.util.parse_url(url).host
                except Exception:  # noqa: BLE001, S112
                    continue
                if host and host.startswith(("github", "www.github", "gitlab")):
                    item["git_links"].append(url)
            item["auto_discovered_urls"] = auto_discovered
            errors.extend(link_errors)

    def _fetch_children(self, ticket_key, max_children=25):
        """
        Fetch children via parent = KEY and "Epic Link" = KEY JQL queries.

        Also fetches remote links for each child and grandchild to populate
        git_links and auto_discovered_urls, so downstream consumers
        (extract_discovered_repos) can find PRs attached to child tickets.

        Returns:
            Dictionary with total, showing, skipped, and issues list.
        """
        errors = []
        seen_keys = set()
        issues = []

        # Query 1: Standard parent field
        jql1 = f"parent = {ticket_key} ORDER BY status ASC, key ASC"
        try:
            results = self.jira.search_issues(jql1, maxResults=max_children)
            for issue in results:
                if issue.key not in seen_keys:
                    seen_keys.add(issue.key)
                    issues.append(self._build_child_info(issue))
        except Exception as e:
            errors.append(f"Children query (parent field): {e}")

        # Query 2: Epic Link custom field
        if self._epic_link_field:
            jql2 = f'"Epic Link" = {ticket_key} ORDER BY status ASC, key ASC'
            try:
                results = self.jira.search_issues(jql2, maxResults=max_children)
                for issue in results:
                    if issue.key not in seen_keys:
                        seen_keys.add(issue.key)
                        issues.append(self._build_child_info(issue))
            except Exception as e:
                errors.append(f"Children query (Epic Link): {e}")

        self._enrich_with_remote_links(issues, errors)

        # Fetch grandchildren (children of children) with remote links
        child_keys = [c["key"] for c in issues]
        if child_keys:
            keys_csv = ", ".join(child_keys)
            jql_gc = f"parent in ({keys_csv}) ORDER BY status ASC, key ASC"
            try:
                gc_results = self.jira.search_issues(jql_gc, maxResults=max_children * 3)
                grandchildren = []
                for issue in gc_results:
                    if issue.key not in seen_keys:
                        seen_keys.add(issue.key)
                        gc_info = self._build_child_info(issue)
                        grandchildren.append(gc_info)
                self._enrich_with_remote_links(grandchildren, errors)
                issues.extend(grandchildren)
            except Exception as e:
                errors.append(f"Grandchildren query: {e}")

        showing = min(len(issues), max_children)
        issues = issues[:max_children]

        return {
            "total": len(seen_keys),
            "showing": showing,
            "skipped": max(0, len(seen_keys) - showing),
            "issues": issues,
        }, errors

    def _fetch_siblings(self, ticket_key, parent_key, parent_source, max_siblings=25):
        """
        Fetch sibling tickets (active statuses only).

        Returns:
            Dictionary with total, showing, skipped, and issues list.
        """
        errors = []

        if parent_source == "parent_link_custom_field":
            parent_clause = f'"Parent Link" = {parent_key}'
        else:
            parent_clause = f"parent = {parent_key}"

        active_statuses = 'Done, "In Progress", "In Review", "Code Review"'
        jql = (
            f"{parent_clause} AND key != {ticket_key} "
            f"AND status in ({active_statuses}) "
            f"ORDER BY status DESC, updated DESC"
        )

        try:
            results = self.jira.search_issues(jql, maxResults=max_siblings)
            issues = []
            for issue in results:
                f = issue.fields
                issues.append(
                    {
                        "key": issue.key,
                        "summary": f.summary,
                        "status": str(f.status) if f.status else None,
                        "issuetype": str(f.issuetype) if f.issuetype else None,
                    }
                )

            total = results.total if hasattr(results, "total") else len(issues)
            showing = len(issues)
            return {
                "total": total,
                "showing": showing,
                "skipped": max(0, total - showing),
                "issues": issues,
            }, errors
        except Exception as e:
            errors.append(f"Siblings query: {e}")
            return {"total": 0, "showing": 0, "skipped": 0, "issues": []}, errors

    def _extract_issue_links(self, issue, max_links=15):
        """
        Extract issue link summaries and fetch their remote links.

        Link metadata comes from the embedded issuelinks field. Remote links
        are fetched per linked issue to populate git_links/auto_discovered_urls.
        """
        raw_links = issue.fields.issuelinks if hasattr(issue.fields, "issuelinks") else []
        links = []

        for link in raw_links:
            link_type = link.type

            if hasattr(link, "inwardIssue") and link.inwardIssue:
                linked_issue = link.inwardIssue
                direction = link_type.inward
            elif hasattr(link, "outwardIssue") and link.outwardIssue:
                linked_issue = link.outwardIssue
                direction = link_type.outward
            else:
                continue

            links.append(
                {
                    "key": linked_issue.key,
                    "direction": direction,
                    "link_type": link_type.name,
                    "summary": linked_issue.fields.summary
                    if hasattr(linked_issue.fields, "summary")
                    else None,
                    "status": str(linked_issue.fields.status)
                    if hasattr(linked_issue.fields, "status") and linked_issue.fields.status
                    else None,
                    "issuetype": str(linked_issue.fields.issuetype)
                    if hasattr(linked_issue.fields, "issuetype") and linked_issue.fields.issuetype
                    else None,
                }
            )

            if len(links) >= max_links:
                break

        total = len(raw_links)
        showing = len(links)

        link_errors = []
        self._enrich_with_remote_links(links, link_errors)

        return {
            "total": total,
            "showing": showing,
            "skipped": max(0, total - showing),
            "links": links,
        }, link_errors

    def _classify_url(self, url):
        """Classify a URL as 'pull_request', 'google_doc', or 'other'."""
        if re.search(r"github\.com/.+/pull/\d+", url):
            return "pull_request"
        if re.search(r"gitlab\..+/-/merge_requests/\d+", url):
            return "pull_request"
        if re.search(r"docs\.google\.com/document/", url):
            return "google_doc"
        return "other"

    def _fetch_remote_links(self, ticket_key):
        """
        Fetch remote/web links from the ticket and classify URLs.

        Returns:
            Tuple of (web_links_dict, auto_discovered_urls_dict, errors).
        """
        errors = []
        try:
            remote_links = self.jira.remote_links(ticket_key)
        except Exception as e:
            errors.append(f"Remote links: {e}")
            return {"total": 0, "links": []}, {"pull_requests": [], "google_docs": []}, errors

        links = []
        pull_requests = []
        google_docs = []

        for item in remote_links:
            try:
                link_url = item.object.url if hasattr(item.object, "url") else ""
                title = item.object.title if hasattr(item.object, "title") else ""
                link_type = self._classify_url(link_url)
                links.append({"title": title, "url": link_url, "type": link_type})
                if link_type == "pull_request":
                    pull_requests.append(link_url)
                elif link_type == "google_doc":
                    google_docs.append(link_url)
            except Exception:  # noqa: S112
                continue

        web_links = {"total": len(links), "links": links}
        auto_discovered = {"pull_requests": pull_requests, "google_docs": google_docs}
        return web_links, auto_discovered, errors

    def save_comments_to_disk(self, jira_id, output_path):
        """
        Fetch all comments for an issue and persist them to disk.

        Args:
            jira_id: JIRA issue key.
            output_path: File path to write comments JSON. If it doesn't
                end with '.json', '.json' is appended.

        Returns metadata dict (no full comment text) for stdout output.
        """
        if not output_path.endswith(".json"):
            output_path = output_path + ".json"
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        comments = self.jira.comments(jira_id)
        processed = self.process_comments(comments)

        comments_data = {
            "total_comments": len(processed),
            "comments": [
                {
                    "index": i,
                    "author": c["participant"],
                    "created": c["timestamp"],
                    "body": c["body"],
                }
                for i, c in enumerate(processed)
            ],
        }

        total_bytes = len(json.dumps(comments_data))
        authors = sorted(set(c["participant"] for c in processed))
        date_range = {}
        if processed:
            timestamps = [c["timestamp"] for c in processed]
            date_range = {"earliest": timestamps[0], "latest": timestamps[-1]}

        comments_data["total_bytes"] = total_bytes
        comments_data["date_range"] = date_range
        comments_data["authors"] = authors

        with open(output_path, "w") as f:
            json.dump(comments_data, f, indent=2)

        return {
            "comments_saved_to": output_path,
            "comments_total": len(processed),
            "comments_total_bytes": total_bytes,
            "comments_date_range": date_range,
            "comments_authors": authors,
        }

    def generate_comments_brief(self, comments_json_path, max_bytes=30720, recent_days=30):
        return generate_comments_brief(comments_json_path, max_bytes, recent_days)

    def fetch_attachments(self, issue_key, output_dir, max_total_bytes=5_000_000):
        """
        Download attachments for an issue to disk.

        Text-extractable files are downloaded first. Binary files get placeholders.
        Stops when cumulative bytes exceed max_total_bytes.
        """
        os.makedirs(output_dir, exist_ok=True)
        attachments_dir = os.path.join(output_dir, "attachments")
        os.makedirs(attachments_dir, exist_ok=True)

        try:
            issue = self.jira.issue(issue_key, fields="attachment")
        except Exception as e:
            return {"error": f"Failed to fetch attachments for {issue_key}: {e}"}

        raw_attachments = issue.fields.attachment or []

        text_extensions = {".txt", ".md", ".csv", ".yaml", ".yml", ".json", ".adoc", ".xml"}
        text_items = []
        binary_items = []

        for att in raw_attachments:
            ext = os.path.splitext(att.filename)[1].lower()
            entry = {
                "filename": att.filename,
                "mime_type": getattr(att, "mimeType", "application/octet-stream"),
                "size_bytes": int(att.size) if hasattr(att, "size") and att.size else 0,
                "jira_id": att.id,
            }
            if ext in text_extensions:
                text_items.append(entry)
            else:
                binary_items.append(entry)

        sorted_items = text_items + binary_items
        downloaded = []
        total_downloaded = 0
        skipped = []

        for item in sorted_items:
            if total_downloaded + item["size_bytes"] > max_total_bytes:
                skipped.append(item["filename"])
                continue

            safe_name = os.path.basename(item["filename"])
            ext = os.path.splitext(safe_name)[1].lower()
            output_path = os.path.join(attachments_dir, safe_name)

            if ext in text_extensions:
                try:
                    content = self.jira.attachment(item["jira_id"]).get()
                    if isinstance(content, bytes):
                        content = content.decode("utf-8", errors="replace")
                    with open(output_path, "w") as f:
                        f.write(content)
                    token_estimate = len(content) // 3
                    downloaded.append(
                        {
                            "filename": item["filename"],
                            "mime_type": item["mime_type"],
                            "size_bytes": item["size_bytes"],
                            "extracted": True,
                            "extracted_path": output_path,
                            "token_estimate": token_estimate,
                        }
                    )
                    total_downloaded += item["size_bytes"]
                except Exception:
                    placeholder_path = output_path + ".txt"
                    with open(placeholder_path, "w") as f:
                        f.write(
                            f"[{ext} attachment: {item['filename']}, "
                            f"{item['size_bytes']} bytes. Download failed.]"
                        )
                    downloaded.append(
                        {
                            "filename": item["filename"],
                            "mime_type": item["mime_type"],
                            "size_bytes": item["size_bytes"],
                            "extracted": False,
                            "extracted_path": placeholder_path,
                            "token_estimate": 0,
                        }
                    )
            else:
                placeholder_path = output_path + ".txt"
                with open(placeholder_path, "w") as f:
                    f.write(
                        f"[{ext.lstrip('.').upper() or 'binary'} attachment: "
                        f"{item['filename']}, {item['size_bytes']} bytes. "
                        f"Content not extracted.]"
                    )
                downloaded.append(
                    {
                        "filename": item["filename"],
                        "mime_type": item["mime_type"],
                        "size_bytes": item["size_bytes"],
                        "extracted": False,
                        "extracted_path": placeholder_path,
                        "token_estimate": 0,
                    }
                )

        return {
            "attachments": downloaded,
            "total_bytes_downloaded": total_downloaded,
            "budget_bytes_remaining": max(0, max_total_bytes - total_downloaded),
            "skipped": skipped,
        }

    def get_ticket_graph(self, ticket_key, max_children=25, max_siblings=25, max_links=15):
        """
        Traverse the JIRA ticket graph: ancestors, children, siblings, issue links, web links.

        Upward traversal walks the parent chain (up to 2 levels by default).
        Downward/lateral traversal is bounded to 1 level deep.

        Args:
            ticket_key: JIRA issue key (e.g., "INFERENG-5233")
            max_children: Maximum children to fetch
            max_siblings: Maximum siblings to fetch
            max_links: Maximum issue links to extract

        Returns:
            Dictionary with full graph traversal results
        """
        all_errors = []

        # Step 1: Discover custom fields
        self._discover_custom_fields()

        # Step 2: Fetch primary ticket
        try:
            issue = self.jira.issue(ticket_key)
        except Exception as e:
            return {"ticket": ticket_key, "error": f"Failed to fetch primary ticket: {e}"}

        # Step 3: Walk the ancestor chain (parent, grandparent, etc.)
        ancestors, errors = self._fetch_ancestor_chain(issue)
        all_errors.extend(errors)

        # Backward compat: parent is the first ancestor (or None)
        parent_info = ancestors[0] if ancestors else None
        parent_key = parent_info["key"] if parent_info else None
        parent_source = parent_info.get("source") if parent_info else None

        # Step 4: Fetch children
        children, errors = self._fetch_children(ticket_key, max_children)
        all_errors.extend(errors)

        # Step 5: Fetch siblings (only if parent exists)
        siblings = {"total": 0, "showing": 0, "skipped": 0, "issues": []}
        if parent_key and parent_source:
            siblings, errors = self._fetch_siblings(
                ticket_key, parent_key, parent_source, max_siblings
            )
            all_errors.extend(errors)

        # Step 6: Extract issue links and fetch their remote links
        issue_links, errors = self._extract_issue_links(issue, max_links)
        all_errors.extend(errors)

        # Step 7: Fetch remote/web links and classify URLs
        web_links, auto_discovered, errors = self._fetch_remote_links(ticket_key)
        all_errors.extend(errors)

        return {
            "ticket": ticket_key,
            "jira_url": self.server,
            "parent": parent_info,
            "ancestors": ancestors,
            "children": children,
            "siblings": siblings,
            "issue_links": issue_links,
            "web_links": web_links,
            "auto_discovered_urls": auto_discovered,
            "errors": all_errors,
        }


def trim_graph(graph, max_tokens):
    """
    Trim a ticket graph to fit within a token budget using depth-decay scoring.

    Nodes closer to the primary ticket score higher. Within the same depth,
    children/parent score higher than siblings, which score higher than links.
    """
    base_scores = {"parent": 1.0, "children": 1.0, "siblings": 0.6, "issue_links": 0.5}
    decay = 0.8

    scored_nodes = []

    for i, ancestor in enumerate(graph.get("ancestors", [])):
        depth = i + 1
        score = base_scores["parent"] * (decay**depth)
        scored_nodes.append(("ancestors", ancestor, score))

    for child in graph.get("children", {}).get("issues", []):
        score = base_scores["children"] * decay
        scored_nodes.append(("children", child, score))

    for sibling in graph.get("siblings", {}).get("issues", []):
        score = base_scores["siblings"] * (decay**2)
        scored_nodes.append(("siblings", sibling, score))

    for link in graph.get("issue_links", {}).get("links", []):
        score = base_scores["issue_links"] * decay
        scored_nodes.append(("issue_links", link, score))

    scored_nodes.sort(key=lambda x: x[2], reverse=True)

    total_nodes = len(scored_nodes)
    kept = {"ancestors": [], "children": [], "siblings": [], "issue_links": []}
    used_tokens = len(json.dumps({"ticket": graph["ticket"]})) // 3

    for category, node, _score in scored_nodes:
        node_tokens = len(json.dumps(node)) // 3
        if used_tokens + node_tokens > max_tokens:
            continue
        used_tokens += node_tokens
        kept[category].append(node)

    trimmed = dict(graph)
    trimmed["ancestors"] = kept["ancestors"]
    trimmed["parent"] = kept["ancestors"][0] if kept["ancestors"] else None
    trimmed["children"] = {
        "total": graph.get("children", {}).get("total", 0),
        "showing": len(kept["children"]),
        "skipped": max(0, graph.get("children", {}).get("total", 0) - len(kept["children"])),
        "issues": kept["children"],
    }
    trimmed["siblings"] = {
        "total": graph.get("siblings", {}).get("total", 0),
        "showing": len(kept["siblings"]),
        "skipped": max(0, graph.get("siblings", {}).get("total", 0) - len(kept["siblings"])),
        "issues": kept["siblings"],
    }
    trimmed["issue_links"] = {
        "total": graph.get("issue_links", {}).get("total", 0),
        "showing": len(kept["issue_links"]),
        "skipped": max(0, graph.get("issue_links", {}).get("total", 0) - len(kept["issue_links"])),
        "links": kept["issue_links"],
    }
    nodes_included = sum(len(v) for v in kept.values())
    trimmed["graph_trimmed"] = nodes_included < total_nodes
    trimmed["nodes_included"] = nodes_included
    trimmed["nodes_total"] = total_nodes

    return trimmed


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Fetch and analyze JIRA issues from Red Hat Issue Tracker"
    )
    parser.add_argument(
        "--issue",
        action="append",
        help="JIRA issue key (e.g., INFERENG-5233). Can be specified multiple times.",
    )
    parser.add_argument("--jql", help="JQL query to search for issues")
    parser.add_argument(
        "--graph",
        help="Traverse the ticket graph for a JIRA issue key (parent, children, siblings, links)",
    )
    parser.add_argument(
        "--include-comments", action="store_true", help="Include anonymized comment threads"
    )
    parser.add_argument(
        "--git-links",
        choices=["github", "gitlab", "all"],
        default="all",
        help="Filter Git links by type",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Maximum number of results for JQL search (default: 50)",
    )
    parser.add_argument(
        "--fetch-details",
        action="store_true",
        help=(
            "Fetch full details for each issue (slow). "
            "By default, JQL searches return fast summaries only."
        ),
    )
    parser.add_argument(
        "--max-children",
        type=int,
        default=25,
        help="Maximum children to fetch in graph mode (default: 25)",
    )
    parser.add_argument(
        "--max-siblings",
        type=int,
        default=25,
        help="Maximum siblings to fetch in graph mode (default: 25)",
    )
    parser.add_argument(
        "--max-links",
        type=int,
        default=15,
        help="Maximum issue links to extract in graph mode (default: 15)",
    )
    parser.add_argument(
        "--max-graph-tokens",
        type=int,
        default=None,
        help="Token budget for graph output. Trims lowest-scored nodes using depth-decay scoring.",
    )
    parser.add_argument(
        "--save-comments",
        metavar="PATH",
        help="Save full comments to <PATH>/comments.json and return metadata only in stdout.",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="With --save-comments, also produce a comments-brief.md digest (under 30 KB).",
    )
    parser.add_argument(
        "--attachments",
        metavar="ISSUE_KEY",
        help="Download attachments for an issue to --output-dir.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        help="Output directory for attachments (required with --attachments).",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=5_000_000,
        help="Maximum total bytes to download for attachments (default: 5000000).",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.issue and not args.jql and not args.graph and not args.attachments:
        parser.error("Must specify --issue, --jql, --graph, or --attachments")

    if args.attachments and not args.output_dir:
        parser.error("--output-dir is required with --attachments")

    if args.brief and not args.save_comments:
        parser.error("--brief requires --save-comments")

    if args.save_comments:
        args.include_comments = True

    try:
        reader = JiraReader()

        # Handle attachments download
        if args.attachments:
            result = reader.fetch_attachments(
                args.attachments, args.output_dir, max_total_bytes=args.max_bytes
            )
            print(json.dumps(result, indent=2))
            if result.get("error"):
                sys.exit(1)
            return

        # Handle graph traversal
        if args.graph:
            result = reader.get_ticket_graph(
                args.graph,
                max_children=args.max_children,
                max_siblings=args.max_siblings,
                max_links=args.max_links,
            )
            if result.get("error"):
                print(json.dumps(result, indent=2))
                sys.exit(1)
            if args.max_graph_tokens:
                result = trim_graph(result, args.max_graph_tokens)
            print(json.dumps(result, indent=2))
            return

        results = []

        # Handle JQL search
        if args.jql:
            search_results = reader.search_issues(
                args.jql, args.max_results, fetch_details=args.fetch_details
            )
            if isinstance(search_results, dict) and "error" in search_results:
                print(json.dumps(search_results, indent=2))
                sys.exit(1)

            if args.fetch_details:
                for issue_key in search_results:
                    issue_data = reader.get_issue_data(
                        issue_key,
                        include_comments=args.include_comments,
                        git_link_types=args.git_links,
                    )
                    results.append(issue_data)
            else:
                results = search_results

        # Handle individual issue requests
        elif args.issue:
            for issue_key in args.issue:
                issue_data = reader.get_issue_data(
                    issue_key, include_comments=args.include_comments, git_link_types=args.git_links
                )

                if args.save_comments and args.include_comments:
                    comment_meta = reader.save_comments_to_disk(issue_key, args.save_comments)
                    if args.brief:
                        brief_meta = reader.generate_comments_brief(
                            comment_meta["comments_saved_to"]
                        )
                        comment_meta.update(brief_meta)
                    issue_data.pop("comments", None)
                    issue_data["comments_metadata"] = comment_meta

                results.append(issue_data)

        # Output results as JSON
        if len(results) == 1:
            print(json.dumps(results[0], indent=2))
        else:
            print(json.dumps(results, indent=2))

    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Unexpected error: {str(e)}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
