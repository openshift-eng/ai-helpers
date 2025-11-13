---
description: Analyze and grade component health based on regression and JIRA bug metrics
argument-hint: <release> [--components comp1 comp2 ...] [--project JIRAPROJECT]
---

## Name

component-health:analyze

## Synopsis

```
/component-health:analyze <release> [--components comp1 comp2 ...] [--project JIRAPROJECT]
```

## Description

The `component-health:analyze` command provides comprehensive component health analysis for a specified OpenShift release by combining regression management metrics with JIRA bug backlog data. It evaluates component health based on:

1. **Regression Management**: How well components are managing test regressions
   - Triage coverage (% of regressions triaged to JIRA bugs)
   - Triage timeliness (average time from detection to triage)
   - Resolution speed (average time from detection to closure)

2. **Bug Backlog Health**: Current state of open bugs for components
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

1. **Parse Arguments**: Extract release version and optional filters from arguments

   - Release format: "X.Y" (e.g., "4.17", "4.21")
   - Optional filters:
     - `--components`: Space-separated list of component search strings (fuzzy match)
     - `--project`: JIRA project key (default: "OCPBUGS")

2. **Resolve Component Names**: Use fuzzy matching to find actual component names

   - Run list_components.py to get all available components:
     ```bash
     python3 plugins/component-health/skills/list-components/list_components.py --release <release>
     ```
   - If `--components` was provided:
     - For each search string, find all components containing that string (case-insensitive)
     - Combine all matches into a single list
     - Remove duplicates
     - If no matches found for a search string, warn the user and show available components
   - If `--components` was NOT provided:
     - Use all available components from the list

3. **Fetch Regression Summary**: Call the summarize-regressions command

   - Execute: `/component-health:summarize-regressions <release> [--components ...]`
   - Pass resolved component names
   - Extract regression metrics:
     - Total regressions, triage percentages, timing metrics
     - Per-component breakdowns
     - Open vs closed regression counts
   - Note development window dates for context

4. **Fetch JIRA Bug Summary**: Call the summarize-jiras command for each component

   - For each resolved component name:
     - Execute: `/component-health:summarize-jiras --project <project> --component "<component>"`
     - Note: Must iterate over components because JIRA queries can be too large otherwise
   - Aggregate bug metrics:
     - Total open bugs by component
     - Bug age distribution
     - Opened vs closed in last 30 days
     - Priority breakdowns

5. **Calculate Combined Health Grades**: Analyze both regression and bug data

   **For each component, grade based on:**

   a. **Regression Health** (from summarize-regressions):
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

   b. **Bug Backlog Health** (from summarize-jiras):
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

6. **Display Overall Health Report**: Present comprehensive analysis

   - Show which components were matched (if fuzzy search was used)

   **Section 1: Overall Release Health**
   - Release version and development window
   - Overall regression metrics (from summarize-regressions)
   - Overall bug metrics (from summarize-jiras)
   - High-level health grade

   **Section 2: Per-Component Health Scorecard**
   - Ranked table of components from best to worst health
   - Key metrics per component:
     - Regression triage coverage
     - Average triage time
     - Average resolution time
     - Open bug count
     - Bug age metrics
     - Combined health grade
   - Visual indicators (✅ ⚠️ ❌) for quick assessment

   **Section 3: Components Needing Attention**
   - Prioritized list of components with specific issues
   - Actionable recommendations for each component:
     - "X open untriaged regressions need triage" (only OPEN, not closed)
     - "High bug backlog: X open bugs (Y older than 90 days)"
     - "Growing bug backlog: +X net bugs in last 30 days"
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
   - Recommendation: Immediate triage sprint needed; consider bug backlog cleanup initiative
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

1. **Analyze overall component health for a release**:

   ```
   /component-health:analyze 4.17
   ```

   Generates comprehensive health report for release 4.17:
   - Regression management metrics
   - JIRA bug backlog metrics
   - Combined health grades
   - Prioritized recommendations

2. **Analyze specific components (exact match)**:

   ```
   /component-health:analyze 4.21 --components Monitoring Etcd
   ```

   Focuses analysis on Monitoring and Etcd components:
   - Compares health between the two
   - Identifies which needs more attention
   - Provides targeted recommendations

3. **Analyze by fuzzy search**:

   ```
   /component-health:analyze 4.21 --components network
   ```

   Analyzes all components containing "network" (e.g., "Networking / ovn-kubernetes", "Networking / DNS", etc.):
   - Compares health across all networking components
   - Identifies networking-related quality issues
   - Provides targeted recommendations

4. **Analyze with custom JIRA project**:

   ```
   /component-health:analyze 4.21 --project OCPSTRAT
   ```

   Analyzes health using bugs from OCPSTRAT project instead of default OCPBUGS.

5. **In-development release analysis**:

   ```
   /component-health:analyze 4.21
   ```

   Analyzes health for an in-development release:
   - Shows current regression management state
   - Tracks bug flow trends
   - Identifies areas to focus on before GA

## Arguments

- `$1` (required): Release version
  - Format: "X.Y" (e.g., "4.17", "4.21")
  - Must be a valid OpenShift release number

- `$2+` (optional): Filter flags
  - `--components <search1> [search2 ...]`: Filter by component names using fuzzy search
    - Space-separated list of component search strings
    - Case-insensitive substring matching
    - Each search string matches all components containing that substring
    - If no components provided, all components are analyzed
    - Applied to both regression and bug queries
    - Example: "network" matches "Networking / ovn-kubernetes", "Networking / DNS", etc.
    - Example: "kube-" matches "kube-apiserver", "kube-controller-manager", etc.

  - `--project <PROJECT>`: JIRA project key
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
   - See `/component-health:summarize-jiras` for setup instructions

3. **Network Access**: Must be able to reach both component health API and JIRA

   - Ensure HTTPS requests can be made to both services
   - Check firewall and VPN settings if needed

## Notes

- This command combines data from two sources: regression API and JIRA
- Health grades are subjective and intended as guidance, not criticism
- Recommendations focus on actionable items (open untriaged regressions, not closed)
- Infrastructure regressions are automatically filtered from regression counts
- JIRA queries default to open bugs + bugs closed in last 30 days
- HTML reports provide interactive visualizations for better insights
- The command internally uses:
  - `/component-health:summarize-regressions` for regression data
  - `/component-health:summarize-jiras` for bug backlog data
- For detailed regression data, use `/component-health:list-regressions`
- For detailed JIRA data, use `/component-health:list-jiras`
- Combined analysis provides holistic view of component quality

## See Also

- Related Command: `/component-health:summarize-regressions` (regression metrics)
- Related Command: `/component-health:summarize-jiras` (bug backlog metrics)
- Related Command: `/component-health:list-regressions` (raw regression data)
- Related Command: `/component-health:list-jiras` (raw JIRA data)
- Skill Documentation: `plugins/component-health/skills/analyze-regressions/SKILL.md`
- Script: `plugins/component-health/skills/list-regressions/list_regressions.py`
- Script: `plugins/component-health/skills/summarize-jiras/summarize_jiras.py`
