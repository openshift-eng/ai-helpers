---
description: List all components from the org data cache
argument-hint: ""
---

## Name

component-health:list-components

## Synopsis

```
/component-health:list-components
```

## Description

The `component-health:list-components` command displays all component names from the local org data cache.

This command is useful for:

- Discovering available components
- Validating component names before analysis
- Understanding which teams/components are tracked
- Generating component lists for reports
- Finding exact component names for use in other commands

## Implementation

1. **Run the list-components Script**

   - **Working Directory**: Ensure you are in the repository root directory
   - Verify working directory: Run `pwd` and confirm you are in the `ai-helpers` repository root
   - Run the script:
     ```bash
     python3 plugins/component-health/skills/list-components/list_components.py
     ```
   - The script will:
     - Check if org data cache exists
     - If cache is missing, display an error with instructions to run org-data-cache skill
     - Extract and return all component names from the cache
     - Output JSON with total count and component list

2. **Handle Cache Missing Error**

   - If the script reports cache is missing, run org-data-cache first:
     ```bash
     python3 plugins/component-health/skills/org-data-cache/org_data_cache.py
     ```
   - Then retry the list-components script

3. **Parse and Display Results**

   - The script outputs JSON with:
     - `total_components`: Number of components found
     - `components`: Array of component names (alphabetically sorted)
   - Display results in a user-friendly format:
     ```
     Found 431 components:

     1. COO
     2. Openshift Advisor
     3. access-transparency
     ...
     ```

4. **Error Handling**: The script handles common error scenarios

   - Cache file missing - instructs user to run org-data-cache
   - Cache file corrupted - suggests deleting and re-downloading
   - Missing components data - verifies cache structure

## Return Value

The command outputs a **Component List** with the following information:

### Component Summary

- **Total Components**: Count of unique components found
- **Cache Age**: How old the cache is (if relevant)

### Component List

An alphabetically sorted list of all components, for example:

```
1. COO
2. Openshift Advisor
3. access-transparency
4. account-manager
5. addons
6. alibaba-disk-csi-driver-operator
7. ansible-operator-plugins
8. aws-ebs-csi-driver-operator
9. aws-efs-csi-driver-operator
10. aws-load-balancer-operator
...
```

## Examples

1. **List all components**:

   ```
   /component-health:list-components
   ```

   Displays all components from the org data cache.

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

- Component names are case-sensitive
- Component names are returned in alphabetical order
- The cache is automatically refreshed if older than 7 days
- Component names returned can be used directly in other component-health commands
- The cache is stored at `~/.cache/ai-helpers/org_data.json`

## See Also

- Skill Documentation: `plugins/component-health/skills/list-components/SKILL.md`
- Script: `plugins/component-health/skills/list-components/list_components.py`
- Related Skill: `plugins/component-health/skills/org-data-cache/SKILL.md`
- Related Command: `/component-health:list-regressions` (for regression data)
- Related Command: `/component-health:summarize-jiras` (for bug data)
- Related Command: `/component-health:analyze` (for health analysis)
