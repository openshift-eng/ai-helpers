---
description: Show Node team scope, responsibilities, component ownership, and plugin routing
argument-hint: "[--sub-team core|devices|kueue]"
---

## Name
node-team:overview

## Synopsis
```text
/node-team:overview [--sub-team core|devices|kueue]
```

## Description

Displays a comprehensive overview of the OpenShift Node team: what the team
owns, its responsibilities, component and repo mappings, sub-team structure,
ceremonies, upstream community involvement, active sprints, and which
specialized plugins handle which domain.

This is the entry point for understanding the Node team's scope and navigating
to the right tool for a given task.

## Implementation

1. **Read shared references:**
   - Team mission, responsibilities, ceremonies, Slack channels, customer
     support tools, key links, and plugin routing from
     [shared/team-info.md](../skills/node/references/shared/team-info.md)
   - Component list and repo mappings from
     [shared/components.md](../skills/node/references/shared/components.md)
   - Sub-team assignments from the sub-teams table in `shared/components.md`
   - Sprint and board info from
     [jira.md](../skills/node/references/jira.md)
   - OCP-to-K8s version mapping from
     [shared/version-map.md](../skills/node/references/shared/version-map.md)

2. **If `--sub-team` is specified**, filter to that sub-team's components.

3. **Present a structured summary** with these sections from the references:
   - Team Mission and Responsibilities (from `team-info.md`)
   - Component Ownership table (from `components.md`)
   - Sub-teams table (from `components.md`). If roster files exist at
     `~/.node-assistant/team-roster-{core,dra}.json`, include member count
     per sub-team. There is no separate roster file for the Kueue sub-team;
     its members are tracked under Core.
   - Ceremonies and sprint cadence (from `team-info.md`)
   - Upstream Communities (from `team-info.md`)
   - Slack Channels and Mailing Lists (from `team-info.md`)
   - Customer Support Tools (from `team-info.md`)
   - Active Sprints: query the Jira Agile API (board 11478) for active
     sprints per jira.md. List sprint names and dates.
   - Version Mapping: show the current OCP-to-K8s version mapping from
     `shared/version-map.md` for the latest 2-3 OCP releases.
   - Plugin Routing table (from `team-info.md`)
   - Key Links (from `team-info.md`)

## Return Value

Formatted text summary of team mission, responsibilities, components,
sub-teams, ceremonies, upstream communities, active sprints, version mapping,
plugin routing, and key links.

## Examples

1. **Full team overview**:
   ```text
   /node-team:overview
   ```

2. **DRA/Devices sub-team only**:
   ```text
   /node-team:overview --sub-team devices
   ```

3. **Kueue sub-team only**:
   ```text
   /node-team:overview --sub-team kueue
   ```

## Arguments

- `--sub-team <name>`: Filter to a specific sub-team (`core`, `devices`, or
  `kueue`). Optional; shows all components when omitted.
