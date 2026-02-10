---
name: Fetch Test Report
description: Fetch an OpenShift CI test report by name to get pass rates, test ID, and Jira component from Sippy
---

# Fetch Test Report

This skill fetches a report for an OpenShift CI test by its full name using the Sippy tests API. It returns test metadata including the BigQuery/Component Readiness test ID, Jira component, pass rates for the current and previous reporting periods, and open bug counts.

## When to Use This Skill

Use this skill when you need to:

- Look up a test's Component Readiness / BigQuery test ID (`test_id`)
- Check current and previous pass rates for a test
- Find the Jira component associated with a test
- Determine if a test is flaking, failing, or stable
- Get run counts and failure/flake breakdowns for a test

## Prerequisites

1. **Sippy Port-Forward**: The Sippy API must be accessible at `http://127.0.0.1:8080`
   - Typically via: `kubectl port-forward -n sippy svc/sippy 8080:8080`
   - Check: `curl -s http://127.0.0.1:8080/api/health?release=4.22`

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

## Implementation Steps

### Step 1: Determine the Release

If the user did not specify a release, use the `fetch-releases` skill to determine the latest OCP release:

```bash
release=$(python3 plugins/ci/skills/fetch-releases/fetch_releases.py --latest)
```

If the user specified a release, use that directly.

### Step 2: Run the Python Script

The skill uses a Python script to query the Sippy tests API:

```bash
# Path to the Python script
script_path="plugins/ci/skills/fetch-test-report/fetch_test_report.py"

# Fetch test report in JSON format
python3 "$script_path" "<test_name>" --release "$release" --format json

# Or fetch as human-readable summary
python3 "$script_path" "<test_name>" --release "$release" --format summary
```

### Step 3: Parse the Output

The script outputs a JSON array (typically with one element for an exact name match):

```bash
# Store JSON output in a variable for processing
test_data=$(python3 "$script_path" "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]" --format json)

# Extract specific fields using jq
test_id=$(echo "$test_data" | jq -r '.[0].test_id')
component=$(echo "$test_data" | jq -r '.[0].jira_component')
pass_rate=$(echo "$test_data" | jq -r '.[0].current_pass_percentage')
runs=$(echo "$test_data" | jq -r '.[0].current_runs')
```

## API Details

### Endpoint

```
GET http://127.0.0.1:8080/api/tests/v2?release={release}&filter={filter_json}
```

### Filter Format

The filter parameter is a JSON object using Sippy's standard filter syntax:

```json
{
  "items": [
    {
      "columnField": "name",
      "operatorValue": "equals",
      "value": "<test_name>"
    }
  ]
}
```

### Response Schema

The API returns a JSON array of test objects:

```json
[
  {
    "id": 5987,
    "test_id": "openshift-tests:e8f7491a505095b6356dfd8d4cf7218b",
    "name": "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]",
    "suite_name": "openshift-tests",
    "variants": null,
    "jira_component": "kube-apiserver",
    "jira_component_id": "12367637",
    "current_successes": 3425,
    "current_failures": 22,
    "current_flakes": 0,
    "current_pass_percentage": 99.36,
    "current_failure_percentage": 0.64,
    "current_flake_percentage": 0,
    "current_working_percentage": 99.36,
    "current_runs": 3447,
    "previous_successes": 2570,
    "previous_failures": 43,
    "previous_flakes": 0,
    "previous_pass_percentage": 98.35,
    "previous_failure_percentage": 1.65,
    "previous_flake_percentage": 0,
    "previous_working_percentage": 98.35,
    "previous_runs": 2613,
    "net_failure_improvement": 1.01,
    "net_flake_improvement": 0,
    "net_working_improvement": 1.01,
    "net_improvement": 1.01,
    "tags": null,
    "open_bugs": 0
  }
]
```

**Key Fields:**
- `id`: Sippy PostgreSQL internal ID (less commonly used)
- `test_id`: BigQuery / Component Readiness test ID (format: `suite:hash`). This is the ID used with modern skills like `fetch-regression-details` and `fetch-test-runs`.
- `name`: Full test name
- `suite_name`: Test suite (e.g., `openshift-tests`)
- `jira_component`: Associated OCPBUGS Jira component
- `jira_component_id`: Jira component numeric ID
- `current_*`: Metrics for the current 7-day reporting period
- `previous_*`: Metrics for the 7 days before the current period
- `net_working_improvement`: Change in working percentage (positive = improving)
- `open_bugs`: Number of open bugs linked to this test

## Error Handling

### Case 1: Sippy Not Reachable

```bash
python3 fetch_test_report.py "[sig-api-machinery] ..."
# Error: Failed to connect to Sippy API: [Errno 61] Connection refused
# Ensure the Sippy port-forward is running (typically: kubectl port-forward -n sippy svc/sippy 8080:8080).
```

### Case 2: No Test Found

If the test name doesn't match any test, the script returns an empty JSON array `[]` or "No tests found matching the given name." in summary mode.

### Case 3: Missing Arguments

```bash
python3 fetch_test_report.py
# usage: fetch_test_report.py [-h] [--release RELEASE] [--format {json,summary}] test_name
# fetch_test_report.py: error: the following arguments are required: test_name
```

**Exit Codes:**
- `0`: Success
- `1`: Error (API error, network error, etc.)

## Examples

### Example 1: Fetch Test Report in JSON Format

```bash
python3 plugins/ci/skills/fetch-test-report/fetch_test_report.py \
  "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]" \
  --release 4.22 --format json
```

### Example 2: Get a Human-Readable Summary

```bash
python3 plugins/ci/skills/fetch-test-report/fetch_test_report.py \
  "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]" \
  --release 4.22 --format summary
```

**Expected Output:**
```
Test: [sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]
  Test ID:         openshift-tests:abc123def456
  Suite:           openshift-tests
  Jira Component:  kube-apiserver
  Open Bugs:       0

  Current Period (last 7 days):
    Runs:       3447
    Pass Rate:  99.36%
    Failures:   22 (0.64%)
    Flakes:     0 (0.00%)

  Previous Period (7 days before current):
    Runs:       2613
    Pass Rate:  98.35%
    Failures:   43 (1.65%)
    Flakes:     0 (0.00%)

  Trend:  improved (+1.01%)
```

### Example 3: Fetch Test Report for a Different Release

```bash
python3 plugins/ci/skills/fetch-test-report/fetch_test_report.py \
  "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]" \
  --release 4.21 --format json
```

## Notes

- The test name must be an **exact match** — use the full test name including sig prefix and suite tags
- The API is accessed via local port-forward; ensure the Sippy port-forward is active
- If `--release` is not specified, use the `fetch-releases` skill to determine the latest release
- `current_*` fields cover the last 7 days; `previous_*` fields cover the 7 days before that
- `current_working_percentage` = pass rate + flake rate (tests that ultimately passed, possibly after retries)
- The `test_id` field is the one used in Component Readiness URLs and with the `fetch-regression-details` and `fetch-test-runs` skills
- An empty result (`[]`) means no test matched — double-check the exact test name spelling

## See Also

- Related Skill: `fetch-releases` (determines the latest OCP release)
- Related Skill: `fetch-regression-details` (uses `test_id` to fetch regression details)
- Related Skill: `fetch-test-runs` (uses test name to fetch individual test run results)
- Related Command: `/ci:fetch-test-report` (command that invokes this skill)
- Related Command: `/ci:analyze-regression` (full regression analysis workflow)
