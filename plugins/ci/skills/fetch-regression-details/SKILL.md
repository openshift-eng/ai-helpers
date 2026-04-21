---
name: Fetch Regression Details
description: Fetch detailed information about a Component Readiness regression from the Sippy API
---

# Fetch Regression Details

This skill fetches detailed regression information from the Component Readiness API. It retrieves comprehensive data about a specific regression including test name, affected variants, release information, triage status, and related metadata.

## When to Use This Skill

Use this skill when you need to retrieve complete details about a Component Readiness regression, such as:

- Analyzing a specific regression from Component Readiness
- Getting test name, release, and variant information for a regression
- Checking triage status and existing bug assignments
- Building regression analysis reports
- Automating regression workflows

## Prerequisites

1. **Network Access**: Must be able to reach the Sippy API
   - Check: `curl -s https://sippy.dptools.openshift.org/api/health`
   - No authentication required for public API endpoints

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Should be available on most systems
   - Uses only standard library (no external dependencies)

## Implementation Steps

### Step 1: Run the Python Script

The skill uses a Python script to fetch and parse regression data (including sample failed jobs):

```bash
# Path to the Python script
script_path="plugins/ci/skills/fetch-regression-details/fetch_regression_details.py"

# Fetch regression data in JSON format (includes failed jobs)
python3 "$script_path" <regression_id> --format json

# Or fetch as human-readable summary
python3 "$script_path" <regression_id> --format summary
```

### Step 2: Parse the Output

The script outputs structured JSON data that can be further processed:

```bash
# Store JSON output in a variable for processing
regression_data=$(python3 "$script_path" 34446 --format json)

# Extract specific fields using jq if needed
test_name=$(echo "$regression_data" | jq -r '.test_name')
component=$(echo "$regression_data" | jq -r '.component')
jira_keys=$(echo "$regression_data" | jq -r '.triages[].jira_key')

# Extract failed job URLs for analysis
failed_job_urls=$(echo "$regression_data" | jq -r '.sample_failed_jobs | to_entries[] | .value.failed_runs[] | .job_url')
```

### Step 3: Use the Data

The structured data includes all necessary regression details:

```json
{
  "regression_id": 34446,
  "test_name": "[sig-builds][Feature:Builds] custom build with buildah...",
  "test_id": "openshift-tests:71c053c318c11cfc47717b9cf711c326",
  "release": "4.22",
  "base_release": "4.21",
  "component": "Build",
  "capability": "Builds",
  "view": "4.22-main",
  "opened": "2026-01-28T08:02:45.127153Z",
  "closed": null,
  "status": "open",
  "last_failure": "2026-01-30T07:03:46Z",
  "variants": [
    "Architecture:amd64",
    "Platform:metal",
    "Network:ovn",
    "Upgrade:none"
  ],
  "max_failures": 18,
  "triages": [
    {
      "id": 344,
      "url": "https://redhat.atlassian.net/browse/OCPBUGS-74651",
      "jira_key": "OCPBUGS-74651",
      "type": "product",
      "description": "RHCOS 10 metal ipv4 job permafailing on ipv6 network access",
      "bug_id": 17817794,
      "resolved": false,
      "created_at": "2026-01-29T17:58:20.858051Z",
      "updated_at": "2026-01-30T13:28:33.429963Z"
    }
  ],
  "analysis_status": -2,
  "analysis_explanations": [
    "Test is failing consistently across multiple job runs",
    "Regression detected compared to baseline release"
  ],
  "sample_failed_jobs": {
    "periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview": {
      "pass_sequence": "FFFFFFFFFFFFFFFFFF",
      "label_summary": {
        "ErrImagePullQuay502BadGateway": 3
      },
      "failed_runs": [
        {
          "job_url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...",
          "job_run_id": "2017184460591599616",
          "start_time": "2026-01-30T10:33:47",
          "test_failures": 3,
          "job_labels": ["ErrImagePullQuay502BadGateway"]
        }
      ]
    },
    "periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-techpreview": {
      "pass_sequence": "SSFSSSSSSSS",
      "label_summary": {},
      "failed_runs": [
        {
          "job_url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...",
          "job_run_id": "2016460830022832128",
          "start_time": "2026-01-28T10:37:27",
          "test_failures": 1,
          "job_labels": []
        }
      ]
    }
  },
  "job_runs": [
    {
      "id": 2600,
      "regression_id": 34446,
      "prowjob_run_id": "2044678206610477056",
      "prowjob_name": "periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview",
      "prowjob_url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview/2044678206610477056",
      "start_time": "2026-04-16T07:23:39Z",
      "test_failures": 3
    }
  ],
  "test_details_url": "https://sippy.dptools.openshift.org/api/component_readiness/test_details?...",
  "api_url": "https://sippy.dptools.openshift.org/api/component_readiness/regressions/34446"
}
```

**Note:**
- `analysis_status`: Integer status code from the regression analysis. Negative numbers indicate problems, with lower numbers representing more severe issues.
- `analysis_explanations`: List of human-readable explanations describing the status of the regression.
- `sample_failed_jobs`: Dictionary keyed by job name. Each job contains:
  - `pass_sequence`: Chronological success/fail pattern for this specific job (newest to oldest). "S" = successful run, "F" = failing run. Example: "FFFFFSSS" shows 5 recent failures, then 3 older successes.
  - `label_summary`: Dictionary of `{label: count}` aggregated across all failed runs for this job. A label appearing in many/all failed runs is a strong signal that the labelled symptom is the root cause. Labels are human-defined: a team member wrote a regex that matches specific artifact content and named the symptom (e.g., `"ErrImagePullQuay502BadGateway"`). If many or all failed runs share a label, prioritize investigating that symptom.
  - `failed_runs`: List of failed runs for this job, sorted by start_time (newest first). Each run includes:
    - `test_failures`: Total number of tests failing in the entire job run (not just the regressed test). High values (>10) indicate a mass failure run where the regressed test may be collateral damage rather than the primary problem.
    - `job_labels`: List of symptom labels applied to this specific run. Labels are precise — they fire only when a human-defined regex matches job artifacts. An empty list means no known symptom was detected for this run.
- `job_runs`: Complete list of all job runs where the failure was observed throughout the entire life of the regression (not just the last reporting period). Sorted by start_time (newest first). Each entry contains:
  - `id`: Unique ID for this job run record
  - `regression_id`: The regression this run belongs to
  - `prowjob_run_id`: The Prow job run ID
  - `prowjob_name`: The Prow job name
  - `prowjob_url`: Direct URL to the Prow job run
  - `start_time`: ISO 8601 timestamp when the job started
  - `test_failures`: Integer — total number of test failures in this job run. High values (e.g., >10) indicate a mass failure run where the regressed test may just be caught up in a larger issue rather than being the primary problem
  - This data is useful for: determining when the regression started (earliest entries), how frequently it occurs, whether failures cluster in certain jobs, identifying mass failure runs where the regression may be collateral damage, and linking related regressions that share the same job runs. Sippy uses this data automatically in the `fetch_related_triages` API to find regressions with shared job runs.

## Error Handling

The Python script handles common error cases automatically:

### Case 1: Regression Not Found (404)

```bash
python3 fetch_regression_details.py 99999999
# Error: Regression ID 99999999 not found.
# Verify the regression ID exists in Component Readiness.
```

### Case 2: Invalid Regression ID

```bash
python3 fetch_regression_details.py abc
# Error: Regression ID must be a positive integer, got 'abc'
```

### Case 3: Network Error

```bash
python3 fetch_regression_details.py 34446
# Error: Failed to connect to Sippy API: [Errno -2] Name or service not known
# Check network connectivity and VPN settings.
```

### Case 4: Missing Arguments

```bash
python3 fetch_regression_details.py
# Usage: fetch_regression_details.py <regression_id> [--format json|summary]
```

**Exit Codes:**
- `0`: Success
- `1`: Error (invalid input, API error, network error, etc.)

## API Response Schema

The API returns a JSON object with the following structure:

```json
{
  "id": 34446,
  "view": "4.22-main",
  "release": "4.22",
  "base_release": "4.21",
  "component": "Build",
  "capability": "Builds",
  "test_id": "openshift-tests:71c053c318c11cfc47717b9cf711c326",
  "test_name": "[sig-builds][Feature:Builds] custom build with buildah...",
  "variants": [
    "Upgrade:none",
    "Architecture:amd64",
    "Platform:metal",
    "Network:ovn"
  ],
  "opened": "2026-01-28T08:02:45.127153Z",
  "closed": {
    "Time": "0001-01-01T00:00:00Z",
    "Valid": false
  },
  "triages": [
    {
      "id": 344,
      "created_at": "2026-01-29T17:58:20.858051Z",
      "updated_at": "2026-01-30T13:28:33.429963Z",
      "url": "https://redhat.atlassian.net/browse/OCPBUGS-74651",
      "description": "Description of the triage",
      "type": "product",
      "bug_id": 17817794,
      "resolved": {
        "Time": "0001-01-01T00:00:00Z",
        "Valid": false
      }
    }
  ],
  "last_failure": {
    "Time": "2026-01-30T07:03:46Z",
    "Valid": true
  },
  "max_failures": 18,
  "job_runs": [
    {
      "id": 2600,
      "regression_id": 34446,
      "prowjob_run_id": "2044678206610477056",
      "prowjob_name": "periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview",
      "prowjob_url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...",
      "start_time": "2026-04-16T07:23:39Z",
      "test_failures": 3
    }
  ],
  "links": {
    "self": "https://sippy.dptools.openshift.org/api/component_readiness/regressions/34446",
    "test_details": "https://sippy.dptools.openshift.org/api/component_readiness/test_details?..."
  }
}
```

**Key Fields:**
- `id`: Regression ID
- `test_name`: Full test name with signature groups
- `release`: Sample release (e.g., "4.22")
- `base_release`: Baseline release for comparison (e.g., "4.21")
- `component`: Component owning the test
- `capability`: Higher-level capability area
- `variants`: Array of variant key:value pairs (e.g., "Platform:metal", "Network:ovn")
- `opened`: ISO 8601 timestamp when regression was first detected
- `closed`: Object with `Valid` boolean and `Time` (valid if regression is closed)
- `triages`: Array of triage objects with JIRA URL, type, and resolution status
- `job_runs`: Array of all job runs where the failure was observed throughout the regression's entire life. Each entry includes `prowjob_run_id`, `prowjob_name`, `prowjob_url`, `start_time`, and `test_failures` (total failures in the run — high values indicate mass failure runs where the regression may be collateral damage)
- `links.test_details`: Direct URL to Sippy test details page with sample failures

## Examples

### Example 1: Fetch Regression as JSON

```bash
# Fetch regression 34446 in JSON format (includes failed jobs)
python3 plugins/ci/skills/fetch-regression-details/fetch_regression_details.py 34446 --format json
```

**Expected Output:**
```json
{
  "regression_id": 34446,
  "test_name": "[sig-builds][Feature:Builds] custom build with buildah...",
  "test_id": "openshift-tests:71c053c318c11cfc47717b9cf711c326",
  "release": "4.22",
  "base_release": "4.21",
  "component": "Build",
  "capability": "Builds",
  "status": "open",
  "variants": ["Architecture:amd64", "Platform:metal", "Network:ovn"],
  "triages": [
    {
      "jira_key": "OCPBUGS-74651",
      "type": "product",
      "resolved": false
    }
  ],
  "analysis_status": -2,
  "analysis_explanations": [
    "Test is failing consistently across multiple job runs",
    "Regression detected compared to baseline release"
  ],
  "sample_failed_jobs": {
    "periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview": {
      "pass_sequence": "FFFFFFFFFFFFFFFFFF",
      "failed_runs": [
        {
          "job_url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...",
          "job_run_id": "2017184460591599616",
          "start_time": "2026-01-30T10:33:47"
        }
      ]
    }
  }
}
```

### Example 2: Fetch Regression as Human-Readable Summary

```bash
# Fetch regression 34446 as formatted summary
python3 plugins/ci/skills/fetch-regression-details/fetch_regression_details.py 34446 --format summary
```

**Expected Output:**
```
Regression #34446 Details:
============================================================

Test Name: [sig-builds][Feature:Builds] custom build with buildah...
Release: 4.22 (baseline: 4.21)
Component: Build

Status: Open (opened: 2026-01-28)
Max Failures: 19

Triages:
  - OCPBUGS-74651 (product, active): Description of the issue

Sample Failed Jobs (19 runs):
  - periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview
    Run ID: 2017184460591599616
    Started: 2026-01-30
    URL: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
```

### Example 3: Extract Failed Job URLs

```bash
# Get all failed job URLs for analysis
script_path="plugins/ci/skills/fetch-regression-details/fetch_regression_details.py"
data=$(python3 "$script_path" 34446 --format json)

# Extract failed job URLs
echo "$data" | jq -r '.sample_failed_jobs | to_entries[] | .value.failed_runs[] | .job_url'
```

**Expected Output:**
```
https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview/2017184460591599616
https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview/2017131608699572224
...
```

## Output Format

The script supports two output formats:

### JSON Format (--format json)

Returns structured JSON data with all regression fields:

```json
{
  "regression_id": 34446,
  "test_name": "...",
  "test_id": "...",
  "release": "4.22",
  "base_release": "4.21",
  "component": "Build",
  "capability": "Builds",
  "view": "4.22-main",
  "opened": "2026-01-28T08:02:45.127153Z",
  "closed": null,
  "status": "open",
  "last_failure": "2026-01-30T07:03:46Z",
  "variants": [...],
  "max_failures": 19,
  "triages": [...],
  "analysis_status": -2,
  "analysis_explanations": ["...", "..."],
  "sample_failed_jobs": {...},
  "test_details_url": "...",
  "api_url": "..."
}
```

### Summary Format (--format summary)

Returns human-readable formatted summary:

```
Regression #34446 Details:
============================================================

Test Name: [sig-builds][Feature:Builds] custom build with buildah...
Release: 4.22 (baseline: 4.21)
Component: Build
Capability: Builds

Status: Open (opened: 2026-01-28)
Last Failure: 2026-01-30
Max Failures: 19

Analysis Status: -2
  (Negative status indicates a problem - lower is more severe)
Analysis Explanations:
  - Test is failing consistently across multiple job runs
  - Regression detected compared to baseline release

Affected Variants:
  - Architecture:amd64
  - Platform:metal
  - Network:ovn
  - Upgrade:none

Triages:
  - OCPBUGS-74651 (product, active): Description...

Test Details: https://sippy.dptools.openshift.org/...
API URL: https://sippy.dptools.openshift.org/api/...
```

## Notes

- The Python script uses only standard library modules (no external dependencies)
- The API does not require authentication for read-only access
- Regression IDs are persistent and do not change
- The `test_details_url` provides links to sample job failures for further analysis
- Closed regressions will have `status: "closed"` and a non-null `closed` timestamp
- The `variants` array shows all platform/topology combinations where the test is failing
- Default output format is JSON; use `--format summary` for human-readable output
- `analysis_status` is an integer where negative values indicate problems (lower = more severe)
- `analysis_explanations` provides human-readable context for the analysis status
- `sample_failed_jobs` is a dictionary keyed by job name, containing only jobs with at least one failed run
- Each job includes a `pass_sequence` string (newest to oldest) with "S" for successful runs and "F" for failed runs
- Each job includes a `label_summary` dict aggregating `job_labels` across all failed runs for that job. This is the first place to look for a shared root cause: if most or all failed runs share a label, that symptom is almost certainly the root cause. Labels are human-defined and precise — they only fire when a regex written by a team member matches specific artifact content.
- Each failed run includes `test_failures` (total tests failing in the job run) and `job_labels` (symptom labels for that specific run). Use `test_failures > 10` as a signal for mass failure runs where the regressed test may be collateral damage.
- `job_runs` contains the complete history of all job runs where the failure was observed across the regression's entire lifetime, sorted by start_time (newest first). Use this to determine when failures started, how common they were, and which jobs are most affected. The `test_failures` field shows the total failure count in each run — high values (e.g., >10) indicate mass failure runs where the regression may just be caught up in a larger issue rather than being the primary problem

## See Also

- Component Readiness API Documentation: https://sippy.dptools.openshift.org/api/docs
- Related Skill: `ci:analyze-prow-job-test-failure` (for analyzing individual test failures)
- Related Command: `/ci:analyze-regression` (uses this skill)
