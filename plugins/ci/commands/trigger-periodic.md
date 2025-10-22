---
description: Trigger a periodic gangway job with optional environment variable overrides
argument-hint: <job-name> [ENV_VAR=value ...]
---

## Name
trigger-periodic

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
The app.ci cluster token (`oc whoami -t`) is used solely for authentication with the gangway REST API. This token grants the same permissions as the authenticated user and must be handled with appropriate care.

## Prerequisites

**Required Authentication:**
- User MUST be authenticated to the app.ci cluster via browser login

To authenticate:
1. Visit https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/
2. Log in through the browser with SSO credentials
3. Click on username → "Copy login command"
4. Paste and execute the `oc login` command in terminal

Verify authentication with:
```bash
oc config get-contexts
```
Look for a context with cluster name containing `ci-l2s4-p1`.

**Note**: Since `oc` maintains multiple cluster contexts in your kubeconfig, you can be authenticated to both the app.ci cluster (for triggering jobs) and the DPCR cluster (for Sippy queries) simultaneously. Each `oc login` creates a new context.

## Implementation

The command performs the following steps:

1. **Find app.ci Context**: Search through `oc` contexts to find the one for the app.ci cluster (cluster name containing `ci-l2s4-p1`). If not found, provide instructions to log in via browser.

2. **Parse Arguments**:
   - First argument is the job name (required)
   - Remaining arguments are environment variable overrides in KEY=VALUE format
   - Note: Variables that need to override multistage parameters should be prefixed with `MULTISTAGE_PARAM_OVERRIDE_`

3. **Construct API Request**: Build the appropriate curl command:

   **Find the app.ci context first:**
   ```bash
   APPCI_CONTEXT=$(oc config get-contexts -o name | while read ctx; do
     if oc config view -o jsonpath="{.contexts[?(@.name=='$ctx')].context.cluster}" | grep -q "ci-l2s4-p1"; then
       echo "$ctx"
       break
     fi
   done)
   ```

   **Without overrides:**
   ```bash
   curl -v -X POST -H "Authorization: Bearer $(oc whoami -t --context=$APPCI_CONTEXT)" \
     -d '{"job_name": "<JOB_NAME>", "job_execution_type": "1"}' \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```

   **With overrides:**
   ```bash
   curl -v -X POST -H "Authorization: Bearer $(oc whoami -t --context=$APPCI_CONTEXT)" \
     -d '{"job_name": "<JOB_NAME>", "job_execution_type": "1", "pod_spec_options": {"envs": {"ENV_VAR": "value"}}}' \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```

   **With multistage parameter override:**
   ```bash
   curl -v -X POST -H "Authorization: Bearer $(oc whoami -t --context=$APPCI_CONTEXT)" \
     -d '{"job_name": "periodic-to-trigger", "job_execution_type": "1", "pod_spec_options": {"envs": {"MULTISTAGE_PARAM_OVERRIDE_FOO": "bar"}}}' \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```

4. **Request User Confirmation**: Display the complete JSON payload and curl command to the user, then explicitly ask for confirmation before proceeding. Wait for affirmative user response.

5. **Execute Request**: Only after receiving user confirmation, run the constructed curl command

6. **Display Results**: Show the API response including the execution ID

7. **Offer Follow-up**: Optionally offer to query the job status using `/query-job-status`

## Return Value
- **Success**: JSON response with execution ID and job details
- **Error**: HTTP error, authentication failure, or missing job name

**Important for Claude**:
1. Parse the JSON response and extract the execution ID
2. Display the execution ID to the user
3. Offer to check job status with `/query-job-status`

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

## Arguments
- **$1** (job-name): The name of the periodic job to trigger (required)
- **$2-$N** (ENV_VAR=value): Optional environment variable overrides in KEY=VALUE format
