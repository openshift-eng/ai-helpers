---
name: Fetch Job Run Summary
description: Fetch a Prow job run summary from Sippy showing all failed tests grouped by SIG with error messages
---

# Fetch Job Run Summary

This skill fetches a summary of a Prow job run from the Sippy API, listing all tests that failed (excluding flakes) along with their error messages.

## When to Use This Skill

Use this skill when you need to:

- List all tests that failed in a specific Prow job run
- Understand which components are affected by failures in a job
- Identify dominant error patterns across multiple test failures
- Investigate mass test failure regressions by examining the underlying test failures
- Get a quick overview of a job run's health (pass rate, infrastructure failure, etc.)

## Prerequisites

1. **Python 3**: Version 3.6 or later
2. **Network Access**: Must be able to reach `https://sippy.dptools.openshift.org`

## Implementation

```bash
script_path="plugins/ci/skills/fetch-job-run-summary/fetch_job_run_summary.py"

# Text output (AI-readable)
python3 "$script_path" <prow_job_run_id>

# JSON output (structured)
python3 "$script_path" <prow_job_run_id> --format json
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `prow_job_run_id` | Yes | The Prow job run ID (numeric, e.g., `2030845545290928128`) |
| `--format` | No | Output format: `text` (default) or `json` |

### Extracting a Job Run ID

The job run ID can be extracted from a Prow job URL:

```
https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job-name>/<job_run_id>
```

The last path segment is the job run ID.

## API Details

**Endpoint**: `https://sippy.dptools.openshift.org/api/job/run/summary`

**Query Parameter**: `prow_job_run_id` (required)

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Prow job run ID |
| `name` | string | Full job name |
| `release` | string | OpenShift release (e.g., `4.22`) |
| `cluster` | string | Build cluster (e.g., `build01`) |
| `url` | string | Prow job URL |
| `startTime` | string | ISO 8601 start time |
| `durationSeconds` | int | Job duration in seconds |
| `overallResult` | string | `S` (success) or `F` (failure) |
| `reason` | string | Human-readable result reason |
| `infrastructureFailure` | bool | Whether this was an infrastructure failure |
| `testCount` | int | Total number of tests run |
| `testFailureCount` | int | Number of failed tests |
| `testFailures` | dict | Map of test name to error message (excludes flakes) |
| `variants` | list | Job variant tags |

### Flake Handling

The Sippy API automatically handles flake detection. When a test has both a failure and a pass in the same job run's junit results (the standard flake pattern), it is **not** included in `testFailures`. Only true failures — tests that failed without a corresponding pass — appear in the results.

## Output

### Text Format

The text output is structured for AI consumption with:

1. **Job Run Summary**: Metadata (job name, release, duration, result, variants)
2. **Test Statistics**: Total tests, failures, pass rate
3. **Failed Tests**: Failure count (sorted by count descending)
4. **Dominant Error Patterns**: Error messages appearing in >5% of failures, with counts
5. **Detailed Failures**: Each failed test with its error message, grouped by SIG

### JSON Format

Structured JSON with the same data:

```json
{
  "success": true,
  "job_name": "periodic-ci-openshift-hypershift-...",
  "job_run_id": "2030845545290928128",
  "release": "4.22",
  "test_count": 3827,
  "failure_count": 400,
  "pass_rate": 89.5,
  "failed_tests": [
    {"test_name": "[sig-cli] example test name", "error": "error message..."}
  ],
  "dominant_error_patterns": [
    {"pattern": "stale GroupVersion discovery: ...", "count": 50, "percentage": 12.5}
  ]
}
```

## Examples

### Example 1: Investigate a Mass Test Failure

```bash
# Get the summary of a job run that triggered mass test failures
python3 plugins/ci/skills/fetch-job-run-summary/fetch_job_run_summary.py 2030845545290928128
```

### Example 2: Compare Two Runs

```bash
# Fetch summaries for a failing and passing run to diff
python3 plugins/ci/skills/fetch-job-run-summary/fetch_job_run_summary.py 2030845545290928128 --format json > failing.json
python3 plugins/ci/skills/fetch-job-run-summary/fetch_job_run_summary.py 2030845542774345728 --format json > passing.json
```

## Notes

- The `testFailureCount` may be slightly higher than the number of entries in `testFailures` due to internal deduplication
- Error messages are truncated to 300 characters in text output to keep output manageable
- The dominant error pattern detection strips UUIDs and timestamps for better grouping
- For test-level output analysis (raw test failure output for a specific test across runs), use the `fetch-test-runs` skill instead

## See Also

- Related Skill: `fetch-test-runs` - Fetch raw outputs for a specific test across multiple job runs
- Related Skill: `fetch-regression-details` - Fetch Component Readiness regression details
- Related Command: `/ci:analyze-prow-job-test-failure` - Deep analysis of test failures in a Prow job
