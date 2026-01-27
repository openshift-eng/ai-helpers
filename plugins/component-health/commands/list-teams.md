---
description: List all teams from the org data cache
argument-hint: ""
---

## Name

component-health:list-teams

## Synopsis

```
/component-health:list-teams
```

## Description

The `component-health:list-teams` command displays all team names from the local org data cache.

This command is useful for:

- Discovering available teams in the organization
- Validating team names before using them in queries or analysis
- Understanding the organizational structure
- Generating team lists for reports
- Finding team names for team-based analysis

## Implementation

1. **Ensure Cache is Available and Fresh**

   - **Working Directory**: Ensure you are in the repository root directory
   - Verify working directory: Run `pwd` and confirm you are in the `ai-helpers` repository root
   - **IMPORTANT**: Before running list-teams, always ensure cache is fresh by running org-data-cache:
     ```bash
     python3 plugins/component-health/skills/org-data-cache/org_data_cache.py
     ```
   - This will:
     - Create cache if it doesn't exist
     - Update cache if it's older than 7 days
     - Do nothing if cache is already fresh
     - Takes only a few seconds if cache is fresh

2. **Run the list-teams Script**

   - After ensuring cache is available, run the script:
     ```bash
     python3 plugins/component-health/skills/list-teams/list_teams.py
     ```
   - The script will:
     - Read from the org data cache
     - Extract team names from `.lookups.teams`
     - Output JSON with total count and team list

3. **Parse and Display Results**

   - The script outputs JSON with:
     - `total_teams`: Number of teams found
     - `teams`: Array of team names (alphabetically sorted)
   - Display results in a user-friendly format:
     ```
     Found 155 teams:

     1. ACS Automation
     2. ACS Cloud Service
     3. API Server
     ...
     ```

4. **Error Handling**: The script handles common error scenarios

   - Cache file missing - you should have run org-data-cache first (step 1)
   - Cache file corrupted - suggests deleting and re-running org-data-cache
   - Missing teams data - verifies cache structure

## Return Value

The command outputs a **Team List** with the following information:

### Team Summary

- **Total Teams**: Count of teams found (typically ~155)
- **Cache Age**: How old the cache is (if relevant)

### Team List

An alphabetically sorted list of all teams, for example:

```
1. ACS Automation
2. ACS Cloud Service
3. ACS Collector
4. ACS Core Workflows
5. ACS Install
6. ACS Scanner
7. ACS Sensor & Ecosystem
8. ACS UI
9. API Server
10. ARO Cluster Lifecycle East
...
```

## Examples

1. **List all teams**:

   ```
   /component-health:list-teams
   ```

   Displays all teams from the org data cache.

## Arguments

None

## Prerequisites

1. **Python 3**: Required to run the script

   - Check: `which python3`
   - Version: 3.6 or later

2. **Google Cloud CLI (gsutil)**: Required for initial cache download

   - Check: `which gsutil`
   - Installation: https://cloud.google.com/sdk/docs/install
   - Only needed if cache is missing or stale

3. **jq**: Required for JSON parsing

   - Check: `which jq`
   - Most systems have this installed by default

## Notes

- Team names are extracted from `.lookups.teams` keys
- Team names are case-sensitive
- Team names are returned in alphabetical order
- The cache is automatically refreshed if older than 7 days
- Team names can be used for org structure analysis and team-based queries
- The cache is stored at `~/.cache/ai-helpers/org_data.json`
- Typical count: ~155 teams (may vary as teams are added/removed)

## See Also

- Skill Documentation: `plugins/component-health/skills/list-teams/SKILL.md`
- Script: `plugins/component-health/skills/list-teams/list_teams.py`
- Related Skill: `plugins/component-health/skills/org-data-cache/SKILL.md`
- Related Command: `/component-health:list-components` (for component list)
- Related Command: `/component-health:analyze` (for health analysis)
