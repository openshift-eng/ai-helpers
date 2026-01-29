---
name: List Teams
description: List all teams from the team component mapping
---

# List Teams

This skill provides functionality to list all team names from the team component mapping.

## When to Use This Skill

Use this skill when you need to:

- Display all available team names
- Validate team names before using them in other commands
- Get a complete list of teams with OCPBUGS components
- Count how many teams are in the system
- Find team names for team-based analysis

## Prerequisites

1. **Python 3 Installation**
   - Check if installed: `which python3`
   - Python 3.6 or later is required

2. **Team Component Mapping File**
   - The mapping file should be in the repository
   - Located at: `plugins/teams/team_component_map.json`
   - This file is committed to the repository

## Implementation Steps

### Step 1: Run the list-teams Script

```bash
python3 plugins/teams/skills/list-teams/list_teams.py
```

### Step 2: Process the Output

The script outputs JSON:

```json
{
  "total_teams": 29,
  "teams": [
    "API Server",
    "Authentication",
    "..."
  ]
}
```

## Examples

### Example 1: List All Teams

```bash
python3 plugins/teams/skills/list-teams/list_teams.py
```

### Example 2: Count Teams

```bash
python3 plugins/teams/skills/list-teams/list_teams.py | jq '.total_teams'
```

## Notes

- Team names are extracted from the committed mapping file
- Team names are case-sensitive
- Teams are returned in alphabetical order
- Very fast execution (< 100ms)
- Typical count: ~29 teams (teams with OCPBUGS components only)

## Data Source

The team and component mapping data originates from:
- **Source**: https://gitlab.cee.redhat.com/hybrid-platforms/org
- **Access**: Requires Red Hat VPN connection
- **Privacy**: The full org data is considered somewhat private, so this project extracts only the team and component mapping

**If data looks wrong or missing**:
1. Submit a PR to https://gitlab.cee.redhat.com/hybrid-platforms/org to correct the source data
2. After the PR merges, regenerate the mapping file in this repository:
   ```
   python3 plugins/teams/generate_team_component_map.py
   ```
3. Commit the updated `team_component_map.json` file

## See Also

- Related Skill: `plugins/teams/skills/list-components/SKILL.md`
- Related Command: `/teams:list-teams`
- Mapping File: `plugins/teams/team_component_map.json`
- Generator Script: `plugins/teams/generate_team_component_map.py`
