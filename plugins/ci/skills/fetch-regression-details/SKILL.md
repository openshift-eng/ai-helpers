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
failed_job_urls=$(echo "$regression_data" | jq -r '.sample_failed_jobs[].job_url')
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
      "url": "https://issues.redhat.com/browse/OCPBUGS-74651",
      "jira_key": "OCPBUGS-74651",
      "type": "product",
      "description": "RHCOS 10 metal ipv4 job permafailing on ipv6 network access",
      "bug_id": 17817794,
      "resolved": false,
      "created_at": "2026-01-29T17:58:20.858051Z",
      "updated_at": "2026-01-30T13:28:33.429963Z"
    }
  ],
  "sample_failed_jobs": [
    {
      "job_url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...",
      "job_run_id": "2017184460591599616",
      "start_time": "2026-01-30T10:33:47",
      "job_name": "periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview"
    }
  ],
  "test_details_url": "https://sippy.dptools.openshift.org/api/component_readiness/test_details?...",
  "api_url": "https://sippy.dptools.openshift.org/api/component_readiness/regressions/34446"
}
```

**Note:** The `sample_failed_jobs` field is always included. These are job runs from the sample release (not baseline) where the test failed (failure_count > 0).

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
      "url": "https://issues.redhat.com/browse/OCPBUGS-74651",
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
  "sample_failed_jobs": [
    {
      "job_url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...",
      "job_run_id": "2017184460591599616",
      "start_time": "2026-01-30T10:33:47",
      "job_name": "periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview"
    }
  ]
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
echo "$data" | jq -r '.sample_failed_jobs[].job_url'
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
- `sample_failed_jobs` is always included and contains runs where the test failed (failure_count > 0) from the sample release (not baseline)
- Failed jobs are sorted by start_time (most recent first)

## See Also

- Component Readiness API Documentation: https://sippy.dptools.openshift.org/api/docs
- Related Skill: `prow-job:analyze-test-failure` (for analyzing individual test failures)
- Related Command: `/ci:analyze-regression` (uses this skill)
