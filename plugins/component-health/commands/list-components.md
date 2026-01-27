---
description: List all OCPBUGS components from the org data cache
argument-hint: ""
---

## Name

component-health:list-components

## Synopsis

```
/component-health:list-components
```

## Description

The `component-health:list-components` command displays all OCPBUGS component names from the local org data cache.

This command is useful for:

- Discovering available OCPBUGS components
- Validating OCPBUGS component names before filing or querying bugs
- Understanding which components are tracked in OCPBUGS
- Generating component lists for OCPBUGS-related reports
- Finding exact component names for use in JIRA queries and other commands

## Implementation

1. **Ensure Cache is Available and Fresh**

   - **Working Directory**: Ensure you are in the repository root directory
   - Verify working directory: Run `pwd` and confirm you are in the `ai-helpers` repository root
   - **IMPORTANT**: Before running list-components, always ensure cache is fresh by running org-data-cache:
     ```bash
     python3 plugins/component-health/skills/org-data-cache/org_data_cache.py
     ```
   - This will:
     - Create cache if it doesn't exist
     - Update cache if it's older than 7 days
     - Do nothing if cache is already fresh
     - Takes only a few seconds if cache is fresh

2. **Run the list-components Script**

   - After ensuring cache is available, run the script:
     ```bash
     python3 plugins/component-health/skills/list-components/list_components.py
     ```
   - The script will:
     - Read from the org data cache
     - Extract OCPBUGS component names
     - Output JSON with total count and component list

3. **Parse and Display Results**

   - The script outputs JSON with:
     - `total_components`: Number of OCPBUGS components found
     - `components`: Array of OCPBUGS component names (alphabetically sorted)
   - Display results in a user-friendly format:
     ```
     Found 95 OCPBUGS components:

     1. Auth
     2. Bare Metal Hardware Provisioning / baremetal-operator
     3. Bare Metal Hardware Provisioning / cluster-baremetal-operator
     ...
     ```

4. **Error Handling**: The script handles common error scenarios

   - Cache file missing - you should have run org-data-cache first (step 1)
   - Cache file corrupted - suggests deleting and re-running org-data-cache
   - Missing components data - verifies cache structure

## Return Value

The command outputs a **Component List** with the following information:

### Component Summary

- **Total Components**: Count of unique OCPBUGS components found (typically ~95)
- **Cache Age**: How old the cache is (if relevant)

### Component List

An alphabetically sorted list of all OCPBUGS components, for example:

```
1. Auth
2. Bare Metal Hardware Provisioning / baremetal-operator
3. Bare Metal Hardware Provisioning / cluster-baremetal-operator
4. Bare Metal Hardware Provisioning / ironic
5. Bugs for the oc-mirror plugin
6. Build
7. Cloud Compute / Cloud Controller Manager
8. Cloud Compute / Cluster API Providers
9. Cloud Compute / ControlPlaneMachineSet
10. Cloud Compute / IBM Provider
...
```

**Note**: Only components with `project: "OCPBUGS"` in their jiras array are included.

## Examples

1. **List all OCPBUGS components**:

   ```
   /component-health:list-components
   ```

   Displays all OCPBUGS components from the org data cache.

## Arguments

None

## Prerequisites

1. **Python 3**: Required to run the cache management script

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

- Only OCPBUGS components are returned (filtered by `project: "OCPBUGS"` in jiras array)
- Component names are case-sensitive
- Component names are returned in alphabetical order
- The cache is automatically refreshed if older than 7 days
- Component names returned can be used directly in OCPBUGS JIRA queries and other component-health commands
- The cache is stored at `~/.cache/ai-helpers/org_data.json`
- Typical count: ~95 OCPBUGS components (may vary as components are added/removed)

## See Also

- Skill Documentation: `plugins/component-health/skills/list-components/SKILL.md`
- Script: `plugins/component-health/skills/list-components/list_components.py`
- Related Skill: `plugins/component-health/skills/org-data-cache/SKILL.md`
- Related Command: `/component-health:list-regressions` (for regression data)
- Related Command: `/component-health:summarize-jiras` (for bug data)
- Related Command: `/component-health:analyze` (for health analysis)
