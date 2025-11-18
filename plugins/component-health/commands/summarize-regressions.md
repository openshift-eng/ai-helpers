---
description: Query and summarize regression data for OpenShift releases with counts and metrics
argument-hint: <release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
---

## Name

component-health:summarize-regressions

## Synopsis

```
/component-health:summarize-regressions <release> [--components comp1 comp2 ...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

## Description

The `component-health:summarize-regressions` command queries regression data for a specified OpenShift release and generates summary statistics. It leverages the `list-regressions` command to fetch raw regression data and then presents counts, percentages, and timing metrics to help understand regression trends at a glance.

By default, the command analyzes:
- All regressions within the release development window
- Both open and closed regressions
- Triage coverage and timing metrics
- Per-component breakdowns

This command is useful for:

- Getting a quick count of regressions in a release
- Analyzing regression distribution by component
- Tracking triage coverage and response times
- Generating summary reports for regression management
- Monitoring regression resolution speed by component
- Comparing regression metrics across different components
- Understanding open vs closed regression breakdown

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

3. **Resolve Component Names**: Use fuzzy matching to find actual component names

   - Run list_components.py to get all available components:
     ```bash
     python3 plugins/component-health/skills/list-components/list_components.py --release <release>
     ```
   - If `--components` was provided:
     - For each search string, find all components containing that string (case-insensitive)
     - Combine all matches into a single list
     - Remove duplicates
     - If no matches found for a search string, warn the user and show available components
   - If `--components` was NOT provided:
     - Use all available components from the list

4. **Fetch Release Dates**: Run the get_release_dates.py script to get development window dates

   - Script location: `plugins/component-health/skills/get-release-dates/get_release_dates.py`
   - Pass release as `--release` argument
   - Extract `development_start` and `ga` dates from JSON output
   - Convert timestamps to simple date format (YYYY-MM-DD)
   - Use these dates if `--start` and `--end` are not explicitly provided

5. **Execute Python Script**: Run the list_regressions.py script with appropriate arguments

   - Script location: `plugins/component-health/skills/list-regressions/list_regressions.py`
   - Pass release as `--release` argument
   - Pass resolved component names as `--components` argument
   - Pass `development_start` date as `--start` argument (if available)
     - Always applied (for both GA'd and in-development releases)
     - Excludes regressions closed before development started
   - Pass `ga` date as `--end` argument (only if GA date is not null)
     - Only applied for GA'd releases
     - Excludes regressions opened after GA
     - For in-development releases (null GA date), no end date filtering is applied
   - **Always pass `--short` flag** to exclude regression arrays (only summaries)

6. **Parse Output**: Process the JSON output from the script

   - Script writes JSON to stdout with summary structure:
     - `summary`: Overall statistics (total, triaged, percentages, timing)
     - `components`: Per-component summary statistics
   - **ALWAYS use the summary fields** for counts and metrics
   - Regression arrays are not included (due to `--short` flag)

7. **Present Results**: Display summary in a clear, readable format

   - Show which components were matched (if fuzzy search was used)
   - Show overall summary statistics
   - Display per-component breakdowns
   - Highlight key metrics:
     - Triage coverage percentages
     - Average time to triage
     - Average time to close (for closed regressions)
     - Open vs closed counts
   - Present data in tables or structured format
   - Note any date filtering applied

8. **Error Handling**: Handle common error scenarios

   - Network connectivity issues
   - Invalid release format
   - API errors (404, 500, etc.)
   - Empty results
   - No matches for component filter
   - Release dates not found

## Return Value

The command outputs a **Regression Summary Report** with the following information:

### Overall Summary

- **Release**: OpenShift release version
- **Development Window**: Start and end dates (or "In Development" if no GA date)
- **Total Regressions**: `summary.total`
- **Filtered Infrastructure Regressions**: `summary.filtered_suspected_infra_regressions`
- **Triaged**: `summary.triaged` regressions (`summary.triage_percentage`%)
- **Open**: `summary.open.total` regressions (`summary.open.triage_percentage`% triaged)
- **Closed**: `summary.closed.total` regressions (`summary.closed.triage_percentage`% triaged)

### Timing Metrics

**Overall Metrics**:
- **Average Time to Triage**: `summary.time_to_triage_hrs_avg` hours
- **Maximum Time to Triage**: `summary.time_to_triage_hrs_max` hours
- **Average Time to Close**: `summary.time_to_close_hrs_avg` hours (closed regressions only)
- **Maximum Time to Close**: `summary.time_to_close_hrs_max` hours (closed regressions only)

**Open Regression Metrics**:
- **Average Open Duration**: `summary.open.open_hrs_avg` hours
- **Maximum Open Duration**: `summary.open.open_hrs_max` hours
- **Average Time to Triage** (open): `summary.open.time_to_triage_hrs_avg` hours
- **Maximum Time to Triage** (open): `summary.open.time_to_triage_hrs_max` hours

**Closed Regression Metrics**:
- **Average Time to Close**: `summary.closed.time_to_close_hrs_avg` hours
- **Maximum Time to Close**: `summary.closed.time_to_close_hrs_max` hours
- **Average Time to Triage** (closed): `summary.closed.time_to_triage_hrs_avg` hours
- **Maximum Time to Triage** (closed): `summary.closed.time_to_triage_hrs_max` hours
- **Average Triage-to-Close Time**: `summary.closed.time_triaged_closed_hrs_avg` hours
- **Maximum Triage-to-Close Time**: `summary.closed.time_triaged_closed_hrs_max` hours

### Per-Component Summary

For each component (from `components.*.summary`):

| Component | Total | Open | Closed | Triaged | Triage % | Avg Time to Triage | Avg Time to Close |
|-----------|-------|------|--------|---------|----------|--------------------|-------------------|
| Monitoring | 15 | 1 | 14 | 13 | 86.7% | 68 hrs | 156 hrs |
| etcd | 20 | 0 | 20 | 19 | 95.0% | 84 hrs | 192 hrs |
| kube-apiserver | 27 | 1 | 26 | 27 | 100.0% | 58 hrs | 144 hrs |

### Additional Information

- **Filters Applied**: Lists any component or date filters used
- **Data Scope**: Notes which regressions are included based on date filtering
  - For GA'd releases: Regressions within development window (start to GA)
  - For in-development releases: Regressions from development start onwards

## Examples

1. **Summarize all regressions for a release**:

   ```
   /component-health:summarize-regressions 4.17
   ```

   Fetches and summarizes all regressions for release 4.17, automatically applying development window date filtering.

2. **Filter by specific component (exact match)**:

   ```
   /component-health:summarize-regressions 4.21 --components Monitoring
   ```

   Shows summary statistics for only the Monitoring component in release 4.21.

3. **Filter by fuzzy search**:

   ```
   /component-health:summarize-regressions 4.21 --components network
   ```

   Finds all components containing "network" (case-insensitive) and shows summary statistics for all matches (e.g., "Networking / ovn-kubernetes", "Networking / DNS", etc.).

4. **Filter by multiple search strings**:

   ```
   /component-health:summarize-regressions 4.21 --components etcd kube-
   ```

   Finds all components containing "etcd" OR "kube-" and shows combined summary statistics.

5. **Specify custom date range**:

   ```
   /component-health:summarize-regressions 4.17 --start 2024-05-17 --end 2024-10-29
   ```

   Summarizes regressions within a specific date range:
   - Excludes regressions closed before 2024-05-17
   - Excludes regressions opened after 2024-10-29

6. **In-development release**:

   ```
   /component-health:summarize-regressions 4.21
   ```

   Summarizes regressions for an in-development release:
   - Automatically fetches development_start date
   - No end date filtering (release not yet GA'd)
   - Shows current state of regression management

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

  - `--start <YYYY-MM-DD>`: Filter by start date
    - Excludes regressions closed before this date
    - Defaults to development_start from release metadata if not provided

  - `--end <YYYY-MM-DD>`: Filter by end date
    - Excludes regressions opened after this date
    - Defaults to GA date from release metadata if not provided and release is GA'd
    - Omitted for in-development releases

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
- Output presents summary statistics in a readable format
- Diagnostic messages are written to stderr
- The script has a 30-second timeout for HTTP requests
- Summary statistics are based on all matching regressions (not limited by pagination)
- The `--short` flag is always used internally to optimize performance
- Infrastructure regressions are automatically filtered from counts
- Date filtering focuses analysis on the development window for accuracy
- This command internally uses `/component-health:list-regressions` to fetch data
- For raw regression data, use `/component-health:list-regressions` instead
- For health grading and analysis, use `/component-health:analyze` instead

## See Also

- Skill Documentation: `plugins/component-health/skills/list-regressions/SKILL.md`
- Script: `plugins/component-health/skills/list-regressions/list_regressions.py`
- Related Command: `/component-health:list-regressions` (for raw regression data)
- Related Command: `/component-health:analyze` (for health grading and analysis)
- Related Skill: `get-release-dates` (for fetching development window dates)
