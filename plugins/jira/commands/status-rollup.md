---
description: Generate a status rollup comment for any JIRA issue based on all child issues and a given date range
argument-hint: issue-id [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
---

## Name
jira:status-rollup

## Synopsis
```
/jira:status-rollup issue-id [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
```

## Description
The `jira:status-rollup` command generates a comprehensive status rollup for any JIRA issue (Feature, Epic, Story, etc.) by recursively analyzing all child issues and their activity within a specified date range. The command intelligently extracts insights from changelogs and comments to create a concise, well-formatted status summary that can be reviewed and refined before being posted to Jira.

This command is particularly useful for:
- Weekly status updates on Features or Epics
- Sprint retrospectives and planning
- Executive summaries of complex work hierarchies
- Identifying blockers and risks across multiple issues

Key capabilities:
- Recursively traverses entire issue hierarchies (any depth) via `childIssuesOf()` JQL
- Analyzes status transitions, assignee changes, and priority shifts
- Extracts blockers, risks, and completion insights from comments
- Generates properly formatted Jira wiki markup with nested bullets
- Caches all data in a temp file for fast iterative refinement
- Allows review and modification before posting to Jira

This command uses the **Status Analysis Engine** skill for core analysis logic. See `plugins/jira/skills/status-analysis/SKILL.md` for detailed implementation.

**IMPORTANT - Skill Loading Requirement:**
Before processing any issues, you MUST invoke `Skill(jira:status-analysis)` to load the Status Analysis Engine skill. This ensures proper use of `childIssuesOf()` for hierarchy traversal and consistent analysis methodology. Do NOT rely on conversation summaries or memory - always load the skill explicitly at the start of execution.

## Implementation

The command executes the following workflow:

### 0. Load Required Skills (MANDATORY)

**This step is non-negotiable and must be performed first:**

```
Skill(jira:status-analysis)
```

This loads the Status Analysis Engine skill which provides:
- Proper `childIssuesOf()` usage for hierarchy traversal
- Activity analysis methodology
- External links processing (GitHub PRs, GitLab MRs)
- Wiki comment formatting rules

**Do NOT skip this step even in continued sessions.** Session summaries do not preserve skill context.

### 1. Parse Arguments and Validate

1. Extract issue ID from $1
2. Parse `--start-date` and `--end-date` if provided
3. Validate date format (YYYY-MM-DD)
4. Default to issue creation date if no start-date provided
5. Default to today if no end-date provided

### 2. Initialize Analysis Configuration

Build the configuration for the Status Analysis Engine:

```json
{
  "root_issues": ["{issue-id}"],
  "date_range": {
    "start": "{start-date}",
    "end": "{end-date}"
  },
  "output_format": "wiki_comment",
  "output_target": "comment",
  "external_links_enabled": false,
  "cache_to_file": true
}
```

### 3. Execute Status Analysis Engine

Follow the skill documentation in `plugins/jira/skills/status-analysis/`:

1. **Data Collection** (`data-collection.md`):
   - Fetch the root issue with `mcp__atlassian-mcp__jira_get_issue`
   - Discover all descendants via JQL: `issue in childIssuesOf({issue-id})`
   - Fetch details and changelogs for all issues
   - Cache data to temp file: `/tmp/jira-status-{issue-id}-{timestamp}.md`

2. **Activity Analysis** (`activity-analysis.md`):
   - Filter changelog and comments to date range
   - Identify status transitions, blockers, risks, achievements
   - Calculate completion metrics
   - Determine overall health (green/yellow/red)

3. **Formatting** (`formatting.md`):
   - Generate Jira wiki markup using `wiki_comment` format
   - Include sections: Overall Status, This Period, Next Steps, Risks, Metrics

### 4. Present to User for Review

Display:
- Temp file location for verification
- Generated summary in formatted output
- Ask: "Would you like to post this to Jira, modify it, or cancel?"

Options:
- `post` or `p`: Proceed to post comment
- `modify` or `m`: Request changes, regenerate from cached data
- `cancel` or `c`: Abort without posting

### 5. Iterative Refinement

If user requests changes, read from temp file (NO re-fetching from Jira):

Support refinement strategies:
- Focus more on blockers/risks/completion
- Add/remove technical details or quotes
- Change grouping (by epic, type, status, assignee)
- Adjust level of detail (high-level vs. detailed)

Regenerate only affected sections and present again.

### 6. Post Comment to Issue

Once approved:

1. Use `mcp__atlassian-mcp__jira_add_comment` to post to the root issue
2. Comment includes footer: `_Generated with [Claude Code|https://claude.com/claude-code] via {{/jira:status-rollup {issue-id} --start-date {date} --end-date {date}}}_`
3. Confirm success and provide issue URL

### 7. Temp File Cleanup

Ask user if they want to keep `/tmp/jira-status-{issue-id}-{timestamp}.md`:
- Keep for reference or future refinement
- Delete if no longer needed

## Return Value
- **Posted to Jira**: Formatted status comment on the root issue
- **Temp file**: `/tmp/jira-status-{issue-id}-{timestamp}.md` containing:
  - Root issue details
  - Complete issue hierarchy with counts by type
  - Raw changelog data for all issues
  - All comments with metadata (author, date, issue key)
  - Analysis results (blockers, risks, achievements, metrics)

## Examples

1. **Generate status for a Feature for a specific week**:
   ```
   /jira:status-rollup FEATURE-123 --start-date 2025-01-06 --end-date 2025-01-13
   ```
   Output: Weekly status comment posted to FEATURE-123

2. **Generate status for an Epic**:
   ```
   /jira:status-rollup EPIC-456 --start-date 2025-01-06 --end-date 2025-01-13
   ```
   Output: Epic status summary with all child stories analyzed

3. **Generate status for a Story with subtasks**:
   ```
   /jira:status-rollup STORY-789
   ```
   Output: Status from story creation date to today

4. **Generate status from a start date to now**:
   ```
   /jira:status-rollup CNTRLPLANE-1234 --start-date 2025-01-06
   ```
   Output: Status from Jan 6 to today

**Example Output:**
```
h2. Status Rollup: 2025-01-06 to 2025-01-13

*Overall Status:* (/) Feature is on track. Core authentication work completed this week with 2 PRs merged. UI integration starting with design approved.

h3. This Period

*Completed:*
*# [AUTH-101|https://issues.redhat.com/browse/AUTH-101] - OAuth2 implementation (PR #456 merged, all review feedback addressed)
*# [AUTH-102|https://issues.redhat.com/browse/AUTH-102] - Token validation with comprehensive unit tests

*In Progress:*
*# [UI-201|https://issues.redhat.com/browse/UI-201] - Login UI components (design review completed, implementing responsive layout)
*# [AUTH-103|https://issues.redhat.com/browse/AUTH-103] - Session handling refactor (draft PR submitted)

*Blocked:*
*# [AUTH-104|https://issues.redhat.com/browse/AUTH-104] - Azure AD integration (waiting on subscription approval)
{quote}Need Azure subscription approved before proceeding - submitted ticket #12345{quote}

h3. Next Steps

* Complete session handling refactor (AUTH-103) and submit for review
* Finish login UI responsive implementation (UI-201)
* Begin end-to-end testing (AUTH-107) once session handling is merged

h3. Risks

* *Medium:* API deprecation in upstream dependency may require refactor in Q2

h3. Metrics

* *Total Issues:* 15
* *Completed:* 8 (53%)
* *In Progress:* 4
* *Blocked:* 1
* *Updated This Period:* 6

----

_Generated with [Claude Code|https://claude.com/claude-code] via {{/jira:status-rollup FEATURE-123 --start-date 2025-01-06 --end-date 2025-01-13}}_
```

## Arguments
- `issue-id` (required): The JIRA issue ID to analyze (e.g., FEATURE-123, EPIC-456, STORY-789, CNTRLPLANE-1234)
- `--start-date` (optional): Start date in YYYY-MM-DD format. Defaults to issue creation date if not provided
- `--end-date` (optional): End date in YYYY-MM-DD format. Defaults to today if not provided

## Error Handling

| Error | Handling |
|-------|----------|
| Invalid issue ID | Display error with verification instructions |
| No child issues | Generate summary for single issue (root only) |
| No activity in date range | Generate summary based on current state |
| Invalid date format | Display error with correct format example |
| Large hierarchies (100+ issues) | Show progress indicators |

## Related

- **Shared skill**: `plugins/jira/skills/status-analysis/SKILL.md`
- **Batch updates**: `/jira:update-weekly-status` - Update Status Summary field for multiple issues
