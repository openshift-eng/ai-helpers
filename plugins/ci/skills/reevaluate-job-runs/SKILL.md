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

Always suggest a `--dry-run` first — it reports what would match without writing anything. Pass numeric build IDs or full Prow job URLs (any count — the script deduplicates and batches automatically):

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

# The script deduplicates and batches (default 10 per request) automatically
python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  $RUN_IDS --format summary
```

**Arguments**:
- `runs`: One or more Prow build IDs or Prow job URLs (positional, required; batched automatically)

**Options**:
- `--token <token>`: Bearer token from the oc-auth skill (optional if the `SIPPY_TOKEN` environment variable is set, which is preferred — argv is visible in process listings; `--token` takes precedence)
- `--dry-run`: Report matches without writing anything
- `--batch-size <n>`: Runs per API request (default 10; max 50, but large batches risk 504 gateway timeouts)
- `--format json|summary`: Output format (default: json)

## API Details

**Endpoint**: `POST https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate`

**Request**:

```json
{"prow_job_build_ids": ["1856789012345678848"], "dry_run": false}
```

The API accepts a maximum of 50 build IDs per request.

**Response**: `results[]` with per-run fields:

| Field | Description |
|-------|-------------|
| `status` | `success`, `missing_error` (run artifacts not found), `eval_error`, or `rewrite_error` |
| `symptoms_evaluated` | Number of symptoms checked against the run |
| `symptoms_matched` | Number of symptoms that matched |
| `labels_applied` | Label IDs applied to the run |
| `bq_entries_written` | BigQuery rows written |
| `gcs_artifacts_written` | GCS label artifacts written |
| `postgres_updated` | Whether the Postgres record was updated |

**Authentication**: `Authorization: Bearer <token>` from the DPCR cluster.

Reevaluation is delete-then-insert and **idempotent** — running it twice on the same run is safe. Manually-applied labels (those with an empty `symptom_id`) are preserved.

## Batching & timeouts (field-tested 2026-07)

- The server evaluates roughly **3-4 seconds per run**, and the fronting gateway times out around **60-90 seconds**, returning an HTML `504 Gateway Time-out` **page** (not JSON). This means 50-run batches reliably fail even though the API nominally accepts them.
- The script therefore defaults to **batches of 10**, with **3 attempts per batch (2 retries)** and a 5-second backoff. Transient gateway errors (HTTP 502/503/504, HTML error pages, and non-JSON response bodies) are all retried. Retries are safe because reevaluation is idempotent — even a batch that partially completed server-side can be resent.
- If 504s persist, lower `--batch-size` (e.g. `--batch-size 5`).
- **Warning:** an HTML **login page** response means the token expired — the SSO proxy redirects to login instead of returning 401. The script detects this and tells you to refresh the token via the `oc-auth` skill.

## Error Handling

- **Invalid/non-numeric IDs**: Caught client-side before any request (exit 1) — pass a numeric build ID or a Prow URL ending in one (query strings and `#fragments` are stripped automatically).
- **Invalid `--batch-size`**: Must be between 1 and 50 (exit 1).
- **Transient gateway errors (502/503/504, HTML error pages, non-JSON bodies)**: Retried automatically (3 attempts, i.e. 2 retries, 5s backoff); persistent failures are reported in `failed_batches` and the script exits 1 — rerun with just those IDs (idempotent, safe).
- **Authentication failure (HTML login page or 401/403)**: Token missing/expired — the script **stops immediately** and marks all remaining batches as `not attempted` in `failed_batches` instead of hammering the API with a bad token. Refresh the token via the `oc-auth` skill and rerun.
- **`missing_error` status**: The run's artifacts were not found — check the build ID.
- **501**: You hit the read-only Sippy instance; make sure the sippy-auth base URL is used (the script already does).

**Exit Codes**:
- `0`: All batches succeeded
- `1`: Validation error, or one or more batches failed (see `failed_batches` in JSON output)

## See Also

- Related Skill: `oc-auth` (provides authentication tokens for sippy-auth)
- Related Skill: `manage-symptoms` (create/update the symptoms you then apply retroactively)
- Related Skill: `diagnose-job-run-symptoms` (explain which symptoms/labels apply to a run)
- Related Skill: `fetch-regression-details` (source of `.job_runs[].prowjob_run_id` values for triage-wide reevaluation)
- Related Command: `/ci:reevaluate-job-runs` (invokes this skill)
