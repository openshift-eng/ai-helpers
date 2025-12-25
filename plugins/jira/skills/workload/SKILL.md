---
name: Workload Analysis with MCP
description: Analyze sprint workload using JIRA MCP server integration
---

# Workload Analysis with MCP

This skill provides guidance for analyzing an associate's workload for a given sprint using the JIRA MCP server.

## Purpose

This skill helps Claude:
- Fetch sprint issues using JIRA MCP tools
- Filter issues by assignee
- Categorize issues by status, priority, and type
- Calculate story points and completion metrics
- Generate comprehensive workload reports in Markdown format

## When to Use This Skill

This skill is automatically invoked by the `/jira:workload` command:

```bash
/jira:workload <assignee> <sprint-name>
```

## MCP Tools Required

This skill requires the `mcp-atlassian` MCP server (https://github.com/sooperset/mcp-atlassian) with these tools enabled:

- **`jira_search`**: Search issues using JQL
- **`jira_get_sprint_issues`**: Get all issues in a sprint (alternative to jira_search)
- **`jira_get_agile_boards`**: List agile boards (for sprint name resolution)
- **`jira_get_sprints_from_board`**: List sprints from a board (for sprint name resolution)
- **`jira_get_user_profile`**: Validate user exists (optional)

## Prerequisites

- JIRA MCP server configured and running locally
- Credentials configured in MCP server settings
- Access to the relevant Jira project and sprints

## Implementation Approach

### Step 1: Fetch Sprint Issues

Use the `jira_search` MCP tool with JQL to get all issues in the sprint:

```
jira_search(
  jql="sprint=\"<sprint-name>\"",
  max_results=200,
  fields=["summary", "status", "priority", "issuetype", "assignee",
          "customfield_12310243", "timetracking", "labels",
          "components", "created", "updated", "resolutiondate", "parent"]
)
```

**Important fields:**
- `assignee`: Required for filtering by user
- `customfield_12310243`: Story points (Red Hat Jira) - may vary by instance
- `status`, `priority`, `issuetype`: For categorization
- `timetracking`: Optional time estimates

### Step 2: Filter by Assignee

From the MCP results, filter issues where the assignee matches:

**Matching logic:**
- Compare against `assignee.name` (username like "jdoe")
- Compare against `assignee.emailAddress` (email like "jane.doe@company.com")
- Compare against `assignee.displayName` (full name like "Jane Doe")
- Use case-insensitive matching
- Support partial matches for display names

**If no matches found:**
- Extract all unique assignees from the sprint
- Display them to the user with usernames and display names
- Suggest the correct assignee name

### Step 3: Categorize Issues

Group the filtered issues by status using these categories:

**Status Categories:**
- **To Do**: Statuses like "open", "new", "backlog", "to do", "todo"
- **In Progress**: Statuses like "in progress", "inprogress", "wip", "review", "in review", "code review"
- **Done**: Statuses like "done", "closed", "resolved", "complete", "completed"
- **Blocked**: Statuses like "blocked", "on hold", "waiting", "hold"
- **Other**: Any custom statuses not matching above

**Priority Mapping:**
- **P0/Blocker**: Critical issues requiring immediate attention
- **P1/Critical**: High-priority issues
- **P2/Major**: Medium-priority issues
- **P3/Minor**: Low-priority issues
- **P4/Trivial**: Lowest priority

### Step 4: Calculate Metrics

For each status category, calculate:

1. **Issue Count**: Number of issues in each status
2. **Story Points**: Sum of story points per status
   - Try these field names in order:
     - `customfield_12310243` (Red Hat Jira)
     - `customfield_10016` (Common Jira)
     - `customfield_10002` (Jira Cloud)
     - Look for any field containing "story" or "point"
   - Default to 0 if not found
3. **Completion Rate**: (Done issues / Total issues) × 100
4. **Points Completion**: (Done points / Total points) × 100

### Step 5: Generate Insights

Analyze the data to provide actionable insights:

**Workload Assessment:**
- **On Track**: ≥50% points complete at sprint midpoint, no blockers
- **At Risk**: <50% points complete, or 1-2 blocked items
- **Behind**: <30% points complete, or 3+ blocked items
- **Blocked**: Multiple blocked items preventing progress

**Key Insights to Include:**
- High-priority items (P0/P1) that are not started
- Issues in progress for more than 5 days (check `updated` field)
- Blocked items requiring attention
- Balance of story points across statuses
- Recommendation on focus areas (e.g., "Complete P0 items before starting new work")

### Step 6: Generate Report

Create a markdown report with this structure:

```markdown
# Sprint Workload: {Display Name} - {Sprint Name}

**Sprint:** {Sprint Name}
**Assignee:** {Display Name} ({username})
**Status as of:** {Current Date}

## Summary
- **Total Issues:** {count}
- **Story Points:** {done} completed / {total} total ({percentage}%)
- **Completion Rate:** {done}/{total} issues ({percentage}%)
- **Status:** {On Track | At Risk | Behind | Blocked}

## Issues by Status

### To Do ({count} issues, {points} points)
{For each issue: [KEY] [Priority] Summary (points) - created {date}}

### In Progress ({count} issues, {points} points)
{For each issue: [KEY] [Priority] Summary (points) - started {date}}

### Blocked ({count} issues, {points} points)
{For each issue: [KEY] [Priority] Summary (points) - blocked since {date}}

### Done ({count} issues, {points} points)
{For each issue: [KEY] [Priority] Summary (points) - completed {date}}

## Priority Breakdown
- **P0 (Critical):** {count} issues ({points} points)
- **P1 (High):** {count} issues ({points} points)
- **P2 (Medium):** {count} issues ({points} points)
- **P3 (Low):** {count} issues ({points} points)

## Insights
{Bulleted list of 3-5 actionable insights}

## Time Tracking (if available)
- **Estimated:** {hours}h
- **Logged:** {hours}h ({percentage}% of estimate)
- **Remaining:** {hours}h
```

### Step 7: Save and Display

1. Create working directory: `~/.work/jira/workload/`
2. Generate filename: `{assignee-sanitized}-{sprint-sanitized}-{timestamp}.md`
3. Write report to file
4. Display full report to user
5. Provide file path for reference

## Error Handling

**MCP Server Not Available:**
```
Error: JIRA MCP server is not available.
Please ensure the mcp-atlassian server is configured and running.

Setup instructions:
1. Install mcp-atlassian: npm install -g @sooperset/mcp-atlassian
2. Configure in ~/.cursor/mcp.json or similar
3. Restart Claude Code
```

**Sprint Not Found:**
```
Error: No issues found for sprint "{sprint-name}"

This could mean:
- The sprint name is incorrect
- The sprint doesn't exist
- You don't have access to this sprint

Would you like me to list available sprints?
```

**Assignee Not Found:**
```
Error: No issues found for assignee "{assignee}" in sprint "{sprint-name}"

Available assignees in this sprint:
- jdoe (Jane Doe, jane.doe@company.com)
- jsmith (John Smith, john.smith@company.com)
...

Please verify the assignee name and try again.
```

**Missing Story Points:**
- Continue with 0 story points
- Note in report if story points are not being tracked
- Still provide valuable insights from issue counts and statuses

## Data Analysis Tips

**Date Calculations:**
- Use `created` field to determine when work was added
- Use `updated` field to see recent activity
- Use `resolutiondate` for completion time
- Calculate "days in progress" by comparing dates

**Story Points Variations:**
Different Jira instances use different custom fields. Try:
1. `customfield_12310243` (Red Hat Jira)
2. `customfield_10016` (Common configuration)
3. `customfield_10002` (Jira Cloud)
4. Search for fields containing "story" or "point" in the field name

**Status Normalization:**
Convert all status names to lowercase and remove special characters for matching:
```
"In Progress" → "inprogress"
"To-Do" → "todo"
"On Hold" → "onhold"
```

## Example MCP Tool Usage

**Searching for sprint issues:**
```
Use jira_search tool:
  jql: sprint="CORENET Sprint 281"
  max_results: 200
  fields: summary,status,priority,assignee,customfield_12310243,timetracking
```

**Listing sprints (if needed):**
```
1. Use jira_get_agile_boards tool to get board IDs
2. Use jira_get_sprints_from_board with board_id
3. Display sprint names to user
```

## Troubleshooting

**Problem:** Can't find the assignee
- **Solution**: Try different formats: username, email, or display name
- **Debug**: List all assignees in the sprint to help user find the right one

**Problem:** Story points are all 0
- **Solution**: Check which custom field your Jira uses for story points
- **Debug**: Inspect the raw MCP response to find the correct field name

**Problem:** Status categorization seems wrong
- **Solution**: Check the actual status names in your Jira workflow
- **Adjust**: Add custom status names to the categorization logic

## Additional Documentation

- MCP Atlassian Server: https://github.com/sooperset/mcp-atlassian
- Jira REST API: https://developer.atlassian.com/cloud/jira/platform/rest/v2/
- Command Documentation: See `../commands/workload.md`
