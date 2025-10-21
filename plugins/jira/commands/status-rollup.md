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
- Recursively traverses entire issue hierarchies (any depth)
- Analyzes status transitions, assignee changes, and priority shifts
- Extracts blockers, risks, and completion insights from comments
- Generates properly formatted Jira wiki markup with nested bullets
- Caches all data in a temp file for fast iterative refinement
- Allows review and modification before posting to Jira

[Extended thinking: This command takes any JIRA issue ID (Feature, Epic, Story, etc.) and optional date range, recursively collects all descendant issues, analyzes their changes and comments within the date range, and generates a concise status summary rolled up to the parent issue level. The summary is presented to the user for review and refinement before being posted as a comment.]

## Implementation

The command executes the following workflow:

1. **Parse Arguments and Validate**
   - Extract issue ID from $1
   - Parse --start-date and --end-date if provided
   - Validate date format (YYYY-MM-DD)
   - Default to issue creation date if no start-date provided
   - Default to today if no end-date provided

2. **Issue Validation**
   - Use `mcp__atlassian__jira_get_issue` to fetch the issue
   - Verify the issue exists and is accessible
   - Extract issue key, summary, type, and basic info
   - Works with any issue type (Feature, Epic, Story, Task, etc.)

3. **Data Collection - Build Issue Hierarchy**
   - Find direct children using JQL: `parent = {issue-id}`
   - Recursively find all descendant issues (any depth)
   - Fetch detailed issue data for each issue (status, summary, assignee, etc.)
   - Use `mcp__atlassian__jira_batch_get_changelogs` for all issue keys
   - Filter changelog entries to date range (status transitions, assignee changes, etc.)
   - Fetch comments using `expand=renderedFields`, filter by date range
   - Save all data to temp file: `/tmp/jira-rollup-{issue-id}-{timestamp}.md`

4. **Data Analysis - Derive Status**
   - Calculate completion metrics (total, done, in-progress, blocked, percentage)
   - Identify issues completed/started/blocked within date range
   - Extract significant status transitions and key changes
   - Analyze comments for keywords:
     - **Blockers**: "blocked", "waiting on", "stuck", "dependency"
     - **Risks**: "risk", "concern", "problem", "at risk"
     - **Completion**: "completed", "done", "merged", "delivered"
     - **Progress**: "started", "working on", "implementing"
     - **Help needed**: "need", "require", "help", "support"
   - Extract entities: team mentions, dependencies, PR references, deadlines
   - Prioritize comments (high/medium/low based on keywords)
   - Cross-reference comments with status transitions
   - Assess overall health (on track, at risk, blocked, complete)
   - Append analysis results to temp file

5. **Generate Status Summary**
   - Read from temp file (NO re-fetching from Jira)
   - Create formatted summary in Jira wiki markup:
     ```
     h2. Status Rollup From: {start-date} to {end-date}

     *Overall Status:* [Clear statement about health and progress]

     *This Week:*
     * Completed:
     *# [ISSUE-ID] - [Specific achievement from comments]
     *# [ISSUE-ID] - [Specific achievement from comments]
     * In Progress:
     *# [ISSUE-ID] - [Current state and specific details]
     * Blocked:
     *# [ISSUE-ID] - [Specific reason for blocker]

     *Next Week:*
     * [Planned item based on analysis]

     *Metrics:* X/Y issues complete (Z%)
     ```
   - Use specific insights from comments (NOT vague phrases like "ongoing work")
   - Include PR references, ticket numbers, specific tasks mentioned
   - Add direct quotes when they provide critical context
   - Use `*#` syntax for nested bullets (Jira wiki markup)

6. **Present to User for Review**
   - Display temp file location for verification
   - Show generated summary
   - Ask if user wants changes

7. **Iterative Refinement**
   - If user requests changes, read from temp file (don't re-fetch)
   - Support refinement strategies:
     - Focus more on blockers/risks/completion
     - Add/remove technical details or quotes
     - Change grouping (by epic, type, status, assignee)
     - Adjust level of detail (high-level vs. detailed)
   - Regenerate only affected sections
   - Repeat until user satisfied

8. **Post Comment to Issue**
   - Use `mcp__atlassian__jira_add_comment` to post to parent issue
   - Append footer: "🤖 Generated with [Claude Code](https://claude.com/claude-code) via `/jira:status-rollup {issue-id} --start-date {date} --end-date {date}`"
   - Confirm with user and provide issue URL

9. **Temp File Cleanup**
   - Ask user if they want to keep `/tmp/jira-rollup-{issue-id}-{timestamp}.md`
   - Delete if user says no, otherwise keep for reference

**Error Handling:**
- Invalid issue ID: Display error with verification instructions
- No child issues: Offer to generate summary for single issue
- No activity in date range: Generate summary based on current state
- Invalid date format: Display error with correct format example
- Large hierarchies (100+ issues): Show progress indicators

**Performance Considerations:**
- Use batch API endpoints where available
- Implement appropriate delays to respect rate limits
- Cache all data in temp file for instant refinement

## Return Value
- **Posted to Jira**: Formatted status comment on the parent issue
- **Temp file**: `/tmp/jira-rollup-{issue-id}-{timestamp}.md` containing:
  - Parent issue details
  - Complete issue hierarchy with counts by type
  - Raw changelog data for all issues
  - All comments with metadata (author, date, issue key)
  - Comment analysis (keywords, priorities, cross-references)
  - Metrics summary

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
h2. Weekly Status: 2025-01-06 to 2025-01-13

*Overall Status:* Feature is on track. Core authentication work completed this week with 2 PRs merged. UI integration starting with design approved.

*This Week:*
* Completed:
*# AUTH-101 - OAuth2 implementation (PR #456 merged, all review feedback addressed)
*# AUTH-102 - OAuth2 token validation (unit tests added, edge cases handled)
* In Progress:
*# UI-201 - Login UI components (design review completed, implementing responsive layout for mobile)
*# AUTH-103 - Session handling (refactoring cookie storage mechanism, PR in draft)
* Blocked:
*# AUTH-104 - Azure AD integration (blocked on subscription approval, escalated to infrastructure team). Per Jane Doe: "Need Azure subscription approved before proceeding - submitted ticket #12345"

*Next Week:*
* Complete session handling refactor (AUTH-103) and submit for review
* Finish login UI responsive implementation (UI-201) once design assets are finalized
* Begin end-to-end testing (AUTH-107) if session handling is merged

*Metrics:* 8/15 issues complete (53%)

🤖 Generated with [Claude Code](https://claude.com/claude-code) via `/jira:status-rollup FEATURE-123 --start-date 2025-01-06 --end-date 2025-01-13`
```

## Arguments
- `issue-id` (required): The JIRA issue ID to analyze (e.g., FEATURE-123, EPIC-456, STORY-789, CNTRLPLANE-1234)
- `--start-date` (optional): Start date in YYYY-MM-DD format. Defaults to issue creation date if not provided
- `--end-date` (optional): End date in YYYY-MM-DD format. Defaults to today if not provided
