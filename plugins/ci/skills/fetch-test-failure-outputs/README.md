# Fetch Test Failure Outputs

Fetch test failure outputs from Sippy API for AI-based similarity analysis.

## Overview

This skill fetches actual JUnit test failure output messages from multiple Prow job runs. The outputs are returned as raw data for the AI command to interpret and analyze for consistency patterns.

Unlike automated analysis, this approach lets the AI:
- Understand nuanced similarities in error messages
- Extract contextual debugging information
- Identify patterns that simple string matching might miss
- Provide natural language explanations of failure consistency

## Usage

```bash
python3 plugins/ci/skills/fetch-test-failure-outputs/fetch_test_failure_outputs.py \
  <test_id> \
  <job_run_id1,job_run_id2,...> \
  [--format json|summary]
```

**Arguments**:
- `test_id`: Test identifier from regression data (e.g., "openshift-tests:71c053c318c11cfc47717b9cf711c326")
- `job_run_ids`: Comma-separated list of Prow job run IDs
- `--format`: Output format - `json` (default) or `summary`

## Example

```bash
# Get test_id and job_run_ids from regression data
test_id=$(echo "$regression_data" | jq -r '.test_id')
job_run_ids=$(echo "$regression_data" | jq -r '.sample_failed_jobs | to_entries[] | .value.failed_runs[] | .job_run_id' | tr '\n' ',' | sed 's/,$//')

# Fetch failure outputs
python3 plugins/ci/skills/fetch-test-failure-outputs/fetch_test_failure_outputs.py \
  "$test_id" \
  "$job_run_ids" \
  --format json
```

## Output

The skill returns raw outputs from the Sippy API:

```json
{
  "success": true,
  "test_id": "openshift-tests:...",
  "requested_job_runs": 18,
  "outputs": [
    {
      "url": "https://prow.ci.openshift.org/...",
      "output": "fail [...]: error message text",
      "test_name": "[sig-api-machinery] test name"
    }
  ]
}
```

The AI command then analyzes the `outputs` array to:
- Determine consistency (how similar the errors are)
- Identify common error patterns
- Extract debugging information (file references, API paths)
- Assess root cause

## See Also

- [SKILL.md](SKILL.md) - Complete implementation guide
- Related: `fetch-regression-details` skill (provides input data)
- Related: `/ci:analyze-regression` command (uses this skill with AI analysis)
