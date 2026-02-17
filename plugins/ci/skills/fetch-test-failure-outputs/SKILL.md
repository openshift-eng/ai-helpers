---
name: Fetch Test Failure Outputs
description: Fetch test failure outputs from Sippy API for AI-based similarity analysis
---

# Fetch Test Failure Outputs

This skill fetches actual JUnit test failure outputs from multiple Prow job runs. The outputs are returned as raw data for the AI command to interpret and analyze for consistency patterns.

## When to Use This Skill

Use this skill when you need to:

- Fetch actual failure output messages from multiple failed job runs
- Get raw test failure data for AI-based similarity analysis
- Compare error messages across runs to determine if they share the same root cause
- Access JUnit test output for debugging and investigation

## Prerequisites

1. **Network Access**: Must be able to reach the Sippy test outputs API
   - **FUTURE**: Will use production Sippy endpoint once code merges
   - Check: `curl -s https://sippy.dptools.openshift.org/api/tests/v2/outputs?test_id=test&prow_job_run_ids=123`

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

3. **Input Data**: Requires test_id and list of job_run_ids
   - Get from `fetch-regression-details` skill output
   - `test_id`: Found in regression data (e.g., "openshift-tests:71c053c318c11cfc47717b9cf711c326")
   - `job_run_ids`: Extracted from `sample_failed_jobs[].failed_runs[].job_run_id`

## Implementation Steps

### Step 1: Prepare Input Data

Extract required data from regression details:

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

### Step 2: Run the Python Script

```bash
# Path to the Python script
script_path="plugins/ci/skills/fetch-test-failure-outputs/fetch_test_failure_outputs.py"

# Fetch test outputs in JSON format
python3 "$script_path" "$test_id" "$job_run_ids" --format json

# Or get human-readable summary
python3 "$script_path" "$test_id" "$job_run_ids" --format summary
```

### Step 3: Parse the Output

The script outputs structured JSON data:

```bash
# Store JSON output for processing
output_data=$(python3 "$script_path" "$test_id" "$job_run_ids" --format json)

# Check if fetch was successful
success=$(echo "$output_data" | jq -r '.success')

if [ "$success" = "true" ]; then
  # Extract outputs array
  outputs=$(echo "$output_data" | jq -r '.outputs')

  # The outputs array contains objects with: url, output, test_name
  # The AI command will analyze these outputs for similarity
  echo "Fetched $(echo "$outputs" | jq 'length') outputs"
else
  # Handle error case
  error=$(echo "$output_data" | jq -r '.error')
  echo "Error: $error"
  echo "Test output API may not be available"
fi
```

## API Response Schema

The Sippy API returns a JSON array of test output objects:

```json
[
  {
    "url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.22-e2e-aws-ovn-techpreview/2016123858595090432",
    "output": "fail [k8s.io/kubernetes/test/e2e/apimachinery/discovery.go:145]: Fail to access: /apis/stable.e2e-validating-admission-policy-1181/: the server could not find the requested resource",
    "test_name": "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]"
  },
  {
    "url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...",
    "output": "fail [k8s.io/kubernetes/test/e2e/apimachinery/discovery.go:145]: Fail to access: /apis/stable.e2e-validating-admission-policy-1181/: the server could not find the requested resource",
    "test_name": "[sig-api-machinery] Discovery should validate PreferredVersion for each APIGroup [Conformance]"
  }
]
```

## Script Output Format

The script supports two output formats:

### JSON Format (--format json)

Returns structured JSON with raw outputs:

```json
{
  "success": true,
  "test_id": "openshift-tests:71c053c318c11cfc47717b9cf711c326",
  "requested_job_runs": 18,
  "outputs": [
    {
      "url": "https://prow.ci.openshift.org/...",
      "output": "fail [...]: error message",
      "test_name": "[sig-api-machinery] test name"
    }
  ]
}
```

**Field Descriptions**:

- **success**: Boolean indicating if the API call succeeded
- **test_id**: The test identifier that was queried
- **requested_job_runs**: Number of job run IDs requested
- **outputs**: Raw array of test output objects from Sippy API
  - **url**: Prow job URL for this specific run
  - **output**: The actual JUnit test failure output text
  - **test_name**: Full test name

**Error Response** (when success is false):

```json
{
  "success": false,
  "error": "Failed to connect to test outputs API: Connection refused",
  "test_id": "openshift-tests:abc123",
  "requested_job_runs": 2
}
```

### Summary Format (--format summary)

Returns human-readable formatted output with sample outputs:

```
Test Failure Outputs
============================================================

Test ID: openshift-tests:71c053c318c11cfc47717b9cf711c326
Requested Job Runs: 18
Outputs Fetched: 18

Sample Outputs:

1. Job URL: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
   Output: fail [k8s.io/kubernetes/test/e2e/apimachinery/discovery.go:145]: Fail to access: /apis/stable.e2e-validating-admission-policy-1181/: the server could not find the requested resource

2. Job URL: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
   Output: fail [k8s.io/kubernetes/test/e2e/apimachinery/discovery.go:145]: Fail to access: /apis/stable.e2e-validating-admission-policy-1181/: the server could not find the requested resource

3. Job URL: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
   Output: timeout waiting for condition

... and 15 more outputs
```

## Error Handling

### Case 1: API Not Available

```bash
python3 fetch_test_failure_outputs.py "openshift-tests:abc" "123,456"
```

**Output** (JSON format):
```json
{
  "success": false,
  "error": "Failed to connect to test outputs API: Connection refused.",
  "test_id": "openshift-tests:abc",
  "requested_job_runs": 2
}
```

**Output** (summary format):
```
Test Failure Outputs - FETCH FAILED
============================================================

Error: Failed to connect to test outputs API: Connection refused. 

The test output API may not be available.
```

### Case 2: No Outputs Returned

If the API returns an empty array:

```json
{
  "success": true,
  "test_id": "openshift-tests:abc",
  "requested_job_runs": 2,
  "outputs": []
}
```

### Case 3: Invalid Arguments

```bash
python3 fetch_test_failure_outputs.py
```

**Output**:
```
Usage: fetch_test_failure_outputs.py <test_id> <job_run_id1,job_run_id2,...> [--format json|summary]
```

**Exit Codes**:
- `0`: Success
- `1`: Error (invalid input, API error, network error, etc.)

## Examples

### Example 1: Fetch Outputs from Regression Data

```bash
# Assume regression_data is already fetched
test_id=$(echo "$regression_data" | jq -r '.test_id')
job_run_ids=$(echo "$regression_data" | jq -r '.sample_failed_jobs | to_entries[] | .value.failed_runs[] | .job_run_id' | tr '\n' ',' | sed 's/,$//')

# Fetch outputs
script_path="plugins/ci/skills/fetch-test-failure-outputs/fetch_test_failure_outputs.py"
output_data=$(python3 "$script_path" "$test_id" "$job_run_ids" --format json)

# Check success
if [ "$(echo "$output_data" | jq -r '.success')" = "true" ]; then
  echo "Successfully fetched outputs"
  # AI command will analyze outputs for similarity
fi
```

### Example 2: Get Summary Report

```bash
python3 plugins/ci/skills/fetch-test-failure-outputs/fetch_test_failure_outputs.py \
  "openshift-tests:71c053c318c11cfc47717b9cf711c326" \
  "2016123858595090432,2016460830022832128" \
  --format summary
```

### Example 3: Extract Output Messages for AI Analysis

```bash
# Fetch outputs
output_data=$(python3 "$script_path" "$test_id" "$job_run_ids" --format json)

# Extract all output messages
if [ "$(echo "$output_data" | jq -r '.success')" = "true" ]; then
  # Get all output texts
  echo "$output_data" | jq -r '.outputs[].output'

  # AI command will analyze these for:
  # - Similarity/consistency
  # - Common error patterns
  # - File references and API paths
  # - Root cause determination
fi
```

## Notes

- The script uses only Python standard library - no external dependencies required
- Handles API unavailability gracefully with clear error messages
- Returns raw outputs for AI-based interpretation and similarity analysis
- The AI command interprets similarity rather than encoding logic in Python
- Summary format shows first 3 outputs only, to keep output manageable

## See Also

- Related Skill: `fetch-regression-details` (provides test_id and job_run_ids)
- Related Command: `/ci:analyze-regression` (uses this skill for failure analysis)
