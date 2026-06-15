---
name: jira-reader
description: Read and analyze JIRA issues from Red Hat Issue Tracker. Use this skill to fetch issue details, search issues, extract comments and discussions, categorize issues (bugs, CVEs, features, stories), analyze custom fields (release notes, fix versions), retrieve Git links, traverse ticket graphs (parent, children, siblings, links), and generate summaries. This skill is read-only and cannot modify JIRA issues. Requires jira and ratelimit Python packages.
author: Gabriel McGoldrick (gmcgoldr@redhat.com)
allowed-tools: Read, Bash, Grep, Glob
---

# JIRA Reader Skill

This skill provides read-only access to JIRA issues on Red Hat Issue Tracker (https://redhat.atlassian.net). It uses the Atlassian REST API v3, which returns rich text fields (description, comments) in Atlassian Document Format (ADF). The skill automatically converts ADF to plain text.

## Prerequisites

The script requires Python packages `jira` and `ratelimit`:

```bash
python3 -m pip install jira ratelimit
```

## Capabilities

- **Fetch Issue Details**: Get full issue information including description, status, priority, assignee, components
- **Process Comments**: Extract and analyze comment threads with anonymized participants
- **Extract Custom Fields**: Access release note types, fix versions, and other custom fields
- **Find Git Links**: Retrieve related GitHub/GitLab pull requests and commits
- **Categorize Issues**: Classify issues as bugs, CVEs, features, stories, epics, tasks
- **Generate Summaries**: Create categorized reports and analysis of multiple issues
- **Ticket Graph Traversal**: Map relationships — parent, children, siblings, issue links, web links

## Usage

The skill uses a Python script that connects to JIRA using an authentication token.

### Environment Variables Required

Set in `~/.env` (global) or `.env` in the project root (local override). See docs-tools README for setup:

```bash
JIRA_API_TOKEN=your-jira-api-token
JIRA_EMAIL=you@redhat.com           # required for Atlassian Cloud
JIRA_URL=https://redhat.atlassian.net  # optional, defaults to redhat.atlassian.net
```

The script loads `.env` files automatically — do **not** prepend `source ~/.env` to bash commands.

### Examples

**Fetch a single issue:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --issue INFERENG-5233
```

**Fetch issue with comments:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --issue INFERENG-5233 --include-comments
```

**Fetch multiple issues:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --issue INFERENG-5233 --issue INFERENG-5049
```

**Search issues by JQL (FAST - returns summaries):**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --jql "project=INFERENG AND status='In Progress'"
```

**Search with full details (SLOW - fetches all fields):**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --jql "project=INFERENG AND status='In Progress'" --fetch-details
```

**Traverse the ticket graph:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --graph INFERENG-5233
```

**Graph with custom limits:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_reader.py --graph INFERENG-5233 --max-children 10 --max-siblings 10 --max-links 20
```

## Performance Modes

### Default: Fast Summary Mode
JQL searches return summaries by default (1 API call, ~3 seconds for any number of results):
- issue_key, issue_type, issue_category, priority, status
- assignee, summary, fix_versions, url

Use for: Quick analysis, categorization, release planning, CVE reports

### Opt-in: Detailed Mode (`--fetch-details`)
Fetches full details for each issue (N+1 API calls, ~2.5 seconds per issue):
- Everything in summary mode PLUS
- Full description, comments, git_links, created/updated dates, all custom fields

Use for: Deep analysis, comment threads, Git link extraction

### Graph Mode (`--graph`)
Traverses ticket relationships:
- Ancestor chain — walks the parent chain (up to 2 levels by default) via standard parent field + Parent Link custom field. This means a task under an Epic under a Feature will return both the Epic and the Feature
- Children (via parent and Epic Link JQL queries, 1 level deep)
- Siblings (active statuses under same parent, 1 level deep)
- Issue links (blocks, clones, relates to)
- Remote/web links (classified as PRs, Google Docs, or other)

Use for: Understanding ticket context, documentation workflows, relationship mapping

## Output Formats

**Summary output (default for JQL):**
```json
{
  "issue_key": "INFERENG-5233",
  "issue_type": "Task",
  "issue_category": "Task",
  "priority": "Undefined",
  "status": "New",
  "assignee": null,
  "summary": "Issue summary text",
  "fix_versions": [],
  "url": "https://redhat.atlassian.net/browse/INFERENG-5233"
}
```

**Detailed output (with --fetch-details or --issue):**
```json
{
  "issue_key": "INFERENG-5233",
  "issue_type": "Task",
  "issue_category": "Task",
  "priority": "Undefined",
  "status": "New",
  "assignee": null,
  "summary": "Issue summary text",
  "description": "Full issue description...",
  "created": "2026-03-16T08:34:09.302+0000",
  "updated": "2026-03-16T09:03:46.166+0000",
  "comments": [
    {
      "participant": "Participant A",
      "timestamp": "2026-03-16 08:34",
      "body": "Comment text..."
    }
  ],
  "custom_fields": {
    "release_note_type": "Bug Fix",
    "fix_versions": ["3.4"]
  },
  "git_links": [
    "https://github.com/org/repo/pull/123"
  ],
  "url": "https://redhat.atlassian.net/browse/INFERENG-5233"
}
```

**Graph output (with --graph):**
```json
{
  "ticket": "INFERENG-5233",
  "jira_url": "https://redhat.atlassian.net",
  "parent": {"key": "INFERENG-5049", "summary": "...", "status": "New", "issuetype": "Epic"},
  "ancestors": [
    {"key": "INFERENG-5049", "summary": "...", "status": "New", "issuetype": "Epic", "priority": "Medium", "assignee": null, "description": "...", "source": "parent_field"},
    {"key": "INFERENG-5000", "summary": "...", "status": "In Progress", "issuetype": "Feature", "priority": "High", "assignee": "John Doe", "description": "...", "source": "parent_link_custom_field"}
  ],
  "children": {"total": 0, "showing": 0, "skipped": 0, "issues": []},
  "siblings": {"total": 0, "showing": 0, "skipped": 0, "issues": []},
  "issue_links": {"total": 1, "showing": 1, "skipped": 0, "links": [...]},
  "web_links": {"total": 1, "links": [...]},
  "auto_discovered_urls": {"pull_requests": [...], "google_docs": []},
  "errors": []
}
```

## Rate Limiting

The skill respects JIRA API rate limits (2 calls per 5 seconds) to avoid overwhelming the server. Summary mode requires only 1 call regardless of result count, making it ~80x faster for bulk operations.

## Security

- Read-only operations only (enforced by allowed-tools)
- Token stored in environment variable (not in code)
- Comment anonymization to protect user identities in analysis

## Common Use Cases

1. **Analyze release issues**: Fetch all issues for a fix version and categorize them
2. **CVE reporting**: Extract security vulnerabilities and their status
3. **Bug triage**: Get issue details with comments for understanding context
4. **Release notes**: Extract information needed for documentation
5. **Link analysis**: Find related Git changes for code review
6. **Ticket graph**: Map relationships for documentation workflow context
