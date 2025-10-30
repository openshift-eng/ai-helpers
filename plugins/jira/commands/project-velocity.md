---
description: Generate velocity metrics for a JIRA project based on closed issues
argument-hint: PROJECT-KEY [--force-public]
---

## Name
jira:project-velocity

## Synopsis
```
/jira:project-velocity PROJECT-KEY [--force-public]
```

## Description
The `jira:project-velocity` command analyzes closed issues in a JIRA project to provide velocity metrics over the last 120 days. It fetches all Story, Task, and Spike issues that have been closed with a resolution of "Done" in the specified timeframe and calculates key performance indicators.

This command is particularly useful for:
- Sprint planning and capacity estimation
- Team performance reviews
- Project health assessments
- Historical velocity tracking for forecasting

Key capabilities:
- Filters by issue type (Story, Task, Spike only)
- Considers only issues with resolution "Done"
- Analyzes the last 120 days of activity
- Calculates total issues closed
- Computes average daily velocity
- Determines average time to close issues
- Supports both authenticated (MCP) and public API modes
- Optional `--force-public` flag to bypass MCP authentication

## Prerequisites

**Authentication (Recommended):**
For access to private projects and reliable query performance, configure the JIRA MCP server:
- See: plugins/jira/README.md#setting-up-jira-mcp-server
- Required environment variables: JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN
- Test your setup: `/jira:test-auth`

**Fallback (Public Issues Only):**
This command can access public issues without authentication, but with limited functionality.

**Mode Display:**
The command will display which authentication mode is active:
- 🔐 Authenticated mode (MCP) - Full access to private projects
- 🌐 Public API mode - Limited to public issues only

**Force Public Mode:**
Use `--force-public` flag to bypass MCP and use public API directly:
- Example: `/jira:project-velocity OCPBUGS --force-public`
- Useful for: Quick queries on public projects
- Limitation: Only works for public projects

## Implementation

The command executes the following workflow:

1. **Parse Arguments and Validate**
   - Extract project key from $1
   - Check for `--force-public` flag in arguments ($2 or any position)
   - Validate project key format (typically uppercase letters, e.g., "OCPBUGS", "STORY")
   - If `--force-public` present: Skip to Step 3B (public API mode)
   - If `--force-public` not present: Continue to MCP detection

2. **Detect MCP Availability** (if not --force-public)
   - Check if MCP Atlassian server is configured
   - Attempt to use `mcp__atlassian__jira_search_issues` with test query
   - If successful: Continue with authenticated path (Step 3A)
   - If fails: Fall back to public API path (Step 3B)

3A. **Fetch Issues Using MCP (Authenticated Path)**
   - Display mode: "🔐 Using authenticated mode (MCP)"
   - Use `mcp__atlassian__jira_search_issues` with the following JQL:
     ```
     project = {PROJECT_KEY}
     AND issuetype IN (Story, Task, Spike)
     AND status = Closed
     AND resolution = Done
     AND resolved >= -120d
     ORDER BY resolved DESC
     ```
   - The MCP tool should return all matching issues with fields:
     - `key`: Issue key (e.g., STORY-123)
     - `created`: Issue creation timestamp
     - `resolutiondate`: When the issue was resolved/closed
     - `issuetype`: The type of issue
   - Handle pagination automatically via MCP tool
   - Benefits:
     - Access to private projects
     - No rate limiting
     - Automatic pagination
     - Consistent with other JIRA commands

3B. **Fetch Issues Using Public API (Fallback/Forced Path)**
   - If `--force-public` flag:
     - Display mode: "🌐 Using public API mode (forced via --force-public flag)"
   - Else (MCP unavailable):
     - Display mode: "🌐 Using public API mode (unauthenticated - limited to public issues)"
     - Display warning: "⚠️  For private projects, run /jira:test-auth to verify MCP setup"
   - Use curl with REST API: `https://issues.redhat.com/rest/api/2/search`
   - URL-encode JQL query parameters
   - Request same fields as MCP path
   - Handle pagination manually (max 1000 results per request)
   - Limitations:
     - Only works for public issues
     - May hit rate limits on large queries
     - Manual pagination required for >1000 results

4. **Data Extraction**
   - Parse the JSON response from the MCP tool
   - Extract for each issue:
     - Issue key
     - Created date (ISO 8601 format)
     - Resolved date (ISO 8601 format)
   - Store data in memory for calculations

5. **Calculate Metrics**
   - **Total Issues Closed**: Count of all returned issues
   - **Average Issues Per Day**:
     - Formula: `total_issues / 120`
     - Round to 2 decimal places
   - **Average Time to Close**:
     - For each issue, calculate: `resolved_date - created_date` (in days)
     - Calculate mean across all issues
     - Round to 1 decimal place

6. **Format Output**
   - Generate a simple text summary (NOT a table)
   - Include:
     - JQL query used (for transparency and reproducibility)
     - Project key
     - Date range analyzed (last 120 days)
     - Total issues closed
     - Average issues closed per day
     - Average time to close (in days)
   - Use clear, readable formatting

7. **Display Results**
   - Display authentication mode indicator at the top
   - Output the summary to the user
   - No temp files needed (straightforward calculation)
   - No posting to JIRA required

**Error Handling:**
- Invalid project key: Display error and suggest checking project key format
- No issues found: Display message indicating no matching issues in the last 120 days
- MCP unavailable AND project is private:
  → Error: "Unable to access project. This may be a private project requiring authentication. Run /jira:test-auth to verify MCP setup."
- `--force-public` AND project is private:
  → Error: "Project appears to be private. Remove --force-public flag or configure MCP authentication."
- MCP tool errors: Display error message with troubleshooting guidance and reference to `/jira:test-auth`
- Date parsing errors: Handle gracefully and report which issues had invalid dates
- Network errors: Provide connectivity troubleshooting steps

**Performance Considerations:**
- Query may return large result sets for active projects
- Handle pagination appropriately (max 100 issues per page typically)
- May need to make multiple API calls for projects with >100 matching issues

## Return Value
- **Console Output**: A formatted text summary containing:
  - The JQL query used
  - Project key
  - Analysis period (last 120 days)
  - Total issues closed
  - Average issues per day (decimal)
  - Average time to close in days (decimal)

## Examples

1. **Analyze velocity for CNTRLPLANE project**:
   ```
   /jira:project-velocity CNTRLPLANE
   ```

   Example Output:
   ```
   🔐 Using authenticated mode (MCP)

   Project Velocity Analysis for CNTRLPLANE
   =====================================

   JQL Query Used:
   project = CNTRLPLANE AND issuetype IN (Story, Task, Spike) AND status = Closed AND resolution = Done AND resolved >= -120d ORDER BY resolved DESC

   Analysis Period: Last 120 days (2025-07-02 to 2025-10-30)

   Results:
   - Total Issues Closed: 47
   - Average Issues Per Day: 0.39
   - Average Time to Close: 12.3 days
   ```

2. **Using --force-public flag**:
   ```
   /jira:project-velocity OCPBUGS --force-public
   ```

   Example Output:
   ```
   🌐 Using public API mode (forced via --force-public flag)

   Project Velocity Analysis for OCPBUGS
   =====================================

   JQL Query Used:
   project = OCPBUGS AND issuetype IN (Story, Task, Spike) AND status = Closed AND resolution = Done AND resolved >= -120d ORDER BY resolved DESC

   Analysis Period: Last 120 days (2025-07-02 to 2025-10-30)

   Results:
   - Total Issues Closed: 47
   - Average Issues Per Day: 0.39
   - Average Time to Close: 12.3 days
   ```

3. **Fallback to public API (MCP unavailable)**:
   ```
   /jira:project-velocity STORY
   ```

   Example Output:
   ```
   🌐 Using public API mode (unauthenticated - limited to public issues)
   ⚠️  For private projects, run /jira:test-auth to verify MCP setup

   Project Velocity Analysis for STORY
   ====================================

   JQL Query Used:
   project = STORY AND issuetype IN (Story, Task, Spike) AND status = Closed AND resolution = Done AND resolved >= -120d ORDER BY resolved DESC

   Analysis Period: Last 120 days (2025-07-02 to 2025-10-30)

   Results:
   - Total Issues Closed: 156
   - Average Issues Per Day: 1.30
   - Average Time to Close: 8.7 days
   ```

4. **No issues found example**:
   ```
   /jira:project-velocity NEWPROJECT
   ```

   Example Output:
   ```
   Project Velocity Analysis for NEWPROJECT
   =========================================

   JQL Query Used:
   project = NEWPROJECT AND issuetype IN (Story, Task, Spike) AND status = Closed AND resolution = Done AND resolved >= -120d ORDER BY resolved DESC

   Analysis Period: Last 120 days (2025-07-02 to 2025-10-30)

   Results:
   - Total Issues Closed: 0
   - Average Issues Per Day: 0.00
   - Average Time to Close: N/A (no issues closed)
   ```

## Arguments
- `PROJECT-KEY` (required): The JIRA project key to analyze (e.g., CNTRLPLANE). Must be a valid project key in your JIRA instance.
- `--force-public` (optional): Force public API mode, skip MCP authentication
  - Use when: Quick queries on public projects without MCP overhead
  - Limitation: Only works for public projects
  - Example: `/jira:project-velocity CNTRLPLANE --force-public`
