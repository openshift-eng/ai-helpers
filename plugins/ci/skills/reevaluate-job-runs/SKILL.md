---
name: reevaluate-job-runs
description: Retroactively re-run Sippy Symptom detection on completed Prow CI job runs to apply or preview failure Labels
---

# Reevaluate Job Runs

Sippy **Symptoms** recognize known conditions in OpenShift CI artifacts. A symptom
selects artifact files with a glob and uses a `string`, `regex`, or `file`
(existence) matcher. A match applies one or more **Labels**: stable,
human-readable tags such as `ImagePullNeverCompletes` that appear in Sippy, Spyglass, and
triage workflows.

Symptom detection normally runs automatically as new job artifacts arrive.
Reevaluation asks Sippy to scan completed runs with the current symptom
definitions, which is useful when a symptom was created or changed after those
runs completed.

## When to Use This Skill

Use this skill to:

- Preview which symptoms and labels match existing runs without writing.
- Apply a new or updated symptom to older completed runs.
- Re-scan every job run behind a Component Readiness regression or triage.

## Prerequisites

Authentication to the sippy-auth API requires a Bearer token from the DPCR
OpenShift cluster (`https://api.cr.j7t7.p1.openshiftapps.com:6443`). Use the
`oc-auth` skill to select the correct context. Export the token rather than
putting it in the process list:

```bash
DPCR_CONTEXT="dpcr-context-name"
SIPPY_TOKEN="$(oc whoami -t --context="$DPCR_CONTEXT")"
export SIPPY_TOKEN
test -n "$SIPPY_TOKEN"
```

The implementation uses Python 3 and the standard library only. The examples
that inspect API JSON also use `jq` and `curl`.

## Preview and Apply

`--dry-run` uses the same asynchronous API and artifact scan as an applied
reevaluation, but reports the labels without changing BigQuery, GCS, or
PostgreSQL:

```bash
JOB="periodic-ci-example-job"
BUILD_ID="1856789012345678848"
PROW_URL="https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/$JOB/$BUILD_ID"

python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  "$PROW_URL" --dry-run --format summary
```

After reviewing the preview, omit `--dry-run` to apply the current symptom
set:

```bash
python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  1856789012345678848 1856789012345678849 --format summary
```

The script deduplicates normalized IDs, submits one asynchronous batch, and
polls until it is `complete`, `failed`, or `cancelled`. Sippy accepts at most
10,000 unique numeric build IDs in a request. Full Prow URLs are also accepted;
query strings, fragments, trailing slashes, and duplicate inputs are
normalized.

### Save the batch ID for recovery

Immediately after Sippy accepts and validates a submission, the script prints
and flushes the batch ID and same-origin status URL **before the first status
GET**. Summary mode writes this notice to stdout. JSON mode writes it to stderr
so stdout remains one parseable document: either the unchanged terminal API
response or, if polling fails, an error object containing `batch_id`,
`status_url`, and `error`. Save the notice: the server-side batch can keep
running if the client loses its connection, exits, or its token expires.

To inspect that same batch later, obtain a fresh token with `oc-auth`, copy the
printed sippy-auth status URL, and make an authenticated GET:

```bash
STATUS_URL="https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate/d15dff1f-431c-48db-aa37-628ab42d755e"

curl --fail-with-body --silent --show-error \
  -H "Accept: application/json" \
  -H "Authorization: Bearer $SIPPY_TOKEN" \
  "$STATUS_URL" | jq .
```

Do not print or echo `SIPPY_TOKEN`. Only send it to the same
`https://sippy-auth.dptools.openshift.org` origin. The script validates this
origin and refuses redirects to a different origin.

The script does **not** have a resume option and does not accept an existing
batch ID. The authenticated GET above observes an existing batch; running the
script again creates a new submission.

### Triage-wide workflow

Sippy has no triage-level reevaluate endpoint. List the regression IDs attached
to the triage, collect every `prowjob_run_id` with the
`fetch-regression-details` skill, and pass the resulting Bash array to one
preview invocation:

```bash
REGRESSION_IDS=(34446 34447 34448)
RUN_IDS=()

for REGRESSION_ID in "${REGRESSION_IDS[@]}"; do
  while IFS= read -r RUN_ID; do
    RUN_IDS+=("$RUN_ID")
  done < <(
    python3 plugins/ci/skills/fetch-regression-details/fetch_regression_details.py \
      "$REGRESSION_ID" --format json |
      jq -r '.job_runs[].prowjob_run_id'
  )
done

python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  "${RUN_IDS[@]}" --dry-run --format summary
```

Review the preview, then repeat the final command without `--dry-run`. The
client deduplicates IDs across regressions and rejects more than 10,000 unique
IDs before submission.

## Arguments and Options

- `runs`: One or more Prow build IDs or Prow job URLs (required; maximum
  10,000 unique IDs).
- `--token TOKEN`: Bearer token. Prefer `SIPPY_TOKEN` because command-line
  arguments are visible in process listings; `--token` takes precedence.
- `--dry-run`: Report matches without writing changes.
- `--poll-interval SECONDS`: Time between status requests (default 5; must be
  finite and greater than zero).
- `--format json|summary`: Output format (default `json`).

## API Contract and Results

Both dry-run and applied requests use:

`POST https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate`

```json
{"prow_job_build_ids": ["1856789012345678848"], "dry_run": false}
```

Sippy returns HTTP 202 with `batch_id`, `requested`, and `links.status`. The
client follows the status link with authenticated GET requests. The batch
response contains these aggregate fields:

| Field | Meaning |
|---|---|
| `status` | Batch lifecycle: `pending`, `processing`, or `running`; terminal `complete`, `failed`, or `cancelled`. |
| `requested` | Unique run IDs accepted in the batch specification. |
| `enqueued` | New River item jobs created for this batch. |
| `deduped` | Items linked to an already-existing equivalent River job instead of creating another. |
| `completed` | Items whose River queue state is `completed`. |
| `failed` | Items in `discarded`, `cancelled`, or synthetic `orphaned` queue states. |
| `running` | Items currently executing. |
| `pending` | All other unfinished states, including `not_enqueued`, `available`, `scheduled`, `retryable`, and `pending`. |

Each `items[]` entry has an `item_key` (the build ID), a River queue `state`,
and optionally a `result`. Queue `state` is authoritative for progress. The
`result` is the latest output recorded by an attempt and may describe a failed
attempt while River has the item waiting to retry. Deduplicated items share the
existing River job's output, and items without recorded output omit `result`.

When present, the per-run `result` fields mean:

| Field | Meaning |
|---|---|
| `prow_job_build_id` | Prow build ID evaluated. |
| `status` | `success`, `missing_error`, `eval_error`, or `rewrite_error`. |
| `symptoms_evaluated` | Number of supported active symptom definitions checked. |
| `symptoms_matched` | IDs of symptoms that matched the run's artifacts. |
| `labels_applied` | Label IDs that were, or in dry-run would be, produced by those matches. |
| `bq_entries_written` | BigQuery label rows written by an applied reevaluation. |
| `gcs_artifacts_written` | GCS label JSON artifacts written by an applied reevaluation. |
| `postgres_updated` | Whether the PostgreSQL job-run label array was updated. |
| `error` | Per-run error detail when `status` is not `success`. |
| `links` | Job-run URL and links to matched symptom resources. |

Zero-valued optional result fields are omitted. `missing_error` means Sippy
could not find the run or its artifacts; `eval_error` means lookup or artifact
scanning failed; `rewrite_error` means matching succeeded but a BigQuery, GCS,
or PostgreSQL write failed.

For applied runs, Sippy deletes only BigQuery label rows with a non-empty
`symptom_id`, then writes the current matches. BigQuery rows without a symptom
ID are preserved as manual labels and merged into the PostgreSQL label array.
A successful repeat against unchanged artifacts and symptom definitions
therefore converges on the same symptom-derived label set. The multi-backend
rewrite is not one atomic transaction, so use each item's result fields to
confirm all stores were updated.

## Error and Recovery Guidance

- **No early batch notice**: validation or POST response validation failed, so
  there is no confirmed batch ID to recover. Fix the reported input/API error
  and submit again.
- **401/403 or an HTML login page**: the token is missing or expired. Refresh
  `SIPPY_TOKEN` with `oc-auth`; if a batch notice was already printed, query its
  status URL with the fresh token instead of assuming the batch stopped.
- **Connection, timeout, or malformed/non-JSON status response after the
  notice**: save the flushed ID and URL. The failure is in client polling and
  does not prove the server-side batch failed. In JSON mode, stdout contains a
  single recovery object with `batch_id`, `status_url`, and `error`. Query the
  URL later.
- **501**: the request reached an instance with write endpoints disabled. Use
  the documented `https://sippy-auth.dptools.openshift.org` endpoint.
- **`missing_error`**: verify the numeric build ID, that Sippy has ingested the
  run, and that the run's artifact bucket/path still exists.
- **Terminal `failed` or `cancelled`**: inspect item queue states and their
  optional results. The client prints the terminal response and exits 1.

Input validation failures and API/polling errors exit 1. A `complete` batch
exits 0; terminal `failed` or `cancelled` exits 1.

## Related Skills

- `oc-auth`: obtain or refresh authentication for sippy-auth.
- `manage-symptoms`: create or update symptoms before reevaluation.
- `manage-labels`: inspect and manage the labels symptoms apply.
- `list-symptoms`: inspect current symptom matchers and label mappings.
- `diagnose-job-run-symptoms`: explain symptoms and labels on one run.
- `fetch-regression-details`: obtain all job-run IDs for a regression.
- `fetch-prow-job-runs`: discover run IDs by job, variant, result, or time.
