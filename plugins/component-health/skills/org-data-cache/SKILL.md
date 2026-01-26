---
name: Org Data Cache
description: Safely manage a local cache of OpenShift org data from GCS
---

# Org Data Cache

This skill provides functionality to safely manage a local cache of OpenShift organization data. The cache is stored outside of any git repository to prevent accidental commits of organizational information.

## When to Use This Skill

Use this skill when you need to:

- Access comprehensive OpenShift organization data including teams, components, and ownership information
- Query team memberships and component assignments
- Analyze organizational structure
- Provide component-to-team mappings
- Generate reports based on organizational data

## Prerequisites

1. **Python 3 Installation**

   - Check if installed: `which python3`
   - Python 3.6 or later is required
   - Comes pre-installed on most systems

2. **Google Cloud CLI (gcloud/gsutil) Installation**

   - Check if installed: `which gsutil`
   - Required for downloading org data from Google Cloud Storage
   - Installation guide: https://cloud.google.com/sdk/docs/install

   **Installation on macOS:**
   ```bash
   brew install google-cloud-sdk
   ```

   **Installation on Linux:**
   ```bash
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   ```

3. **Google Cloud Authentication**

   - Check if authenticated: `gcloud auth list`
   - If not authenticated, run: `gcloud auth login`
   - You must have access to the `gs://resolved-org` bucket
   - Contact your team lead if you don't have access

## Cache Location

The cache is stored in a secure location outside any git repository:

```
~/.cache/ai-helpers/org_data.json
```

**Why this location?**

1. **Not in git**: The `~/.cache` directory is a standard location for application cache files and is never tracked by git
2. **User-specific**: Each user has their own cache in their home directory
3. **Safe from accidental commits**: Even if you run `git add .` in any project, this file will never be included
4. **Easy to clean**: Standard cache cleanup tools will recognize and manage this location
5. **Secure permissions**: The cache file is automatically set to `600` (rw-------), readable and writable only by the owner

## Implementation Steps

### Step 1: Verify Prerequisites

First, ensure all prerequisites are met:

```bash
# Check Python 3
python3 --version

# Check gsutil
which gsutil

# Check gcloud authentication
gcloud auth list
```

If any prerequisite is missing, guide the user through installation:

- **Python 3**: Should be pre-installed on macOS/Linux
- **gsutil**: Install Google Cloud SDK (see Prerequisites section)
- **Authentication**: Run `gcloud auth login` and follow the prompts

### Step 2: Locate the Script

The script is located at:

```
plugins/component-health/skills/org-data-cache/org_data_cache.py
```

### Step 3: Run the Script

Execute the script to get or update the cached org data:

```bash
# Get org data (uses cache if fresh, updates if stale or missing)
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py

# Force refresh the cache regardless of age
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py --force-refresh

# Show cache information without downloading
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py --info
```

### Step 4: Process the Output

The script outputs cache metadata (not the actual data) with the following structure:

```json
{
  "cache_path": "/Users/username/.cache/ai-helpers/org_data.json",
  "cache_age_days": 2.5,
  "cache_status": "fresh",
  "cache_size_mb": 1.2,
  "last_updated": "2024-01-24T10:30:00Z"
}
```

**Field Descriptions**:

- `cache_path`: Absolute path to the cache file
- `cache_age_days`: Age of the cache in days (fractional)
- `cache_status`: One of "fresh", "stale", "missing", "updated"
- `cache_size_mb`: Size of the cache file in megabytes
- `last_updated`: ISO timestamp of when the cache was last updated

**Note**: The script only outputs metadata. The actual org data is cached at the path specified in `cache_path` and can be read directly using tools like `jq` or loaded in Python/other scripts.

**Cache Status Values**:

- `fresh`: Cache exists and is less than 7 days old
- `stale`: Cache exists but is more than 7 days old (cache will be updated)
- `missing`: No cache exists (cache will be created)
- `updated`: Cache was just updated (new data downloaded)

### Step 5: Use the Org Data

To access the cached org data, read it from the cache file:

```bash
# Read the entire org data file
cat ~/.cache/ai-helpers/org_data.json | jq '.'

# Extract specific information using jq
jq '.indexes.github_id_mappings.github_id_to_uid.someuser' ~/.cache/ai-helpers/org_data.json
```

Based on the org data, you can:

1. **Map GitHub usernames to Kerberos IDs**: Look up the actual identity of contributors
2. **Find team assignments**: Determine which team owns which component
3. **Analyze organizational structure**: Understand team hierarchies and relationships
4. **Generate reports**: Create team-based metrics and summaries
5. **Validate permissions**: Check if users have appropriate access

## Cache Management

### Cache Freshness Policy

The cache follows a 7-day freshness policy:

- **Fresh (0-7 days)**: Use cached data without downloading
- **Stale (>7 days)**: Automatically refresh from GCS
- **Missing**: Download from GCS

### Manual Cache Control

```bash
# Force refresh regardless of age
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py --force-refresh

# Check cache status
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py --info

# Delete cache (will be recreated on next run)
rm ~/.cache/ai-helpers/org_data.json
```

### Cache Safety Features

The implementation includes multiple safeguards:

1. **Location outside git**: Cache is always in `~/.cache/ai-helpers/`, never in a git repository
   - This location is hardcoded and cannot be changed
   - Even if you run the script from within a git repository, the cache is stored outside of it
   - The script warns you if run from a git repo to reassure you the cache is safe
2. **Secure file permissions**: Automatically sets `600` (rw-------) permissions on the cache file
   - Only the file owner can read or write the cache
   - Group and others have no access
   - Permissions are enforced on every download and verified on every read
3. **Clear documentation**: All documentation emphasizes proper handling of this data

## Error Handling

The script handles several error scenarios:

1. **Missing gsutil**:
   ```
   Error: gsutil not found. Please install Google Cloud SDK.
   Installation: https://cloud.google.com/sdk/docs/install
   ```

2. **Not authenticated**:
   ```
   Error: Not authenticated with gcloud.
   Please run: gcloud auth application-default login
   ```

3. **No access to bucket**:
   ```
   Error: Access denied to gs://resolved-org/orgdata/comprehensive_index_dump.json
   Please contact the Continuous Release Tooling team for access.
   ```

4. **Network errors**:
   ```
   Error: Failed to download org data: [details]
   ```

## Output Format

The script outputs JSON to stdout with:

- **Success**: Exit code 0, JSON with org data and metadata
- **Error**: Exit code 1, error message to stderr

Diagnostic messages are written to stderr, so they don't interfere with JSON parsing.

## Data Structure

The org data JSON contains the following key sections:

```json
{
  "indexes": {
    "github_id_mappings": {
      "github_id_to_uid": {
        "github_username": "kerberos_id"
      },
      "uid_to_github_id": {
        "kerberos_id": "github_username"
      }
    },
    "component_mappings": {
      "component_to_team": {
        "component_name": "team_name"
      }
    },
    "team_data": {
      "team_name": {
        "members": ["kerberos_id1", "kerberos_id2"],
        "components": ["component1", "component2"]
      }
    }
  }
}
```

## Examples

### Example 1: Get Fresh Org Data

```bash
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py
```

Output (if cache is fresh):

```json
{
  "cache_path": "/Users/username/.cache/ai-helpers/org_data.json",
  "cache_age_days": 2.5,
  "cache_status": "fresh",
  "cache_size_mb": 1.2,
  "last_updated": "2024-01-24T10:30:00Z"
}
```

### Example 2: Force Refresh

```bash
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py --force-refresh
```

Output:

```json
{
  "cache_path": "/Users/username/.cache/ai-helpers/org_data.json",
  "cache_age_days": 0.0,
  "cache_status": "updated",
  "cache_size_mb": 1.2,
  "last_updated": "2024-01-26T15:45:00Z"
}
```

### Example 3: Check Cache Info

```bash
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py --info
```

Output:

```json
{
  "cache_path": "/Users/username/.cache/ai-helpers/org_data.json",
  "cache_age_days": 9.2,
  "cache_status": "stale",
  "cache_size_mb": 1.2,
  "last_updated": "2024-01-17T10:30:00Z"
}
```

## Integration with Other Skills

This skill will be used as a foundation for other component-health skills:

1. **list-teams**: List all teams in the organization
2. **list-components-by-team**: Show components owned by a team
3. **find-team-for-component**: Lookup the owning team for a component
4. **map-github-to-kerberos**: Convert GitHub usernames to Kerberos IDs
5. **team-members**: List members of a specific team

**Example Integration**:

```bash
# Ensure cache is fresh
python3 plugins/component-health/skills/org-data-cache/org_data_cache.py

# Read from cache and extract team list
jq -r '.indexes.team_data | keys[]' ~/.cache/ai-helpers/org_data.json

# Find components for a specific team
TEAM="networking"
jq -r ".indexes.team_data.\"$TEAM\".components[]" ~/.cache/ai-helpers/org_data.json
```

## Security Considerations

**IMPORTANT**: The org data contains organizational information:

**Never**:

- Commit this data to git repositories
- Share it publicly
- Include it in bug reports or issues
- Store it in project directories

**Always**:

- Keep it in the designated cache location (`~/.cache/ai-helpers/`)
- Respect data privacy and confidentiality
- Follow your organization's data handling policies

## Notes

- The script uses Python's standard library plus subprocess for `gsutil`
- Cache is automatically created in `~/.cache/ai-helpers/` (safe from git)
- Cache file permissions are automatically set to `600` (user read/write only)
  - New downloads are created with secure permissions
  - Existing files with incorrect permissions are automatically fixed on first read
- Cache freshness is checked on every invocation
- The 7-day freshness window balances data currency with download frequency
- The script will create the cache directory if it doesn't exist
- File size is approximately 1-2MB (may grow over time)
- Download time depends on network speed (typically 1-5 seconds)
- The script validates gsutil availability before attempting downloads

## See Also

- Google Cloud SDK: https://cloud.google.com/sdk/docs/install
- Related Plugin: `plugins/component-health/README.md`
- Cache Location: `~/.cache/ai-helpers/org_data.json`
