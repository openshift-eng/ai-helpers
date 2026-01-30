# Workload Analysis with JIRA MCP

This directory contains guidance and helper resources for the `/jira:workload` command, which analyzes an associate's workload for a given sprint using the JIRA MCP server.

## Overview

The `/jira:workload` command leverages the JIRA MCP server to:
- Fetch sprint issues using native MCP tools
- Filter issues by assignee
- Categorize issues by status, priority, and type
- Calculate story points and completion metrics
- Generate actionable insights
- Create formatted markdown reports

## Usage

```bash
/jira:workload <assignee> <sprint-name>
```

**Arguments:**
- `<assignee>`: Username, email, or display name of the assignee
- `<sprint-name>`: Name of the sprint (e.g., "Sprint 23", "CORENET Sprint 281")

**Examples:**
```bash
/jira:workload jdoe "Sprint 23"
/jira:workload jane.doe@company.com "CORENET Sprint 281"
/jira:workload "Jane Doe" "2025-Q1 Sprint 3"
```

## How It Works

### 1. MCP Integration

The command uses the `mcp-atlassian` MCP server (https://github.com/sooperset/mcp-atlassian) with these tools:

- **`jira_search`**: Search issues using JQL
- **`jira_get_sprint_issues`**: Get all issues in a sprint
- **`jira_get_agile_boards`**: List agile boards (for sprint resolution)
- **`jira_get_sprints_from_board`**: List sprints from a board

### 2. Workflow

1. **Fetch Sprint Issues**: Uses `jira_search` with JQL `sprint="<sprint-name>"`
2. **Filter by Assignee**: Matches on username, email, or display name
3. **Categorize**: Groups issues by status (To Do, In Progress, Blocked, Done)
4. **Calculate Metrics**: Sums story points and calculates completion rates
5. **Generate Insights**: Analyzes workload patterns and provides recommendations
6. **Create Report**: Generates a markdown report and saves to `.work/jira/workload/`

### 3. Status Categorization

The command automatically categorizes Jira statuses:

- **To Do**: open, new, backlog, to do, todo
- **In Progress**: in progress, wip, review, in review, code review
- **Done**: done, closed, resolved, complete, completed
- **Blocked**: blocked, on hold, waiting, hold
- **Other**: Any custom statuses not matching above

### 4. Story Points

The command looks for story points in these custom fields:
1. `customfield_12310243` (Red Hat Jira)
2. `customfield_10016` (Common Jira)
3. `customfield_10002` (Jira Cloud)
4. Any field containing "story" or "point"

Defaults to 0 if not found.

## Prerequisites

### MCP Server Setup

You must have the JIRA MCP server configured:

1. **Install the MCP server:**
   ```bash
   npm install -g @sooperset/mcp-atlassian
   ```

2. **Configure credentials** in your MCP configuration file (e.g., `~/.cursor/mcp.json`):
   ```json
   {
     "mcpServers": {
       "mcp-atlassian": {
         "command": "npx",
         "args": ["-y", "@sooperset/mcp-atlassian"],
         "env": {
           "JIRA_URL": "https://your-jira-instance.atlassian.net",
           "JIRA_PERSONAL_TOKEN": "your-jira-api-token"
         }
       }
     }
   }
   ```

3. **Restart Claude Code** to load the MCP server

### Jira Access

- Access to the Jira project and sprints
- Valid Jira API token with read permissions
- Appropriate project permissions

## Report Format

The generated report includes:

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
{List of issues with key, priority, summary, and story points}

### In Progress ({count} issues, {points} points)
{List of issues...}

### Blocked ({count} issues, {points} points)
{List of issues...}

### Done ({count} issues, {points} points)
{List of issues...}

## Priority Breakdown
- **P0 (Critical):** {count} issues ({points} points)
- **P1 (High):** {count} issues ({points} points)
- **P2 (Medium):** {count} issues ({points} points)
- **P3 (Low):** {count} issues ({points} points)

## Insights
{Bulleted list of actionable insights}

## Time Tracking (if available)
- **Estimated:** {hours}h
- **Logged:** {hours}h ({percentage}% of estimate)
- **Remaining:** {hours}h
```

Reports are saved to: `~/.work/jira/workload/{assignee}-{sprint}-{timestamp}.md`

## Error Handling

The command handles common errors:

- **MCP Server Not Available**: Provides setup instructions
- **Sprint Not Found**: Suggests using sprint listing tools to find the correct name
- **Assignee Not Found**: Lists all assignees in the sprint to help identify the correct one
- **Missing Story Points**: Continues with 0 points and notes this in the report
- **Custom Field Variations**: Tries multiple common field names

## Insights Generated

The command provides actionable insights such as:

- **Progress Assessment**: "On Track" / "At Risk" / "Behind" based on completion rate
- **Priority Alerts**: High-priority items not yet started
- **Stale Work**: Issues in progress for more than 5 days
- **Blocked Items**: Items requiring attention
- **Workload Balance**: Distribution of story points across statuses
- **Recommendations**: Focus areas (e.g., "Complete P0 items before starting new work")

## Troubleshooting

### Can't find assignee
- Try different formats: username, email, or display name
- Check the list of available assignees shown in the error message
- Use case-insensitive matching

### Story points are all 0
- Verify your Jira instance uses story points
- Check which custom field your Jira uses (varies by instance)
- The command will still provide useful metrics based on issue counts

### Sprint not found
- Verify the sprint name matches exactly (including capitalization)
- Use quotes around sprint names with spaces
- Try listing sprints using the MCP tools to find the correct name

### MCP server not responding
- Verify the MCP server is configured in your settings
- Check that credentials are correct
- Restart Claude Code to reload the MCP server

## Additional Resources

- **Command Documentation**: See `../commands/workload.md`
- **Skill Implementation**: See `SKILL.md` in this directory
- **MCP Atlassian Server**: https://github.com/sooperset/mcp-atlassian
- **Jira API Documentation**: https://developer.atlassian.com/cloud/jira/platform/rest/v2/

## Legacy Files

### `generate_workload_report.py`

**Note**: This Python script is legacy code from the pre-MCP implementation. It is no longer used by the `/jira:workload` command, which now uses the JIRA MCP server directly.

The script remains in this directory for reference and potential future use cases, but the MCP-based approach is preferred for all new implementations.

If you need to use the old curl-based approach for any reason, refer to the git history for the previous implementation details.
