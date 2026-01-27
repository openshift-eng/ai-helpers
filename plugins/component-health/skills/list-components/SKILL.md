---
name: List Components
description: List all components from the org data cache
---

# List Components

This skill provides functionality to list all component names from the local org data cache.

## When to Use This Skill

Use this skill when you need to:

- Display all available component names
- Validate component names before using them in other commands
- Get a complete list of tracked components
- Count how many components are in the system

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
   - If missing, it will be automatically created by the script
   - Requires gsutil and gcloud authentication (see org-data-cache skill for details)

## Implementation Steps

### Step 1: Locate the Script

The script is located at:

```
plugins/component-health/skills/list-components/list_components.py
```

### Step 2: Run the Script from Repository Root

**IMPORTANT**: The script must be run from the repository root directory.

```bash
# Verify you are in the repository root
pwd
# Expected output: /path/to/ai-helpers

# Run the script
python3 plugins/component-health/skills/list-components/list_components.py
```

### Step 3: Process the Output

The script outputs JSON with the following structure:

```json
{
  "total_components": 150,
  "components": [
    "COO",
    "Openshift Advisor",
    "access-transparency",
    "account-manager",
    "..."
  ]
}
```

**Field Descriptions**:

- `total_components`: Total number of components found
- `components`: Alphabetically sorted list of component names

### Step 4: Display Results to User

Present the component list in a user-friendly format:

```
Found 150 components:

1. COO
2. Openshift Advisor
3. access-transparency
4. account-manager
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

3. **Missing components key**:
   ```
   Error: No components found in cache file. Expected structure: .lookups.components
   ```

   **Solution**: Verify cache file structure or re-download

## Output Format

The script outputs JSON to stdout:

- **Success**: Exit code 0, JSON with component list
- **Error**: Exit code 1, error message to stderr

## Examples

### Example 1: List All Components

```bash
python3 plugins/component-health/skills/list-components/list_components.py
```

Output:

```json
{
  "total_components": 150,
  "components": [
    "COO",
    "Openshift Advisor",
    "access-transparency",
    "..."
  ]
}
```

### Example 2: Count Components

```bash
python3 plugins/component-health/skills/list-components/list_components.py | jq '.total_components'
```

Output:

```
150
```

### Example 3: Search for Specific Component

```bash
python3 plugins/component-health/skills/list-components/list_components.py | jq '.components[] | select(contains("apiserver"))'
```

Output:

```
"kube-apiserver"
"oauth-apiserver"
"openshift-apiserver"
```

## Integration with org-data-cache Skill

This skill depends on the org-data-cache skill to maintain the cache:

1. **First-time setup**: If cache doesn't exist, the user needs to run org-data-cache skill
2. **Cache refresh**: org-data-cache automatically refreshes stale cache (> 7 days old)
3. **Shared cache**: Both skills use the same cache file at `~/.cache/ai-helpers/org_data.json`

## Notes

- Component names are case-sensitive
- Components are returned in alphabetical order
- The script reads directly from the cache file (no network calls)
- Very fast execution (< 100ms typically)
- Cache location is fixed at `~/.cache/ai-helpers/org_data.json`
- Component names can be used directly in other component-health commands

## See Also

- Related Skill: `plugins/component-health/skills/org-data-cache/SKILL.md`
- Related Command: `/component-health:list-components`
- Cache Location: `~/.cache/ai-helpers/org_data.json`
