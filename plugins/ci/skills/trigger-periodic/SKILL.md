---
name: "trigger-periodic"
description: Trigger a periodic gangway job with optional environment variable overrides
argument-hint: <job-name> [ENV_VAR=value ...]
user-invocable: true
disable-model-invocation: true
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
The app.ci cluster token is used solely for authentication with the gangway REST API. This token grants the same permissions as the authenticated user and must be handled with appropriate care. Retrieve it from the app.ci `oc` context immediately before the request and keep it in a shell variable.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - First argument is the job name (required)
   - Remaining arguments are environment variable overrides in KEY=VALUE format
   - Note: Variables that need to override multistage parameters should be prefixed with `MULTISTAGE_PARAM_OVERRIDE_`

2. **Construct API Request**: Locate the app.ci context and retrieve its token, then build the appropriate curl command:

   ```bash
   APP_CI_CONTEXT=$(oc config get-contexts -o name | while read -r context; do
     server=$(oc --context="$context" whoami --show-server 2>/dev/null || true)
     [ "$server" = "https://api.ci.l2s4.p1.openshiftapps.com:6443" ] && { echo "$context"; break; }
   done)
   [ -n "$APP_CI_CONTEXT" ] || { echo "Log in to the app.ci cluster first" >&2; exit 1; }
   APP_CI_TOKEN=$(oc --context="$APP_CI_CONTEXT" whoami -t)
   ```

   **Without overrides:**
   ```bash
   curl -H "Authorization: Bearer $APP_CI_TOKEN" -v -X POST \
     -d '{"job_name": "<JOB_NAME>", "job_execution_type": "1"}' \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```

   **With overrides:**
   ```bash
   curl -H "Authorization: Bearer $APP_CI_TOKEN" -v -X POST \
     -d '{"job_name": "<JOB_NAME>", "job_execution_type": "1", "pod_spec_options": {"envs": {"ENV_VAR": "value"}}}' \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```

   **With multistage parameter override:**
   ```bash
   curl -H "Authorization: Bearer $APP_CI_TOKEN" -v -X POST \
     -d '{"job_name": "periodic-to-trigger", "job_execution_type": "1", "pod_spec_options": {"envs": {"MULTISTAGE_PARAM_OVERRIDE_FOO": "bar"}}}' \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```
   
   Do not print or persist `APP_CI_TOKEN`; unset it when the workflow finishes.

3. **Request User Confirmation**: Display the complete JSON payload and curl command to the user, then explicitly ask for confirmation before proceeding. Wait for affirmative user response.

4. **Execute Request**: Only after receiving user confirmation, run the constructed curl command

6. **Display Results**: Show the API response including the execution ID

7. **Poll for Prow URL**: After a successful trigger, automatically resolve the Prow dashboard URL:
   - Wait 15 seconds for the job to be scheduled
   - Query the job status with the same token: `curl -H "Authorization: Bearer $APP_CI_TOKEN" https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions/<EXECUTION_ID>`
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
1. Verify that the selected `oc` context points to the app.ci API before retrieving its token.
2. Parse the JSON response and extract the execution ID.
3. Display the execution ID to the user.
4. **Automatically poll for the Prow URL** — do NOT just offer to check status. Poll until the Prow URL is resolved or retries are exhausted.
5. Display the Prow dashboard URL once available.

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
