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
   - Located at: `plugins/component-health/team_component_map.json`
   - This file is committed to the repository

## Implementation Steps

### Step 1: Run the list-teams Script

```bash
python3 plugins/component-health/skills/list-teams/list_teams.py
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
python3 plugins/component-health/skills/list-teams/list_teams.py
```

### Example 2: Count Teams

```bash
python3 plugins/component-health/skills/list-teams/list_teams.py | jq '.total_teams'
```

## Notes

- Team names are extracted from the committed mapping file
- Team names are case-sensitive
- Teams are returned in alphabetical order
- Very fast execution (< 100ms)
- Typical count: ~29 teams (teams with OCPBUGS components only)

## See Also

- Related Skill: `plugins/component-health/skills/list-components/SKILL.md`
- Related Command: `/component-health:list-teams`
- Mapping File: `plugins/component-health/team_component_map.json`
