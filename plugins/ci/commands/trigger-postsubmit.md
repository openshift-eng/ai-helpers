---
description: Trigger a postsubmit gangway job with repository refs
argument-hint: <job-name> <org> <repo> <base-ref> <base-sha> [ENV_VAR=value ...]
---

## Name
ci:trigger-postsubmit

## Synopsis
```
/trigger-postsubmit <job-name> <org> <repo> <base-ref> <base-sha> [ENV_VAR=value ...]
```

## Description

The `trigger-postsubmit` command triggers a postsubmit gangway job via the REST API. Postsubmit jobs run after code is merged and require repository reference information.

The command accepts:
- Job name (required)
- Organization (required, e.g., "openshift")
- Repository name (required, e.g., "assisted-installer")
- Base ref/branch (required, e.g., "release-4.12")
- Base SHA/commit hash (required)
- Environment variable overrides (optional, additional arguments in KEY=VALUE format)

It constructs the necessary JSON payload with refs structure and executes the curl command to trigger the job via the gangway REST API.

## Security

**IMPORTANT SECURITY REQUIREMENTS:**

Claude is granted LIMITED and SPECIFIC access to the app.ci cluster token for the following AUTHORIZED operations ONLY:
- **READ operations**: Checking authentication status (`oc whoami`)
- **TRIGGERING jobs**: POST requests to the gangway API to trigger jobs

Claude is EXPLICITLY PROHIBITED from:
- Modifying cluster resources (deployments, pods, services, etc.)
- Deleting or altering existing jobs or executions
- Accessing secrets, configmaps, or sensitive data
- Making any cluster modifications beyond job triggering
- Using the token for any purpose other than the specific operations listed above

**MANDATORY USER CONFIRMATION:**
Before executing ANY POST operation (job trigger), Claude MUST:
1. Display the complete payload that will be sent
2. Show the exact curl command that will be executed
3. Request explicit user confirmation with a clear "yes/no" prompt
4. Only proceed after receiving affirmative confirmation

**Token Usage:**
The app.ci cluster token is used solely for authentication with the gangway REST API. This token grants the same permissions as the authenticated user and must be handled with appropriate care. The `curl_with_token.sh` wrapper handles all authentication automatically.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - $1: job name (required)
   - $2: organization (required)
   - $3: repository name (required)
   - $4: base ref/branch (required)
   - $5: base SHA (required)
   - $6-$N: environment variable overrides in KEY=VALUE format (optional)

3. **Construct JSON Payload**: Build the payload with refs structure:

   **Without overrides:**
   ```json
   {
     "job_name": "<JOB_NAME>",
     "job_execution_type": "2",
     "refs": {
       "org": "<ORG>",
       "repo": "<REPO>",
       "base_ref": "<BASE_REF>",
       "base_sha": "<BASE_SHA>",
       "repo_link": "https://github.com/<ORG>/<REPO>"
     }
   }
   ```

   **With overrides:**
   ```json
   {
     "job_name": "<JOB_NAME>",
     "job_execution_type": "2",
     "refs": {
       "org": "<ORG>",
       "repo": "<REPO>",
       "base_ref": "<BASE_REF>",
       "base_sha": "<BASE_SHA>",
       "repo_link": "https://github.com/<ORG>/<REPO>"
     },
     "pod_spec_options": {
       "envs": {"ENV_VAR": "value"}
     }
   }
   ```

4. **Save JSON to Temporary File**: Write the payload to a temp file (e.g., `/tmp/postsubmit-spec.json`)

5. **Request User Confirmation**: Display the complete JSON payload and curl command to the user, then explicitly ask for confirmation before proceeding. Wait for affirmative user response.

6. **Execute Request**: Only after receiving user confirmation, run the curl command using the `oc-auth` skill's curl wrapper:
   ```bash
   # Use curl_with_token.sh from oc-auth skill - it automatically adds the OAuth token
   # app.ci cluster API: https://api.ci.l2s4.p1.openshiftapps.com:6443
   curl_with_token.sh https://api.ci.l2s4.p1.openshiftapps.com:6443 -v -X POST \
     -d @/tmp/postsubmit-spec.json \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```
   The `curl_with_token.sh` wrapper retrieves the OAuth token from the app.ci cluster and adds it as an Authorization header automatically, without exposing the token.

7. **Clean Up**: Remove the temporary JSON file

8. **Display Results**: Show the API response including the execution ID

9. **Poll for Prow URL**: After a successful trigger, automatically resolve the Prow dashboard URL:
   - Wait 15 seconds for the job to be scheduled
   - Query the job status: `curl_with_token.sh https://api.ci.l2s4.p1.openshiftapps.com:6443 -X GET https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions/<EXECUTION_ID>`
   - If `gcs_path` is present, derive the Prow URL (see below) and display it
   - If `gcs_path` is missing and status is `TRIGGERED`, wait 15 seconds and retry (up to 20 retries, ~5 minutes total)
   - Stop polling once `gcs_path` is populated or status reaches a terminal state
   - If retries are exhausted without a `gcs_path`, provide `https://prow.ci.openshift.org/?job=<job_name>` so the user can find the job on the Prow dashboard

   **GCS Path → Prow URL conversion**: Strip the `gs://<bucket-name>/` prefix and prepend `https://prow.ci.openshift.org/view/gs/test-platform-results/`. The Prow URL always uses `test-platform-results` regardless of the bucket name in `gcs_path`.

   Example: `gs://origin-ci-test/logs/branch-ci-openshift-origin-master-images/1234567890` → `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/branch-ci-openshift-origin-master-images/1234567890`

## Return Value
- **Success**: JSON response with execution ID and job details
- **Error**: HTTP error, authentication failure, or missing required arguments

**Important for Claude**:
1. **REQUIRED**: Before executing this command, you MUST ensure the `ci:oc-auth` skill is loaded by invoking it with the Skill tool. The curl_with_token.sh script depends on this skill being active.
2. You must locate and verify curl_with_token.sh before running it, you (Claude Code) have a bug that tries to use the script from the wrong directory!
3. Validate all required arguments are provided
4. Parse the JSON response and extract the execution ID
5. Display the execution ID to the user
6. **Automatically poll for the Prow URL** — do NOT just offer to check status. Poll until the Prow URL is resolved or retries are exhausted.
7. Display the Prow dashboard URL once available

## Examples

1. **Trigger a postsubmit job without overrides**:
   ```
   /trigger-postsubmit branch-ci-openshift-assisted-installer-release-4.12-images openshift assisted-installer release-4.12 7336f38f75f91a876313daacbfw97f25dfe21bbf
   ```

2. **Trigger a postsubmit job with environment override**:
   ```
   /trigger-postsubmit branch-ci-openshift-origin-master-images openshift origin master abc123def456 RELEASE_IMAGE_LATEST=quay.io/image:latest
   ```

3. **Trigger with multiple environment overrides**:
   ```
   /trigger-postsubmit my-postsubmit-job openshift cluster-api-provider-aws master def789ghi012 MULTISTAGE_PARAM_OVERRIDE_TIMEOUT=7200 BUILD_ID=custom-123
   ```

## Notes

- **Job Execution Type**: For postsubmit jobs, always use `"2"`
- **Rate Limits**: The REST API has rate limits; username is recorded in annotations
- **Authentication**: Tokens expire and may need to be refreshed via browser login
- **Refs Structure**: The refs object is required for postsubmit jobs to identify the repository and commit
- **Repo Link**: Automatically constructed as `https://github.com/<org>/<repo>`
- **Execution ID**: Save the execution ID from the response to query job status later
- **Prow URL Delay**: The Prow URL may not be available immediately after triggering — the job needs to be scheduled and transition from TRIGGERED to PENDING before `gcs_path` is populated. The command automatically polls until the URL is resolved.

## Arguments
- **$1** (job-name): The name of the postsubmit job to trigger (required)
- **$2** (org): GitHub organization (e.g., "openshift") (required)
- **$3** (repo): Repository name (e.g., "assisted-installer") (required)
- **$4** (base-ref): Base branch/ref (e.g., "release-4.12", "master") (required)
- **$5** (base-sha): Base commit SHA hash (required)
- **$6-$N** (ENV_VAR=value): Optional environment variable overrides in KEY=VALUE format
