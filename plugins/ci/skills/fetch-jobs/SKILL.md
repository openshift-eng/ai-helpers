---
name: fetch-jobs
description: Fetch OpenShift CI job reports from Sippy with pass rates, run counts, and trend data for release or presubmit jobs
---

# Fetch Jobs

This skill fetches job reports from the Sippy jobs API. It returns job metadata including pass rates, run counts, and trend data comparing the current 7-day window to the previous 7-day window. It supports both release jobs (e.g., `4.19`, `5.0`) and presubmit (pull request) jobs.

## When to Use This Skill

Use this skill when you need to:

- List jobs for a specific OpenShift release with their pass rates and run counts
- List presubmit (pull request) jobs across all repos or filtered to a specific repo
- Find the most frequently run jobs (sort by `current_runs`)
- Find jobs with declining pass rates (sort by `net_improvement`)
- Identify the least stable jobs (sort by `current_pass_percentage` ascending)
- Check how a repo's presubmit jobs are performing
- Get trend data comparing current vs previous reporting periods

## Prerequisites

1. **Network Access**: The Sippy API must be accessible at `https://sippy.dptools.openshift.org`
   - No authentication required for read operations
   - Check: `curl -s https://sippy.dptools.openshift.org/api/health?release=4.19`

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

## Implementation Steps

### Step 1: Determine the Release

If the user wants presubmit jobs, use `--release Presubmits`.

If the user wants release jobs and did not specify a version, use the `fetch-releases` skill:

```bash
release=$(python3 plugins/ci/skills/fetch-releases/fetch_releases.py --latest)
```

If the user specified a release, use that directly (e.g., `4.19`, `5.0`).

### Step 2: Run the Python Script

```bash
script_path="plugins/ci/skills/fetch-jobs/fetch_jobs.py"

# Fetch release jobs sorted by most runs (default)
python3 "$script_path" --release 5.0 --format json

# Fetch presubmit jobs for a specific repo
python3 "$script_path" --release Presubmits --repo origin --format summary

# Fetch the top 20 most frequently run presubmit jobs
python3 "$script_path" --release Presubmits --sort-field current_runs --sort desc --limit 20 --format summary

# Fetch jobs sorted by worst pass rate
python3 "$script_path" --release 4.19 --sort-field current_pass_percentage --sort asc --limit 10 --format summary

# Fetch jobs sorted by biggest regression
python3 "$script_path" --release 4.19 --sort-field net_improvement --sort asc --limit 10 --format summary

# Filter jobs by name substring
python3 "$script_path" --release 4.19 --name "e2e-aws-ovn" --format json
```

### Step 3: Parse the Output

The script outputs a JSON array of job objects:

```bash
# Store JSON output for processing
jobs=$(python3 "$script_path" --release Presubmits --repo machine-config-operator --format json)

# Extract specific fields using jq
echo "$jobs" | jq '.[0].name'
echo "$jobs" | jq '.[0].current_pass_percentage'
echo "$jobs" | jq '.[0].current_runs'

# Get top 5 jobs by run count
echo "$jobs" | jq 'sort_by(-.current_runs) | .[0:5] | .[] | {name, current_runs, current_pass_percentage}'
```

## API Details

### Endpoint

```
GET https://sippy.dptools.openshift.org/api/jobs?release={release}&filter={filter_json}&sortField={field}&sort={asc|desc}&period={default|twoDay}&limit={n}
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `release` | Yes | - | Release version (e.g., `4.19`, `5.0`) or `Presubmits` for PR jobs |
| `filter` | No | - | JSON-encoded filter (see filter format below) |
| `sortField` | No | `current_pass_percentage` | Field to sort by |
| `sort` | No | `asc` | Sort direction: `asc` or `desc` |
| `period` | No | `default` | `default` (7-day windows) or `twoDay` (2-day current vs 7-day previous) |
| `limit` | No | 0 (all) | Maximum results to return |

### Filter Format

The filter parameter is a JSON object using Sippy's standard filter syntax:

```json
{
  "items": [
    {
      "columnField": "variants",
      "operatorValue": "has entry",
      "value": "never-stable",
      "not": true
    },
    {
      "columnField": "repo",
      "operatorValue": "equals",
      "value": "origin"
    }
  ],
  "linkOperator": "and"
}
```

**Filterable fields:** `name`, `brief_name`, `org`, `repo`, `variants`, `current_pass_percentage`, `current_runs`, `previous_pass_percentage`, `previous_runs`, `net_improvement`, `open_bugs`

**Filter operators:** `contains`, `equals`, `starts with`, `ends with`, `has entry` (arrays), `has entry containing` (arrays), `is empty`, `is not empty`, `=`, `!=`, `>`, `>=`, `<`, `<=`

### Response Schema

The API returns a JSON array of job objects:

```json
[
  {
    "id": 123,
    "name": "periodic-ci-openshift-release-master-nightly-4.19-e2e-aws-ovn",
    "brief_name": "e2e-aws-ovn",
    "org": "openshift",
    "repo": "release",
    "variants": ["amd64", "aws", "ovn", "ha"],
    "last_pass": "2026-05-21T10:30:00Z",
    "current_pass_percentage": 87.5,
    "current_projected_pass_percentage": 88.2,
    "current_runs": 40,
    "current_passes": 35,
    "current_fails": 5,
    "current_infra_fails": 0,
    "previous_pass_percentage": 85.0,
    "previous_projected_pass_percentage": 84.5,
    "previous_runs": 40,
    "previous_passes": 34,
    "previous_fails": 6,
    "previous_infra_fails": 0,
    "net_improvement": 2.5,
    "average_retests_to_merge": 1.3,
    "test_grid_url": "https://testgrid.k8s.io/...",
    "open_bugs": 3
  }
]
```

**Key Fields:**
- `name`: Full job name
- `brief_name`: Short human-readable name
- `org`, `repo`: GitHub organization and repository (useful for presubmit jobs)
- `variants`: Array of job variant tags (e.g., platform, network, architecture)
- `current_runs` / `previous_runs`: Number of job runs in each 7-day window
- `current_pass_percentage` / `previous_pass_percentage`: Overall job pass rate (all tests passed)
- `current_fails` / `previous_fails`: Number of failing runs
- `current_infra_fails` / `previous_infra_fails`: Infrastructure-related failures (not code failures)
- `net_improvement`: Percentage point change in pass rate from previous to current period (positive = improving)
- `average_retests_to_merge`: Average retries needed before presubmit passes (presubmit jobs only)
- `open_bugs`: Count of open related Jira bugs
- `last_pass`: Timestamp of most recent successful run (null if never passed)

## Error Handling

### Case 1: Sippy Not Reachable

```bash
python3 fetch_jobs.py --release 4.19
# Error: Failed to connect to Sippy API: [Errno 61] Connection refused
# Check network connectivity to sippy.dptools.openshift.org.
```

### Case 2: No Jobs Found

If no jobs match the filters, the script returns an empty JSON array `[]` or "No jobs found matching the given criteria." in summary mode.

### Case 3: Missing Release

```bash
python3 fetch_jobs.py
# Using latest release: 5.0  (auto-detected)
```

**Exit Codes:**
- `0`: Success
- `1`: Error (API error, network error, etc.)

## Examples

### Example 1: List Presubmit Jobs for a Repo

```bash
python3 plugins/ci/skills/fetch-jobs/fetch_jobs.py \
  --release Presubmits --repo origin --format summary
```

### Example 2: Top 10 Most Frequently Run Release Jobs

```bash
python3 plugins/ci/skills/fetch-jobs/fetch_jobs.py \
  --release 4.19 --sort-field current_runs --sort desc --limit 10 --format summary
```

### Example 3: Jobs With Biggest Regressions

```bash
python3 plugins/ci/skills/fetch-jobs/fetch_jobs.py \
  --release 5.0 --sort-field net_improvement --sort asc --limit 10 --format summary
```

### Example 4: Filter Jobs by Name

```bash
python3 plugins/ci/skills/fetch-jobs/fetch_jobs.py \
  --release 4.19 --name "upgrade" --format json
```

### Example 5: Presubmit Jobs Using 2-Day Window

```bash
python3 plugins/ci/skills/fetch-jobs/fetch_jobs.py \
  --release Presubmits --repo machine-config-operator --period twoDay --format summary
```

## Notes

- Never-stable jobs are excluded by default — use `--include-never-stable` to include them
- For presubmit jobs, use `--release Presubmits` (case-sensitive)
- The `repo` filter matches the repository name only (e.g., `origin`), not the full org/repo path
- `current_*` fields cover the last 7 days; `previous_*` fields cover the 7 days before that (with `period=default`)
- With `period=twoDay`, current covers the last 2 days and previous covers the 7 days before that
- The `net_improvement` field is the difference in pass percentage between periods — negative values indicate regression
- `average_retests_to_merge` is primarily meaningful for presubmit jobs

## See Also

- Related Skill: `fetch-releases` (determines the latest OCP release)
- Related Skill: `fetch-test-report` (fetches test-level pass rates)
- Related Skill: `fetch-job-run-summary` (fetches details for a specific job run)
- Related Agent: `pr-risk-analyst` (uses job data for PR risk assessment)
