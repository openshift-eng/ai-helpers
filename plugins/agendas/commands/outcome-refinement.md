---
description: Analyze the list of JIRA outcome issues to prepare an outcome refinement meeting agenda.
---

## Name
agendas:outcome-refinement

## Synopsis
```
/agendas:outcome-refinement
```

## Description
The `agendas:outcome-refinement` command helps analyze the outcome issues and should be used to assist in preparting for outcome refinement collaboration sessions. It automatically checks for common issues that we observe that indicate follow-up actions are needed by humans. This command generates structured outcome refinement meeting agenda.

## Examples
```bash
/agendas:outcome-refinement
```

## Implementation

The `agendas:outcome-refinement` command runs in three main phases:

### 🧩 Phase 1: Data Collection
- Queries JIRA for outcome issues in the OCPSTRAT project that require work to be done, meaning the issue status is not closed or release pending.

### 🧠 Phase 2: Analysis & Processing
- Flags routine hygiene issues to resolve with follow up actions.
- People assignments (Assignee, Architect, QA Contact, Doc Contact) should all be filled in.
- Outcome issues should only have Feature issue types as child issues.
- Identified if child issue are actively being worked on but the outcome doesn't represent the right status.
- Shows how long an outcome issue has been open and their corresponding priority.
- Identifies incomplete or unclear issues that need clarification.
- If and outcome issue has child issues that are actively being updated but the outcome has been open for a more than a year we should discuss the scope.
- If an outcome has stayed in the new status for over a year, we should probably discuss whether it's a real outcome priority.
- Looking at all the OCPSTRAT outcomes, if any specific component is commonly assigned to the child feature issues, this indicates an team overload, so we should discuss this.
- Highlights risks, dependencies, and recommended next actions.

### 📋 Phase 3: Report Generation
- Automatically generates a **structured outcome refinement meeting agenda** in Markdown format.
- Includes discussion points, decision checklists, and action items.
- Saves report to `.work/agendas/outcome-refinement/report-{timestamp}.md` and displays file path for easy opening.
- Output can be copied directly into Confluence or shared with the team.

## Output Format

### Outcome Refinement Meeting Agenda

The command outputs a ready-to-use Markdown document that can be copied into Confluence or shared with your team.

```markdown
# Outcome Refinement Agenda
**Outcome Issues**: [count]

## 🚨 Critical Issues ([count])
- **[OCPSTRAT-1234]** BGP integration with public clouds - *Critical, needs immediate attention*
- **[OCPSTRAT-1235]** Consistent Ingress/Egress into OpenShift clusters across providers - *High, assign to team lead*

## 📝 Needs Clarification ([count])
- **[OCPSTRAT-1238]** Missing architect
- **[OCPSTRAT-1239]** Component team is overloaded
- **[OCPSTRAT-1240]** Outcome has been open for years with no delivery

## 📋 Action Items
- [ ] Set architect for OCPSTRAT-1236 to SME architect (immediate)
- [ ] Schedule review for OCPSTRAT-1236 (this week)
```

## Return Value
- **Format**: Markdown report with ready-to-use outcome refinement agenda
- **Location**: `.work/agendas/outcome-refinement/report-{timestamp}.md`
- **Content**: Structured agenda with categorized issues (Critical Issues, Needs Clarification) and action items
- **Output**: File path displayed in chat for easy opening
