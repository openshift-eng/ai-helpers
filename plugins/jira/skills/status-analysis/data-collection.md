---
name: Data Collection
description: Fetching issues, changelogs, and comments from Jira for status analysis
---

# Data Collection

This module handles all Jira API interactions for the Status Analysis Engine. It fetches issues, their hierarchies, changelogs, and comments.

## Overview

Data collection follows this flow:

```
1. Fetch root issue(s)
         │
         ▼
2. Discover descendants via childIssuesOf()
         │
         ▼
3. Fetch details for all issues (batch where possible)
         │
         ▼
4. Fetch changelogs (batch via jira_batch_get_changelogs)
         │
         ▼
5. Build IssueActivityData structures
         │
         ▼
6. Optionally cache to temp file
```

## Step 1: Fetch Root Issue(s)

For each root issue key in `config.root_issues`:

```
mcp__atlassian-mcp__jira_get_issue(
  issue_key = "{root-issue-key}",
  fields = "summary,status,assignee,issuetype,created,updated,description,issuelinks,comment,{status-summary-field-id}",
  expand = "changelog",
  comment_limit = 20
)
```

**Extract from response**:
- `key`: Issue key (e.g., "OCPSTRAT-1234")
- `fields.summary`: Issue title
- `fields.status.name`: Current status
- `fields.assignee.displayName` and `fields.assignee.emailAddress`: Assignee info
- `fields.issuetype.name`: Issue type (Epic, Story, Task, etc.)
- `fields.created`: Creation date
- `fields.updated`: Last update date
- `fields.description`: Issue description (for PR URL extraction)
- `fields.issuelinks`: Linked issues and remote links
- `fields.comment.comments`: Recent comments
- `fields.{status-summary-field-id}`: Current Status Summary value (if applicable)
- `changelog.histories`: Field change history

**Validate**:
- If issue not found, log error and skip to next root issue
- If permission denied, display clear error with MCP config guidance

## Step 2: Discover Descendants

Use the `childIssuesOf()` JQL function to find all descendants:

```
mcp__atlassian-mcp__jira_search(
  jql = "issue in childIssuesOf({root-issue-key})",
  fields = "key",
  limit = 100
)
```

**Important notes**:
- `childIssuesOf()` is **already recursive** - returns ALL descendants at any depth
- Single JQL query gets the entire hierarchy
- Only fetch `key` field here - will fetch full details in Step 3
- If more than 100 descendants, increase `limit` or use pagination

**Optional date filter**: To focus on recently active issues:
```
mcp__atlassian-mcp__jira_search(
  jql = "issue in childIssuesOf({root-issue-key}) AND updated >= {start-date}",
  fields = "key",
  limit = 100
)
```

**Extract from response**:
- `issues[].key`: List of all descendant issue keys
- `total`: Total count of descendants

**Handle edge cases**:
- If no descendants found, continue with root issue only
- For large hierarchies (100+ issues), show progress indicator

## Step 3: Fetch Issue Details

For each descendant issue key (and root if not already fetched):

```
mcp__atlassian-mcp__jira_get_issue(
  issue_key = "{issue-key}",
  fields = "summary,status,assignee,issuetype,created,updated,issuelinks,comment",
  expand = "changelog",
  comment_limit = 20
)
```

**Optimization**: Parallelize these calls where possible. MCP tools can be called concurrently for different issues.

**Extract and store for each issue**:
```json
{
  "key": "OCPSTRAT-1235",
  "summary": "Sub-task title",
  "status": "In Progress",
  "assignee": {
    "displayName": "John Doe",
    "emailAddress": "jdoe@example.com"
  },
  "issue_type": "Story",
  "created": "2025-01-01T10:00:00Z",
  "updated": "2025-01-10T15:30:00Z",
  "issuelinks": [...],
  "comments": [...],
  "changelog": {...}
}
```

## Step 4: Fetch Changelogs (Batch)

For efficiency, use batch changelog fetching for all issue keys:

```
mcp__atlassian-mcp__jira_batch_get_changelogs(
  issue_ids_or_keys = ["OCPSTRAT-1234", "OCPSTRAT-1235", "OCPSTRAT-1236", ...],
  fields = ["status", "assignee", "Status Summary"],
  limit = -1
)
```

**Parameters**:
- `issue_ids_or_keys`: Array of all issue keys (root + descendants)
- `fields`: Filter to relevant fields only (reduces response size)
  - `"status"`: Status transitions
  - `"assignee"`: Assignee changes
  - `"Status Summary"`: Status Summary field updates (for recent update warnings)
- `limit`: `-1` for all changelogs, or a positive number to limit per issue

**Extract from response**:
For each issue, extract changelog entries:
```json
{
  "issue_key": "OCPSTRAT-1235",
  "changelogs": [
    {
      "created": "2025-01-07T09:00:00Z",
      "author": {
        "displayName": "John Doe",
        "emailAddress": "jdoe@example.com"
      },
      "items": [
        {
          "field": "status",
          "fromString": "To Do",
          "toString": "In Progress"
        }
      ]
    }
  ]
}
```

**Note**: This batch endpoint is only available on Jira Cloud. For Jira Server/Data Center, fall back to per-issue changelog extraction from the `expand=changelog` response in Step 3.

## Step 5: Build IssueActivityData Structures

For each issue (root and descendants), combine all collected data into an `IssueActivityData` structure:

```json
{
  "issue_key": "OCPSTRAT-1234",
  "summary": "Implement feature X",
  "status": "In Progress",
  "assignee": "jdoe@example.com",
  "issue_type": "Feature",
  "date_range": {
    "start": "2025-01-06",
    "end": "2025-01-13"
  },
  "changelog": {
    "status_transitions": [
      {
        "from": "To Do",
        "to": "In Progress",
        "date": "2025-01-07T09:00:00Z",
        "author": "jdoe@example.com"
      }
    ],
    "field_changes": [...],
    "last_status_summary_update": "2025-01-05T10:30:00Z"
  },
  "comments": [
    {
      "author": "jdoe@example.com",
      "author_display_name": "John Doe",
      "date": "2025-01-08T14:00:00Z",
      "body": "Started work on PR #123",
      "is_bot": false
    }
  ],
  "descendants": [
    {
      "key": "OCPSTRAT-1235",
      "summary": "Sub-task 1",
      "status": "Done",
      "issue_type": "Story",
      "updated": "2025-01-10T15:30:00Z",
      "updated_in_range": true
    }
  ],
  "issuelinks": [...],
  "external_links": {
    "github_prs": [],
    "gitlab_mrs": []
  }
}
```

**Processing steps**:

1. **Filter comments**:
   - Exclude bot/automation comments (check author for known bot patterns)
   - Known bot patterns: "Automation for Jira", "GitHub Actions", account IDs starting with "5..."
   - Keep only human comments for analysis

2. **Extract status transitions**:
   - Parse changelog for `field == "status"` entries
   - Store from/to status, date, and author

3. **Find last Status Summary update**:
   - Parse changelog for `field == "Status Summary"` entries
   - Store the most recent update timestamp
   - Used for "recently updated" warnings in update-weekly-status

4. **Mark descendants updated in range**:
   - Compare each descendant's `updated` timestamp to date range
   - Set `updated_in_range: true` if within [start_date, end_date]

5. **Preserve issuelinks**:
   - Store for external-links module to process

## Step 6: Cache to Temp File (Optional)

If `config.cache_to_file` is true (used by status-rollup for refinement):

**File location**: `/tmp/jira-status-{root-issue-key}-{timestamp}.md`

**File format**:
```markdown
# Status Analysis Cache

**Root Issue**: {ROOT-ISSUE-KEY}
**Generated**: {timestamp}
**Date Range**: {start-date} to {end-date}

## Issue Hierarchy

Total issues: {count}
- Features: {n}
- Epics: {n}
- Stories: {n}
- Tasks: {n}
- Subtasks: {n}

## Raw Data

### {ISSUE-KEY}: {Summary}

**Status**: {status}
**Assignee**: {assignee}
**Type**: {issue_type}
**Updated**: {updated}

#### Changelog

| Date | Field | From | To | Author |
|------|-------|------|-----|--------|
| {date} | {field} | {from} | {to} | {author} |

#### Comments

**{date}** - {author}:
> {comment body}

---

[Repeat for each issue]

## Analysis Results

[Filled in by activity-analysis module]
```

**Purpose**:
- Allows refinement without re-fetching from Jira
- User can inspect raw data if needed
- Provides audit trail of what was analyzed

## Field Reference

### Required Fields for Analysis

| Field | Purpose |
|-------|---------|
| `summary` | Issue title for display |
| `status` | Current status and transition tracking |
| `assignee` | For user filtering and attribution |
| `issuetype` | Grouping and metrics |
| `created` | Default start date if not specified |
| `updated` | Recent activity detection |
| `issuelinks` | External link extraction |
| `comment` | Activity context and blockers |

### Custom Fields

| Field | ID (example) | Purpose |
|-------|--------------|---------|
| Status Summary | `customfield_12320841` | Field to update in update-weekly-status |

**Finding custom field IDs**:
```
mcp__atlassian-mcp__jira_search_fields(
  keyword = "status summary"
)
```

## Error Handling

| Error | Handling |
|-------|----------|
| Issue not found | Log warning: "Issue {key} not found, skipping", continue with others |
| Permission denied (403) | Display: "Permission denied for {key}. Check MCP server credentials." |
| Rate limiting (429) | Display: "Rate limited. Wait {retry-after} seconds.", pause and retry |
| Network timeout | Retry once, then log warning and continue |
| Invalid JQL | Display JQL and error message, help user fix syntax |
| No descendants | Not an error - continue with root issue only |

## Performance Tips

1. **Batch where possible**: Use `jira_batch_get_changelogs` instead of per-issue fetches
2. **Limit fields**: Only request fields you need
3. **Limit comments**: Use `comment_limit=20` unless you need full history
4. **Parallelize**: Issue detail fetches can run concurrently
5. **Filter in JQL**: Apply date filters in the query, not post-fetch
6. **Cache results**: Use temp file to avoid re-fetching during refinement
