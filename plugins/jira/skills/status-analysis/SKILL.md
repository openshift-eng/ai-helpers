---
name: Jira Status Analysis Engine
description: Shared engine for analyzing Jira issue activity and generating status summaries
---

# Jira Status Analysis Engine

This skill provides the core analysis logic shared by status-related commands (`/jira:status-rollup` and `/jira:update-weekly-status`). It handles data collection, activity analysis, and status generation in a unified way.

**IMPORTANT FOR AI**: This is a **procedural skill** - when invoked by a command, you should execute the implementation steps defined in this document and its sub-modules. The calling command determines the configuration parameters.

## When to Use This Skill

This skill is invoked automatically by:

- `/jira:status-rollup` - Single root issue, outputs as Jira comment
- `/jira:update-weekly-status` - Multiple root issues (batch), outputs to Status Summary field

Do NOT invoke this skill directly. Use the commands above.

## Architecture Overview

### For update-weekly-status (Pre-Gathered Data)

```
┌─────────────────────────────────────────────────────────────────┐
│                  /jira:update-weekly-status                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Python Data Gatherer                         │
│                  (gather_status_data.py)                        │
│                                                                 │
│  • Async HTTP requests (aiohttp)                                │
│  • Jira: issues, descendants, changelogs                        │
│  • GitHub: PRs via GraphQL (batched)                            │
│  • Output: .work/weekly-status/{date}/issues/*.json             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Status Analysis Engine                       │
│  ┌───────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Read JSON     │  │ Activity         │  │ PR Activity      │  │
│  │ (pre-gathered)│─▶│ Analysis         │─▶│ (pre-gathered)   │  │
│  └───────────────┘  └──────────────────┘  └──────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│                    ┌──────────────────┐                         │
│                    │ Formatting       │                         │
│                    │ (formatting.md)  │                         │
│                    └──────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                Status Summary field (R/Y/G template)            │
└─────────────────────────────────────────────────────────────────┘
```

### For status-rollup (Direct MCP Calls)

```
┌─────────────────────────────────────────────────────────────────┐
│                      /jira:status-rollup                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Status Analysis Engine                       │
│                         (SKILL.md)                              │
│  ┌───────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Data          │  │ Activity         │  │ External         │  │
│  │ Collection    │─▶│ Analysis         │─▶│ Links            │  │
│  │ (data-        │  │ (activity-       │  │ (external-       │  │
│  │ collection.md)│  │ analysis.md)     │  │ links.md)        │  │
│  └───────────────┘  └──────────────────┘  └──────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│                    ┌──────────────────┐                         │
│                    │ Formatting       │                         │
│                    │ (formatting.md)  │                         │
│                    └──────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Jira comment (wiki markup)                    │
└─────────────────────────────────────────────────────────────────┘
```

## Sub-Modules

This skill is composed of four sub-modules. Read each when executing the analysis:

| Module | File | Purpose |
|--------|------|---------|
| Data Collection | `data-collection.md` | Reading pre-gathered JSON or fetching via MCP |
| Activity Analysis | `activity-analysis.md` | Detecting blockers, progress, risks, completion |
| External Links | `external-links.md` | GitHub PR and GitLab MR integration |
| Formatting | `formatting.md` | Output templates for different modes |
| Data Gatherer | `scripts/gather_status_data.py` | Async batch data collection (update-weekly-status) |

## Configuration Parameters

Both commands share the same engine with different configuration:

| Parameter | status-rollup | update-weekly-status |
|-----------|---------------|----------------------|
| `data_source` | MCP API calls | Pre-gathered JSON files |
| `root_issues` | Single issue key | Multiple (from manifest.json) |
| `date_range.start` | User-specified or issue creation | `today - 7 days` |
| `date_range.end` | User-specified or today | `today` |
| `output_format` | `wiki_comment` | `ryg_field` |
| `output_target` | Comment on root issue | Status Summary field |
| `external_links` | Via `gh` CLI | Pre-gathered in JSON |
| `user_review` | Yes (before posting comment) | Yes (approve/modify/skip per issue) |
| `caching` | Temp file for refinement | JSON files in `.work/` |

## Hierarchy Traversal

Both commands use the same traversal mechanism via `childIssuesOf()` JQL:

```
Root Issue (FEATURE-123)
    │
    ├── Epic 1 (EPIC-456)
    │   ├── Story 1.1
    │   │   └── Subtask 1.1.1
    │   └── Story 1.2
    │
    └── Epic 2 (EPIC-789)
        └── Story 2.1

JQL: issue in childIssuesOf(FEATURE-123)
Returns: ALL descendants at any depth (EPIC-456, Story 1.1, Subtask 1.1.1, Story 1.2, EPIC-789, Story 2.1)
```

**Key benefit**: `childIssuesOf()` is already recursive - a single JQL query returns the entire hierarchy regardless of depth. No manual recursion needed.

The difference between commands is not in traversal but in:

- **Data source**: update-weekly-status uses pre-gathered JSON; status-rollup uses MCP calls
- **Scope**: status-rollup analyzes one root; update-weekly-status analyzes many roots
- **Filtering**: update-weekly-status data is pre-filtered to date range by the Python script
- **Aggregation**: status-rollup combines all descendants into one summary; update-weekly-status generates per-root summaries

## Shared Data Structures

### AnalysisConfig

Configuration passed from calling command:

```json
{
  "root_issues": ["OCPSTRAT-1234"],
  "date_range": {
    "start": "2025-01-06",
    "end": "2025-01-13"
  },
  "output_format": "wiki_comment",
  "output_target": "comment",
  "external_links_enabled": true,
  "cache_to_file": true,
  "filters": {
    "component": null,
    "label": null,
    "assignees": [],
    "excluded_assignees": []
  }
}
```

### IssueActivityData

The core data structure for each analyzed issue:

```json
{
  "issue_key": "OCPSTRAT-1234",
  "summary": "Implement feature X",
  "status": "In Progress",
  "assignee": "user@example.com",
  "issue_type": "Story",
  "date_range": {
    "start": "2025-01-06",
    "end": "2025-01-13"
  },
  "changelog": {
    "status_transitions": [
      {"from": "To Do", "to": "In Progress", "date": "2025-01-07", "author": "user@example.com"}
    ],
    "field_changes": [],
    "last_status_summary_update": "2025-01-05T10:30:00Z"
  },
  "comments": [
    {"author": "user@example.com", "date": "2025-01-08", "body": "Started work on PR #123", "is_bot": false}
  ],
  "descendants": [
    {"key": "OCPSTRAT-1235", "summary": "Sub-task 1", "status": "Done", "updated_in_range": true}
  ],
  "external_links": {
    "github_prs": [
      {"url": "https://github.com/org/repo/pull/123", "state": "MERGED", "title": "Add feature X"}
    ],
    "gitlab_mrs": []
  },
  "analysis": {
    "health": "green",
    "blockers": [],
    "risks": [],
    "achievements": ["PR #123 merged", "Sub-task 1 completed"],
    "in_progress": ["Sub-task 2 under review"],
    "metrics": {
      "total_descendants": 3,
      "completed": 1,
      "in_progress": 1,
      "blocked": 0,
      "completion_percentage": 33
    }
  }
}
```

## Execution Flow

When a command invokes this skill, follow this sequence:

### Step 1: Initialize Configuration

The calling command provides an AnalysisConfig. Parse and validate:

```
REQUIRED parameters:
  - root_issues: Array of issue keys to analyze
  - date_range: {start, end} in YYYY-MM-DD format
  - output_format: "wiki_comment" or "ryg_field"

OPTIONAL parameters:
  - external_links_enabled: boolean (default: true)
  - cache_to_file: boolean (default: false)
  - filters: component, label, assignee filters
```

### Step 2: Data Collection

Follow `data-collection.md` which supports two modes:

**Option A: Pre-Gathered Data (update-weekly-status)**

Data has already been collected by the Python script (`gather_status_data.py`):

1. Read manifest from `.work/weekly-status/{date}/manifest.json`
2. For each issue, read `.work/weekly-status/{date}/issues/{ISSUE-KEY}.json`
3. Data includes: issue metadata, descendants, changelogs, comments, PRs (all pre-filtered to date range)

**Option B: Direct MCP Calls (status-rollup)**

1. **For each root issue**:
   - Fetch issue details with `fields=summary,status,assignee,issuelinks,comment,{custom-fields}`
   - Fetch changelog with `expand=changelog`

2. **Discover all descendants**:
   - Use `issue in childIssuesOf({root-issue})` to get full hierarchy
   - Optionally filter by date range: `AND updated >= {start-date}`
   - Use `limit=100` (increase if needed for large hierarchies)

3. **For each descendant issue**:
   - Fetch issue details and changelog
   - Track which descendants were updated within date range

4. **Build IssueActivityData** for root and all descendants

5. **Optionally cache to temp file** (for refinement workflows)

### Step 3: Activity Analysis

Follow `activity-analysis.md` to:

1. **Filter to date range**:
   - Changelog entries within [start_date, end_date]
   - Comments created within [start_date, end_date]

2. **Identify key events**:
   - Status transitions (especially: started, completed, blocked)
   - Assignee changes
   - Priority/severity changes

3. **Analyze comment content**:
   - Blockers: "blocked", "waiting on", "stuck", "dependency"
   - Risks: "risk", "concern", "problem", "at risk"
   - Completion: "completed", "done", "merged", "delivered"
   - Progress: "started", "working on", "implementing"

4. **Determine health status**:
   - **Green**: Good progress, PRs merged/in review, no blockers
   - **Yellow**: Minor concerns, slow progress, manageable blockers
   - **Red**: Significant blockers, no progress, major risks

5. **Calculate metrics**:
   - Total/completed/in-progress/blocked descendants
   - Completion percentage

### Step 4: External Links (if enabled)

Follow `external-links.md` to:

1. **Extract GitHub PR URLs**:
   - From `issuelinks` field (remote links)
   - From description and comments (text parsing)
   - From descendants' links

2. **Fetch PR metadata** (if `gh` CLI available):

   ```bash
   gh pr view {PR-NUMBER} --repo {REPO} --json state,updatedAt,mergedAt,title
   ```

3. **Track PR activity**:
   - PRs merged within date range
   - PRs updated within date range
   - Open PRs awaiting review

4. **Handle GitLab MRs**:
   - Extract URLs, note for manual checking
   - Use `glab` if available

### Step 5: Format Output

Follow `formatting.md` to generate output based on `output_format`:

**For `wiki_comment` (status-rollup)**:

```
h2. Status Rollup From: {start-date} to {end-date}

*Overall Status:* [Health assessment]

*This Week:*
* Completed:
*# [ISSUE-KEY] - [Achievement]
* In Progress:
*# [ISSUE-KEY] - [Current state]
* Blocked:
*# [ISSUE-KEY] - [Blocker reason]

*Next Week:*
* [Planned items]

*Metrics:* X/Y issues complete (Z%)
```

**For `ryg_field` (update-weekly-status)**:

```
* Color Status: {Red, Yellow, Green}
 * Status summary:
     ** Thing 1 that happened since last week
     ** Thing 2 that happened since last week
 * Risks:
     ** Risk 1 (or "None at this time")
```

### Step 6: Return to Calling Command

Return structured result:

```json
{
  "issues_analyzed": [...IssueActivityData],
  "formatted_outputs": {
    "OCPSTRAT-1234": "formatted status text..."
  },
  "summary": {
    "total": 5,
    "by_health": {"green": 3, "yellow": 1, "red": 1}
  },
  "cache_file": "/tmp/jira-status-{issue-id}-{timestamp}.md"
}
```

The calling command then handles:

- User review and approval workflow
- Posting to Jira (comment or field update)
- Summary report generation

## Error Handling

All modules should handle these error cases:

| Error | Handling |
|-------|----------|
| Issue not found | Log warning, skip issue, continue with others |
| Permission denied | Display clear error, suggest checking MCP config |
| No activity in date range | Generate summary based on current state |
| GitHub CLI not available | Skip PR analysis, note in output |
| Rate limiting | Display error with retry guidance |
| Large hierarchies (100+ issues) | Show progress indicators |
| Missing JSON file | Log warning: "Data file for {key} not found, skipping" |

## Performance Considerations

- **Use pre-gathered data**: For batch operations (update-weekly-status), always use the Python data gatherer
- **Minimize API calls**: Only fetch fields you need (for status-rollup)
- **Use batch endpoints**: `jira_batch_get_changelogs` for multiple issues
- **Single JQL for hierarchy**: `childIssuesOf()` returns all descendants in one call
- **Cache data**: Store in temp file for refinement iterations
- **Parallelize**: Python script handles parallel fetching; MCP calls can run concurrently
- **Limit comments**: Use `comment_limit=20` to reduce response size
- **Filter early**: Data gatherer pre-filters to date range; apply in JQL for MCP calls

## Prerequisites

### For update-weekly-status

- **Python 3.8+** with `aiohttp` package
- **Environment variables**:
  - `JIRA_TOKEN` or `JIRA_PERSONAL_TOKEN`: Jira API bearer token
  - `GITHUB_TOKEN` or authenticated `gh` CLI
- **Jira MCP server** configured (for argument resolution)

Check setup:

```bash
python3 -c "import aiohttp; print('aiohttp OK')"
echo $JIRA_TOKEN
gh auth token
```

### For status-rollup

- **Jira MCP server** configured and accessible
- **GitHub CLI** (`gh`) installed and authenticated (optional but recommended)
- **GitLab CLI** (`glab`) installed and authenticated (optional)

Check for tools:

```bash
which gh && gh auth status
which glab && glab auth status  # optional
```
