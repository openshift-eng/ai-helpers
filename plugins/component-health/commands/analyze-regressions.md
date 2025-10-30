---
description: Analyze component health regressions for an OpenShift release
argument-hint: <release> [--components comp1 comp2 ...]
---

## Name

component-health:analyze-regressions

## Synopsis

```
/component-health:analyze-regressions <release> [--components comp1 comp2 ...]
```

## Description

The `component-health:analyze-regressions` command fetches and displays component health regression data for a specified OpenShift release. It queries a component health API to retrieve regression information and can optionally filter by component names.

This command is useful for:

- Analyzing component health across releases
- Tracking regression trends
- Identifying problematic components
- Generating quality reports

## Implementation

1. **Parse Arguments**: Extract release version and optional component filter from arguments

   - Release format: "X.Y" (e.g., "4.17", "4.16")
   - Components: List of component names (optional)

2. **Execute Python Script**: Run the list_regressions.py script with appropriate arguments

   - Script location: `plugins/component-health/skills/list-regressions/list_regressions.py`
   - Pass release as `--release` argument
   - Pass components as `--components` argument if provided

3. **Parse Output**: Process the JSON output from the script

   - Script writes JSON to stdout with the following structure:
     ```json
     {
       "summary": {
         "total": <number>,
         "open": {
           "total": <number>,
           "triaged": <number>,
           "time_to_triage_hrs_avg": <number or null>,
           "time_to_triage_hrs_max": <number or null>,
           "open_hrs_avg": <number or null>,
           "open_hrs_max": <number or null>
         },
         "closed": {
           "total": <number>,
           "triaged": <number>,
           "time_to_triage_hrs_avg": <number or null>,
           "time_to_triage_hrs_max": <number or null>,
           "time_to_close_hrs_avg": <number or null>,
           "time_to_close_hrs_max": <number or null>,
           "time_triaged_closed_hrs_avg": <number or null>,
           "time_triaged_closed_hrs_max": <number or null>
         }
       },
       "components": {
         "ComponentName": {
           "summary": {
             "total": <number>,
             "open": {
               "total": <number>,
               "triaged": <number>,
               "time_to_triage_hrs_avg": <number or null>,
               "time_to_triage_hrs_max": <number or null>,
               "open_hrs_avg": <number or null>,
               "open_hrs_max": <number or null>
             },
             "closed": {
               "total": <number>,
               "triaged": <number>,
               "time_to_triage_hrs_avg": <number or null>,
               "time_to_triage_hrs_max": <number or null>,
               "time_to_close_hrs_avg": <number or null>,
               "time_to_close_hrs_max": <number or null>,
               "time_triaged_closed_hrs_avg": <number or null>,
               "time_triaged_closed_hrs_max": <number or null>
             }
           },
           "open": [...],
           "closed": [...]
         }
       }
     }
     ```
   - Script writes diagnostic messages to stderr
   - Parse JSON to extract summary and regression data grouped by component
   - **CRITICAL**: Always use the summary.total, summary.open.total, summary.closed.total and components._.summary._ fields for counts
   - Note: Component filtering is performed by the script after fetching from API
   - Note: Time fields (`closed`, `last_failure`) are simplified to either timestamp strings or null
   - Note: If closed is null this indicates the regression is on-going

4. **Format Results**: Present the regression data in a readable format

   - **FIRST**: Display overall summary statistics from the `summary` object:
     - Total regressions: Use `summary.total` (NOT by counting arrays)
     - Open regressions: Use `summary.open.total` (items where `closed` is null)
     - Open triaged: Use `summary.open.triaged` (open regressions with non-empty triages list)
     - Open avg time to triage: Use `summary.open.time_to_triage_hrs_avg` (average hours, null if none triaged)
     - Open max time to triage: Use `summary.open.time_to_triage_hrs_max` (maximum hours, null if none triaged)
     - Open avg duration: Use `summary.open.open_hrs_avg` (average hours open, from opened to now)
     - Open max duration: Use `summary.open.open_hrs_max` (maximum hours open, from opened to now)
     - Closed regressions: Use `summary.closed.total` (items where `closed` is not null)
     - Closed triaged: Use `summary.closed.triaged` (closed regressions with non-empty triages list)
     - Closed avg time to triage: Use `summary.closed.time_to_triage_hrs_avg` (average hours, null if none triaged)
     - Closed max time to triage: Use `summary.closed.time_to_triage_hrs_max` (maximum hours, null if none triaged)
     - Closed avg time to close: Use `summary.closed.time_to_close_hrs_avg` (average hours from opened to closed)
     - Closed max time to close: Use `summary.closed.time_to_close_hrs_max` (maximum hours from opened to closed)
     - Closed avg time triaged to closed: Use `summary.closed.time_triaged_closed_hrs_avg` (average hours from triage to closed, only triaged closed regressions)
     - Closed max time triaged to closed: Use `summary.closed.time_triaged_closed_hrs_max` (maximum hours from triage to closed, only triaged closed regressions)
   - **SECOND**: Display per-component breakdown using `components.*.summary`:
     - For each component, show total, open, and closed counts from its `summary`
     - Identify components with the most open regressions using `summary.open.total`
   - List regressions grouped by component from the `components` object
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

- **Overall Summary**: Statistics from the `summary` object in the JSON response
  - Total regressions count across all components
  - Open regressions count (where `closed` is null)
  - Open triaged count (regressions triaged to a JIRA bug)
  - Open average time to triage in hours (from opened to first triage timestamp)
  - Open maximum time to triage in hours
  - Open average duration in hours (how long regressions have been open)
  - Open maximum duration in hours
  - Closed regressions count (where `closed` is not null)
  - Closed triaged count (regressions triaged to a JIRA bug)
  - Closed average time to triage in hours (from opened to first triage timestamp)
  - Closed maximum time to triage in hours
  - Closed average time to close in hours (from opened to closed timestamp)
  - Closed maximum time to close in hours
  - Closed average time from triage to closed in hours (only for triaged closed regressions)
  - Closed maximum time from triage to closed in hours (only for triaged closed regressions)
- **Regressions by Component**: Details grouped by component from the `components` object
  - Each component maps to an object containing:
    - `summary`: Per-component statistics (total, open, closed counts)
    - `open`: Array of open regression objects for that component
    - `closed`: Array of closed regression objects for that component
  - Component names are sorted alphabetically
  - Each regression includes:
    - Component name
    - Regression ID
    - Test information
    - Status (open/closed - indicated by closed field)
    - Timestamps (opened, closed, last_failure)
- **Format**: Human-readable formatted output with optional JSON data

**IMPORTANT - Accurate Counting**:

- The script outputs a JSON object with `summary` at the top level and `summary` within each component
- **ALWAYS use these summary counts** (`summary.total`, `summary.open.total`, `summary.open.triaged`, `summary.closed.total`, `summary.closed.triaged` and corresponding `components.*.summary.*`) rather than attempting to count the regression arrays
- This ensures accuracy even when the output is truncated due to size

**Note**: Time fields are simplified in the output:

- `closed`: Shows timestamp if closed (e.g., `"2025-09-27T12:04:24.966914Z"`), otherwise `null` (indicates ongoing regression)
- `last_failure`: Shows timestamp if valid (e.g., `"2025-09-25T14:41:17Z"`), otherwise `null`

## Examples

1. **Analyze all regressions for release 4.17**:

   ```
   /component-health:analyze-regressions 4.17
   ```

   Fetches all regressions (both open and closed) for OpenShift 4.17

2. **Filter by specific components**:

   ```
   /component-health:analyze-regressions 4.21 --components Monitoring etcd
   ```

   Fetches regressions for only Monitoring and etcd components in release 4.21

3. **Filter by single component**:

   ```
   /component-health:analyze-regressions 4.21 --components "kube-apiserver"
   ```

   Fetches regressions for the kube-apiserver component in release 4.21

## Arguments

- `$1` (required): Release version in format "X.Y" (e.g., "4.17", "4.16")
- `$2+` (optional): Filter flags
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
