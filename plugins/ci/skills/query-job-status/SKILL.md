---
name: "query-job-status"
description: Query the status of a gangway job execution by ID
argument-hint: <execution-id>
user-invocable: true
disable-model-invocation: true
---

## Name
ci:query-job-status

## Synopsis
```
/query-job-status <execution-id>
```

## Description

The `query-job-status` command queries the status of a gangway job execution via the REST API using the execution ID returned when a job is triggered.

The command accepts:
- Execution ID (required, UUID returned when triggering a job)

It makes an authenticated GET request to the gangway API and returns the current status of the job including its name, type, status, and GCS path to artifacts if available.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - $1: execution ID (required, UUID format)

2. **Execute API Request**: Locate the app.ci context, retrieve its token, and query the job status:
   ```bash
   APP_CI_CONTEXT=$(oc config get-contexts -o name | while read -r context; do
     server=$(oc --context="$context" whoami --show-server 2>/dev/null || true)
     [ "$server" = "https://api.ci.l2s4.p1.openshiftapps.com:6443" ] && { echo "$context"; break; }
   done)
   [ -n "$APP_CI_CONTEXT" ] || { echo "Log in to the app.ci cluster first" >&2; exit 1; }
   APP_CI_TOKEN=$(oc --context="$APP_CI_CONTEXT" whoami -t)
   curl -H "Authorization: Bearer $APP_CI_TOKEN" -X GET \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions/<EXECUTION_ID>
   ```
   Do not print or persist `APP_CI_TOKEN`; unset it when the workflow finishes.

3. **Display Results**: Parse and present the JSON response with:
   - `id`: The execution ID
   - `job_name`: The name of the job
   - `job_type`: The type of job execution (PERIODIC, POSTSUBMIT, PRESUBMIT)
   - `job_status`: Current status (TRIGGERED, PENDING, SUCCESS, FAILURE, ABORTED)
   - `gcs_path`: Path to job artifacts in GCS (if available)
   - `prow_url`: Derived Prow dashboard URL (see step 4)

4. **Derive Prow URL from GCS Path**: If `gcs_path` is present, convert it to a Prow dashboard URL:
   - Strip the `gs://<bucket-name>/` prefix (bucket is typically `origin-ci-test` or `test-platform-results`)
   - Prepend `https://prow.ci.openshift.org/view/gs/test-platform-results/`
   - Example: `gs://origin-ci-test/logs/periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn/1234567890` → `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn/1234567890`
   - The Prow URL always uses `test-platform-results` as the bucket name regardless of what `gcs_path` reports

5. **Poll if Prow URL Not Yet Available**: If `gcs_path` is empty/missing and `job_status` is `TRIGGERED`, the job has not started yet. Automatically re-query:
   - Wait 15 seconds, then re-query the execution status
   - Repeat up to 20 times (~5 minutes total)
   - Stop polling once `gcs_path` is populated or `job_status` reaches a terminal state (`SUCCESS`, `FAILURE`, `ABORTED`)
   - If polling exhausts all retries without a `gcs_path`, report the current status and provide a Prow dashboard search link so the user can find the job manually: `https://prow.ci.openshift.org/?job=<job_name>` (using the `job_name` from the status response)

6. **Offer Follow-up Actions**:
   - If status is PENDING with prow_url: Provide the Prow dashboard link (job is actively running)
   - If status is SUCCESS or FAILURE with prow_url: Provide the link and offer to help access logs/artifacts
   - If prow_url could not be derived: Provide `https://prow.ci.openshift.org/?job=<job_name>` so the user can find it on the Prow dashboard

## Return Value
- **Success**: JSON response with job status details and derived Prow URL
- **Error**: HTTP error, authentication failure, or invalid execution ID

**Important for Claude**:
1. Verify that the selected `oc` context points to the app.ci API before retrieving its token.
2. Parse the JSON response and present it in a readable format.
3. Highlight the job status prominently.
4. **Always derive and display the Prow URL** when `gcs_path` is available.
5. If `gcs_path` is missing and job is not terminal, **poll automatically** — do not just offer to check again.
6. If PENDING with Prow URL, provide the link — PENDING means the job is actively running.
7. If SUCCESS/FAILURE, indicate completion status and provide the Prow link.

## Examples

1. **Query status of a triggered job**:
   ```
   /query-job-status ca249d50-dee8-4424-a0a7-6dd9d5605267
   ```
   Returns:
   ```json
   {
     "id": "ca249d50-dee8-4424-a0a7-6dd9d5605267",
     "job_name": "periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn",
     "job_type": "PERIODIC",
     "job_status": "SUCCESS",
     "gcs_path": "gs://origin-ci-test/logs/periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn/1234567890"
   }
   ```
   Claude derives and displays: `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn/1234567890`

2. **Query a recently triggered job (auto-polling)**:
   ```
   /query-job-status 8f3a9b2c-1234-5678-9abc-def012345678
   ```
   First query returns `job_status: TRIGGERED` with no `gcs_path` — Claude automatically waits 15 seconds and re-queries until `gcs_path` appears, then displays the Prow URL.

3. **Check failed job**:
   ```
   /query-job-status 5a6b7c8d-9e0f-1a2b-3c4d-5e6f7a8b9c0d
   ```
   Status shows "FAILURE" — Claude displays the Prow dashboard link for log analysis.

## Notes

- **Execution ID Format**: UUID format (e.g., `ca249d50-dee8-4424-a0a7-6dd9d5605267`)
- **Job Status Values**:
  - `TRIGGERED`: The ProwJob CR exists but has not been scheduled yet — waiting to transition to PENDING. `gcs_path` may not be populated yet.
  - `PENDING`: The job is actively running (despite the name, this means in-progress, not queued)
  - `SUCCESS`: Job completed successfully (terminal)
  - `FAILURE`: Job completed with a failure (terminal)
  - `ABORTED`: Job was cancelled (terminal)
- **Rate Limits**: The REST API has rate limits
- **Authentication**: Tokens expire and may need to be refreshed via browser login
- **GCS Path**: Provides access to job logs and artifacts when available
- **Prow URL Derivation**: The Prow URL is always derived using `test-platform-results` as the bucket name, regardless of what bucket name appears in `gcs_path` (commonly `origin-ci-test`)
- **Auto-Polling**: When `gcs_path` is not yet available (common immediately after triggering), the command polls automatically every 15 seconds for up to ~5 minutes. Prow can be slow to schedule jobs. Do not just offer to check again — poll proactively.

## Arguments
- **$1** (execution-id): The UUID execution ID returned when a job was triggered (required)
