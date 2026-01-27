---
name: List Teams
description: List all teams from the org data cache
---

# List Teams

This skill provides functionality to list all team names from the local org data cache.

## When to Use This Skill

Use this skill when you need to:

- Display all available team names
- Validate team names before using them in other commands
- Get a complete list of tracked teams
- Count how many teams are in the system
- Find team names for org structure analysis

## Prerequisites

1. **Python 3 Installation**

   - Check if installed: `which python3`
   - Python 3.6 or later is required
   - Comes pre-installed on most systems

2. **jq Installation**

   - Check if installed: `which jq`
   - Required for JSON parsing
   - Usually pre-installed on most systems
   - macOS: `brew install jq`
   - Linux: `sudo apt-get install jq` or `sudo yum install jq`

3. **Org Data Cache**

   - The org data cache must exist at `~/.cache/ai-helpers/org_data.json`
   - If missing, it will be automatically created by running org-data-cache
   - Requires gsutil and gcloud authentication (see org-data-cache skill for details)

## Implementation Steps

### Step 1: Ensure Cache is Fresh

**IMPORTANT**: Always run org-data-cache first to ensure the cache is available and up-to-date.

```bash
# Verify you are in the repository root
pwd
# Expected output: /path/to/ai-helpers

# Ensure cache is fresh (creates/updates if needed)
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py
```

This step will:
- Create the cache if it doesn't exist
- Update the cache if it's older than 7 days
- Do nothing if the cache is already fresh
- Only takes a few seconds if cache exists and is fresh

### Step 2: Run the list-teams Script

After ensuring the cache is available, run the list-teams script:

```bash
python3 plugins/component-health/skills/list-teams/list_teams.py
```

### Step 3: Process the Output

The script outputs JSON with the following structure:

```json
{
  "total_teams": 155,
  "teams": [
    "ACS Automation",
    "ACS Cloud Service",
    "API Server",
    "ARO Cluster Lifecycle East",
    "..."
  ]
}
```

**Field Descriptions**:

- `total_teams`: Total number of teams found
- `teams`: Alphabetically sorted list of team names

### Step 4: Display Results to User

Present the team list in a user-friendly format:

```
Found 155 teams:

1. ACS Automation
2. ACS Cloud Service
3. API Server
4. ARO Cluster Lifecycle East
...
```

## Error Handling

The script handles several error scenarios:

1. **Cache file missing**:
   ```
   Error: Cache file not found at ~/.cache/ai-helpers/org_data.json
   Please run the org-data-cache skill first to create the cache.
   ```

   **Solution**: Run `python3 plugins/component-health/skills/org-data-cache/org_data_cache.py`

2. **Invalid JSON in cache**:
   ```
   Error: Failed to parse cache file. Cache may be corrupted.
   ```

   **Solution**: Delete cache and re-download with org-data-cache skill

3. **Missing teams key**:
   ```
   Error: No teams found in cache file. Expected structure: .lookups.teams
   ```

   **Solution**: Verify cache file structure or re-download

4. **No teams found**:
   ```
   Warning: No teams found in cache file.
   This may indicate the cache is outdated or incomplete.
   ```

   **Solution**: Refresh the cache using org-data-cache skill

## Output Format

The script outputs JSON to stdout:

- **Success**: Exit code 0, JSON with team list
- **Error**: Exit code 1, error message to stderr

## Examples

### Example 1: List All Teams

```bash
# Ensure cache is fresh first
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py

# Then list teams
python3 plugins/component-health/skills/list-teams/list_teams.py
```

Output:

```json
{
  "total_teams": 155,
  "teams": [
    "ACS Automation",
    "ACS Cloud Service",
    "API Server",
    "..."
  ]
}
```

### Example 2: Count Teams

```bash
# Ensure cache is fresh
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py

# Count teams
python3 plugins/component-health/skills/list-teams/list_teams.py | jq '.total_teams'
```

Output:

```
155
```

### Example 3: Search for Specific Team

```bash
# Ensure cache is fresh
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py

# Search for teams containing "API"
python3 plugins/component-health/skills/list-teams/list_teams.py | jq '.teams[] | select(contains("API"))'
```

Output:

```
"API Server"
"Cloud Compute API"
```

## Integration with org-data-cache Skill

This skill depends on the org-data-cache skill to maintain the cache:

1. **First-time setup**: If cache doesn't exist, the user needs to run org-data-cache skill
2. **Cache refresh**: org-data-cache automatically refreshes stale cache (> 7 days old)
3. **Shared cache**: Both skills use the same cache file at `~/.cache/ai-helpers/org_data.json`

## Notes

- Team names are extracted from `.lookups.teams` keys
- Team names are case-sensitive
- Teams are returned in alphabetical order
- The script reads directly from the cache file (no network calls)
- Very fast execution (< 100ms typically)
- Cache location is fixed at `~/.cache/ai-helpers/org_data.json`
- Team names can be used for org structure analysis and team-based queries
- Typical count: ~155 teams (may vary as teams are added/removed)

## See Also

- Related Skill: `plugins/component-health/skills/org-data-cache/SKILL.md`
- Related Skill: `plugins/component-health/skills/list-components/SKILL.md`
- Related Command: `/component-health:list-teams`
- Cache Location: `~/.cache/ai-helpers/org_data.json`
