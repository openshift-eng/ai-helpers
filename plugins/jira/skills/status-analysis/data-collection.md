---
name: Data Collection
description: Fetching issues, changelogs, and comments from Jira for status analysis
---

# Data Collection

This module handles data acquisition for the Status Analysis Engine. Data can come from two sources:
1. **Pre-gathered JSON files** (preferred for batch operations like `update-weekly-status`)
2. **Direct MCP API calls** (for single-issue operations like `status-rollup`)

## Overview

### Option A: Pre-Gathered Data (update-weekly-status)

When using the Python data gatherer script, all data is already collected:

```
1. Python script has already collected all data
         │
         ▼
2. Read manifest.json to get issue list
         │
         ▼
3. For each issue, read {ISSUE-KEY}.json
         │
         ▼
4. Data is already in IssueActivityData format
         │
         ▼
5. Proceed to Activity Analysis
```

### Option B: Direct MCP Calls (status-rollup)

For single-issue analysis, fetch data directly from Jira:

```
1. Fetch root issue(s) via MCP
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

---

## Option A: Reading Pre-Gathered Data

For `update-weekly-status`, the Python data gatherer script has already collected all data.

### Step 1: Read Manifest

Read the manifest file to get the list of issues:

**Location**: `.work/weekly-status/{YYYY-MM-DD}/manifest.json`

```json
{
  "generated_at": "2026-02-05T10:04:26.579793",
  "config": {
    "project": "OCPSTRAT",
    "component": "Hosted Control Planes",
    "label": "control-plane-work",
    "date_range": {
      "start": "2026-01-29",
      "end": "2026-02-05"
    },
    "status_summary_field": "customfield_12320841"
  },
  "issues": [
    {
      "key": "OCPSTRAT-1234",
      "summary": "Feature title",
      "assignee": "user@example.com",
      "status": "In Progress",
      "descendants_count": 15,
      "prs_count": 3
    }
  ],
  "stats": {
    "total_issues": 23,
    "total_descendants": 299,
    "total_prs": 39,
    "jira_requests": 56,
    "fetch_duration_seconds": 80.4
  }
}
```

### Step 2: Read Per-Issue Data

For each issue in `manifest.issues`, read its detailed data:

**Location**: `.work/weekly-status/{YYYY-MM-DD}/issues/{ISSUE-KEY}.json`

```json
{
  "issue": {
    "key": "OCPSTRAT-1234",
    "summary": "Feature title",
    "status": "In Progress",
    "assignee": {
      "email": "user@example.com",
      "name": "User Name"
    },
    "current_status_summary": "* Color Status: Green\n * Status summary:\n     ** Work in progress\n * Risks:\n     ** None",
    "last_status_summary_update": "2026-01-28T10:30:00Z"
  },
  "descendants": {
    "total": 15,
    "by_status": {
      "Closed": 5,
      "In Progress": 8,
      "To Do": 2
    },
    "updated_in_range": [
      {
        "key": "CNTRLPLANE-1234",
        "summary": "Sub-task completed",
        "status": "Closed",
        "updated": "2026-02-04T13:37:19.000+0000"
      }
    ],
    "completion_pct": 33.3
  },
  "changelog_in_range": [
    {
      "date": "2026-02-01T09:00:00Z",
      "author": "user@example.com",
      "items": [
        {
          "field": "status",
          "from": "To Do",
          "to": "In Progress"
        }
      ]
    }
  ],
  "comments_in_range": [
    {
      "author": "user@example.com",
      "author_name": "User Name",
      "date": "2026-02-03T14:00:00Z",
      "body": "PR submitted for review",
      "is_bot": false
    }
  ],
  "prs": [
    {
      "url": "https://github.com/org/repo/pull/123",
      "number": 123,
      "title": "Add feature X",
      "state": "MERGED",
      "is_draft": false,
      "review_decision": "APPROVED",
      "dates": {
        "created_at": "2026-01-25T10:00:00Z",
        "updated_at": "2026-02-01T15:30:00Z",
        "merged_at": "2026-02-01T15:30:00Z"
      },
      "files_changed": {
        "total": 5,
        "additions": 250,
        "deletions": 30,
        "files": [
          {"path": "pkg/feature/handler.go", "additions": 150, "deletions": 10},
          {"path": "pkg/feature/handler_test.go", "additions": 100, "deletions": 20}
        ]
      },
      "commits_in_range": [
        {
          "sha": "abc1234",
          "message": "Add feature handler",
          "date": "2026-01-30T09:00:00Z",
          "author": "user@example.com"
        }
      ],
      "reviews_in_range": [
        {
          "author": "reviewer",
          "state": "APPROVED",
          "body": "LGTM",
          "submitted_at": "2026-01-31T14:00:00Z"
        }
      ],
      "review_comments_in_range": [],
      "activity_summary": {
        "commits_in_range": 3,
        "reviews_in_range": 2,
        "review_comments_in_range": 0
      },
      "found_in_descendants": ["CNTRLPLANE-1234"]
    }
  ]
}
```

### Key Fields from Pre-Gathered Data

| Field Path | Purpose |
|------------|---------|
| `issue.key` | Issue identifier |
| `issue.summary` | Issue title for display |
| `issue.status` | Current status |
| `issue.assignee` | For attribution and display |
| `issue.current_status_summary` | Existing status text (may need update) |
| `issue.last_status_summary_update` | For "recently updated" warnings |
| `descendants.total` | Total child issue count |
| `descendants.by_status` | Status breakdown for metrics |
| `descendants.updated_in_range` | Issues with recent activity |
| `descendants.completion_pct` | Completion percentage |
| `changelog_in_range` | Field changes in date range |
| `comments_in_range` | Human comments in date range |
| `comments_in_range[].is_bot` | Filter out bot comments |
| `prs` | GitHub PRs linked to this issue |
| `prs[].state` | OPEN, CLOSED, MERGED |
| `prs[].activity_summary` | Quick check for in-range activity |
| `prs[].commits_in_range` | Commits within date range |
| `prs[].reviews_in_range` | Reviews within date range |

### Mapping to IssueActivityData

The pre-gathered JSON maps directly to the IssueActivityData structure:

```
Pre-gathered JSON          →  IssueActivityData
─────────────────────────────────────────────────
issue.key                  →  issue_key
issue.summary              →  summary
issue.status               →  status
issue.assignee.email       →  assignee
issue.last_status_summary  →  changelog.last_status_summary_update
descendants.by_status      →  analysis.metrics
descendants.completion_pct →  analysis.metrics.completion_percentage
changelog_in_range         →  changelog.status_transitions
comments_in_range          →  comments (already filtered)
prs                        →  external_links.github_prs (enhanced)
```

---

## Option B: Direct MCP API Calls

For `status-rollup` or when pre-gathered data is not available.

### Step 1: Fetch Root Issue(s)

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

### Step 2: Discover Descendants

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

### Step 3: Fetch Issue Details

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

### Step 4: Fetch Changelogs (Batch)

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

### Step 5: Build IssueActivityData Structures

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

### Step 6: Cache to Temp File (Optional)

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

---

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
| Missing JSON file | Log warning: "Data file for {key} not found, skipping" |

## Performance Tips

1. **Use pre-gathered data**: For batch operations, always prefer the Python data gatherer
2. **Batch where possible**: Use `jira_batch_get_changelogs` instead of per-issue fetches
3. **Limit fields**: Only request fields you need
4. **Limit comments**: Use `comment_limit=20` unless you need full history
5. **Parallelize**: Issue detail fetches can run concurrently
6. **Filter in JQL**: Apply date filters in the query, not post-fetch
7. **Cache results**: Use temp file to avoid re-fetching during refinement
