---
description: List all teams from the team component mapping
argument-hint: ""
---

## Name

teams:list-teams

## Synopsis

```
/teams:list-teams
```

## Description

The `teams:list-teams` command displays all team names from the team component mapping.

This command is useful for:

- Discovering available teams
- Validating team names before using them in other commands
- Finding team names for use with `/teams:list-components --team`

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
   /teams:list-teams
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

- Skill: `plugins/component-health/skills/list-teams/SKILL.md`
- Related Command: `/teams:list-components`
- Mapping File: `plugins/component-health/team_component_map.json`
- Generator Script: `plugins/component-health/generate_team_component_map.py`
