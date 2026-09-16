---
name: reevaluate-job-runs
description: Retroactively re-run Sippy Symptom detection on completed Prow CI job runs to apply or preview failure Labels
---

# Reevaluate Job Runs

Sippy Symptoms are known-failure signatures for OpenShift CI. Reevaluation asks
Sippy to re-scan completed job runs using the current symptom definitions and
apply their Labels. Use it for runs that completed before a symptom was created
or changed.

## When to Use This Skill

Use this skill to:

- Preview which symptoms would match existing runs without writing anything.
- Apply a new or updated symptom to older completed runs.
- Re-scan every job run behind a triage or regression.

Always suggest a dry run first.

## Prerequisites

Authentication to the sippy-auth API requires a Bearer token from the DPCR
OpenShift cluster (`https://api.cr.j7t7.p1.openshiftapps.com:6443`). Use the
`oc-auth` skill to obtain it, then export it instead of putting it in the
process list:

```bash
export SIPPY_TOKEN="$(oc whoami -t --context=<dpcr-context>)"
```

The implementation uses Python 3 and the standard library only.

## Preview Changes

`--dry-run` is synchronous: Sippy returns HTTP 200 with its existing
per-run `results` response and the script prints it without polling.

```bash
python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/<job>/<build_id> \
  --dry-run --format summary
```

## Apply Changes

Without `--dry-run`, the script deduplicates all normalized IDs, submits them
in one asynchronous batch, and polls the API-provided status link until the
batch is `complete`, `failed`, or `cancelled`:

```bash
python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  1856789012345678848 1856789012345678849 --format summary
```

The API accepts at most **10,000 unique job run IDs in one request**. The
client validates this limit before making a request. Numeric build IDs and
full Prow URLs ending in a numeric build ID are accepted; query strings,
fragments, trailing slashes, and duplicate inputs are normalized.

### Bulk workflow for a triage

Sippy has no triage-level reevaluate endpoint. Use the
`fetch-regression-details` skill to collect every `prowjob_run_id` from each
regression in the triage, then pass all IDs to this script in one invocation.
The combined unique set must not exceed 10,000 IDs.

## Arguments and Options

- `runs`: One or more Prow build IDs or Prow job URLs (required; maximum
  10,000 unique IDs).
- `--token <token>`: Bearer token. Prefer the `SIPPY_TOKEN` environment
  variable because command-line arguments are visible in process listings;
  `--token` takes precedence.
- `--dry-run`: Preview matches synchronously without writing changes.
- `--poll-interval <seconds>`: Time between asynchronous status requests
  (default 5; must be greater than zero).
- `--format json|summary`: Output format (default `json`).

## API Contract

### Request

`POST https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate`

```json
{"prow_job_build_ids": ["1856789012345678848"], "dry_run": false}
```

For a non-dry-run request, Sippy returns HTTP 202:

```json
{
  "batch_id": "d15dff1f-431c-48db-aa37-628ab42d755e",
  "requested": 1,
  "links": {
    "status": "/api/jobs/runs/reevaluate/d15dff1f-431c-48db-aa37-628ab42d755e"
  }
}
```

The client follows `links.status` with authenticated GET requests. For safety,
it refuses a cross-origin status URL and strips `Authorization` from any
cross-origin HTTP redirect.

### Status response

The final JSON output preserves the complete aggregate response and every
item, including each optional River job result:

```json
{
  "batch_id": "d15dff1f-431c-48db-aa37-628ab42d755e",
  "status": "complete",
  "requested": 2,
  "enqueued": 2,
  "deduped": 0,
  "completed": 1,
  "failed": 1,
  "running": 0,
  "pending": 0,
  "items": [
    {
      "item_key": "1856789012345678848",
      "state": "completed",
      "result": {
        "prow_job_build_id": "1856789012345678848",
        "status": "success",
        "symptoms_evaluated": 42,
        "symptoms_matched": ["KnownFailure"],
        "labels_applied": ["InfraFailure"]
      }
    },
    {
      "item_key": "1856789012345678849",
      "state": "discarded",
      "result": {
        "prow_job_build_id": "1856789012345678849",
        "status": "eval_error",
        "error": "artifact scan failed"
      }
    }
  ]
}
```

`state` is the River queue state and is authoritative for progress. The
optional `result` is the latest JSON recorded in River
`metadata->'output'`; it can describe an earlier failed attempt while a retry
is pending. The summary format prints the aggregate counts and the complete
JSON result for every item that has one.

Terminal batch states are `complete`, `failed`, and `cancelled`. A terminal
`failed` or `cancelled` batch exits 1; `complete` and successful dry runs exit
0. Input, authentication, malformed response, API, connection, and socket/read
timeout errors are reported as controlled errors and exit 1.

The Sippy API also has a DELETE endpoint for cancellation, but this skill has
never exposed a cancellation operation, so the client does not introduce one.

## See Also

- `oc-auth`: obtain authentication for sippy-auth.
- `manage-symptoms`: create or update the symptoms to apply retroactively.
- `diagnose-job-run-symptoms`: explain symptoms and labels on a run.
- `fetch-regression-details`: obtain job run IDs for triage-wide reevaluation.
- `fetch-prow-job-runs`: discover run IDs by job, variant, result, or time.
