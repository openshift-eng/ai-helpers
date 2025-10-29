---
description: List component health regressions for an OpenShift release
argument-hint: <release> [--opened true|false] [--components comp1 comp2 ...]
---

## Name

component-health:list-regressions

## Synopsis

```
/component-health:list-regressions <release> [--opened true|false] [--components comp1 comp2 ...]
```

## Description

The `component-health:list-regressions` command fetches and displays component health regression data for a specified OpenShift release. It queries a component health API to retrieve regression information and can optionally filter by open/closed status.

This command is useful for:

- Analyzing component health across releases
- Tracking regression trends
- Identifying problematic components
- Generating quality reports

## Implementation

1. **Parse Arguments**: Extract release version and optional filters from arguments

   - Release format: "X.Y" (e.g., "4.17", "4.16")
   - Opened flag: "true" or "false" (optional)
   - Components: List of component names (optional)

2. **Execute Python Script**: Run the list_regressions.py script with appropriate arguments

   - Script location: `plugins/component-health/skills/list-regressions/list_regressions.py`
   - Pass release as `--release` argument
   - Pass opened flag as `--opened` argument if provided
   - Pass components as `--components` argument if provided

3. **Parse Output**: Process the JSON output from the script

   - Script writes JSON to stdout
   - Script writes diagnostic messages to stderr
   - Parse JSON to extract regression data
   - Note: Component filtering is performed by the script after fetching from API

4. **Format Results**: Present the regression data in a readable format

   - Display summary statistics (total count, open count, closed count)
   - List regressions by component
   - Highlight critical regressions if applicable
   - Provide links or references to detailed regression data

5. **Error Handling**: Handle common error scenarios
   - Network errors (connectivity issues)
   - Invalid release format
   - API errors (404, 500, etc.)
   - Empty results
   - No matches for component filter

## Return Value

The command outputs:

- **Summary**: Total regression count and breakdown by status
- **Regression List**: Details of each regression including:
  - Component name
  - Regression ID
  - Description
  - Status (open/closed)
  - Timestamps
- **Format**: Human-readable formatted output with optional JSON data

## Examples

1. **List all regressions for release 4.17**:

   ```
   /component-health:list-regressions 4.17
   ```

   Fetches all regressions (both open and closed) for OpenShift 4.17

2. **List only open regressions**:

   ```
   /component-health:list-regressions 4.17 --opened true
   ```

   Fetches only open regressions for OpenShift 4.17

3. **List closed regressions for previous release**:

   ```
   /component-health:list-regressions 4.16 --opened false
   ```

   Fetches only closed regressions for OpenShift 4.16

4. **Filter by specific components**:

   ```
   /component-health:list-regressions 4.21 --components Monitoring etcd
   ```

   Fetches regressions for only Monitoring and etcd components in release 4.21

5. **Combine filters**:

   ```
   /component-health:list-regressions 4.21 --opened true --components "kube-apiserver" Monitoring
   ```

   Fetches only open regressions for kube-apiserver and Monitoring components in release 4.21

## Arguments

- `$1` (required): Release version in format "X.Y" (e.g., "4.17", "4.16")
- `$2+` (optional): Filter flags
  - `--opened true|false`: Show only open or closed regressions
    - `--opened true`: Show only open regressions
    - `--opened false`: Show only closed regressions
    - Omit to show all regressions
  - `--components comp1 [comp2 ...]`: Filter by component names (space-separated)
    - Case-insensitive matching
    - Filtering performed after API fetch
    - Can quote multi-word component names: `"kube-apiserver"`

## Prerequisites

1. **Python 3**: Required to run the data fetching script

   - Check: `which python3`
   - Version: 3.6 or later

2. **Network Access**: Must be able to reach the component health API

3. **API Configuration**: The API endpoint must be configured in the script
   - Location: `plugins/component-health/skills/list-regressions/list_regressions.py`
   - Update `base_url` variable with actual endpoint

## Notes

- The script uses Python's standard library only (no external dependencies)
- Output is cached temporarily for performance
- Regression data is fetched in real-time from the API
- Large result sets may take time to fetch and display

## See Also

- Skill Documentation: `plugins/component-health/skills/list-regressions/SKILL.md`
- Script: `plugins/component-health/skills/list-regressions/list_regressions.py`
