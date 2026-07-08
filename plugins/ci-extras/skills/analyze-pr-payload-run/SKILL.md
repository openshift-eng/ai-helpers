---
name: analyze-pr-payload-run
description: Analyze a PR payload validation run by fetching the run page and checking each job's status via prowjob.json from GCS
---

# Analyze PR Payload Run

This skill analyzes a PR payload validation run from `pr-payload-tests.ci.openshift.org`, producing a consolidated summary of all jobs with their pass/fail status, test statistics, and failure details.

## When to Use This Skill

Use this skill when you need to:

- Check the overall status of a PR payload validation run
- See which jobs passed and which failed across a payload run
- Get a quick summary of test failures across all jobs in a run
- Determine whether all payload jobs have finished

## Prerequisites

1. **Python 3**: Version 3.7 or later
2. **Network Access**: Must be able to reach `pr-payload-tests.ci.openshift.org`, `gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com`, and optionally `sippy.dptools.openshift.org`

## Implementation

```bash
script_path="plugins/ci-extras/skills/analyze-pr-payload-run/analyze_pr_payload_run.py"

# Text output (AI-readable)
python3 "$script_path" <pr-payload-test-url>

# JSON output (structured)
python3 "$script_path" <pr-payload-test-url> --format json
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `pr_payload_url` | Yes | The full `https://pr-payload-tests.ci.openshift.org/runs/ci/<uuid>` URL |
| `--format` | No | Output format: `text` (default) or `json` |

## How It Works

1. Fetches the pr-payload-tests HTML page
2. Extracts all prow job URLs from the page using regex
3. Extracts PR metadata (repo, PR number) and completion status
4. Parses each prow URL to extract the job name, run ID, and GCS path
5. Fetches `prowjob.json` from GCS in parallel for all jobs to get status (success/failure/aborted/pending) and duration
6. For failed jobs, queries the Sippy API to enrich with test failure details (test counts, failed tests, error patterns) when available
7. Classifies each job as passed (S), failed (F), aborted (A), error (E), or pending

## Output

### Text Format

Structured markdown output with:

1. **PR Payload Run Summary**: URL, PR reference, completion status
2. **Job Results Table**: All jobs with result and duration
3. **Failed Job Details**: For each failed job — reason, duration, top failed tests, error patterns
4. **Errored Jobs**: Jobs where status could not be fetched (fetch failures)
5. **Pending Jobs**: Jobs still running
6. **Next Steps**: Suggested `prow-job-analysis` skill invocation for failed jobs

### JSON Format

```json
{
  "url": "https://pr-payload-tests.ci.openshift.org/runs/ci/<uuid>",
  "uuid": "<uuid>",
  "pr_metadata": {"repo": "openshift/repo", "pr_number": "1234"},
  "all_jobs_finished": true,
  "summary": {"total_jobs": 14, "passed": 12, "failed": 2, "errors": 0, "pending": 0},
  "jobs": [
    {
      "job_name": "periodic-ci-...",
      "prow_url": "https://prow.ci.openshift.org/...",
      "run_id": "2071329727112548352",
      "result": "S",
      "test_count": 3827,
      "failure_count": 0,
      "pass_rate": 100.0
    }
  ]
}
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid URL | Prints error and exits with code 1 |
| Page unreachable | Prints error and exits with code 1 |
| No prow jobs found | Prints message and exits with code 1 |
| GCS prowjob.json unreachable | Job marked as "E" (error) with error detail |
| Sippy unavailable for a failed job | Job shown as failed without test-level details |
| AllJobsFinished not on page | Status shown as "Jobs still running" |

## See Also

- Related Skill: `fetch-job-run-summary` — Fetch individual job run summary from Sippy
- Related Skill: `trigger-payload-job` — Trigger payload jobs and extract the payload test URL
- Related Skill: `prow-job-analysis` — Comprehensive Prow CI job failure analysis (test, install, disruption, and more)
