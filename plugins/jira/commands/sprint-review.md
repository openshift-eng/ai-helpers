---
description: Generate comprehensive sprint review report with custom date range and flexible scope filtering
argument-hint: "[--project project-name] [--component component-name] [--jql custom-filter] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--output filename]"
---

## Name
jira:sprint-review

## Synopsis
```
/jira:sprint-review [--project project-name] [--component component-name] [--jql custom-filter] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--output filename]
```

## Description
The `jira:sprint-review` command generates comprehensive sprint review reports for any project or component combination. It analyzes all issue activity within a specified date range and produces detailed insights on blockers, new work, completed issues, activity trends, and team accomplishments.

This command is particularly useful for:
- End-of-sprint retrospectives and reviews
- Executive status reports across multiple sprints
- Team performance analysis and metrics tracking
- Identifying patterns in issue creation and resolution
- Planning future sprint capacity based on historical data

Key capabilities:
- Flexible scope filtering (project, component, or custom JQL)
- Custom date range specification with smart defaults
- Multi-dimensional analysis (blockers, new work, closed issues, activity)
- Automatic work breakdown by type and area
- Metrics calculation and trend analysis
- Risk identification and recommendations
- Markdown output for easy sharing and documentation

## Implementation

The command executes the following workflow:

### 1. Parameter Collection

Prompt the user for the following parameters if not provided:

**Scope Filter** (choose one approach):
- **Option A**: Project and optional component(s)
  - Project name (e.g., "OCM", "OCPSTRAT")
  - Component(s) (e.g., "Multicluster Networking", or multiple: "Control Plane,Storage")
- **Option B**: Custom JQL filter
  - Full JQL query (e.g., `project=OCM AND component="ARO HCP"`)

**Date Range**:
- Start date in YYYY-MM-DD format (required)
- End date in YYYY-MM-DD format (defaults to today if not provided)

**Output Settings**:
- Report filename (optional, defaults to `sprint-review-{start-date}-to-{end-date}.md`)

### 2. Build JQL Queries

Construct base filter based on user input:

**If using project + components:**
```jql
project="{PROJECT}" AND component in ("{COMPONENT1}", "{COMPONENT2}")
```

**If using custom JQL:**
```jql
{USER_JQL}
```

Then construct specific queries for data collection:

1. **Blocker bugs:**
   ```jql
   {BASE_FILTER} AND priority=Blocker AND resolution is EMPTY
   ```

2. **New issues created during sprint:**
   ```jql
   {BASE_FILTER} AND created >= "{START_DATE}" AND created <= "{END_DATE}"
   ```

3. **Closed issues during sprint:**
   ```jql
   {BASE_FILTER} AND status in (Closed, Done, Resolved) AND resolved >= "{START_DATE}" AND resolved <= "{END_DATE}"
   ```

4. **Updated issues during sprint:**
   ```jql
   {BASE_FILTER} AND updated >= "{START_DATE}" AND updated <= "{END_DATE}"
   ```

### 3. Data Collection

Execute each JQL query using the `jira issue list` command:
- Use `--raw` flag for JSON output
- Use `--paginate 100` to capture all results
- Validate date formats before execution
- Handle authentication and API errors gracefully

Extract key fields from each issue:
- Issue key, summary, type, priority
- Status, resolution, assignee, reporter
- Created date, updated date, resolved date
- Components, labels, story points (if available)
- Links to related issues

### 4. Data Analysis

**Blocker Analysis:**
- Identify all open blocker-priority issues
- Categorize by age, component, and assignee status
- Flag unassigned or stale blockers

**New Work Analysis:**
- Group new issues by type (Bug, Story, Task, Epic, etc.)
- Categorize by purpose (feature, bug fix, tech debt, etc.)
- Identify trends in issue creation patterns

**Completion Analysis:**
- Calculate completion rate (closed vs. created)
- Analyze resolution time distribution
- Identify high-performing areas and bottlenecks

**Activity Analysis:**
- Track status transitions during the sprint
- Identify most active components/assignees
- Detect issues with excessive churn

**Metrics Calculation:**
- Total issues: created, closed, in-progress, blocked
- Story points: planned vs. completed (if available)
- Velocity trends and capacity utilization
- Blocker impact and resolution time

### 5. Report Generation

Generate a comprehensive Markdown report with the following sections:

**Report Header:**
- Sprint date range
- Scope (project/component filter)
- Generation timestamp
- Claude Code attribution

**Main Sections:**

1. **📊 Executive Summary**
   - Key metrics and highlights
   - Overall sprint health assessment

2. **🚨 Blocker Bugs**
   - All open blocker-priority issues
   - Detailed status and recommended actions

3. **✨ New Work Items**
   - All issues created during sprint
   - Grouped by type and purpose

4. **✅ Closed Issues**
   - All issues resolved/closed during sprint
   - Completion details and trends

5. **📈 Activity Summary**
   - Issues updated during sprint
   - Status transition analysis

6. **🔍 Work Breakdown**
   - Analysis by issue type
   - Analysis by work area/component

7. **📉 Key Metrics**
   - Counts, percentages, and trends
   - Velocity and capacity metrics

8. **⚠️ Risks & Concerns**
   - Identified blockers requiring attention
   - Process or capacity concerns

9. **💡 Recommendations**
   - Actionable next steps for the team
   - Suggested process improvements

10. **🎯 Team Accomplishments**
    - Highlights of completed work
    - Notable achievements

**Appendix:**
- Links to all key issues referenced
- Full JQL queries used for data collection

### 6. Output and Review

- Save report to specified location (current directory by default)
- Display filename and path to user
- Provide summary of key findings
- Offer to open the report or make adjustments

## Usage Examples

1. **Single project sprint review:**
   ```
   /jira:sprint-review --project OCPSTRAT --start-date 2024-12-01 --end-date 2024-12-15
   ```

2. **Project with specific component:**
   ```
   /jira:sprint-review --project OCM --component "Multicluster Networking" --start-date 2024-12-01
   ```

3. **Multiple components:**
   ```
   /jira:sprint-review --project OCPSTRAT --component "Control Plane,Storage" --start-date 2024-12-01 --end-date 2024-12-15
   ```

4. **Custom JQL filter:**
   ```
   /jira:sprint-review --jql "project=OCM AND component='ARO HCP'" --start-date 2024-12-01 --end-date 2024-12-15
   ```

5. **Custom output filename:**
   ```
   /jira:sprint-review --project OCPBUGS --start-date 2024-12-01 --output "q4-sprint-3-review.md"
   ```

6. **End date defaults to today:**
   ```
   /jira:sprint-review --project HOSTEDCP --start-date 2024-12-15
   ```

## Arguments

- **--project** *(optional if --jql provided)*
  JIRA project key for scope filtering.
  Example: `OCPSTRAT`, `OCM`, `HOSTEDCP`

- **--component** *(optional)*
  JIRA component name(s) for filtering (single or comma-separated).
  Examples:
    - `--component "Multicluster Networking"`
    - `--component "Control Plane,Storage"`

- **--jql** *(optional, alternative to --project/--component)*
  Custom JQL filter for maximum flexibility.
  Example: `--jql "project=OCM AND component='ARO HCP' AND labels=customer-facing"`

- **--start-date** *(required)*
  Sprint start date in YYYY-MM-DD format.
  Example: `--start-date 2024-12-01`

- **--end-date** *(optional)*
  Sprint end date in YYYY-MM-DD format.
  Default: Today's date
  Example: `--end-date 2024-12-15`

- **--output** *(optional)*
  Custom filename for the generated report.
  Default: `sprint-review-{start-date}-to-{end-date}.md`
  Example: `--output "december-sprint-review.md"`

## Return Value

- **Markdown Report**: Comprehensive sprint review document saved to the current directory
- **Console Summary**: Key findings and metrics displayed to the user
- **File Path**: Full path to the generated report

**Report Format:**
```
Current Directory/
└── {output-filename}.md  (e.g., sprint-review-2024-12-01-to-2024-12-15.md)
```

## See Also
- `jira:grooming` - Backlog grooming meeting agendas
- `jira:status-rollup` - Status rollup for parent issues
