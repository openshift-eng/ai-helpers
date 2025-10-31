---
description: Grade component health based on regression triage metrics for an OpenShift release
argument-hint: <release> [--components comp1 comp2 ...]
---

## Name

component-health:analyze-regressions

## Synopsis

```
/component-health:analyze-regressions <release> [--components comp1 comp2 ...]
```

## Description

The `component-health:analyze-regressions` command grades component health for a specified OpenShift release by analyzing regression management metrics. It evaluates how well components are managing their test regressions based on three key health indicators:

1. **Triage Coverage**: The percentage of regressions that have been triaged to JIRA bugs
2. **Triage Timeliness**: How quickly regressions are being triaged (average time from detection to triage)
3. **Resolution Speed**: How quickly closed regressions are being resolved (average time from detection to closure)

This command is useful for:

- **Grading component health** using regression management metrics
- **Identifying components** that need attention in their regression handling
- **Tracking triage and resolution efficiency**
- **Generating component quality scorecards**

## Implementation

1. **Parse Arguments**: Extract release version and optional component filter from arguments

   - Release format: "X.Y" (e.g., "4.17", "4.16")
   - Components: List of component names (optional)

2. **Fetch Release Dates**: Run the get_release_dates.py script to get development window dates

   - Script location: `plugins/component-health/skills/get-release-dates/get_release_dates.py`
   - Pass release as `--release` argument
   - Extract `development_start` and `ga` dates from JSON output
   - Convert timestamps to simple date format (YYYY-MM-DD)

3. **Execute Python Script**: Run the list_regressions.py script with appropriate arguments

   - Script location: `plugins/component-health/skills/list-regressions/list_regressions.py`
   - Pass release as `--release` argument
   - Pass components as `--components` argument if provided
   - Pass `development_start` date as `--start` argument (if available)
     - Always applied (for both GA'd and in-development releases)
     - Excludes regressions closed before development started (not relevant to this release)
   - Pass `ga` date as `--end` argument (only if GA date is not null)
     - Only applied for GA'd releases
     - Excludes regressions opened after GA (post-release regressions, often not monitored/triaged)
     - For in-development releases (null GA date), no end date filtering is applied
   - **Always pass `--short` flag** to exclude regression data from response (only include summaries)

4. **Parse Output**: Process the JSON output from the script

   - Script writes JSON to stdout with the following structure (when using `--short` flag):
     ```json
     {
       "summary": {
         "total": <number>,
         "triaged": <number>,
         "triage_percentage": <number>,
         "time_to_triage_hrs_avg": <number or null>,
         "time_to_triage_hrs_max": <number or null>,
         "time_to_close_hrs_avg": <number or null>,
         "time_to_close_hrs_max": <number or null>,
         "open": {
           "total": <number>,
           "triaged": <number>,
           "triage_percentage": <number>,
           "time_to_triage_hrs_avg": <number or null>,
           "time_to_triage_hrs_max": <number or null>,
           "open_hrs_avg": <number or null>,
           "open_hrs_max": <number or null>
         },
         "closed": {
           "total": <number>,
           "triaged": <number>,
           "triage_percentage": <number>,
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
             "triaged": <number>,
             "triage_percentage": <number>,
             "time_to_triage_hrs_avg": <number or null>,
             "time_to_triage_hrs_max": <number or null>,
             "time_to_close_hrs_avg": <number or null>,
             "time_to_close_hrs_max": <number or null>,
             "open": {
               "total": <number>,
               "triaged": <number>,
               "triage_percentage": <number>,
               "time_to_triage_hrs_avg": <number or null>,
               "time_to_triage_hrs_max": <number or null>,
               "open_hrs_avg": <number or null>,
               "open_hrs_max": <number or null>
             },
             "closed": {
               "total": <number>,
               "triaged": <number>,
               "triage_percentage": <number>,
               "time_to_triage_hrs_avg": <number or null>,
               "time_to_triage_hrs_max": <number or null>,
               "time_to_close_hrs_avg": <number or null>,
               "time_to_close_hrs_max": <number or null>,
               "time_triaged_closed_hrs_avg": <number or null>,
               "time_triaged_closed_hrs_max": <number or null>
             }
           }
         }
       }
     }
     ```
   - Script writes diagnostic messages to stderr
   - Parse JSON to extract summary data grouped by component
   - **CRITICAL**: Always use the summary.total, summary.open.total, summary.closed.total and components._.summary._ fields for counts
   - **Note**: The `--short` flag is always used, so regression arrays (`open`/`closed`) are not included in component data
   - Note: Component filtering is performed by the script after fetching from API
   - Note: Date filtering is applied to focus on the development window
     - Regressions closed before development started are excluded (always applied)
     - Regressions opened after GA are excluded (only for GA'd releases)
     - For in-development releases (null GA date), only start date filtering is applied

5. **Grade Component Health**: Calculate and present health scores based on triage metrics

   - **FIRST**: Display overall health grade from the `summary` object:

     - **Triage Coverage**: Use `summary.triage_percentage` - percentage of all regressions that have been triaged
       - 90-100%: Excellent ✅
       - 70-89%: Good ⚠️
       - 50-69%: Needs Improvement ⚠️
       - <50%: Poor ❌
     - **Triage Timeliness**: Use `summary.time_to_triage_hrs_avg` - average hours to triage
       - <24 hours: Excellent ✅
       - 24-72 hours: Good ⚠️
       - 72-168 hours (1 week): Needs Improvement ⚠️
       - > 168 hours: Poor ❌
     - **Resolution Speed**: Use `summary.time_to_close_hrs_avg` - average hours to close (for closed regressions)
       - <168 hours (1 week): Excellent ✅
       - 168-336 hours (1-2 weeks): Good ⚠️
       - 336-720 hours (2-4 weeks): Needs Improvement ⚠️
       - > 720 hours (4+ weeks): Poor ❌
     - Total regressions: Use `summary.total` (NOT by counting arrays)
     - Total triaged: Use `summary.triaged`
     - Open vs Closed breakdown:
       - Open: `summary.open.total` (with `summary.open.triage_percentage`)
       - Closed: `summary.closed.total` (with `summary.closed.triage_percentage`)

   - **SECOND**: Display per-component health scorecard using `components.*.summary`:

     - For each component, calculate health grade based on:
       - Triage Coverage: `components.*.summary.triage_percentage`
       - Triage Timeliness: `components.*.summary.time_to_triage_hrs_avg`
       - Resolution Speed: `components.*.summary.time_to_close_hrs_avg`
     - Rank components from best to worst health
     - Highlight components needing attention (low triage %, high time to triage, slow resolution)
     - Show open regression count: `components.*.summary.open.total`

   - **Note**: Detailed regression data is not available when using `--short` flag
     - Only summary statistics are included in the response
     - For detailed regression lists, the script can be run without the `--short` flag
     - Can provide links to Sippy dashboards for drill-down analysis

6. **Error Handling**: Handle common error scenarios
   - Network errors (connectivity issues)
   - Invalid release format
   - API errors (404, 500, etc.)
   - Empty results
   - No matches for component filter

## Return Value

The command outputs a **Component Health Report** focused on triage metrics:

### Overall Health Grade

From the `summary` object:

- **Triage Coverage Score**: `summary.triage_percentage`% of regressions triaged
  - Grade interpretation (Excellent/Good/Needs Improvement/Poor)
  - Total: `summary.total` regressions
  - Triaged: `summary.triaged` regressions
- **Triage Timeliness Score**: `summary.time_to_triage_hrs_avg` hours average
  - Grade interpretation (Excellent/Good/Needs Improvement/Poor)
  - Maximum time to triage: `summary.time_to_triage_hrs_max` hours
- **Resolution Speed Score**: `summary.time_to_close_hrs_avg` hours average (closed regressions only)
  - Grade interpretation (Excellent/Good/Needs Improvement/Poor)
  - Maximum time to close: `summary.time_to_close_hrs_max` hours
- **Breakdown by Status**:
  - Open: `summary.open.total` (`summary.open.triage_percentage`% triaged)
  - Closed: `summary.closed.total` (`summary.closed.triage_percentage`% triaged)

### Per-Component Health Scorecard

Ranked table from `components.*.summary`:

| Component | Triage Coverage | Triage Time (hrs) | Resolution Time (hrs) | Open | Health Grade |
| --------- | --------------- | ----------------- | --------------------- | ---- | ------------ |
| ...       | X.X%            | X hrs             | X hrs                 | X    | ✅/⚠️/❌     |

- **Triage Coverage**: `components.*.summary.triage_percentage`
- **Triage Time**: `components.*.summary.time_to_triage_hrs_avg`
- **Resolution Time**: `components.*.summary.time_to_close_hrs_avg` (closed regressions only)
- **Open Count**: `components.*.summary.open.total`
- **Health Grade**: Combined score based on coverage, triage time, and resolution time

### Components Needing Attention

Highlighted list of components with:

- Low triage coverage (<50%)
- Slow triage response (>72 hours average)
- Slow resolution time (>336 hours / 2 weeks average)
- High open regression counts
- High overall regression counts throughout the release

### Detailed Metrics (Optional)

If requested, include:

- Time to close metrics (for closed regressions)
- Age of open regressions
- List of untriaged regressions by component
- Links to Sippy dashboards

**IMPORTANT - Accurate Counting**:

- The script outputs a JSON object with `summary` at the top level and `summary` within each component
- **ALWAYS use these summary counts** (`summary.total`, `summary.open.total`, `summary.open.triaged`, `summary.closed.total`, `summary.closed.triaged` and corresponding `components.*.summary.*`) rather than attempting to count the regression arrays
- This ensures accuracy even when the output is truncated due to size

**Note**: The output is optimized for analysis:

- **Short mode is always used** (`--short` flag):
  - Regression data arrays (`open` and `closed`) are excluded from component objects
  - Only summary statistics are included
  - This significantly reduces response size for better performance
- **Summary statistics provide complete metrics**:
  - Total counts, triage percentages, and timing metrics are available at both overall and per-component levels
  - No need to iterate through regression arrays

## Examples

1. **Grade overall component health for release 4.17**:

   ```
   /component-health:analyze-regressions 4.17
   ```

   Generates a health report showing:

   - Overall triage coverage percentage
   - Average time to triage
   - Per-component health scorecard
   - Components needing attention

   **Note**: The command automatically fetches release dates and applies filtering:

   - For GA'd releases (like 4.17):
     - Excludes regressions closed before development started (--start filter)
     - Excludes regressions opened after GA (--end filter)
   - For in-development releases (like 4.21 with null GA):
     - Excludes regressions closed before development started (--start filter only)
     - No end date filtering (release still in development)

2. **Grade specific components**:

   ```
   /component-health:analyze-regressions 4.21 --components Monitoring etcd
   ```

   Focuses health grading on Monitoring and etcd components:

   - Shows triage coverage for these components only
   - Compares their triage timeliness
   - Identifies which needs more attention

3. **Assess single component health**:

   ```
   /component-health:analyze-regressions 4.21 --components "kube-apiserver"
   ```

   Deep dive into kube-apiserver component health:

   - Detailed triage metrics
   - Open vs closed regression breakdown
   - List of untriaged regressions if any

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
