---
description: List all teams from the team component mapping
argument-hint: ""
---

## Name

component-health:list-teams

## Synopsis

```
/component-health:list-teams
```

## Description

The `component-health:list-teams` command displays all team names from the team component mapping.

This command is useful for:

- Discovering available teams
- Validating team names before using them in other commands
- Finding team names for use with `/component-health:list-components --team`

## Implementation

1. **Verify Working Directory**
   - Ensure you are in the repository root directory

2. **Run the list-teams Script**
   - `python3 plugins/component-health/skills/list-teams/list_teams.py`

3. **Parse and Display Results**
   - Script outputs JSON with total_teams and teams array

## Examples

1. **List all teams**:
   ```
   /component-health:list-teams
   ```

## Arguments

None

## Prerequisites

- Python 3.6 or later

## Notes

- Team names are case-sensitive
- Returns only teams with OCPBUGS components
- Typical count: ~29 teams
- Reads from committed mapping file (no download needed)

## See Also

- Skill: `plugins/component-health/skills/list-teams/SKILL.md`
- Related Command: `/component-health:list-components`
- Mapping File: `plugins/component-health/team_component_map.json`
