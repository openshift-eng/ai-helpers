---
description: List all OCPBUGS components, optionally filtered by team
argument-hint: "[--team <team-name>]"
---

## Name

component-health:list-components

## Synopsis

```
/component-health:list-components [--team <team-name>]
```

## Description

The `component-health:list-components` command displays all OCPBUGS component names, with optional filtering by team.

This command is useful for:

- Discovering available OCPBUGS components
- Discovering OCPBUGS components for a specific team
- Validating OCPBUGS component names before filing or querying bugs
- Understanding which components are tracked in OCPBUGS per team
- Finding exact component names for use in JIRA queries

## Implementation

1. **Verify Working Directory**
   - Ensure you are in the repository root directory
   - Run `pwd` to confirm

2. **Run the list-components Script**
   - For all components: `python3 plugins/component-health/skills/list-components/list_components.py`
   - For team components: `python3 plugins/component-health/skills/list-components/list_components.py --team "API Server"`
   - Team names must match exactly (case-sensitive)

3. **Parse and Display Results**
   - Script outputs JSON with total_components, components array, and optional team field

## Examples

1. **List all OCPBUGS components**:
   ```
   /component-health:list-components
   ```

2. **List OCPBUGS components for a specific team**:
   ```
   /component-health:list-components --team "API Server"
   ```

## Arguments

- `--team` (optional): Filter components by team name
  - Use `/component-health:list-teams` to get available team names
  - Example: `--team "API Server"`

## Prerequisites

- Python 3.6 or later

## Notes

- Only OCPBUGS components are returned
- Team names are case-sensitive - use `/component-health:list-teams` to get correct names
- Typical count: ~87 total components across 29 teams
- Reads from committed mapping file (no download needed)

## Data Source

The team and component mapping data originates from:
- **Source**: https://gitlab.cee.redhat.com/hybrid-platforms/org
- **Access**: Requires Red Hat VPN connection
- **Privacy**: The full org data is considered somewhat private, so this project extracts only the team and component mapping

**If data looks wrong or missing**:
1. Submit a PR to https://gitlab.cee.redhat.com/hybrid-platforms/org to correct the source data
2. After the PR merges, regenerate the mapping file in this repository:
   ```
   python3 plugins/component-health/generate_team_component_map.py
   ```
3. Commit the updated `team_component_map.json` file

## See Also

- Skill: `plugins/component-health/skills/list-components/SKILL.md`
- Related Command: `/component-health:list-teams`
- Mapping File: `plugins/component-health/team_component_map.json`
- Generator Script: `plugins/component-health/generate_team_component_map.py`
