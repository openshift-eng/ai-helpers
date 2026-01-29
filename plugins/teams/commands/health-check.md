---
description: Analyze and grade component health based on regression and JIRA bug metrics
argument-hint: <release> [--components comp1 comp2 ...] [--team <team-name>] [--project JIRAPROJECT]
---

## Name

teams:health-check

## Synopsis

```
/teams:health-check <release> [--components comp1 comp2 ...] [--project JIRAPROJECT]
/teams:health-check <release> --team <team-name> [--project JIRAPROJECT]
```

## Description

The `teams:health-check` command provides comprehensive component health analysis for a specified OpenShift release by **automatically combining** regression management metrics with JIRA bug backlog data.

**CRITICAL**: This command REQUIRES and AUTOMATICALLY fetches BOTH data sources:
1. Regression data (via health-check-regressions)
2. JIRA bug data (via health-check-jiras)

The analysis is INCOMPLETE without both data sources. Both are fetched automatically without user prompting.

The command evaluates component health based on:

1. **Regression Management** (ALWAYS fetched automatically): How well components are managing test regressions
   - Triage coverage (% of regressions triaged to JIRA bugs)
   - Triage timeliness (average time from detection to triage)
   - Resolution speed (average time from detection to closure)

2. **Bug Backlog Health** (ALWAYS fetched automatically): Current state of open bugs for components
   - Open bug counts by component
   - Bug age distribution
   - Bug priority breakdown
   - Recent bug flow (opened vs closed in last 30 days)

This command is useful for:

- **Grading overall component health** using multiple quality metrics
- **Identifying components** that need help with regression or bug management
- **Tracking quality trends** across releases
- **Generating comprehensive quality scorecards** for stakeholders
- **Prioritizing engineering investment** based on data-driven insights

Grading is subjective and not meant to be a critique of team performance. This is intended to help identify where help is needed and track progress as we improve our quality practices.

## Implementation

**CRITICAL WORKFLOW**: The analyze command MUST execute steps 3 and 4 (fetch regression data AND fetch JIRA data) automatically without waiting for user prompting. Both data sources are required for a complete analysis.

1. **Parse Arguments**: Extract release version and required filters from arguments

   - Release format: "X.Y" (e.g., "4.17", "4.21")
   - Required filter (must provide one):
     - `--components`: Space-separated list of component search strings (fuzzy match)
     - `--team`: Team name (looks up all components for that team)
   - Optional filters:
     - `--project`: JIRA project key (default: "OCPBUGS")
   - Note: `--components` and `--team` are mutually exclusive
   - Note: One of `--components` or `--team` is REQUIRED (analyzing all components is too much data)

2. **Resolve Component Names**: Use fuzzy matching to find actual component names, or look up by team

   - **Validate required parameter**: If neither `--team` nor `--components` is provided:
     - Error: "Either --team or --components is required. Analyzing all components is too much data."
     - Show usage examples
     - Exit with error
   - If `--team` was provided:
     - Look up all components for that team from `team_component_map.json`
     - Use `/teams:list-components --team "<team>"` to get the component list
     - If team not found, display available teams (via `/teams:list-teams`) and exit
   - Else if `--components` was provided:
     - Run list_components.py to get all available components:
       ```bash
       python3 plugins/component-health/skills/list-components/list_components.py
       ```
     - For each search string, find all components containing that string (case-insensitive)
     - Combine all matches into a single list
     - Remove duplicates
     - If no matches found for a search string, warn the user and show available components

3. **Fetch Regression Summary**: REQUIRED - Always call the health-check-regressions command

   **IMPORTANT**: This step is REQUIRED for the analyze command. Regression data must ALWAYS be fetched automatically without user prompting. The analyze command combines both regression and bug metrics - it is incomplete without both data sources.

   - **ALWAYS execute this step** - do not skip or wait for user to request it
   - If `--team` was provided:
     - Execute: `/teams:health-check-regressions <release> --team "<team>"`
   - Else (if `--components` was provided):
     - Execute: `/teams:health-check-regressions <release> --components <resolved-components>`
   - Extract regression metrics:
     - Total regressions, triage percentages, timing metrics
     - Per-component breakdowns
     - Open vs closed regression counts
   - Note development window dates for context
   - If regression API is unreachable, inform the user and note this in the report but continue with bug-only analysis

4. **Fetch JIRA Bug Summary**: REQUIRED - Always call the health-check-jiras command

   **IMPORTANT**: This step is REQUIRED for the analyze command. JIRA bug data must ALWAYS be fetched automatically without user prompting. The analyze command combines both regression and bug metrics - it is incomplete without both data sources.

   - **ALWAYS execute this step** - do not skip or wait for user to request it
   - For each resolved component name:
     - Execute: `/teams:health-check-jiras --project <project> --component "<component>" --limit 1000`
     - Note: Must iterate over components because JIRA queries can be too large otherwise
   - Aggregate bug metrics across all components:
     - Total open bugs by component
     - Bug age distribution
     - Opened vs closed in last 30 days
     - Priority breakdowns
   - If JIRA authentication is not configured, inform the user and provide setup instructions
   - If JIRA queries fail, note this in the report but continue with regression-only analysis

5. **Calculate Combined Health Grades**: REQUIRED - Analyze BOTH regression and bug data

   **IMPORTANT**: This step requires data from BOTH step 3 (regressions) AND step 4 (JIRA bugs). Do not perform analysis with only one data source unless the other failed to fetch.

   **For each component, grade based on:**

   a. **Regression Health** (from step 3: health-check-regressions):
      - Triage Coverage: % of regressions triaged
        - 90-100%: Excellent ✅
        - 70-89%: Good ⚠️
        - 50-69%: Needs Improvement ⚠️
        - <50%: Poor ❌
      - Triage Timeliness: Average hours to triage
        - <24 hours: Excellent ✅
        - 24-72 hours: Good ⚠️
        - 72-168 hours (1 week): Needs Improvement ⚠️
        - >168 hours: Poor ❌
      - Resolution Speed: Average hours to close
        - <168 hours (1 week): Excellent ✅
        - 168-336 hours (1-2 weeks): Good ⚠️
        - 336-720 hours (2-4 weeks): Needs Improvement ⚠️
        - >720 hours (4+ weeks): Poor ❌

   b. **Bug Backlog Health** (from step 4: health-check-jiras):
      - Open Bug Count: Total open bugs
        - Component-relative thresholds (compare across components)
      - Bug Age: Average/maximum age of open bugs
        - <30 days average: Excellent ✅
        - 30-90 days: Good ⚠️
        - 90-180 days: Needs Improvement ⚠️
        - >180 days: Poor ❌
      - Bug Flow: Opened vs closed in last 30 days
        - More closed than opened: Positive trend ✅
        - Equal: Stable ⚠️
        - More opened than closed: Growing backlog ❌

   c. **Combined Health Score**: Weighted average of regression and bug health
      - Weight regression health more heavily (e.g., 60%) as it's more actionable
      - Bug backlog provides context (40%)

6. **Display Overall Health Report**: Present comprehensive analysis combining BOTH data sources

   **IMPORTANT**: The report MUST include BOTH regression metrics AND JIRA bug metrics. Do not present regression-only analysis unless JIRA data fetch failed.

   - Show which components were matched (if fuzzy search was used)
   - Inform user that both regression and bug data were analyzed

   **Section 1: Overall Release Health**
   - Release version and development window
   - Overall regression metrics (from health-check-regressions):
     - Total regressions, triage %, timing metrics
   - Overall bug metrics (from health-check-jiras):
     - Total open bugs, opened/closed last 30 days, priority breakdown
   - High-level combined health grade

   **Section 2: Per-Component Health Scorecard**
   - Ranked table of components from best to worst combined health
   - Key metrics per component (BOTH regression AND bug data):
     - Regression triage coverage
     - Average triage time
     - Average resolution time
     - Open bug count (from JIRA)
     - Bug age metrics (from JIRA)
     - Bug flow (opened vs closed, from JIRA)
     - Combined health grade
   - Visual indicators (✅ ⚠️ ❌) for quick assessment

   **Section 3: Components Needing Attention**
   - Prioritized list of components with specific issues from BOTH sources
   - Actionable recommendations for each component:
     - "X open untriaged regressions need triage" (only OPEN, not closed)
       - **IMPORTANT**: Phrase regression triage as a "few hours task", NOT a "sprint"
       - Triaging regressions typically takes a few hours, not an entire 3-week sprint
       - Example: "Triage 5 open regressions (typically a few hours)" ✅
       - Example: "Immediate triage sprint needed" ❌
     - "High bug backlog: X open bugs (Y older than 90 days)" (from JIRA)
     - "Growing bug backlog: +X net bugs in last 30 days" (from JIRA)
     - "Slow regression triage: X hours average"
   - Context for each issue

7. **Offer HTML Report Generation** (AFTER displaying the text report):
   - Ask the user if they would like an interactive HTML report
   - If yes, generate an HTML report combining both data sources
   - Use template from: `plugins/component-health/skills/analyze-regressions/report_template.html`
   - Enhance template to include bug backlog metrics
   - Save report to: `.work/component-health-{release}/health-report.html`
   - Open the report in the user's default browser
   - Display the file path to the user

8. **Error Handling**: Handle common error scenarios

   - Network connectivity issues
   - Invalid release format
   - Missing regression or JIRA data
   - API errors
   - No matches for component filter
   - JIRA authentication issues

## Return Value

The command outputs a **Comprehensive Component Health Report**:

### Overall Health Grade

From combined regression and bug data:

- **Release**: OpenShift version and development window
- **Regression Metrics**:
  - Total regressions: X (Y% triaged)
  - Average triage time: X hours
  - Average resolution time: X hours
  - Open vs closed breakdown
- **Bug Backlog Metrics**:
  - Total open bugs: X across all components
  - Bugs opened/closed in last 30 days
  - Priority distribution
- **Overall Health**: Combined grade (Excellent/Good/Needs Improvement/Poor)

### Per-Component Health Scorecard

Ranked table combining both metrics:

| Component | Regression Triage | Triage Time | Resolution Time | Open Bugs | Bug Age | Health Grade |
|-----------|-------------------|-------------|-----------------|-----------|---------|--------------|
| kube-apiserver | 100.0% | 58 hrs | 144 hrs | 15 | 45d avg | ✅ Excellent |
| etcd | 95.0% | 84 hrs | 192 hrs | 8 | 30d avg | ✅ Good |
| Monitoring | 86.7% | 68 hrs | 156 hrs | 23 | 120d avg | ⚠️ Needs Improvement |

### Components Needing Attention

Prioritized list with actionable items:

```
1. Monitoring (Needs Improvement):
   - 1 open untriaged regression (needs triage)
   - High bug backlog: 23 open bugs (8 older than 90 days)
   - Growing backlog: +5 net bugs in last 30 days
   - Recommendation: Focus on triaging open regression and addressing oldest bugs

2. Example-Component (Poor):
   - 5 open untriaged regressions (urgent triage needed)
   - Slow triage response: 120 hours average
   - Very high bug backlog: 45 open bugs (15 older than 180 days)
   - Recommendation: Triage 5 open regressions (typically a few hours); consider bug backlog cleanup initiative
```

**IMPORTANT**: When listing untriaged regressions:
- **Only list OPEN untriaged regressions** - these are actionable
- **Do NOT recommend triaging closed regressions** - tooling doesn't support retroactive triage
- Calculate actionable count as: `open.total - open.triaged`

### Additional Sections

If requested:
- Detailed regression metrics by component
- Detailed bug breakdowns by status and priority
- Links to Sippy dashboards for regression analysis
- Links to JIRA queries for bug investigation
- Trends compared to previous releases (if available)

## Examples

1. **Analyze team health (recommended)**:

   ```
   /teams:health-check 4.21 --team "API Server"
   ```

   Automatically fetches BOTH data sources for all components owned by the "API Server" team:
   - Looks up all team components from team_component_map.json
   - Fetches regression metrics for all team components
   - Fetches JIRA bug metrics for all team components
   - Provides comprehensive team-level health analysis
   - Shows per-component breakdowns within the team
   - Identifies which team components need attention
   - Use `/teams:list-teams` to see available team names

2. **Analyze specific components (exact match)**:

   ```
   /teams:health-check 4.21 --components Monitoring Etcd
   ```

   Automatically fetches BOTH regression and bug data for Monitoring and Etcd:
   - Compares combined health between the two components
   - Shows regression metrics AND bug backlog for each
   - Identifies which component needs more attention
   - Provides targeted recommendations based on both data sources

3. **Analyze by fuzzy search**:

   ```
   /teams:health-check 4.21 --components network
   ```

   Automatically fetches BOTH data sources for all components containing "network":
   - Finds all networking components (e.g., "Networking / ovn-kubernetes", "Networking / DNS", etc.)
   - Compares combined health across all networking components
   - Shows regression metrics AND bug backlog for each
   - Identifies networking-related quality issues from both sources
   - Provides targeted recommendations

4. **Team analysis with custom JIRA project**:

   ```
   /teams:health-check 4.21 --team "Networking" --project OCPBUGS
   ```

   Analyzes health for the Networking team using bugs from OCPBUGS project

## Arguments

- `$1` (required): Release version
  - Format: "X.Y" (e.g., "4.17", "4.21")
  - Must be a valid OpenShift release number

- `$2+` (required): Filter flags - must provide either --components or --team
  - `--components <search1> [search2 ...]`: Filter by component names using fuzzy search
    - Space-separated list of component search strings
    - Case-insensitive substring matching
    - Each search string matches all components containing that substring
    - Applied to both regression and bug queries
    - Example: "network" matches "Networking / ovn-kubernetes", "Networking / DNS", etc.
    - Example: "kube-" matches "kube-apiserver", "kube-controller-manager", etc.
    - Mutually exclusive with `--team`
    - Required if `--team` is not provided

  - `--team <team-name>`: Filter by team name
    - Looks up all components for the team from team_component_map.json
    - Applied to both regression and bug queries
    - Team-level health analysis with per-component breakdowns
    - Use `/teams:list-teams` to see available team names
    - Team names are case-sensitive
    - Mutually exclusive with `--components`
    - Required if `--components` is not provided

  - `--project <PROJECT>`: JIRA project key (optional)
    - Default: "OCPBUGS"
    - Use alternative project if component bugs are tracked elsewhere
    - Examples: "OCPSTRAT", "OCPQE"

## Prerequisites

1. **Python 3**: Required to run the underlying data fetching scripts

   - Check: `which python3`
   - Version: 3.6 or later

2. **JIRA Authentication**: Environment variables must be configured for bug data

   - `JIRA_URL`: Your JIRA instance URL
   - `JIRA_PERSONAL_TOKEN`: Your JIRA bearer token or personal access token
   - See `/teams:health-check-jiras` for setup instructions

3. **Network Access**: Must be able to reach both component health API and JIRA

   - Ensure HTTPS requests can be made to both services
   - Check firewall and VPN settings if needed

## Notes

- **CRITICAL**: This command AUTOMATICALLY fetches data from TWO sources:
  1. Regression API (via `/teams:health-check-regressions`)
  2. JIRA API (via `/teams:health-check-jiras`)
- Both data sources are REQUIRED and fetched automatically without user prompting
- The analysis is incomplete without both regression and bug data
- Health grades are subjective and intended as guidance, not criticism
- Recommendations focus on actionable items (open untriaged regressions, not closed)
- Infrastructure regressions are automatically filtered from regression counts
- JIRA queries default to open bugs + bugs closed in last 30 days
- HTML reports provide interactive visualizations combining both data sources
- If one data source fails, the command continues with the available data and notes the failure
- For detailed regression data only, use `/teams:list-regressions`
- For detailed JIRA data only, use `/teams:list-jiras`
- This command provides the most comprehensive view by combining both sources

## See Also

- Related Command: `/teams:health-check-regressions` (regression metrics)
- Related Command: `/teams:health-check-jiras` (bug backlog metrics)
- Related Command: `/teams:list-regressions` (raw regression data)
- Related Command: `/teams:list-jiras` (raw JIRA data)
- Skill Documentation: `plugins/component-health/skills/analyze-regressions/SKILL.md`
- Script: `plugins/component-health/skills/list-regressions/list_regressions.py`
- Script: `plugins/component-health/skills/health-check-jiras/summarize_jiras.py`
