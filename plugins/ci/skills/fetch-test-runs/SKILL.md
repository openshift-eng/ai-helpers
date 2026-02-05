---
name: Fetch Test Runs
description: Fetch test runs from Sippy API including outputs for AI-based similarity analysis
---

# Fetch Test Runs

This skill fetches test runs from the Sippy API. It can return both failed and successful test runs, including JUnit output for AI-based analysis.

## When to Use This Skill

Use this skill when you need to:

- Fetch test run data for a specific test across all jobs
- Get raw test failure outputs for AI-based similarity analysis
- Compare error messages across runs to determine if they share the same root cause
- Include successful runs in addition to failures (optional)
- Access JUnit test output for debugging and investigation

## Prerequisites

1. **Network Access**: Must be able to reach the Sippy test runs API
   - **NOTE**: Currently using localhost endpoint while API is in development
   - Check: `curl -s http://127.0.0.1:8080/api/tests/v2/runs?test_id=test`

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

3. **Input Data**: Requires test_id (job_run_ids are optional)
   - Get from `fetch-regression-details` skill output
   - `test_id`: Found in regression data (e.g., "openshift-tests:71c053c318c11cfc47717b9cf711c326")
   - `job_run_ids`: Optional - extracted from `sample_failed_jobs[].failed_runs[].job_run_id`

## Implementation Steps

### Step 1: Run the Python Script

```bash
# Path to the Python script
script_path="plugins/ci/skills/fetch-test-runs/fetch_test_runs.py"

# Fetch all test runs (failures only, by default)
python3 "$script_path" "$test_id" --format json

# Include successful runs as well
python3 "$script_path" "$test_id" --include-success --format json

# Filter to a specific Prow job
python3 "$script_path" "$test_id" --prowjob-name "periodic-ci-openshift-release-..." --format json

# Filter to a specific job and include successes (useful for regression start analysis)
python3 "$script_path" "$test_id" --include-success --prowjob-name "periodic-ci-openshift-..." --format json

# Filter to specific job run IDs (backward compatible with analyze-regression)
python3 "$script_path" "$test_id" "$job_run_ids" --format json

# Get human-readable summary
python3 "$script_path" "$test_id" --format summary
```

**Arguments**:
- `test_id`: Required test identifier (e.g., "openshift-tests:abc123")
- `job_run_ids`: Optional comma-separated list of Prow job run IDs to filter by

**Options**:
- `--include-success`: Include successful test runs (default: failures only)
- `--prowjob-name <name>`: Filter to runs from a specific Prow job
- `--start-date <YYYY-MM-DD>`: Start date to look further back than default 7 days
- `--format json|summary`: Output format (default: json)

### Step 2: Prepare Input Data (for analyze-regression)

When used with regression analysis, extract required data from regression details:

```bash
# Assuming you have regression_data from fetch-regression-details skill
test_id=$(echo "$regression_data" | jq -r '.test_id')

# Collect all job_run_ids from sample_failed_jobs
# This creates a comma-separated list of all failed job run IDs
job_run_ids=$(echo "$regression_data" | jq -r '
  .sample_failed_jobs
  | to_entries[]
  | .value.failed_runs[]
  | .job_run_id
' | tr '\n' ',' | sed 's/,$//')

echo "Test ID: $test_id"
echo "Job Run IDs: $job_run_ids"
```

### Step 3: Parse the Output

The script outputs structured JSON data:

```bash
# Store JSON output for processing
output_data=$(python3 "$script_path" "$test_id" --format json)

# Check if fetch was successful
success=$(echo "$output_data" | jq -r '.success')

if [ "$success" = "true" ]; then
  # Extract runs array
  runs=$(echo "$output_data" | jq -r '.runs')

  # The runs array contains objects with: url, output, test_name, success
  # The AI command will analyze these runs for similarity
  echo "Fetched $(echo "$runs" | jq 'length') runs"
else
  # Handle error case
  error=$(echo "$output_data" | jq -r '.error')
  echo "Error: $error"
  echo "Test runs API may not be available"
fi
```

## API Response Schema

The Sippy API returns a JSON array of test run objects:

```json
[
  {
    "url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.22-e2e-aws-ovn-techpreview/2016123858595090432",
    "output": "fail [k8s.io/kubernetes/test/e2e/apimachinery/discovery.go:145]: Fail to access: /apis/stable.e2e-validating-admission-policy-1181/: the server could not find the requested resource",
    "test_name": "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]",
    "success": false
  },
  {
    "url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...",
    "output": "",
    "test_name": "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]",
    "success": true
  }
]
```

## Script Output Format

The script supports two output formats:

### JSON Format (--format json)

Returns structured JSON with raw runs:

```json
{
  "success": true,
  "test_id": "openshift-tests:71c053c318c11cfc47717b9cf711c326",
  "requested_job_runs": 0,
  "include_success": false,
  "runs": [
    {
      "url": "https://prow.ci.openshift.org/...",
      "output": "fail [...]: error message",
      "test_name": "[sig-api-machinery] test name",
      "success": false
    }
  ],
  "api_url": "http://127.0.0.1:8080/api/tests/v2/runs?test_id=..."
}
```

**Field Descriptions**:

- **success**: Boolean indicating if the API call succeeded
- **test_id**: The test identifier that was queried
- **requested_job_runs**: Number of job run IDs requested (0 if none specified)
- **include_success**: Whether successful runs were requested
- **runs**: Raw array of test run objects from Sippy API
  - **url**: Prow job URL for this specific run
  - **output**: The actual JUnit test failure output text (empty for successes)
  - **test_name**: Full test name
  - **success**: Boolean indicating if this run passed
- **api_url**: The API URL that was called

**Error Response** (when success is false):

```json
{
  "success": false,
  "error": "Failed to connect to test runs API: Connection refused",
  "test_id": "openshift-tests:abc123",
  "requested_job_runs": 0,
  "include_success": false
}
```

### Summary Format (--format summary)

Returns human-readable formatted output with sample runs:

```
Test Runs
============================================================

Test ID: openshift-tests:71c053c318c11cfc47717b9cf711c326
Include Successes: False
Runs Fetched: 18

Successes: 0, Failures: 18

Sample Runs:

1. [FAIL] Job URL: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
   Output: fail [k8s.io/kubernetes/test/e2e/apimachinery/discovery.go:145]: Fail to access...

2. [FAIL] Job URL: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
   Output: fail [k8s.io/kubernetes/test/e2e/apimachinery/discovery.go:145]: Fail to access...

3. [PASS] Job URL: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...

... and 15 more runs
```

## Error Handling

### Case 1: API Not Available

```bash
python3 fetch_test_runs.py "openshift-tests:abc"
```

**Output** (JSON format):
```json
{
  "success": false,
  "error": "Failed to connect to test runs API: Connection refused.",
  "test_id": "openshift-tests:abc",
  "requested_job_runs": 0,
  "include_success": false
}
```

**Output** (summary format):
```
Test Runs - FETCH FAILED
============================================================

Error: Failed to connect to test runs API: Connection refused.

The test runs API may not be available.
```

### Case 2: No Runs Returned

If the API returns an empty array:

```json
{
  "success": true,
  "test_id": "openshift-tests:abc",
  "requested_job_runs": 0,
  "include_success": false,
  "runs": []
}
```

### Case 3: Invalid Arguments

```bash
python3 fetch_test_runs.py
```

**Output**:
```
Usage: fetch_test_runs.py <test_id> [job_run_ids] [options]

Arguments:
  test_id       Test identifier (e.g., 'openshift-tests:abc123')
  job_run_ids   Optional comma-separated list of Prow job run IDs

Options:
  --include-success    Include successful test runs (default: failures only)
  --format json|summary   Output format (default: json)
```

**Exit Codes**:
- `0`: Success
- `1`: Error (invalid input, API error, network error, etc.)

## Examples

### Example 1: Fetch All Failures for a Test

```bash
script_path="plugins/ci/skills/fetch-test-runs/fetch_test_runs.py"
python3 "$script_path" "openshift-tests:bb3a7d828630760296ef203c5cacf708" --format json
```

### Example 2: Fetch All Runs Including Successes

```bash
script_path="plugins/ci/skills/fetch-test-runs/fetch_test_runs.py"
python3 "$script_path" "openshift-tests:bb3a7d828630760296ef203c5cacf708" --include-success --format json
```

### Example 3: Fetch Specific Job Runs (Backward Compatible)

Used by analyze-regression command:

```bash
# Assume regression_data is already fetched
test_id=$(echo "$regression_data" | jq -r '.test_id')
job_run_ids=$(echo "$regression_data" | jq -r '.sample_failed_jobs | to_entries[] | .value.failed_runs[] | .job_run_id' | tr '\n' ',' | sed 's/,$//')

# Fetch outputs for specific job runs
script_path="plugins/ci/skills/fetch-test-runs/fetch_test_runs.py"
output_data=$(python3 "$script_path" "$test_id" "$job_run_ids" --format json)

# Check success
if [ "$(echo "$output_data" | jq -r '.success')" = "true" ]; then
  echo "Successfully fetched runs"
fi
```

### Example 4: Get Summary Report

```bash
python3 plugins/ci/skills/fetch-test-runs/fetch_test_runs.py \
  "openshift-tests:71c053c318c11cfc47717b9cf711c326" \
  --format summary
```

### Example 5: Extract Output Messages for AI Analysis

```bash
# Fetch runs
output_data=$(python3 "$script_path" "$test_id" --format json)

# Extract all failure output messages
if [ "$(echo "$output_data" | jq -r '.success')" = "true" ]; then
  # Get all output texts from failed runs
  echo "$output_data" | jq -r '.runs[] | select(.success == false) | .output'

  # AI command will analyze these for:
  # - Similarity/consistency
  # - Common error patterns
  # - File references and API paths
  # - Root cause determination
fi
```

### Example 6: Determine Regression Start Date

Used by analyze-regression command to find when failures began:

```bash
script_path="plugins/ci/skills/fetch-test-runs/fetch_test_runs.py"

# Get the job with the most failures
most_failed_job="periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn"

# Calculate start date (28 days ago) for extended history
start_date=$(date -v-28d +%Y-%m-%d 2>/dev/null || date -d "28 days ago" +%Y-%m-%d)

# Fetch all runs (including successes) for this specific job, going back 28 days
job_history=$(python3 "$script_path" "$test_id" \
  --include-success \
  --prowjob-name "$most_failed_job" \
  --start-date "$start_date" \
  --format json)

# Analyze the run history
if [ "$(echo "$job_history" | jq -r '.success')" = "true" ]; then
  # Runs are returned newest to oldest
  # Iterate to find where failures started
  echo "$job_history" | jq -r '.runs[] | "\(.success) \(.url)"'

  # Look for transition from passing to failing
  # Find the first failure that's part of the current regression
fi
```

## Notes

- The script uses only Python standard library - no external dependencies required
- **Currently using localhost endpoint** - will switch to production Sippy once API is deployed
- Handles API unavailability gracefully with clear error messages
- Returns raw outputs for AI-based interpretation and similarity analysis
- Job run IDs are optional - can fetch all runs for a test
- `--include-success` allows analyzing both passing and failing runs
- `--prowjob-name` filters results to a specific Prow job (useful for regression start analysis)
- `--start-date` allows looking back further than the default 7 days (use YYYY-MM-DD format)
- Combine `--include-success`, `--prowjob-name`, and `--start-date` to get full test history for regression analysis
- Backward compatible with analyze-regression command (accepts job_run_ids)
- Summary format shows first 5 runs only, to keep output manageable
- Runs are returned in order from most recent to least recent

## See Also

- Related Skill: `fetch-regression-details` (provides test_id and job_run_ids)
- Related Command: `/ci:analyze-regression` (uses this skill for failure analysis)
