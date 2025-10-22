---
description: Query the status of a gangway job execution by ID
argument-hint: <execution-id>
---

## Name
query-job-status

## Synopsis
```
/query-job-status <execution-id>
```

## Description

The `query-job-status` command queries the status of a gangway job execution via the REST API using the execution ID returned when a job is triggered.

The command accepts:
- Execution ID (required, UUID returned when triggering a job)

It makes a GET request to the gangway API and returns the current status of the job including its name, type, status, and GCS path to artifacts if available. The `curl_with_token.sh` wrapper handles all authentication automatically.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - $1: execution ID (required, UUID format)

2. **Execute API Request**: Make a GET request to query the job status using the `oc-auth` skill's curl wrapper:
   ```bash
   # Use curl_with_token.sh from oc-auth skill - it automatically adds the OAuth token
   # app.ci cluster API: https://api.ci.l2s4.p1.openshiftapps.com:6443
   curl_with_token.sh https://api.ci.l2s4.p1.openshiftapps.com:6443 -X GET \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions/<EXECUTION_ID>
   ```
   The `curl_with_token.sh` wrapper retrieves the OAuth token from the app.ci cluster and adds it as an Authorization header automatically, without exposing the token.

3. **Display Results**: Parse and present the JSON response with:
   - `id`: The execution ID
   - `job_name`: The name of the job
   - `job_type`: The type of job execution (PERIODIC, POSTSUBMIT, PRESUBMIT)
   - `job_status`: Current status (SUCCESS, FAILURE, PENDING, RUNNING, ABORTED)
   - `gcs_path`: Path to job artifacts in GCS (if available)

4. **Offer Follow-up Actions**:
   - If status is PENDING or RUNNING: Offer to check again after a delay
   - If status is SUCCESS or FAILURE with gcs_path: Offer to help access logs/artifacts

## Return Value
- **Success**: JSON response with job status details
- **Error**: HTTP error, authentication failure, or invalid execution ID

**Important for Claude**:
1. **REQUIRED**: Before executing this command, you MUST ensure the `ci:oc-auth` skill is loaded by invoking it with the Skill tool. The curl_with_token.sh script depends on this skill being active.
2. You must locate and verify curl_with_token.sh before running it, you (Claude Code) have a bug that tries to use the script from the wrong directory!
3. Parse the JSON response and present it in a readable format
4. Highlight the job status prominently
5. If PENDING/RUNNING, mention the job is still in progress
6. If SUCCESS/FAILURE, indicate completion status
7. If gcs_path is available, provide the path to artifacts

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

2. **Check running job**:
   ```
   /query-job-status 8f3a9b2c-1234-5678-9abc-def012345678
   ```
   Status shows "RUNNING" - Claude offers to check again later.

3. **Check failed job**:
   ```
   /query-job-status 5a6b7c8d-9e0f-1a2b-3c4d-5e6f7a8b9c0d
   ```
   Status shows "FAILURE" - Claude displays the gcs_path for log analysis.

## Notes

- **Execution ID Format**: UUID format (e.g., `ca249d50-dee8-4424-a0a7-6dd9d5605267`)
- **Job Status Values**: SUCCESS, FAILURE, PENDING, RUNNING, ABORTED
- **Rate Limits**: The REST API has rate limits
- **Authentication**: Tokens expire and may need to be refreshed via browser login
- **GCS Path**: Provides access to job logs and artifacts when available
- **Polling**: For long-running jobs, you may need to query multiple times

## Arguments
- **$1** (execution-id): The UUID execution ID returned when a job was triggered (required)
