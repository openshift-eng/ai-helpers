---
name: Analyze Regressions
description: Grade component health based on regression triage metrics for OpenShift releases
---

# Analyze Regressions

This skill provides functionality to analyze and grade component health for OpenShift releases based on regression management metrics. It evaluates how well components are managing their test regressions by analyzing triage coverage, triage timeliness, and resolution speed.

## When to Use This Skill

Use this skill when you need to:

- Grade component health for a specific OpenShift release
- Identify components that need help with regression handling
- Track triage and resolution efficiency across releases
- Generate component quality scorecards
- Produce health reports (text or HTML) for stakeholders

**Important Note**: Grading is subjective and not meant to be a critique of team performance. This is intended to help identify where help is needed and track progress as we try to improve our regression response rates.

## Prerequisites

1. **Python 3 Installation**

   - Check if installed: `which python3`
   - Python 3.6 or later is required
   - Comes pre-installed on most systems

2. **Network Access**

   - The scripts require network access to reach the component health API and release dates API
   - Ensure you can make HTTPS requests

3. **Required Scripts**

   - `plugins/component-health/skills/get-release-dates/get_release_dates.py`
   - `plugins/component-health/skills/list-regressions/list_regressions.py`
   - `plugins/component-health/skills/analyze-regressions/generate_html_report.py` (for HTML reports)
   - `plugins/component-health/skills/analyze-regressions/report_template.html` (for HTML reports)

## Implementation Steps

### Step 1: Parse Arguments

Extract the release version and optional component filter from the command arguments:

- **Release format**: "X.Y" (e.g., "4.17", "4.21")
- **Components** (optional): List of component names to filter by

**Example argument parsing**:

```
/component-health:analyze-regressions 4.17
/component-health:analyze-regressions 4.21 --components Monitoring etcd
```

### Step 2: Fetch Release Dates

Run the `get_release_dates.py` script to determine the development window for the release:

```bash
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release 4.17
```

**Expected output** (JSON on stdout):

```json
{
  "release": "4.17",
  "development_start": "2024-05-17T00:00:00Z",
  "feature_freeze": "2024-08-26T00:00:00Z",
  "code_freeze": "2024-09-30T00:00:00Z",
  "ga": "2024-10-29T00:00:00Z"
}
```

**Processing steps**:

1. Parse the JSON output
2. Extract `development_start` date - convert to YYYY-MM-DD format
3. Extract `ga` date - convert to YYYY-MM-DD format (may be null for in-development releases)
4. Handle null dates appropriately:
   - `development_start`: Usually always present; if null, omit `--start` parameter
   - `ga`: Will be null for in-development releases; if null, omit `--end` parameter

**Date conversion example**:

```
"2024-05-17T00:00:00Z" → "2024-05-17"
null → do not use this parameter
```

### Step 3: Execute List Regressions Script

Run the `list_regressions.py` script with the appropriate arguments:

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.17 \
  --start 2024-05-17 \
  --end 2024-10-29 \
  --short
```

**Parameter rules**:

- `--release`: Always required (from Step 1)
- `--components`: Optional, only if specified by user (from Step 1)
- `--start`: Use `development_start` date from Step 2 (if not null)
  - **Always applied** for both GA'd and in-development releases
  - Excludes regressions closed before development started (not relevant to this release)
- `--end`: Use `ga` date from Step 2 (only if not null)
  - **Only applied for GA'd releases** (when GA date is not null)
  - Excludes regressions opened after GA (post-release regressions, often not monitored/triaged)
  - **Not applied for in-development releases** (when GA date is null)
- `--short`: **Always include** this flag
  - Excludes regression data arrays from response
  - Only includes summary statistics
  - Prevents truncation problems with large datasets

**Example for GA'd release** (4.17):

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.17 \
  --start 2024-05-17 \
  --end 2024-10-29 \
  --short
```

**Example for in-development release** (4.21 with null GA):

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --start 2025-09-02 \
  --short
```

**Example with component filter**:

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --components Monitoring etcd \
  --start 2025-09-02 \
  --short
```

### Step 4: Parse Output Structure

The script outputs JSON to stdout with the following structure:

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
    "open": {
      "total": 2,
      "triaged": 1,
      "triage_percentage": 50.0,
      "time_to_triage_hrs_avg": 48,
      "time_to_triage_hrs_max": 48,
      "open_hrs_avg": 120,
      "open_hrs_max": 200
    },
    "closed": {
      "total": 60,
      "triaged": 58,
      "triage_percentage": 96.7,
      "time_to_triage_hrs_avg": 72,
      "time_to_triage_hrs_max": 240,
      "time_to_close_hrs_avg": 168,
      "time_to_close_hrs_max": 480,
      "time_triaged_closed_hrs_avg": 96,
      "time_triaged_closed_hrs_max": 240
    }
  },
  "components": {
    "ComponentName": {
      "summary": {
        "total": 15,
        "triaged": 13,
        "triage_percentage": 86.7,
        "filtered_suspected_infra_regressions": 0,
        "time_to_triage_hrs_avg": 68,
        "time_to_triage_hrs_max": 180,
        "time_to_close_hrs_avg": 156,
        "time_to_close_hrs_max": 360,
        "open": {
          "total": 1,
          "triaged": 0,
          "triage_percentage": 0.0,
          "time_to_triage_hrs_avg": null,
          "time_to_triage_hrs_max": null,
          "open_hrs_avg": 72,
          "open_hrs_max": 72
        },
        "closed": {
          "total": 14,
          "triaged": 13,
          "triage_percentage": 92.9,
          "time_to_triage_hrs_avg": 68,
          "time_to_triage_hrs_max": 180,
          "time_to_close_hrs_avg": 156,
          "time_to_close_hrs_max": 360,
          "time_triaged_closed_hrs_avg": 88,
          "time_triaged_closed_hrs_max": 180
        }
      }
    }
  }
}
```

**CRITICAL - Use Summary Counts**:

- **ALWAYS use `summary.total`, `summary.open.total`, `summary.closed.total`** for counts
- **ALWAYS use `components.*.summary.*`** for per-component counts
- Do NOT attempt to count regression arrays (they are excluded with `--short` flag)
- This ensures accuracy even with large datasets

**Key Metrics to Extract**:

From `summary` object:

- `summary.total` - Total regressions
- `summary.triaged` - Total triaged regressions
- `summary.triage_percentage` - **KEY HEALTH METRIC**: Percentage triaged
- `summary.filtered_suspected_infra_regressions` - Count of filtered infrastructure regressions
- `summary.time_to_triage_hrs_avg` - **KEY HEALTH METRIC**: Average hours to triage
- `summary.time_to_triage_hrs_max` - Maximum hours to triage
- `summary.time_to_close_hrs_avg` - **KEY HEALTH METRIC**: Average hours to close
- `summary.time_to_close_hrs_max` - Maximum hours to close
- `summary.open.total` - Open regressions count
- `summary.open.triaged` - Open triaged count
- `summary.open.triage_percentage` - Open triage percentage
- `summary.closed.total` - Closed regressions count
- `summary.closed.triaged` - Closed triaged count
- `summary.closed.triage_percentage` - Closed triage percentage

From `components` object:

- Same fields as summary, but per-component
- Use `components.*.summary.*` for all per-component statistics

### Step 5: Calculate Health Grades

**IMPORTANT - Closed Regression Triage**:

- **DO NOT recommend retroactively triaging closed regressions** - the tooling does not support this
- When identifying untriaged regressions that need attention, **only consider open regressions**: `summary.open.total - summary.open.triaged`
- Closed regression triage percentages are provided for historical analysis only, not as actionable items

#### Overall Health Grade

Calculate grades based on three key metrics:

**1. Triage Coverage** (`summary.triage_percentage`):

- 90-100%: Excellent ✅
- 70-89%: Good ⚠️
- 50-69%: Needs Improvement ⚠️
- <50%: Poor ❌

**2. Triage Timeliness** (`summary.time_to_triage_hrs_avg`):

- <24 hours: Excellent ✅
- 24-72 hours: Good ⚠️
- 72-168 hours (1 week): Needs Improvement ⚠️
- > 168 hours: Poor ❌

**3. Resolution Speed** (`summary.time_to_close_hrs_avg`):

- <168 hours (1 week): Excellent ✅
- 168-336 hours (1-2 weeks): Good ⚠️
- 336-720 hours (2-4 weeks): Needs Improvement ⚠️
- > 720 hours (4+ weeks): Poor ❌

#### Per-Component Health Grades

For each component in `components`:

1. Calculate the same three grades using `components.*.summary.*` fields
2. Rank components from best to worst health
3. Highlight components needing attention:
   - Low triage coverage (<50%)
   - Slow triage response (>72 hours average)
   - Slow resolution time (>336 hours / 2 weeks average)
   - High open regression counts
   - High overall regression counts

### Step 6: Display Text Report

Present a well-formatted text report with:

#### Overall Health Grade Section

Display overall statistics from `summary`:

```
=== Overall Health Grade for Release 4.17 ===
Development Window: 2024-05-17 to 2024-10-29 (GA'd release)

Total Regressions: 62
Filtered Infrastructure Regressions: 8
Triaged: 59 (95.2%)
Open: 2 (50.0% triaged)
Closed: 60 (96.7% triaged)

Triage Coverage: ✅ Excellent (95.2%)
Triage Timeliness: ⚠️ Good (68 hours average, 240 hours max)
Resolution Speed: ✅ Excellent (168 hours average, 480 hours max)
```

**Important**: If the GA date is null (in-development release), note:

```
Development Window: 2025-09-02 onwards (In Development)
```

#### Per-Component Health Scorecard

Display ranked table from `components.*.summary`:

```
=== Component Health Scorecard ===

| Component       | Triage Coverage | Triage Time | Resolution Time | Open | Grade |
|-----------------|-----------------|-------------|-----------------|------|-------|
| kube-apiserver  | 100.0%          | 58 hrs      | 144 hrs         | 1    | ✅    |
| etcd            | 95.0%           | 84 hrs      | 192 hrs         | 0    | ✅    |
| Monitoring      | 86.7%           | 68 hrs      | 156 hrs         | 1    | ⚠️    |
```

#### Components Needing Attention

Highlight specific components with issues:

```
=== Components Needing Attention ===

Monitoring:
  - 1 open untriaged regression (needs triage)
  - Triage coverage: 86.7% (below 90%)

Example-Component:
  - 5 open untriaged regressions (needs triage)
  - Slow triage response: 120 hours average
  - High open count: 5 open regressions
```

**CRITICAL**: When listing untriaged regressions that need action:

- **Only list OPEN untriaged regressions** - these are actionable
- **Do NOT recommend triaging closed regressions** - the tooling does not support retroactive triage
- Calculate actionable untriaged count as: `components.*.summary.open.total - components.*.summary.open.triaged`

### Step 7: Offer HTML Report Generation

After displaying the text report, ask the user if they want an interactive HTML report:

```
Would you like me to generate an interactive HTML report? (yes/no)
```

If the user responds affirmatively:

#### Step 7a: Prepare Data for HTML Report

The HTML report requires data in a specific structure. Transform the JSON data:

```python
# Prepare component data for HTML template
component_data = []
for component_name, component_obj in components.items():
    summary = component_obj['summary']
    component_data.append({
        'name': component_name,
        'total': summary['total'],
        'open': summary['open']['total'],
        'closed': summary['closed']['total'],
        'triaged': summary['triaged'],
        'triage_percentage': summary['triage_percentage'],
        'time_to_triage_hrs_avg': summary.get('time_to_triage_hrs_avg'),
        'time_to_close_hrs_avg': summary.get('time_to_close_hrs_avg'),
        'health_grade': calculate_health_grade(summary)  # Calculate combined grade
    })
```

#### Step 7b: Generate HTML Report

Use the `generate_html_report.py` script (or inline Python code):

```bash
python3 plugins/component-health/skills/analyze-regressions/generate_html_report.py \
  --release 4.17 \
  --data regression_data.json \
  --output .work/component-health-4.17/report.html
```

Or use inline Python with the template:

```python
import json
from datetime import datetime

# Load template
with open('plugins/component-health/skills/analyze-regressions/report_template.html', 'r') as f:
    template = f.read()

# Replace placeholders
template = template.replace('{{RELEASE}}', '4.17')
template = template.replace('{{GENERATED_DATE}}', datetime.now().isoformat())
template = template.replace('{{SUMMARY_DATA}}', json.dumps(summary))
template = template.replace('{{COMPONENT_DATA}}', json.dumps(component_data))

# Write output
output_path = '.work/component-health-4.17/report.html'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w') as f:
    f.write(template)
```

#### Step 7c: Open the Report

Open the HTML report in the user's default browser:

**macOS**:

```bash
open .work/component-health-4.17/report.html
```

**Linux**:

```bash
xdg-open .work/component-health-4.17/report.html
```

**Windows**:

```bash
start .work/component-health-4.17/report.html
```

Display the file path to the user:

```
HTML report generated: .work/component-health-4.17/report.html
Opening in your default browser...
```

## Error Handling

### Common Errors

1. **Network Errors**

   - **Symptom**: `URLError` or connection timeout
   - **Solution**: Check network connectivity and firewall rules
   - **Retry**: Both scripts have 30-second timeouts

2. **Invalid Release Format**

   - **Symptom**: Empty results or error response
   - **Solution**: Verify the release format (e.g., "4.17", not "v4.17" or "4.17.0")

3. **Release Dates Not Found**

   - **Symptom**: `get_release_dates.py` returns error
   - **Solution**: Verify the release exists in the system; may be too old or not yet created
   - **Fallback**: Proceed without date filtering (omit `--start` and `--end` parameters)

4. **No Regressions Found**

   - **Symptom**: Empty components object
   - **Solution**: Verify the release has regression data; may be too early in development
   - **Action**: Inform user that no regressions exist yet for this release

5. **Component Filter No Matches**

   - **Symptom**: Empty components object after filtering
   - **Solution**: Check component name spelling; component names are case-insensitive
   - **Action**: List available components from unfiltered query

6. **HTML Template Not Found**
   - **Symptom**: FileNotFoundError when generating HTML report
   - **Solution**: Verify template exists at `plugins/component-health/skills/analyze-regressions/report_template.html`
   - **Fallback**: Offer text report only

### Debugging

Enable verbose output by examining stderr:

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.17 \
  --short 2>&1 | tee debug.log
```

Diagnostic messages include:

- URL being queried
- Number of regressions fetched
- Number after filtering
- Number of suspected infrastructure regressions filtered

## Output Format

### Text Report Structure

The text report should include:

1. **Header**

   - Release version
   - Development window dates (start and end/GA)
   - Release status (GA'd or In Development)

2. **Overall Health Grade**

   - Total regressions
   - Filtered infrastructure regressions count
   - Open/closed breakdown
   - Triage coverage score with grade
   - Triage timeliness score with grade
   - Resolution speed score with grade

3. **Component Health Scorecard**

   - Ranked table of all components
   - Key metrics per component
   - Health grade per component

4. **Components Needing Attention**

   - List of components with specific issues
   - Actionable recommendations (only for open untriaged regressions)
   - Context for each issue

5. **Footer**
   - Link to Sippy dashboard (if applicable)
   - Timestamp of report generation

### HTML Report Features

The HTML report should include:

- **Interactive table** with sorting and filtering
- **Visual indicators** for health grades (colors, icons)
- **Charts/graphs** showing:
  - Triage coverage by component
  - Time to triage distribution
  - Open vs closed breakdown
- **Detailed metrics** on hover or click
- **Export functionality** (CSV, PDF)
- **Responsive design** for mobile viewing

## Examples

### Example 1: Grade Overall Release Health

```
/component-health:analyze-regressions 4.17
```

**Execution flow**:

1. Fetch release dates for 4.17
2. Run list_regressions.py with --start and --end (GA'd release)
3. Display overall health grade
4. Display per-component scorecard
5. Highlight components needing attention
6. Offer HTML report generation

### Example 2: Grade Specific Components

```
/component-health:analyze-regressions 4.21 --components Monitoring etcd
```

**Execution flow**:

1. Fetch release dates for 4.21 (may have null GA)
2. Run list_regressions.py with --components and --start only (in-development)
3. Display health grades for Monitoring and etcd only
4. Compare the two components
5. Identify which needs more attention

### Example 3: Grade Single Component

```
/component-health:analyze-regressions 4.21 --components "kube-apiserver"
```

**Execution flow**:

1. Fetch release dates for 4.21
2. Run list_regressions.py with single component filter
3. Display detailed health metrics for kube-apiserver
4. Show open vs closed breakdown
5. List count of open untriaged regressions (if any)

## Health Grade Calculation Details

### Combined Health Grade

To calculate an overall health grade for a component, consider all three metrics:

```python
def calculate_health_grade(summary):
    """Calculate combined health grade based on three key metrics."""
    triage_coverage = summary['triage_percentage']
    triage_time = summary.get('time_to_triage_hrs_avg')
    resolution_time = summary.get('time_to_close_hrs_avg')

    # Score each metric (0-3)
    coverage_score = (
        3 if triage_coverage >= 90 else
        2 if triage_coverage >= 70 else
        1 if triage_coverage >= 50 else
        0
    )

    time_score = 3  # Default to excellent if no data
    if triage_time is not None:
        time_score = (
            3 if triage_time < 24 else
            2 if triage_time < 72 else
            1 if triage_time < 168 else
            0
        )

    resolution_score = 3  # Default to excellent if no data
    if resolution_time is not None:
        resolution_score = (
            3 if resolution_time < 168 else
            2 if resolution_time < 336 else
            1 if resolution_time < 720 else
            0
        )

    # Average the scores
    avg_score = (coverage_score + time_score + resolution_score) / 3

    # Return grade
    if avg_score >= 2.5:
        return "Excellent ✅"
    elif avg_score >= 1.5:
        return "Good ⚠️"
    elif avg_score >= 0.5:
        return "Needs Improvement ⚠️"
    else:
        return "Poor ❌"
```

### Prioritizing Components Needing Attention

Rank components by priority based on:

1. **High open untriaged count** (most urgent)

   - Calculate: `summary.open.total - summary.open.triaged`
   - Threshold: >3 open untriaged regressions

2. **Low triage coverage** (second priority)

   - Use: `summary.triage_percentage`
   - Threshold: <50%

3. **Slow triage response** (third priority)

   - Use: `summary.time_to_triage_hrs_avg`
   - Threshold: >72 hours

4. **High total regression count** (fourth priority)
   - Use: `summary.total`
   - Threshold: Component-relative (top quartile)

## Advanced Features

### Trend Analysis (Future Enhancement)

Compare metrics across releases:

```
/component-health:analyze-regressions 4.17 --compare 4.16
```

### Export to CSV

Generate CSV report for spreadsheet analysis:

```
/component-health:analyze-regressions 4.17 --export-csv
```

### Custom Thresholds

Allow users to customize health grade thresholds:

```
/component-health:analyze-regressions 4.17 --triage-threshold 80
```

## Integration with Other Commands

This skill can be used by:

- `/component-health:analyze-regressions` command (primary)
- Quality metrics dashboards
- Release readiness reports
- Team performance tracking tools

## Related Skills

- `get-release-dates` - Fetches release development window dates
- `list-regressions` - Fetches raw regression data
- `prow-job:analyze-test-failure` - Analyzes individual test failures

## Notes

- All scripts use Python's standard library only (no external dependencies)
- Output is cached in `.work/` directory for performance
- Regression data is fetched in real-time from the API
- HTML reports are standalone (no external dependencies, embedded CSS/JS)
- The `--short` flag is critical to prevent output truncation with large datasets
- Health grades are subjective and intended as guidance, not criticism
- Infrastructure regressions (closed within 96 hours on high-volume days) are automatically filtered
- Retroactive triage of closed regressions is not supported by the tooling

## Troubleshooting

### Issue: Report Shows 0 Regressions

**Possible causes**:

1. Release is too early in development
2. Date filtering excluded all regressions
3. Component filter didn't match any components

**Solutions**:

1. Check release dates with `get_release_dates.py`
2. Try without date filtering
3. List available components without filter first

### Issue: Triage Percentages Seem Low

**Context**:

- Many teams are still ramping up regression triage practices
- Low percentages indicate opportunity for improvement, not failure
- Focus on the trend over time rather than absolute numbers

**Actions**:

- Identify specific untriaged open regressions that need attention
- Prioritize by regression severity and frequency
- Track improvement over subsequent releases

### Issue: HTML Report Not Opening

**Possible causes**:

1. Browser security restrictions on local files
2. Incorrect file path
3. Missing file permissions

**Solutions**:

1. Manually open the file from file explorer
2. Verify the file was created at the expected path
3. Check file permissions: `ls -la .work/component-health-*/report.html`

## Summary

This skill provides comprehensive component health analysis by:

1. Fetching release development window dates
2. Retrieving regression data filtered to the development window
3. Calculating health grades based on triage metrics
4. Generating actionable reports (text and HTML)
5. Identifying components that need help

The key focus is on **actionable insights** - particularly identifying open untriaged regressions that need immediate attention, while avoiding recommendations for closed regressions which cannot be retroactively triaged.
