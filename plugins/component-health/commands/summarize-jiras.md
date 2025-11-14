---
description: Query and summarize JIRA bugs for a specific project with counts by component
argument-hint: --project <project> [--component comp1 comp2 ...] [--status status1 status2 ...] [--include-closed] [--limit N]
---

## Name

component-health:summarize-jiras

## Synopsis

```
/component-health:summarize-jiras --project <project> [--component comp1 comp2 ...] [--status status1 status2 ...] [--include-closed] [--limit N]
```

## Description

The `component-health:summarize-jiras` command queries JIRA bugs for a specified project and generates summary statistics. It leverages the `list-jiras` command to fetch raw JIRA data and then calculates counts by status, priority, and component to help understand the bug backlog at a glance.

By default, the command includes:
- All currently open bugs
- Bugs closed in the last 30 days (to track recent closure activity)

This command is useful for:

- Getting a quick count of open bugs in a JIRA project
- Analyzing bug distribution by status, priority, or component
- Tracking recent bug flow (opened vs closed in last 30 days)
- Generating summary reports for bug backlog
- Monitoring bug velocity and closure rates by component
- Comparing bug counts across different components

## Implementation

1. **Verify Prerequisites**: Check that Python 3 is installed

   - Run: `python3 --version`
   - Verify version 3.6 or later is available

2. **Verify Environment Variables**: Ensure JIRA authentication is configured

   - Check that the following environment variables are set:
     - `JIRA_URL`: Base URL for JIRA instance (e.g., "https://issues.redhat.com")
     - `JIRA_PERSONAL_TOKEN`: Your JIRA bearer token or personal access token

   - Verify with:
     ```bash
     echo "JIRA_URL: ${JIRA_URL}"
     echo "JIRA_PERSONAL_TOKEN: ${JIRA_PERSONAL_TOKEN:+***set***}"
     ```

   - If missing, guide the user to set them:
     ```bash
     export JIRA_URL="https://issues.redhat.com"
     export JIRA_PERSONAL_TOKEN="your-token-here"
     ```

3. **Parse Arguments**: Extract project key and optional filters from arguments

   - Project key: Required `--project` flag (e.g., "OCPBUGS", "OCPSTRAT")
   - Optional filters:
     - `--component`: Space-separated list of component search strings (fuzzy match)
     - `--status`: Space-separated list of status values
     - `--include-closed`: Flag to include closed bugs
     - `--limit`: Maximum number of issues to fetch per component (default: 1000, max: 1000)

4. **Resolve Component Names** (if component filter provided): Use fuzzy matching to find actual component names

   - Extract release from context or ask user for release version
   - Run list_components.py to get all available components:
     ```bash
     python3 plugins/component-health/skills/list-components/list_components.py --release <release>
     ```
   - For each search string in `--component`:
     - Find all components containing that string (case-insensitive)
     - Combine all matches into a single list
     - Remove duplicates
     - If no matches found for a search string, warn the user and show available components

5. **Execute Python Script**: Run the summarize_jiras.py script for each component

   - Script location: `plugins/component-health/skills/summarize-jiras/summarize_jiras.py`
   - The script internally calls `list_jiras.py` to fetch raw data
   - **Important**: Iterate over each resolved component separately to avoid overly large queries
   - For each component:
     - Build command with project, single component, and other filters
     - Execute: `python3 summarize_jiras.py --project <project> --component "<component>" [other args]`
     - Capture JSON output from stdout
   - Aggregate summary statistics from all components into a combined response

6. **Parse Output**: Process the aggregated JSON response

   - Extract summary statistics:
     - `total_count`: Total matching issues in JIRA
     - `fetched_count`: Number of issues actually fetched
     - `summary.by_status`: Count of issues per status
     - `summary.by_priority`: Count of issues per priority
     - `summary.by_component`: Count of issues per component
   - Extract per-component breakdowns:
     - Each component has its own counts by status and priority
     - Includes opened/closed in last 30 days per component

7. **Present Results**: Display summary in a clear format

   - Show which components were matched (if fuzzy search was used)
   - Show total bug count across all components
   - Display status breakdown (e.g., New, In Progress, Verified, etc.)
   - Display priority breakdown (Critical, Major, Normal, Minor, etc.)
   - Display component distribution
   - Show per-component breakdowns with status and priority counts
   - Highlight any truncation (if fetched_count < total_count for any component)
   - Suggest increasing --limit if results are truncated

8. **Error Handling**: Handle common error scenarios

   - Network connectivity issues
   - Invalid JIRA credentials
   - Invalid project key
   - HTTP errors (401, 404, 500, etc.)
   - Rate limiting (429)

## Return Value

The command outputs a **JIRA Bug Summary** with the following information:

### Project Overview

- **Project**: JIRA project key
- **Total Count**: Total number of matching bugs (open + recently closed)
- **Query**: JQL query that was executed (includes 30-day closed bug filter)
- **Fetched Count**: Number of bugs actually fetched (may be less than total if limited)

### Summary Statistics

**Overall Metrics**:
- Total bugs fetched
- Bugs opened in last 30 days
- Bugs closed in last 30 days

**By Status**: Count of bugs in each status (includes recently closed)

| Status | Count |
|--------|-------|
| New | X |
| In Progress | X |
| Verified | X |
| Closed | X |
| ... | ... |

**By Priority**: Count of bugs by priority level

| Priority | Count |
|----------|-------|
| Critical | X |
| Major | X |
| Normal | X |
| Minor | X |
| Undefined | X |

**By Component**: Count of bugs per component

| Component | Count |
|-----------|-------|
| kube-apiserver | X |
| Management Console | X |
| Networking | X |
| ... | ... |

### Per-Component Breakdown

For each component:
- **Total**: Number of bugs assigned to this component
- **Opened (30d)**: Bugs created in the last 30 days
- **Closed (30d)**: Bugs closed in the last 30 days
- **By Status**: Status distribution for this component
- **By Priority**: Priority distribution for this component

### Additional Information

- **Filters Applied**: Lists any component, status, or other filters used
- **Note**: If results are truncated, suggests increasing the limit
- **Query Scope**: By default includes open bugs and bugs closed in the last 30 days

## Examples

1. **Summarize all open bugs for a project**:

   ```
   /component-health:summarize-jiras --project OCPBUGS
   ```

   Fetches all open bugs in the OCPBUGS project (up to default limit of 1000) and displays summary statistics.

2. **Filter by specific component**:

   ```
   /component-health:summarize-jiras --project OCPBUGS --component "kube-apiserver"
   ```

   Shows bug counts for only the kube-apiserver component.

3. **Filter by multiple components**:

   ```
   /component-health:summarize-jiras --project OCPBUGS --component "kube-apiserver" "etcd" "Networking"
   ```

   Shows bug counts for kube-apiserver, etcd, and Networking components.

4. **Include closed bugs**:

   ```
   /component-health:summarize-jiras --project OCPBUGS --include-closed --limit 500
   ```

   Includes both open and closed bugs, fetching up to 500 issues.

5. **Filter by status**:

   ```
   /component-health:summarize-jiras --project OCPBUGS --status New "In Progress" Verified
   ```

   Shows only bugs in New, In Progress, or Verified status.

6. **Combine multiple filters**:

   ```
   /component-health:summarize-jiras --project OCPBUGS --component "Management Console" --status New Assigned --limit 200
   ```

   Shows bugs for Management Console component that are in New or Assigned status.

## Arguments

- `--project <project>` (required): JIRA project key
  - Format: Project key in uppercase (e.g., "OCPBUGS", "OCPSTRAT")
  - Must be a valid JIRA project you have access to

- Additional optional flags:
  - `--component <search1> [search2 ...]`: Filter by component names using fuzzy search
    - Space-separated list of component search strings
    - Case-insensitive substring matching
    - Each search string matches all components containing that substring
    - Makes separate JIRA queries for each matched component to avoid overly large results
    - Example: "network" matches "Networking / ovn-kubernetes", "Networking / DNS", etc.
    - Example: "kube-" matches "kube-apiserver", "kube-controller-manager", etc.
    - Note: Requires release context (inferred from recent commands or specified by user)

  - `--status <status1> [status2 ...]`: Filter by status values
    - Space-separated list of status names
    - Examples: `New`, `"In Progress"`, `Verified`, `Modified`, `ON_QA`

  - `--include-closed`: Include closed bugs in results
    - By default, only open bugs are returned
    - When specified, closed bugs are included

  - `--limit <N>`: Maximum number of issues to fetch per component
    - Default: 1000
    - Range: 1-1000
    - When using component filters, this limit applies to each component separately
    - Higher values provide more accurate statistics but slower performance

## Prerequisites

1. **Python 3**: Required to run the data fetching and summarization scripts

   - Check: `which python3`
   - Version: 3.6 or later

2. **JIRA Authentication**: Environment variables must be configured

   - `JIRA_URL`: Your JIRA instance URL
   - `JIRA_PERSONAL_TOKEN`: Your JIRA bearer token or personal access token

   How to get a JIRA token:
   - Navigate to JIRA → Profile → Personal Access Tokens
   - Generate a new token with appropriate permissions
   - Export it as an environment variable

3. **Network Access**: Must be able to reach your JIRA instance

   - Ensure HTTPS requests can be made to JIRA_URL
   - Check firewall and VPN settings if needed

## Notes

- The script uses Python's standard library only (no external dependencies)
- Output is JSON format for easy parsing
- Diagnostic messages are written to stderr, data to stdout
- The script has a 30-second timeout for HTTP requests
- For large projects, consider using component filters to reduce query size
- Summary statistics are based on fetched issues (controlled by --limit), not total matching issues
- If results show truncation, increase the --limit parameter for more accurate statistics
- This command internally uses `/component-health:list-jiras` to fetch raw data

## See Also

- Skill Documentation: `plugins/component-health/skills/summarize-jiras/SKILL.md`
- Script: `plugins/component-health/skills/summarize-jiras/summarize_jiras.py`
- Related Command: `/component-health:list-jiras` (for raw JIRA data)
- Related Command: `/component-health:analyze`
