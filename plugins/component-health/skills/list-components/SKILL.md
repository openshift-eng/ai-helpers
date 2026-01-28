---
name: List Components
description: List all OCPBUGS components, optionally filtered by team
---

# List Components

This skill provides functionality to list all OCPBUGS component names from the team component mapping, with optional filtering by team.

## When to Use This Skill

Use this skill when you need to:

- Display all OCPBUGS component names
- Display OCPBUGS components for a specific team
- Validate OCPBUGS component names before using them in other commands
- Get a complete list of OCPBUGS-tracked components
- Count how many OCPBUGS components are in the system or per team
- Find component names for filing or querying OCPBUGS issues

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

3. **Team Component Mapping File**

   - The mapping file `team_component_map.json` should be in the repository
   - Located at: `plugins/component-health/team_component_map.json`
   - This file is committed to the repository - no download needed
   - To regenerate: `python3 plugins/component-health/generate_team_component_map.py`

## Implementation Steps

### Step 1: Verify Repository

Ensure you are in the repository root directory:

```bash
# Verify you are in the repository root
pwd
# Expected output: /path/to/ai-helpers
```

### Step 2: Run the list-components Script

**List all OCPBUGS components:**
```bash
python3 plugins/component-health/skills/list-components/list_components.py
```

**List OCPBUGS components for a specific team:**
```bash
python3 plugins/component-health/skills/list-components/list_components.py --team "API Server"
```

**Note**: Use the exact team name from the list-teams command output.

### Step 3: Process the Output

The script outputs JSON with the following structure:

**All components:**
```json
{
  "total_components": 87,
  "components": [
    "Auth",
    "apiserver-auth",
    "config-operator",
    "..."
  ]
}
```

**Components filtered by team:**
```json
{
  "total_components": 8,
  "components": [
    "apiserver-auth",
    "config-operator",
    "kube-apiserver",
    "kube-controller-manager",
    "kube-storage-version-migrator",
    "openshift-apiserver",
    "openshift-controller-manager / controller-manager",
    "service-ca"
  ],
  "team": "API Server"
}
```

**Field Descriptions**:

- `total_components`: Total number of OCPBUGS components found
- `components`: Alphabetically sorted list of OCPBUGS component names
- `team`: (Optional) The team name used for filtering

## Error Handling

The script handles several error scenarios:

1. **Mapping file missing**:
   ```
   Error: Team component mapping file not found at ...
   This file should be in the repository. Please check your installation.
   ```

   **Solution**: Verify repository checkout or regenerate with `generate_team_component_map.py`

2. **Invalid JSON in mapping**:
   ```
   Error: Failed to parse mapping file. File may be corrupted.
   ```

   **Solution**: Regenerate the mapping file

3. **Team not found**:
   ```
   Error: Team 'Invalid Team' not found in mapping.
   Use list-teams to see available teams.
   ```

   **Solution**: Run list-teams to get correct team name, ensure exact match (case-sensitive)

4. **No OCPBUGS components for team**:
   ```
   Warning: No OCPBUGS components found for team 'Team Name'.
   The team may not have any OCPBUGS components assigned.
   ```

   **Note**: This is a warning, not an error. Some teams may not have OCPBUGS components.

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
  "total_components": 87,
  "components": [
    "Auth",
    "apiserver-auth",
    "..."
  ]
}
```

### Example 2: List Components for a Specific Team

```bash
python3 plugins/component-health/skills/list-components/list_components.py --team "API Server"
```

Output:

```json
{
  "total_components": 8,
  "components": [
    "apiserver-auth",
    "config-operator",
    "kube-apiserver",
    "..."
  ],
  "team": "API Server"
}
```

### Example 3: Count Components

```bash
python3 plugins/component-health/skills/list-components/list_components.py | jq '.total_components'
```

Output:

```
87
```

### Example 4: Search for Specific Component

```bash
python3 plugins/component-health/skills/list-components/list_components.py | jq '.components[] | select(contains("apiserver"))'
```

Output:

```
"apiserver-auth"
"kube-apiserver"
"openshift-apiserver"
```

## Notes

- Only OCPBUGS components are included in the mapping
- Team names must match exactly (case-sensitive) - use list-teams to get correct names
- When filtering by team, only components owned by that team are returned
- Component names are case-sensitive
- Components are returned in alphabetical order
- The script reads from the committed mapping file (no network calls)
- Very fast execution (< 100ms typically)
- Mapping file location: `plugins/component-health/team_component_map.json`
- Component names can be used directly in OCPBUGS JIRA queries and other component-health commands
- Typical count: ~87 total components across 29 teams (may vary as components are added/removed)
- To refresh mapping: Run `python3 plugins/component-health/generate_team_component_map.py`

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

- Related Skill: `plugins/component-health/skills/list-teams/SKILL.md`
- Related Command: `/component-health:list-components`
- Mapping File: `plugins/component-health/team_component_map.json`
- Generator Script: `plugins/component-health/generate_team_component_map.py`
