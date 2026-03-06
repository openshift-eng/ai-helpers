---
name: Find Regressing Jobs
description: Query Sippy for regressing CI jobs and rank them by severity
---

# Find Regressing Jobs

This skill queries the public Sippy API to find CI jobs that are regressing in a given OpenShift release, ranked by severity.

## When to Use This Skill

Use this skill when you need to:

- Find which CI jobs are currently regressing for a release
- Triage CI health for a specific OpenShift version
- Identify jobs that need investigation or bug filing
- Get a quick overview of CI problems sorted by severity

## Prerequisites

1. **Network Access**: Must be able to reach `sippy.dptools.openshift.org` (public, no auth)
2. **curl or WebFetch**: For making API requests

## Implementation Steps

### Step 1: Parse Arguments

Parse the command arguments:

- `release` (required): OpenShift version, e.g., "4.22"
- `--period` (optional, default: "twoDay"): Time period for comparison. Options: "twoDay", "default"
- `--min-runs` (optional, default: 5): Minimum number of runs to include a job
- `--limit` (optional, default: 20): Maximum number of results to return

### Step 2: Query Sippy Jobs API

Make a GET request to the public Sippy jobs API:

```
GET https://sippy.dptools.openshift.org/api/jobs?release={release}&filter={filter_json}&period={period}&sortField=net_improvement&sort=asc&perPage={limit}&page=0
```

The filter JSON should be URL-encoded and contain:

```json
{
  "items": [
    {
      "columnField": "current_runs",
      "operatorValue": ">=",
      "value": "{min_runs}"
    },
    {
      "columnField": "variants",
      "operatorValue": "has entry",
      "value": "never-stable",
      "not": true
    }
  ],
  "linkOperator": "and"
}
```

Use `curl` or `WebFetch` to make the request. Example with curl:

```bash
RELEASE="4.22"
PERIOD="twoDay"
MIN_RUNS="5"
LIMIT="20"

FILTER='{"items":[{"columnField":"current_runs","operatorValue":">=","value":"'"$MIN_RUNS"'"},{"columnField":"variants","operatorValue":"has entry","value":"never-stable","not":true}],"linkOperator":"and"}'

curl -s "https://sippy.dptools.openshift.org/api/jobs?release=${RELEASE}&period=${PERIOD}&sortField=net_improvement&sort=asc&perPage=${LIMIT}&page=0&filter=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${FILTER}'))")"
```

### Step 3: Parse Response

The API returns a JSON array of job objects. Each job has these key fields:

- `name`: Full Prow job name
- `current_pass_percentage`: Pass rate in current period (0-100)
- `previous_pass_percentage`: Pass rate in previous period (0-100)
- `net_improvement`: Change in pass rate (negative = regression)
- `current_runs`: Number of runs in current period
- `open_bugs`: Number of open bugs linked to this job
- `variants`: Array of variant tags (e.g., ["aws", "ovn", "serial"])
- `test_grid_url`: Link to TestGrid for this job

Parse the JSON response. If the response is empty or an error, report it and exit.

### Step 4: Classify and Format Results

For each job in the results:

1. **Flag "already tracked"**: If `open_bugs > 0`, mark the job as already having bugs filed
2. **Flag "needs investigation"**: If `current_pass_percentage < 50` AND `net_improvement < -20`, mark as needing investigation
3. **Compute delta**: `net_improvement` is already the delta (current - previous)

### Step 5: Output Results

Output a markdown table sorted by `net_improvement` (worst first):

```markdown
## Regressing Jobs for {release} ({period} period)

| # | Job | Current % | Prev % | Delta | Runs | Bugs | Status |
|---|-----|-----------|--------|-------|------|------|--------|
| 1 | {short_name} | {current}% | {prev}% | {delta} | {runs} | {bugs} | {status_flag} |
```

Where:
- `short_name`: Remove the `periodic-ci-openshift-release-main-nightly-{version}-` prefix if present for readability, but include the full name in a details section or tooltip
- `status_flag`: "INVESTIGATE" for needs-investigation jobs, "TRACKED" for jobs with open bugs, empty otherwise
- `delta`: Show with sign (e.g., "-34.5")

After the table, output a summary:

```markdown
### Summary
- **Total regressing jobs**: {count}
- **Need investigation** (< 50% pass, > 20pt regression): {investigate_count}
- **Already tracked** (have open bugs): {tracked_count}
- **Untracked regressions**: {untracked_count}
```

### Step 6: Output Structured Data

After the human-readable table, output a structured block that downstream skills can parse:

```
REGRESSING_JOBS_DATA:
  release: {release}
  period: {period}
  jobs:
    - name: {full_job_name}
      current_pass_percentage: {value}
      previous_pass_percentage: {value}
      net_improvement: {value}
      current_runs: {value}
      open_bugs: {value}
      needs_investigation: {true|false}
      variants: [{variant_list}]
```

## Error Handling

1. **Network error**: Print error message and exit
2. **Empty response**: Report "No jobs found matching criteria" -- may indicate wrong release version
3. **API error**: Print the error response body for debugging

## Notes

- The Sippy API is public and requires no authentication
- The `twoDay` period is recommended for catching fresh regressions (default)
- The `default` period uses Sippy's default comparison window (typically 7 days)
- Jobs with the `never-stable` variant are excluded because they have never been expected to pass consistently
- The `net_improvement` field is negative for regressions (lower is worse)
- Results are pre-sorted by the API (ascending `net_improvement`), so worst regressions come first

## See Also

- Related Command: `/ci:find-regressing-jobs` - The user-facing command
- Related Command: `/ci:investigate-job` - Deep-dive a specific job from these results
- Related Command: `/ci:hunt-problems` - Orchestrator that uses this skill as the first step
- Related Command: `/ci:list-unstable-tests` - Find unstable tests (complementary view)
