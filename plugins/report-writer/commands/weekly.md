---
description: Generate comprehensive weekly team activity reports from Jira
argument-hint: "[--project PROJECT] [--component COMPONENT] [--week-offset N] [--batch-size N]"
---

## Name
report-writer:weekly

## Synopsis
```
/report-writer:weekly --project CLID [--component oc-mirror] [--week-offset -1] [--batch-size 5]
```

## Description

The `report-writer:weekly` command generates comprehensive weekly team activity reports by collecting and analyzing data from Atlassian Jira. It systematically fetches sprint data, issue details with complete changelogs and comments, filters by activity within the reporting window, and produces structured reports with team metrics and contribution summaries.

**Key Features:**
- Automatic sprint discovery based on date ranges
- Batch fetching of issue data with changelogs
- Activity filtering for the specified week
- Detailed team contribution analysis
- Markdown report generation

## Implementation

This command uses the **weekly-report** skill which provides detailed implementation guidance. The workflow consists of:

1. **Parse Arguments**: Extract project, component, week-offset, and batch-size from command
2. **Discover Board & Sprint**: Find the appropriate Jira board and sprint for the reporting period
3. **Collect Issue Data**: Fetch issue data via MCP tools and save to individual JSON files with verification
4. **Generate Report**: Analyze activity and create markdown report with metrics

**For detailed implementation steps, refer to the [weekly-report skill](../skills/weekly-report/SKILL.md).**

### Prerequisites

This command requires the **Jira MCP server** to be configured and running. See the [plugin README](../README.md) for setup instructions.

### Process Flow

The command follows these phases:

1. **Argument Parsing**:
   - Extract `--project` (required), `--component` (optional), `--week-offset` (default: -1), `--batch-size` (default: 5)
   - Validate parameters and confirm with user if ambiguous

2. **Board & Sprint Discovery**:
   - Call `mcp__atlassian__jira_get_agile_boards` to find the board ID
   - Call `mcp__atlassian__jira_get_sprints_from_board` with `limit=50` to fetch recent sprints (sprints are returned in chronological order, so higher limit ensures we get current/active sprints)
   - Calculate target week (Monday-Sunday) based on week-offset
   - Parse sprint dates and select the sprint that overlaps with target week (check if target week falls between sprint start_date and end_date)

3. **Issue Collection**:
   - **IMPORTANT**: Get issue keys using `mcp__atlassian__jira_get_board_issues` with `fields="key"` (NOT `jira_get_sprint_issues` which causes large response errors)
   - Fetch complete issue data in batches using `mcp__atlassian__jira_get_issue` with:
     - `fields="*all"`
     - `expand="changelog"`
     - `comment_limit=100`
   - Save each fetched issue immediately to individual JSON file: `/tmp/weekly-{timestamp}/{ISSUE_KEY}.json`
   - Verify data completeness by checking file count and structure
   - Store in working directory: `/tmp/weekly-{timestamp}/`

4. **Report Generation**:
   - Read JSON files from working directory
   - Filter issues by activity within report week
   - Calculate team metrics and contributions
   - Generate markdown report with sections:
     - Header (project, sprint, date range)
     - Summary metrics
     - Issues with activity
     - Team contributions
     - PR activity
   - Save report as `/tmp/weekly-{timestamp}/weekly-report.md`
   - Display highlights and full report to user

### Data Verification

After fetching and saving issues, the command verifies data completeness:
- **File Count**: Ensures all issues were saved (count matches expected)
- **Structure Check**: Verifies sample files have required fields (key, summary, changelog)
- **Size Check**: Confirms reasonable file sizes (typically 5-10 KB per issue)

See the skill documentation for detailed verification steps.

## Return Value

- **Format**: Markdown report file at `/tmp/weekly-{timestamp}/weekly-report.md`
- **Console Output**: Report highlights and full report text
- **Data Files**: Individual issue JSON files in `/tmp/weekly-{timestamp}/`

The command reports:
- Working directory path
- Number of issues processed
- Report file location
- Key metrics and highlights

## Arguments

- `--project`: Jira project key (e.g., "CLID") - **REQUIRED**
- `--component`: Optional component filter (e.g., "oc-mirror")
- `--week-offset`: Number of weeks back from current week (default: -1 for last week)
  - `-1`: Last Monday-Sunday
  - `0`: Current Monday-Sunday
  - `-2`: Two weeks ago
- `--batch-size`: Number of issues to fetch in parallel per batch (default: 5, range: 1-10)
- `--slack-file`: Path to Slack standup file for supplementary context (optional)
- `--notes`: Manual notes text to include in report (optional)

## Examples

1. **Basic weekly report**:
   ```bash
   /report-writer:weekly --project CLID
   ```
   Generates last week's report (previous Monday-Sunday) for all CLID issues.

2. **Component-specific report**:
   ```bash
   /report-writer:weekly --project CLID --component oc-mirror
   ```
   Generates last week's report filtered to the oc-mirror component only.

3. **Current week report**:
   ```bash
   /report-writer:weekly --project CLID --week-offset 0
   ```
   Generates report for the current week (this Monday-Sunday).

4. **Faster parallel fetching**:
   ```bash
   /report-writer:weekly --project CLID --batch-size 10
   ```
   Fetches 10 issues in parallel for faster execution on good network connections.

The command provides progress updates during execution and creates a comprehensive report with all team activity for the specified period.
