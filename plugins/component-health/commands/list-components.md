---
description: List all components tracked in Sippy for a release
argument-hint: <release>
---

## Name

component-health:list-components

## Synopsis

```
/component-health:list-components <release>
```

## Description

The `component-health:list-components` command fetches and displays all component names tracked in the Sippy component readiness system for a specified OpenShift release.

This command is useful for:

- Discovering available components for a release
- Validating component names before analysis
- Understanding which teams/components are tracked
- Generating component lists for reports
- Finding exact component names for use in other commands

## Implementation

1. **Verify Prerequisites**: Check that Python 3 is installed

   - Run: `python3 --version`
   - Verify version 3.6 or later is available

2. **Parse Arguments**: Extract release version from arguments

   - Release format: "X.Y" (e.g., "4.17", "4.21")

3. **Execute Python Script**: Run the list_components.py script

   - Script location: `plugins/component-health/skills/list-components/list_components.py`
   - Pass release as `--release` argument
   - The script automatically appends "-main" suffix to construct the view
   - Capture JSON output from stdout

4. **Parse Output**: Process the JSON response

   - Extract component count and component list
   - Components are returned alphabetically sorted and unique

5. **Present Results**: Display components in a readable format

   - Show total count
   - Display components in a numbered or bulleted list
   - Optionally group by category (e.g., Networking, Storage, etc.)

6. **Error Handling**: Handle common error scenarios

   - Network connectivity issues
   - Invalid release format
   - API errors (400, 404, 500, etc.)
   - Empty results

## Return Value

The command outputs a **Component List** with the following information:

### Component Summary

- **Release**: The release version queried
- **View**: The constructed view parameter (release + "-main")
- **Total Components**: Count of unique components found

### Component List

An alphabetically sorted list of all components, for example:

```
1. Bare Metal Hardware Provisioning
2. Build
3. Cloud Compute / Cloud Controller Manager
4. Cluster Version Operator
5. Etcd
6. HyperShift
7. Image Registry
8. Installer / openshift-installer
9. kube-apiserver
10. Machine Config Operator
11. Management Console
12. Monitoring
13. Networking / ovn-kubernetes
14. OLM
15. Storage
...
```

## Examples

1. **List all components for release 4.21**:

   ```
   /component-health:list-components 4.21
   ```

   Displays all components tracked in Sippy for release 4.21.

2. **List components for release 4.20**:

   ```
   /component-health:list-components 4.20
   ```

   Displays all components for the 4.20 release.

## Arguments

- `$1` (required): Release version
  - Format: "X.Y" (e.g., "4.17", "4.21")
  - Must be a valid OpenShift release number

## Prerequisites

1. **Python 3**: Required to run the data fetching script

   - Check: `which python3`
   - Version: 3.6 or later

2. **Network Access**: Must be able to reach the Sippy API

   - Ensure HTTPS requests can be made to `sippy.dptools.openshift.org`

## Notes

- The script automatically appends "-main" to the release version
- Component names are case-sensitive
- Component names are returned in alphabetical order
- Some components use hierarchical names with "/" separator (e.g., "Networking / ovn-kubernetes")
- The script has a 30-second timeout for HTTP requests
- Component names returned can be used directly in other component-health commands

## See Also

- Skill Documentation: `plugins/component-health/skills/list-components/SKILL.md`
- Script: `plugins/component-health/skills/list-components/list_components.py`
- Related Command: `/component-health:list-regressions` (for regression data)
- Related Command: `/component-health:summarize-jiras` (for bug data)
- Related Command: `/component-health:analyze` (for health analysis)
