---
name: reevaluate-job-runs
description: Retroactively re-run Sippy Symptom detection on completed Prow CI job runs to apply or preview failure Labels
---

# Reevaluate Job Runs

Sippy Symptoms are known-failure signatures for OpenShift CI. A symptom is a rule made of a file pattern (a glob over a CI job run's artifact files, e.g. `**/build-log.txt`) and a matcher (`string` = substring, `regex` = regular expression, `none` = file merely exists, `cel` = a compound CEL expression over other label names). When a symptom matches a job run's artifacts, Sippy applies one or more **Labels** — human-readable tags like `InfraFailure` — to that run. Labels appear in the Sippy UI and Spyglass and help everyone quickly recognize known failure modes without re-debugging them. You do not need any prior Sippy knowledge to use this skill.

Symptom detection normally runs automatically as job artifacts arrive. Reevaluation is for runs that completed **before** a symptom was created or changed — it asks Sippy to re-scan those runs server-side and apply the current symptom set.

## When to Use This Skill

Use this skill when you need to:

- Apply a newly created or updated symptom to job runs that finished before the change (see `manage-symptoms`)
- Preview (`--dry-run`) which symptoms would match a run without writing anything
- Re-scan every job run behind a triage or regression so known-failure labels appear on them

## Prerequisites

1. **OpenShift CLI Authentication**: Required for authenticating to the sippy-auth API
   - Must be logged into the DPCR cluster via `oc login`
   - Cluster API: `https://api.cr.j7t7.p1.openshiftapps.com:6443`
   - Use the `oc-auth` skill to obtain the Bearer token

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

## Implementation Steps

### Step 1: Obtain Authentication Token

Use the `oc-auth` skill to obtain a Bearer token from the DPCR cluster:

```bash
# Get token from the DPCR cluster context
# The oc-auth skill's curl_with_token.sh uses this cluster for sippy-auth
DPCR_CLUSTER="https://api.cr.j7t7.p1.openshiftapps.com:6443"

# Find the oc context for the DPCR cluster and get the token
CONTEXT=$(oc config get-contexts -o name 2>/dev/null | while read -r ctx; do
  server=$(oc config view -o jsonpath="{.clusters[?(@.name=='$(oc config view -o jsonpath="{.contexts[?(@.name=='$ctx')].context.cluster}" 2>/dev/null)')].cluster.server}" 2>/dev/null || echo "")
  server_clean=$(echo "$server" | sed -E 's|^https?://||')
  if [ "$server_clean" = "api.cr.j7t7.p1.openshiftapps.com:6443" ]; then
    echo "$ctx"
    break
  fi
done)

if [ -z "$CONTEXT" ]; then
  echo "Error: Not logged into DPCR cluster. Please run: oc login $DPCR_CLUSTER"
  exit 1
fi

export SIPPY_TOKEN=$(oc whoami -t --context="$CONTEXT" 2>/dev/null)
if [ -z "$SIPPY_TOKEN" ]; then
  echo "Error: Failed to get token. Please re-authenticate to DPCR cluster."
  exit 1
fi
```

Prefer exporting `SIPPY_TOKEN` as above rather than passing `--token` on the command line — command-line arguments are visible in process listings. `--token` still works and takes precedence over the environment variable.

### Step 2: Dry-run First

Always suggest a `--dry-run` first — it reports what would match without writing anything. Pass numeric build IDs or full Prow job URLs (up to 10,000 unique runs). The script deduplicates the IDs, submits them as one asynchronous batch, and polls until the batch finishes:

```bash
python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job>/<build_id> --dry-run --format summary
```

### Step 3: Apply

Rerun without `--dry-run` to actually write labels:

```bash
python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  1856789012345678848 1856789012345678849 --format summary
```

### Bulk workflow: reevaluate all runs behind a triage

Sippy has no triage-level reevaluate endpoint. To "reevaluate symptoms on a triage", collect the `prowjob_run_id` of every job run from each regression in the triage using the `fetch-regression-details` skill, then pass them all to this script:

```bash
# For each regression ID in the triage, collect its job run IDs
RUN_IDS=""
for REG_ID in 12345 12346 12347; do
  IDS=$(python3 plugins/ci/skills/fetch-regression-details/fetch_regression_details.py "$REG_ID" \
        | jq -r '.job_runs[].prowjob_run_id')
  RUN_IDS="$RUN_IDS $IDS"
done

# The script deduplicates the IDs and submits one asynchronous batch
python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  $RUN_IDS --format summary
```

**Arguments**:
- `runs`: One or more Prow build IDs or Prow job URLs (positional, required; maximum 10,000 unique IDs)

**Options**:
- `--token <token>`: Bearer token from the oc-auth skill (optional if the `SIPPY_TOKEN` environment variable is set, which is preferred — argv is visible in process listings; `--token` takes precedence)
- `--dry-run`: Report matches without writing anything
- `--format json|summary`: Output format (default: json)

## API Details

**Endpoint**: `POST https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate`

**Request**:

```json
{"prow_job_build_ids": ["1856789012345678848"], "dry_run": false}
```

The API accepts a maximum of **10,000 unique build IDs per request**. The client submits all deduplicated IDs in one request; do not split the request into small client-side batches.

**Submission response** (`202 Accepted`):

```json
{
  "batch_id": "6e2c31fa-298d-4b9e-89bc-bc94f58c1082",
  "requested": 1,
  "links": {
    "status": "https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate/6e2c31fa-298d-4b9e-89bc-bc94f58c1082"
  }
}
```

Poll the returned `links.status` URL (or `GET /api/jobs/runs/reevaluate/{batch_id}`) until `status` is terminal.

**Status response** (`200 OK`):

```json
{
  "batch_id": "6e2c31fa-298d-4b9e-89bc-bc94f58c1082",
  "status": "complete",
  "requested": 1,
  "enqueued": 1,
  "deduped": 0,
  "completed": 1,
  "failed": 0,
  "running": 0,
  "pending": 0,
  "items": [{"item_key": "1856789012345678848", "state": "completed"}]
}
```

Batch status progresses through `pending`, `processing`, and `running`. Terminal statuses are `complete`, `failed`, and `cancelled`. A `complete` batch can contain a mixture of successful and failed items; inspect the `failed` counter and each item's `state`.

Status fields:

| Field | Description |
|-------|-------------|
| `status` | Current batch lifecycle status |
| `requested` | Number of unique job runs accepted in the batch |
| `enqueued` | Per-run jobs newly enqueued by the server |
| `deduped` | Per-run jobs deduplicated by the server's work queue |
| `completed` | Per-run jobs that completed successfully |
| `failed` | Per-run jobs that were discarded, cancelled, or orphaned |
| `running` | Per-run jobs currently running |
| `pending` | Per-run jobs not yet running |
| `items` | Per-run `item_key` (build ID) and work-queue `state` |

**Authentication**: `Authorization: Bearer <token>` from the DPCR cluster.

Reevaluation is delete-then-insert and **idempotent**. Manually-applied labels (those with an empty `symptom_id`) are preserved. Individual server-side jobs retry up to three times with exponential backoff.

## Asynchronous batching and polling

- The script makes exactly one POST containing all unique IDs and `dry_run`, captures the returned `batch_id`, then polls the batch status endpoint every 2.5 seconds.
- Polling continues through `pending`, `processing`, and `running` until the server reports `complete`, `failed`, or `cancelled`.
- Transient status polling errors (HTTP 429/502/503/504 or connection errors) are retried up to five consecutive times. The POST is not retried automatically because a successful submission creates a new batch even if the client loses the response.
- The returned status link must match the documented HTTPS origin and batch path. Authorization is preserved across same-origin redirects but stripped before following any cross-origin redirect.
- **Warning:** an HTML login page response means the token expired — the SSO proxy redirects to login instead of returning 401. The script detects this and tells you to refresh the token via the `oc-auth` skill.

## Error Handling

- **Invalid/non-numeric IDs**: Caught client-side before any request (exit 1) — pass a numeric build ID or a Prow URL ending in one (query strings and `#fragments` are stripped automatically).
- **More than 10,000 unique IDs**: Rejected client-side before submission (exit 1).
- **Submission HTTP error or malformed 202 response**: Reported immediately; the POST is not retried (exit 1).
- **Transient polling error or request timeout**: Retried up to five consecutive times; persistent failure exits 1 while preserving the batch ID in preceding progress output so polling can be resumed manually.
- **Authentication failure (HTML login page or 401/403)**: Token missing/expired — the script stops immediately. Refresh the token via the `oc-auth` skill and rerun or query the captured batch ID.
- **Malformed status response**: Unknown statuses, missing counters/items, or a mismatched batch ID stop polling (exit 1).
- **Per-run failure**: Inspect the `failed` counter and item states. River reports failed work as `discarded`, `cancelled`, or `orphaned`.
- **501**: You hit the read-only Sippy instance; make sure the sippy-auth base URL is used (the script already does).

When `--format json` is selected, submission and polling failures also produce a valid JSON object on stdout with `submission`, `status: null`, and a single `failed_batches` entry. The same useful error is written to stderr and the process exits 1.

**Exit Codes**:
- `0`: The batch reached `complete` with zero failed items
- `1`: Validation/API error, interrupted polling, `failed`/`cancelled` terminal status, or one or more failed items

## See Also

- Related Skill: `oc-auth` (provides authentication tokens for sippy-auth)
- Related Skill: `manage-symptoms` (create/update the symptoms you then apply retroactively)
- Related Skill: `diagnose-job-run-symptoms` (explain which symptoms/labels apply to a run)
- Related Skill: `fetch-regression-details` (source of `.job_runs[].prowjob_run_id` values for triage-wide reevaluation)
- Related Skill: `fetch-prow-job-runs` (discover run IDs by job name, variant, result, or time window)
