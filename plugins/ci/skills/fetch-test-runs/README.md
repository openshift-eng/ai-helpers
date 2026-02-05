# Fetch Test Runs

Fetch test runs from Sippy API including outputs for AI-based similarity analysis.

## Overview

This skill fetches test runs from the Sippy API. It can return both failed and successful test runs, including JUnit output for AI-based analysis.

Key features:
- Fetch all test runs for a specific test (failures only by default)
- Optionally include successful runs with `--include-success`
- Filter to a specific Prow job with `--prowjob-name`
- Filter to specific job run IDs for targeted analysis
- Backward compatible with analyze-regression command

## Usage

```bash
# Fetch all failures for a test
python3 plugins/ci/skills/fetch-test-runs/fetch_test_runs.py \
  <test_id> \
  [--format json|summary]

# Include successful runs
python3 plugins/ci/skills/fetch-test-runs/fetch_test_runs.py \
  <test_id> \
  --include-success \
  [--format json|summary]

# Filter to a specific Prow job
python3 plugins/ci/skills/fetch-test-runs/fetch_test_runs.py \
  <test_id> \
  --prowjob-name "periodic-ci-openshift-release-..." \
  [--format json|summary]

# Get full history for a specific job (for regression start analysis)
python3 plugins/ci/skills/fetch-test-runs/fetch_test_runs.py \
  <test_id> \
  --include-success \
  --prowjob-name "periodic-ci-openshift-release-..." \
  [--format json|summary]

# Filter to specific job run IDs (backward compatible)
python3 plugins/ci/skills/fetch-test-runs/fetch_test_runs.py \
  <test_id> \
  <job_run_id1,job_run_id2,...> \
  [--format json|summary]
```

**Arguments**:
- `test_id`: Test identifier from regression data (e.g., "openshift-tests:71c053c318c11cfc47717b9cf711c326")
- `job_run_ids`: Optional comma-separated list of Prow job run IDs

**Options**:
- `--include-success`: Include successful test runs (default: failures only)
- `--prowjob-name <name>`: Filter to runs from a specific Prow job
- `--start-date <YYYY-MM-DD>`: Start date to look further back than default 7 days
- `--format`: Output format - `json` (default) or `summary`

## Example

```bash
# Get test_id and job_run_ids from regression data
test_id=$(echo "$regression_data" | jq -r '.test_id')
job_run_ids=$(echo "$regression_data" | jq -r '.sample_failed_jobs | to_entries[] | .value.failed_runs[] | .job_run_id' | tr '\n' ',' | sed 's/,$//')

# Fetch test runs (backward compatible with analyze-regression)
python3 plugins/ci/skills/fetch-test-runs/fetch_test_runs.py \
  "$test_id" \
  "$job_run_ids" \
  --format json

# Or fetch all runs for a test including successes
python3 plugins/ci/skills/fetch-test-runs/fetch_test_runs.py \
  "$test_id" \
  --include-success \
  --format json
```

## Output

The skill returns test runs from the Sippy API:

```json
{
  "success": true,
  "test_id": "openshift-tests:...",
  "requested_job_runs": 0,
  "include_success": false,
  "runs": [
    {
      "url": "https://prow.ci.openshift.org/...",
      "output": "fail [...]: error message text",
      "test_name": "[sig-api-machinery] test name",
      "success": false
    }
  ],
  "api_url": "http://127.0.0.1:8080/api/tests/v2/runs?..."
}
```

The AI command then analyzes the `runs` array to:
- Determine consistency (how similar the errors are)
- Identify common error patterns
- Extract debugging information (file references, API paths)
- Assess root cause

## Note

Currently using localhost endpoint (`http://127.0.0.1:8080`) while the API is in development. Will switch to production Sippy URL once the API is deployed.

## See Also

- [SKILL.md](SKILL.md) - Complete implementation guide
- Related: `fetch-regression-details` skill (provides input data)
- Related: `/ci:analyze-regression` command (uses this skill with AI analysis)
