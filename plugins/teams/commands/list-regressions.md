---
description: Fetch and list raw regression data for OpenShift releases
argument-hint: <release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
---

## Name

teams:list-regressions

## Synopsis

```
/teams:list-regressions <release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

## Description

The `teams:list-regressions` command fetches regression data for a specified OpenShift release and returns raw regression details without performing any summarization or analysis. It provides complete regression information including test names, timestamps, triages, and metadata.

This command is useful for:

- Fetching raw regression data for further processing
- Accessing complete regression details for specific components
- Building custom analysis workflows
- Providing data to other commands (like `summarize-regressions` and `analyze`)
- Exporting regression data for offline analysis
- Investigating specific test failures across releases

## Implementation

1. **Verify Prerequisites**: Check that Python 3 is installed

   - Run: `python3 --version`
   - Verify version 3.6 or later is available

2. **Parse Arguments**: Extract release version and optional filters from arguments

   - Release format: "X.Y" (e.g., "4.17", "4.21")
   - Optional filters:
     - `--components`: Space-separated list of component search strings (fuzzy match)
     - `--start`: Start date for filtering (YYYY-MM-DD)
     - `--end`: End date for filtering (YYYY-MM-DD)
     - `--short`: Exclude regression arrays from output (only summaries)

3. **Resolve Component Names**: Use fuzzy matching to find actual component names

   - Run list_components.py to get all available components:
     ```bash
     python3 plugins/component-health/skills/list-components/list_components.py --release <release>
     ```
   - If `--components` was provided:
     - For each search string, find all components containing that string (case-insensitive)
     - Example: "network" matches "Networking / ovn-kubernetes", "Networking / DNS", etc.
     - Combine all matches into a single list
     - Remove duplicates
     - If no matches found for a search string, warn the user and show available components
   - If `--components` was NOT provided:
     - Use all available components from the list

4. **Fetch Release Dates** (if date filtering needed): Run the get_release_dates.py script

   - Script location: `plugins/component-health/skills/get-release-dates/get_release_dates.py`
   - Pass release as `--release` argument
   - Extract `development_start` and `ga` dates from JSON output
   - Use these dates for `--start` and `--end` parameters if not explicitly provided

5. **Execute Python Script**: Run the list_regressions.py script

   - Script location: `plugins/component-health/skills/list-regressions/list_regressions.py`
   - Pass release as `--release` argument
   - Pass resolved component names as `--components` argument
   - Pass `--start` date if filtering by start date
   - Pass `--end` date if filtering by end date
   - Capture JSON output from stdout

6. **Parse Output**: Process the JSON response

   - The script outputs JSON with the following structure:
     - `summary`: Overall statistics (total, triaged, percentages, timing metrics)
     - `components`: Dictionary mapping component names to regression data
       - Each component has:
         - `summary`: Component-specific statistics
         - `open`: Array of open regression objects
         - `closed`: Array of closed regression objects
   - **Note**: When using `--short` flag, regression arrays are excluded (only summaries)

7. **Present Results**: Display or store the raw regression data

   - Show which components were matched (if fuzzy search was used)
   - The command returns the complete JSON response with metadata and raw regressions
   - Inform the user about overall counts from the summary
   - The raw regression data can be passed to other commands for analysis
   - Suggest using `/teams:summarize-regressions` for summary statistics
   - Suggest using `/teams:analyze` for health grading

8. **Error Handling**: Handle common error scenarios

   - Network connectivity issues
   - Invalid release format
   - API errors (404, 500, etc.)
   - Empty results
   - No matches for component filter

## Return Value

The command outputs **raw regression data** in JSON format with the following structure:

### Overall Summary

- `summary.total`: Total number of regressions
- `summary.triaged`: Total number of regressions triaged to JIRA bugs
- `summary.triage_percentage`: Percentage of regressions that have been triaged
- `summary.filtered_suspected_infra_regressions`: Count of infrastructure regressions filtered
- `summary.time_to_triage_hrs_avg`: Average hours from opened to first triage
- `summary.time_to_triage_hrs_max`: Maximum hours from opened to first triage
- `summary.time_to_close_hrs_avg`: Average hours from opened to closed (closed only)
- `summary.time_to_close_hrs_max`: Maximum hours from opened to closed (closed only)
- `summary.open`: Summary statistics for open regressions
  - `total`: Number of open regressions
  - `triaged`: Number of open regressions triaged
  - `triage_percentage`: Percentage of open regressions triaged
  - `time_to_triage_hrs_avg`, `time_to_triage_hrs_max`: Triage timing metrics
  - `open_hrs_avg`, `open_hrs_max`: How long regressions have been open
- `summary.closed`: Summary statistics for closed regressions
  - `total`: Number of closed regressions
  - `triaged`: Number of closed regressions triaged
  - `triage_percentage`: Percentage of closed regressions triaged
  - `time_to_triage_hrs_avg`, `time_to_triage_hrs_max`: Triage timing metrics
  - `time_to_close_hrs_avg`, `time_to_close_hrs_max`: Time to close metrics
  - `time_triaged_closed_hrs_avg`, `time_triaged_closed_hrs_max`: Time from triage to close

### Per-Component Data

- `components`: Dictionary mapping component names to objects containing:
  - `summary`: Component-specific statistics (same structure as overall summary)
  - `open`: Array of open regression objects
  - `closed`: Array of closed regression objects

### Regression Object Structure

Each regression object (in `components.*.open` or `components.*.closed` arrays) contains:

- `id`: Unique regression identifier
- `view`: Release view (e.g., "4.21-main")
- `release`: Release version
- `base_release`: Base release for comparison
- `component`: Component name
- `capability`: Test capability/area
- `test_name`: Full test name
- `variants`: Array of test variants where regression occurred
- `opened`: Timestamp when regression was first detected
- `closed`: Timestamp when regression was closed (null if still open)
- `triages`: Array of triage objects (JIRA bugs linked to this regression)
  - Each triage has `jira_key`, `created_at`, `url` fields
- `last_failure`: Timestamp of most recent test failure
- `max_failures`: Maximum number of failures detected

### Example Output Structure

```json
{
  "summary": {
    "total": 62,
    "triaged": 59,
    "triage_percentage": 95.2,
    "filtered_suspected_infra_regressions": 8,
    "time_to_triage_hrs_avg": 68,
    "time_to_triage_hrs_max": 240,
    "time_to_close_hrs_avg": 168,
    "time_to_close_hrs_max": 480,
    "open": { "total": 2, "triaged": 1, ... },
    "closed": { "total": 60, "triaged": 58, ... }
  },
  "components": {
    "Monitoring": {
      "summary": {
        "total": 15,
        "triaged": 13,
        "triage_percentage": 86.7,
        ...
      },
      "open": [
        {
          "id": 12894,
          "component": "Monitoring",
          "test_name": "[sig-instrumentation] Prometheus ...",
          "opened": "2025-10-15T10:30:00Z",
          "closed": null,
          "triages": [],
          ...
        }
      ],
      "closed": [...]
    },
    "etcd": {
      "summary": { "total": 20, "triaged": 19, ... },
      "open": [],
      "closed": [...]
    }
  }
}
```

**Note**: When using `--short` flag, the `open` and `closed` arrays are excluded from component objects to reduce response size.

## Examples

1. **List all regressions for a release**:

   ```
   /teams:list-regressions 4.17
   ```

   Fetches all regression data for release 4.17, including all components.

2. **Filter by specific component (exact match)**:

   ```
   /teams:list-regressions 4.21 --components Monitoring
   ```

   Returns regression data for only the Monitoring component.

3. **Filter by fuzzy search**:

   ```
   /teams:list-regressions 4.21 --components network
   ```

   Finds all components containing "network" (case-insensitive):
   - Networking / ovn-kubernetes
   - Networking / DNS
   - Networking / router
   - Networking / cluster-network-operator
   - ... and returns regression data for all matches

4. **Filter by multiple search strings**:

   ```
   /teams:list-regressions 4.21 --components etcd kube-
   ```

   Finds all components containing "etcd" OR "kube-":
   - Etcd
   - kube-apiserver
   - kube-controller-manager
   - kube-scheduler
   - kube-storage-version-migrator

5. **Filter by development window** (GA'd release):

   ```
   /teams:list-regressions 4.17 --start 2024-05-17 --end 2024-10-29
   ```

   Fetches regressions within the development window:
   - Excludes regressions closed before 2024-05-17
   - Excludes regressions opened after 2024-10-29

6. **Filter for in-development release**:

   ```
   /teams:list-regressions 4.21 --start 2025-09-02
   ```

   Fetches regressions for an in-development release:
   - Excludes regressions closed before development started
   - No end date (release still in development)

7. **Combine fuzzy component search and date filters**:

   ```
   /teams:list-regressions 4.21 --components network --start 2025-09-02
   ```

   Returns regressions for all networking components from the development window.

## Arguments

- `$1` (required): Release version
  - Format: "X.Y" (e.g., "4.17", "4.21")
  - Must be a valid OpenShift release number

- `$2+` (optional): Filter flags
  - `--components <search1> [search2 ...]`: Filter by component names using fuzzy search
    - Space-separated list of component search strings
    - Case-insensitive substring matching
    - Each search string matches all components containing that substring
    - If no components provided, all components are analyzed
    - Example: "network" matches "Networking / ovn-kubernetes", "Networking / DNS", etc.
    - Example: "kube-" matches "kube-apiserver", "kube-controller-manager", etc.

  - `--start <YYYY-MM-DD>`: Filter regressions by start date
    - Excludes regressions closed before this date
    - Typically the development_start date from release metadata

  - `--end <YYYY-MM-DD>`: Filter regressions by end date
    - Excludes regressions opened after this date
    - Typically the GA date for released versions
    - Omit for in-development releases

  - `--short`: Exclude regression arrays from output
    - Only include summary statistics
    - Significantly reduces response size for large datasets
    - Use when you only need counts and metrics, not individual regressions

## Prerequisites

1. **Python 3**: Required to run the data fetching script

   - Check: `which python3`
   - Version: 3.6 or later

2. **Network Access**: Must be able to reach the component health API

   - Ensure HTTPS requests can be made
   - Check firewall and VPN settings if needed

3. **API Configuration**: The API endpoint must be configured in the script
   - Location: `plugins/component-health/skills/list-regressions/list_regressions.py`
   - The script should have the correct API base URL

## Notes

- The script uses Python's standard library only (no external dependencies)
- Output is JSON format for easy parsing and further processing
- Diagnostic messages are written to stderr, data to stdout
- The script has a 30-second timeout for HTTP requests
- For large result sets, consider using component filters or the `--short` flag
- Date filtering helps focus on relevant regressions within the development window
- Infrastructure regressions (closed quickly on high-volume days) are automatically filtered
- The returned data includes complete regression information, not summaries
- If you need summary statistics, use `/teams:summarize-regressions` instead
- If you need health grading, use `/teams:analyze` instead

## See Also

- Skill Documentation: `plugins/component-health/skills/list-regressions/SKILL.md`
- Script: `plugins/component-health/skills/list-regressions/list_regressions.py`
- Related Command: `/teams:summarize-regressions` (for summary statistics)
- Related Command: `/teams:analyze` (for health grading and analysis)
- Related Skill: `get-release-dates` (for fetching development window dates)
