---
description: Show Node team component ownership, repos, sub-teams, and specialized plugin routing
argument-hint: "[--sub-team core|dra]"
---

## Name
node-team:overview

## Synopsis
```text
/node-team:overview [--sub-team core|dra]
```

## Description

Displays a structured overview of the OpenShift Node team: which components
the team owns, which repos map to each component, sub-team assignments, active
sprint info, and which specialized plugins handle which domain.

This is the entry point for understanding the Node team's scope and navigating
to the right tool for a given task.

## Implementation

1. Read the component list and repo mappings from
   [shared/components.md](../skills/node/references/shared/components.md).
2. Read sprint and board info from
   [jira.md](../skills/node/references/jira.md) (boards section, sprint
   naming conventions).
3. If `--sub-team` is specified, filter to that sub-team's components using
   the sub-teams table in `shared/components.md`.
4. Present a structured summary:
   - Component ownership table (component, downstream fork, sub-team)
   - Active sprint names (query the Jira Agile API per the jira.md reference)
   - Specialized plugin routing:
     - CVE triage: `/node-cve:triage`
     - General development/deployment/debugging: `node-team:node` skill
5. If a team roster file exists at `~/.node-assistant/team-roster-{core,dra}.json`,
   include a member count per sub-team.

## Return Value

- Formatted text summary of team components, repos, sub-teams, sprint info,
  and plugin routing

## Examples

1. **Full team overview**:
   ```text
   /node-team:overview
   ```

2. **DRA/Devices sub-team only**:
   ```text
   /node-team:overview --sub-team dra
   ```

## Arguments

- `--sub-team <name>`: Filter to a specific sub-team (`core` or `dra`).
  Optional; shows all components when omitted.
