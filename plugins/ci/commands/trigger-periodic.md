---
description: Trigger a periodic gangway job with optional environment variable overrides
argument-hint: <job-name> [ENV_VAR=value ...]
---

## Name
ci:trigger-periodic

## Synopsis
```
/trigger-periodic <job-name> [ENV_VAR=value ...]
```

## Description

The `trigger-periodic` command triggers a periodic gangway job via the REST API. Periodic jobs run on a schedule but can be manually triggered for testing or urgent runs.

The command accepts:
- Job name (required, first argument)
- Environment variable overrides (optional, additional arguments in KEY=VALUE format)

It then constructs and executes the appropriate curl command to trigger the job via the gangway REST API.

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
   - First argument is the job name (required)
   - Remaining arguments are environment variable overrides in KEY=VALUE format
   - Note: Variables that need to override multistage parameters should be prefixed with `MULTISTAGE_PARAM_OVERRIDE_`

2. **Construct API Request**: Build the appropriate curl command using the `oc-auth` skill's curl wrapper:

   **Without overrides:**
   ```bash
   # Use curl_with_token.sh from oc-auth skill - it automatically adds the OAuth token
   # app.ci cluster API: https://api.ci.l2s4.p1.openshiftapps.com:6443
   curl_with_token.sh https://api.ci.l2s4.p1.openshiftapps.com:6443 -v -X POST \
     -d '{"job_name": "<JOB_NAME>", "job_execution_type": "1"}' \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```

   **With overrides:**
   ```bash
   curl_with_token.sh https://api.ci.l2s4.p1.openshiftapps.com:6443 -v -X POST \
     -d '{"job_name": "<JOB_NAME>", "job_execution_type": "1", "pod_spec_options": {"envs": {"ENV_VAR": "value"}}}' \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```

   **With multistage parameter override:**
   ```bash
   curl_with_token.sh https://api.ci.l2s4.p1.openshiftapps.com:6443 -v -X POST \
     -d '{"job_name": "periodic-to-trigger", "job_execution_type": "1", "pod_spec_options": {"envs": {"MULTISTAGE_PARAM_OVERRIDE_FOO": "bar"}}}' \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```
   
   The `curl_with_token.sh` wrapper retrieves the OAuth token from the app.ci cluster and adds it as an Authorization header automatically, without exposing the token.

3. **Request User Confirmation**: Display the complete JSON payload and curl command to the user, then explicitly ask for confirmation before proceeding. Wait for affirmative user response.

4. **Execute Request**: Only after receiving user confirmation, run the constructed curl command

6. **Display Results**: Show the API response including the execution ID

7. **Poll for Prow URL**: After a successful trigger, automatically resolve the Prow dashboard URL:
   - Wait 15 seconds for the job to be scheduled
   - Query the job status: `curl_with_token.sh https://api.ci.l2s4.p1.openshiftapps.com:6443 -X GET https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions/<EXECUTION_ID>`
   - If `gcs_path` is present, derive the Prow URL (see below) and display it
   - If `gcs_path` is missing and status is `TRIGGERED`, wait 15 seconds and retry (up to 20 retries, ~5 minutes total)
   - Stop polling once `gcs_path` is populated or status reaches a terminal state
   - If retries are exhausted without a `gcs_path`, provide `https://prow.ci.openshift.org/?job=<job_name>` so the user can find the job on the Prow dashboard

   **GCS Path → Prow URL conversion**: Strip the `gs://<bucket-name>/` prefix and prepend `https://prow.ci.openshift.org/view/gs/test-platform-results/`. The Prow URL always uses `test-platform-results` regardless of the bucket name in `gcs_path`.

   Example: `gs://origin-ci-test/logs/periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn/1234567890` → `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn/1234567890`

## Return Value
- **Success**: JSON response with execution ID and job details
- **Error**: HTTP error, authentication failure, or missing job name

**Important for Claude**:
1. **REQUIRED**: Before executing this command, you MUST ensure the `ci:oc-auth` skill is loaded by invoking it with the Skill tool. The curl_with_token.sh script depends on this skill being active.
2. You must locate and verify curl_with_token.sh before running it, you (Claude Code) have a bug that tries to use the script from the wrong directory!
3. Parse the JSON response and extract the execution ID
4. Display the execution ID to the user
5. **Automatically poll for the Prow URL** — do NOT just offer to check status. Poll until the Prow URL is resolved or retries are exhausted.
6. Display the Prow dashboard URL once available

## Examples

1. **Trigger a periodic job without overrides**:
   ```
   /trigger-periodic periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn
   ```

2. **Trigger a periodic job with payload override**:
   ```
   /trigger-periodic periodic-ci-openshift-release-master-ci-4.14-e2e-aws-ovn RELEASE_IMAGE_LATEST=quay.io/openshift-release-dev/ocp-release:4.18.8-x86_64
   ```

3. **Trigger with multistage parameter override**:
   ```
   /trigger-periodic periodic-to-trigger MULTISTAGE_PARAM_OVERRIDE_FOO=bar
   ```

4. **Trigger with multiple environment overrides**:
   ```
   /trigger-periodic periodic-ci-job RELEASE_IMAGE_LATEST=quay.io/image:4.18.8 MULTISTAGE_PARAM_OVERRIDE_TIMEOUT=3600
   ```

## Notes

- **Job Execution Type**: For periodic jobs, always use `"1"`
- **Rate Limits**: The REST API has rate limits; username is recorded in annotations
- **Authentication**: Tokens expire and may need to be refreshed via browser login
- **Multistage Overrides**: Prefix variables with `MULTISTAGE_PARAM_OVERRIDE_` to override multistage job parameters
- **Execution ID**: Save the execution ID from the response to query job status later
- **Prow URL Delay**: The Prow URL may not be available immediately after triggering — the job needs to be scheduled and transition from TRIGGERED to PENDING before `gcs_path` is populated. The command automatically polls until the URL is resolved.

## Arguments
- **$1** (job-name): The name of the periodic job to trigger (required)
- **$2-$N** (ENV_VAR=value): Optional environment variable overrides in KEY=VALUE format
