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

1. **Use org-data-cache Skill**: Ensure the cache is fresh

   - **IMPORTANT**: This command does NOT use the Skill tool. Instead, run the Python script directly.
   - **Working Directory**: Ensure you are in the repository root directory before running the script
   - Verify working directory: Run `pwd` and confirm you are in the `ai-helpers` repository root
   - Run the cache script:
     ```bash
     python3 plugins/component-health/skills/org-data-cache/org_data_cache.py
     ```
   - This ensures the cache is up to date (refreshes if > 7 days old)
   - **DO NOT** run this script from within the `plugins/component-health/skills/org-data-cache/` directory

2. **Extract Component Names**: Read components from cache

   - Cache location: `~/.cache/ai-helpers/org_data.json`
   - Extract component keys from `.lookups.components`
   - Command: `jq '.lookups.components | keys' ~/.cache/ai-helpers/org_data.json`

3. **Present Results**: Display components in a readable format

   - Show total count
   - Display components in alphabetical order (already sorted by jq)
   - Components can be displayed in a numbered or bulleted list

4. **Error Handling**: Handle common error scenarios

   - Cache file missing or corrupted
   - org-data-cache skill failures (network, authentication, etc.)

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

- Skill Documentation: `plugins/component-health/skills/org-data-cache/SKILL.md`
- Script: `plugins/component-health/skills/org-data-cache/org_data_cache.py`
- Related Command: `/component-health:list-regressions` (for regression data)
- Related Command: `/component-health:summarize-jiras` (for bug data)
- Related Command: `/component-health:analyze` (for health analysis)
