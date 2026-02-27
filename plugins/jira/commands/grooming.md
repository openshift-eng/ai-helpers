---
description: Analyze new bugs and cards added over a time period and generate grooming meeting agenda
argument-hint: "[project-filter] [time-period] [--component component-name] [--label label-name] [--type issue-type] [--status status] [--story-points]"
---

## Name
jira:grooming

## Synopsis
```
/jira:grooming [project-filter] [time-period] [--component component-name] [--label label-name] [--type issue-type] [--status status] [--story-points]
```

## Description
The `jira:grooming` command helps teams prepare for backlog grooming meetings. It automatically collects bugs and user stories created within a specified time period OR assigned to a specific sprint, analyzes their priority, complexity, and dependencies, and generates structured grooming meeting agendas.

This command is particularly useful for:
- Backlog organization before sprint planning
- Sprint-specific grooming sessions
- Sprint-specific grooming sessions with story point summaries
- Sprint retrospectives analyzing completed work
- Regular requirement grooming meetings
- Priority assessment of new bugs
- Technical debt organization and planning

## Key Features

- **Automated Data Collection** – Collect and categorize issues within specified time periods or sprints by type (Bug, Story, Task, Epic), extract key information (priority, components, labels), and identify unassigned or incomplete issues.

- **Story Point Analysis** – When `--story-points` flag is used, extract and analyze story points for all issues, calculate totals by status, priority, and type, and provide velocity metrics for sprint retrospectives.

- **Status Filtering** – Filter issues by status (e.g., Closed, Done, In Progress, Open) using the `--status` flag to focus on specific workflow states for sprint reviews or retrospectives.

- **Intelligent Analysis** – Evaluate issue complexity based on historical data, identify related or duplicate issues, analyze business value and technical impact, and detect potential dependencies.

- **Agenda Generation** – Build a structured, actionable meeting outline organized by priority and type, with discussion points, decision recommendations, estimation references, and risk alerts.

## Implementation

The `jira:grooming` command runs in three main phases:

### 🧩 Phase 1: Data Collection
- Automatically queries JIRA for issues based on the provided time range or sprint name:
  - **Time range mode**: Filters issues by creation date within the specified period (e.g., `last-week`, `2024-01-01:2024-01-31`)
  - **Sprint mode**: Filters issues by JIRA Sprint without time constraints (e.g., `"OTA 277"`)
  - Sprint detection: If the time-period parameter doesn't match known time range formats, it's treated as a sprint name
- Supports complex JQL filters, including multi-project, component-based, label-based, issue-type and status filtering.
- Extracts key fields such as title, type, priority, component, reporter, story points and assignee.
- Detects related or duplicate issues to provide better context.

### 🧠 Phase 2: Analysis & Processing
- Groups collected issues by type and priority (e.g., Critical Bugs, High Priority Stories).
- When `--story-points` flag is used:
  - Calculates total story points by status (Closed, In Progress, Open, etc.)
  - Calculates story points by priority and type
  - Identifies issues missing story point estimates
  - Computes velocity metrics for sprint retrospectives
- Identifies incomplete or unclear issues that need clarification.
- Estimates complexity and effort based on similar historical data.
- Highlights risks, dependencies, and recommended next actions.

### 📋 Phase 3: Report Generation
- Automatically generates a **structured grooming meeting agenda** in Markdown format.
- Includes discussion points, decision checklists, and action items.
- When `--story-points` flag is used, includes:
  - Story point summary section with totals by status
  - Velocity metrics and completion percentages
  - Breakdown by priority and issue type
  - List of issues missing story point estimates
- Saves report to `.work/jira/grooming/report-{timestamp}.md` and displays file path for easy opening.
- Output can be copied directly into Confluence or shared with the team.

## Usage Examples

1. **Single project weekly review**:
   ```
   /jira:grooming OCPSTRAT last-week
   ```

2. **Multiple OpenShift projects**:
   ```
   /jira:grooming "OCPSTRAT,OCPBUGS,HOSTEDCP" last-2-weeks
   ```

3. **Filter by component**:
   ```
   /jira:grooming OCPSTRAT last-week --component "Control Plane"
   ```

4. **Custom date range**:
   ```
   /jira:grooming OCPBUGS 2024-10-01:2024-10-15
   ```

5. **Filter by label**:
   ```
   /jira:grooming OCPSTRAT last-week --label "technical-debt"
   ```

6. **Combine component and label filters**:
   ```
   /jira:grooming OCPSTRAT last-week --component "Control Plane" --label "performance"
   ```

7. **Query sprint issues with component filter**:
   ```bash
   /jira:grooming OCPBUGS "OTA 277" --component "Cluster Version Operator"
   ```

8. **Filter by issue type**:
   ```
   /jira:grooming OCPSTRAT last-week --type Bug
   ```

9. **Filter by multiple issue types**:
   ```
   /jira:grooming OCPSTRAT last-week --type "Bug,Epic"
   ```

10. **Combine all filters**:
    ```
    /jira:grooming OCPSTRAT last-week --component "Control Plane" --label "performance" --type Story
    ```

11. **Sprint retrospective with closed issues and story points**:
   ```bash
   /jira:grooming "CORENET" "Sprint 276" --status Closed --story-points
   ```

12. **Combine Label and status filters**:
    ```bash
    /jira:grooming OCPBUGS last-week --label "performance" --status "NEW"


## Output Format

### Grooming Meeting Agenda

The command outputs a ready-to-use Markdown document that can be copied into Confluence or shared with your team.

```markdown
# Backlog Grooming Agenda
**Project**: [project-key] | **Period**: [time-period] | **New Issues**: [count]

## 📊 Summary

## 📊 Story Point Summary (when --story-points is used)

**Total Story Points**: 89

### By Status
- **Closed**: 55 points (61.8%)
- **In Progress**: 21 points (23.6%)
- **Open**: 13 points (14.6%)

### By Type
- **Story**: 55 points
- **Bug**: 21 points
- **Task**: 13 points

### Issues Missing Story Points (3)
- PROJ-1240 - Performance optimization needed
- PROJ-1241 - Update documentation
- PROJ-1242 - Refactor authentication module

## 🚨 Critical Issues ([count])
- **[PROJ-1234]** System crashes on login - *Critical, needs immediate attention*
- **[PROJ-1235]** Performance degradation - *High, assign to team lead*

## 📈 High Priority Stories ([count])  
- **[PROJ-1236]** User profile enhancement - *Ready for sprint*
- **[PROJ-1237]** Payment integration - *Needs design review*

## 📝 Needs Clarification ([count])
- **[PROJ-1238]** Missing acceptance criteria
- **[PROJ-1239]** Unclear technical requirements

## 📋 Action Items
- [ ] Assign PROJ-1234 to senior developer (immediate)
- [ ] Schedule design review for PROJ-1237 (this week)
- [ ] Clarify requirements for PROJ-1238,1239 (before next grooming)
- [ ] Add story point estimates to 3 issues
```

## Configuration

### Default Query Configuration (.jira-grooming.json)
```json
{
  "defaultProjects": ["OCPSTRAT", "OCPBUGS"],
  "defaultLabels": [],
  "priorityMapping": {
    "Critical": "🚨 Critical",
    "High": "📈 High Priority"
  },
  "estimationReference": {
    "enableHistoricalComparison": true
  }
}
```

## Arguments

- **$1 – project-filter**  
  JIRA project selector. Supports single or multiple projects (comma-separated).  
  Examples:
    - `OCPSTRAT`
    - `"OCPSTRAT,OCPBUGS,HOSTEDCP"`
    - `"OpenShift Virtualization,Red Hat OpenShift Control Planes"`  
      Default: read from configuration file

- **$2 – time-period**
  Time range for issue collection OR sprint name.
  Options:
  - Time ranges: `last-week` | `last-2-weeks` | `last-month` | `YYYY-MM-DD:YYYY-MM-DD`
  - Sprint name: Any string that doesn't match time range formats (e.g., `"OTA 277"`)
  Default: `last-week`

  **Behavior:**
  - If a time range is provided, filters issues by creation date within that range
  - If a sprint name is provided, filters issues by JIRA Sprint WITHOUT applying time range constraints

- **--component** *(optional)*
  Filter by JIRA component (single or comma-separated).
  Examples:
    - `--component "Networking"`
    - `--component "Control Plane,Storage"`

- **--label** *(optional)*
  Filter by JIRA labels (single or comma-separated).
  Examples:
    - `--label "technical-debt"`
    - `--label "performance,security"`

- **--type** *(optional)*
  Filter by JIRA issue type (single or comma-separated).
  Examples:
    - `--type Bug`
    - `--type "Epic,Story"`
    - `--type "Bug,Task,Feature"`

  Common issue types: `Bug`, `Story`, `Task`, `Epic`, `Feature`, `Sub-task`

- **--status** *(optional)*
  Filter by JIRA issue status (single or comma-separated).
  Examples:
    - `--status Closed`
    - `--status "POST,ON_QA"`
    - `--status "In Progress"`

- **--story-points** *(optional)*
  Include story point analysis in the grooming report.
  When this flag is present:
    - Extracts story points from JIRA issues
    - Calculates total story points by status, and type
    - Identifies issues missing story point estimates
    - Generates velocity metrics for sprint retrospectives
    - Includes story point summary section in the report
    
## Return Value
- **Format**: Markdown report with ready-to-use grooming agenda
- **Location**: `.work/jira/grooming/report-{timestamp}.md`
- **Content**: Structured agenda with summary, categorized issues (Critical Issues, High Priority Stories, Needs Clarification), and action items
- **Additional sections** (when `--story-points` used): Story point summary with totals by status, type, and missing estimates
- **Output**: File path displayed in chat for easy opening

## See Also
- `jira:status-rollup` - Status rollup reports
- `jira:solve` - Issue solution generation
