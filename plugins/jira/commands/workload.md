---
description: Retrieve and analyze an associate's workload for a given sprint
argument-hint: <assignee> <sprint-name>
---

## Name
jira:workload

## Synopsis
```
/jira:workload <assignee> <sprint-name>
```

## Description

The `jira:workload` command retrieves and analyzes an associate's workload for a specific sprint. It provides a comprehensive breakdown of all issues assigned to the associate within the sprint, including their status, priority, story points, and time tracking information.

This command is particularly useful for:
- Sprint planning and capacity assessment
- Identifying overloaded team members
- Understanding individual contributor workload distribution
- Tracking progress on assigned work during a sprint
- Generating reports for 1-on-1s and retrospectives

Key capabilities:
- Fetches all issues assigned to a user within a specified sprint
- Groups issues by status (To Do, In Progress, Done, Blocked)
- Calculates total story points and time estimates
- Shows priority distribution
- Identifies blockers and dependencies
- Generates a formatted report with actionable insights

## MCP Tools Used

This command requires the `mcp-atlassian` MCP server (https://github.com/sooperset/mcp-atlassian) with the following Jira tools enabled:

**Read Operations:**
- `jira_search` - Search issues using JQL to find workload by assignee and sprint
- `jira_get_sprint_issues` - Get all issues in a specific sprint
- `jira_get_agile_boards` - List all agile boards to find sprints
- `jira_get_sprints_from_board` - List sprints from a board to resolve sprint names
- `jira_get_user_profile` - Validate user exists (optional)

**Write Operations (optional):**
- `jira_add_comment` - Post workload report as a comment to a Jira issue

## Implementation

The command executes the following workflow using the JIRA MCP server:

### Step 1: Parse and Validate Arguments

Extract the command arguments:
- `$1`: assignee (username, email, or display name)
- `$2`: sprint name (e.g., "Sprint 23", "CORENET Sprint 281")

Both arguments are required for the command to proceed.

### Step 2: Fetch Sprint Issues via MCP

Use the MCP `jira_search` tool to fetch all issues in the specified sprint:

1. **Build the JQL query:**
   ```
   sprint="<sprint-name>"
   ```

2. **Call the `jira_search` tool:**
   - Set `jql` parameter to the query built above
   - Set `max_results` to 200 (or higher if needed)
   - Request comprehensive fields including:
     - `summary`, `status`, `priority`, `issuetype`
     - `assignee` (critical for filtering)
     - `customfield_12310243` (story points for Red Hat Jira)
     - `timetracking` (original estimate, time spent, remaining)
     - `labels`, `components`
     - `created`, `updated`, `resolutiondate`
     - `parent` (for subtasks)

3. **Verify the response:**
   - Check that issues were returned
   - If no issues found, inform the user that the sprint name may be incorrect
   - Display total number of issues found in the sprint

**Note on Sprint Name Resolution:**
If the initial search fails, you can help the user find the correct sprint name:
- Use `jira_get_agile_boards` to list available boards
- Use `jira_get_sprints_from_board` with a board ID to list sprint names
- Suggest similar sprint names to the user

### Step 3: Filter Issues by Assignee

From the full sprint results, filter to find issues assigned to the specified user:

1. **Match by assignee fields:**
   - Compare against `assignee.name` (username)
   - Compare against `assignee.emailAddress` (email)
   - Compare against `assignee.displayName` (full name)
   - Support partial matches for display name

2. **Handle case sensitivity:**
   - Perform case-insensitive matching for better user experience
   - Normalize email addresses (lowercase)

3. **Verify matches found:**
   - If no issues found for the assignee, list all unique assignees in the sprint
   - Suggest correct assignee names to help the user

### Step 4: Categorize and Analyze Issues

Organize the filtered issues into meaningful categories:

**Status Categorization:**
- **To Do**: Statuses like "open", "new", "backlog", "to do"
- **In Progress**: Statuses like "in progress", "wip", "review", "in review", "code review"
- **Done**: Statuses like "done", "closed", "resolved", "complete"
- **Blocked**: Statuses like "blocked", "on hold", "waiting"
- **Other**: Any custom statuses not matching above categories

**Calculate Metrics:**
- Count issues in each status category
- Sum story points for each category (use `customfield_12310243` or similar)
- Calculate completion percentage (done issues / total issues)
- Analyze priority distribution (P0, P1, P2, P3, etc.)
- Extract time tracking data if available

**Priority Analysis:**
- Group by priority level
- Count issues and sum story points per priority
- Identify high-priority items that are blocked or still in "To Do"

**Identify Insights:**
- Issues that have been in progress for a long time (compare `updated` date)
- High-priority items not yet started
- Blocked items requiring attention
- Sprint progress assessment based on completion rate
- Workload balance (story points vs. capacity)

### Step 5: Generate Workload Report

Create a comprehensive markdown report with the following structure:

```markdown
# Sprint Workload: {Assignee Display Name} - {Sprint Name}

**Sprint:** {Sprint Name}
**Assignee:** {Assignee Display Name} ({username})
**Status as of:** {Current Date}

## Summary
- **Total Issues:** {count}
- **Story Points:** {done points} completed / {total points} total ({percentage}%)
- **Completion Rate:** {done count}/{total count} issues ({percentage}%)
- **Status:** {On Track | At Risk | Behind}

## Issues by Status

### To Do ({count} issues, {points} points)
{List issues with: [KEY] [Priority] Summary (story points) - created date}

### In Progress ({count} issues, {points} points)
{List issues with: [KEY] [Priority] Summary (story points) - started date}

### Blocked ({count} issues, {points} points)
{List issues with: [KEY] [Priority] Summary (story points) - blocked since date}

### Done ({count} issues, {points} points)
{List issues with: [KEY] [Priority] Summary (story points) - completed date}

## Priority Breakdown
- **P0 (Critical):** {count} issues ({points} points)
- **P1 (High):** {count} issues ({points} points)
- **P2 (Medium):** {count} issues ({points} points)
- **P3 (Low):** {count} issues ({points} points)

## Insights
{Bulleted list of actionable insights based on the data}

## Time Tracking (if available)
- **Estimated:** {total estimate}
- **Logged:** {time spent} ({percentage}% of estimate)
- **Remaining:** {remaining estimate}
```

### Step 6: Save and Display Report

1. **Setup working directory:**
   ```bash
   WORK_DIR="$HOME/.work/jira/workload"
   mkdir -p "$WORK_DIR"
   ```

2. **Generate filename:**
   - Use format: `{assignee-sanitized}-{sprint-sanitized}-{timestamp}.md`
   - Sanitize names by replacing spaces with hyphens and removing special characters

3. **Write report to file:**
   - Save the generated markdown to the working directory
   - Preserve formatting for proper markdown rendering

4. **Display to user:**
   - Show the complete report in the console
   - Provide the file path for future reference

### Error Handling

The implementation handles these error cases:

1. **Missing Arguments**:
   - Display usage message if assignee or sprint name is missing
   - Example: `Usage: /jira:workload <assignee> <sprint-name>`

2. **MCP Server Not Available**:
   - Check if the `jira_search` tool is available
   - If not, inform the user to configure the JIRA MCP server
   - Provide setup instructions or link to MCP documentation

3. **Sprint Not Found**:
   - If JQL query returns no results, the sprint name may be incorrect
   - Suggest using `jira_get_sprints_from_board` to find the correct sprint name
   - Offer to list available sprints

4. **Assignee Not Found**:
   - If filtering yields no issues, list all assignees found in the sprint
   - Suggest the correct assignee name based on similarity
   - Support case-insensitive matching to help find the user

5. **Missing Story Points**:
   - Default to 0 story points if the field is not set
   - Calculate metrics with available data
   - Note in the report if story points are not being used

6. **Custom Field Variations**:
   - Different Jira instances use different custom field IDs for story points
   - Common field names: `customfield_12310243`, `customfield_10016`, `Story Points`
   - Try multiple field names and use the first one that has values

## Return Value

- **Markdown Report**: Saved to `.work/jira/workload/{assignee}-{sprint-sanitized}-{timestamp}.md`
- **Console Output**: Complete formatted report displayed in terminal

The report includes:
- Sprint metadata (name, assignee details)
- Executive summary with completion metrics
- Issue breakdown by status with counts and story points
- Detailed listing of issues in each status category
- Priority distribution analysis
- Time tracking summary (if available in Jira)
- Actionable insights and recommendations based on workload analysis

## Examples

1. **Get workload for a user by username**:
   ```
   /jira:workload jdoe "Sprint 23"
   ```
   Output: Workload report for user jdoe in Sprint 23

2. **Get workload using email address**:
   ```
   /jira:workload jane.doe@company.com "2025-Q1 Sprint 3"
   ```
   Output: Workload report for jane.doe@company.com in 2025-Q1 Sprint 3

3. **Get workload for current sprint**:
   ```
   /jira:workload jsmith "Current Sprint"
   ```
   Output: Workload report for the currently active sprint

**Example Output:**

```markdown
# Sprint Workload: Jane Doe - Sprint 23

**Sprint:** Sprint 23
**Assignee:** Jane Doe (jdoe)
**Status as of:** 2025-01-13

## Summary
- **Total Issues:** 12
- **Story Points:** 18 completed / 34 total (53%)
- **Completion Rate:** 6/12 issues (50%)
- **Status:** On Track

## Issues by Status

### To Do (3 issues, 8 points)
- [TEAM-456] [P2] Implement user settings page (5 points)
- [TEAM-457] [P3] Update API documentation (2 points)
- [TEAM-458] [P2] Add error handling for edge cases (1 point)

### In Progress (3 issues, 8 points)
- [TEAM-451] [P0] Fix critical authentication bug (3 points) - Started 2 days ago
- [TEAM-452] [P1] Refactor database queries (5 points) - Started 5 days ago

### Blocked (0 issues, 0 points)
- None

### Done (6 issues, 18 points)
- [TEAM-441] [P1] Implement OAuth2 login (8 points) - Completed 7 days ago
- [TEAM-442] [P2] Add unit tests for auth service (5 points) - Completed 5 days ago
- [TEAM-443] [P3] Update dependencies (2 points) - Completed 3 days ago
- [TEAM-444] [P2] Fix UI rendering bug (3 points) - Completed 2 days ago

## Priority Breakdown
- **P0 (Critical):** 1 issue (3 points)
- **P1 (High):** 3 issues (13 points)
- **P2 (Medium):** 6 issues (15 points)
- **P3 (Low):** 2 issues (3 points)

## Insights
- Good progress: 53% of story points completed at sprint midpoint
- Critical P0 issue (TEAM-451) is being actively worked on
- No blocked items currently
- Workload appears balanced with clear priority distribution
- Recommendation: Focus on completing P0 and P1 items before picking up new work

## Time Tracking
- **Estimated:** 68h
- **Logged:** 42h (62% of estimate)
- **Remaining:** 26h

---
Report saved to: .work/jira/workload/jane.doe-sprint-23.md
```

## Arguments

- `<assignee>` (required): The JIRA user to analyze. Can be:
  - Username (e.g., `jdoe`)
  - Email address (e.g., `jane.doe@company.com`)
  - Display name (e.g., `Jane Doe`)

- `<sprint-name>` (required): The sprint to analyze. Examples:
  - `"Sprint 23"`
  - `"2025-Q1 Sprint 3"`
  - `"Current Sprint"` (for active sprint)
  - Sprint ID number if known (e.g., `12345`)
