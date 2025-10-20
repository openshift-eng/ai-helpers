---
description: Analyze new bugs and cards added over a time period and generate grooming meeting agenda
argument-hint: [project-filter] [time-period] [--component component-name] [--label label-name]
---

## Name
jira:grooming

## Synopsis
```
/jira:grooming [project-filter] [time-period] [--component component-name] [--label label-name]
```

## Description
The `jira:grooming` command helps teams prepare for backlog grooming meetings. It automatically collects bugs and user stories created within a specified time period, analyzes their priority, complexity, and dependencies, and generates structured grooming meeting agendas.

This command is particularly useful for:
- Backlog organization before sprint planning
- Regular requirement grooming meetings
- Priority assessment of new bugs
- Technical debt organization and planning

## Key Features

- **Automated Data Collection** – Collect and categorize new issues within specified time periods by type (Bug, Story, Task, Epic), extract key information (priority, components, labels), and identify unassigned or incomplete issues.

- **Intelligent Analysis** – Evaluate issue complexity based on historical data, identify related or duplicate issues, analyze business value and technical impact, and detect potential dependencies.

- **Agenda Generation** – Build a structured, actionable meeting outline organized by priority and type, with discussion points, decision recommendations, estimation references, and risk alerts.

## Implementation

The `jira:grooming` command runs in three main phases:

### 🧩 Phase 1: Data Collection
- Automatically queries JIRA for new issues within the selected projects and time range.
- Supports complex JQL filters, including multi-project, component-based, and label-based queries.
- Extracts key fields such as title, type, priority, component, reporter, and assignee.
- Detects related or duplicate issues to provide better context.

### 🧠 Phase 2: Analysis & Processing
- Groups collected issues by type and priority (e.g., Critical Bugs, High Priority Stories).
- Identifies incomplete or unclear issues that need clarification.
- Estimates complexity and effort based on similar historical data.
- Highlights risks, dependencies, and recommended next actions.

### 📋 Phase 3: Report Generation
- Automatically generates a **structured grooming meeting agenda** in Markdown format.
- Includes discussion points, decision checklists, and action items.
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

## Output Format

### Grooming Meeting Agenda

The command outputs a ready-to-use Markdown document that can be copied into Confluence or shared with your team.

```markdown
# Backlog Grooming Agenda
**Project**: [project-key] | **Period**: [time-period] | **New Issues**: [count]

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
  Time range for issue collection.  
  Options: `last-week` | `last-2-weeks` | `last-month` | `YYYY-MM-DD:YYYY-MM-DD`  
  Default: `last-week`

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

## Return Value
- **Markdown Report**: Ready-to-use grooming agenda with categorized issues and action items

## See Also
- `jira:status-rollup` - Status rollup reports
- `jira:solve` - Issue solution generation
