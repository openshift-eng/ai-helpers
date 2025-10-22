---
description: Trigger a presubmit gangway job (typically use GitHub Prow commands instead)
argument-hint: <job-name> <org> <repo> <base-ref> <base-sha> <pr-number> <pr-sha> [ENV_VAR=value ...]
---

## Name
trigger-presubmit

## Synopsis
```
/trigger-presubmit <job-name> <org> <repo> <base-ref> <base-sha> <pr-number> <pr-sha> [ENV_VAR=value ...]
```

## Description

The `trigger-presubmit` command triggers a presubmit gangway job via the REST API.

**WARNING:** Triggering presubmit jobs via REST is generally unnecessary and not recommended. Presubmit jobs should typically be triggered using Prow commands like `/test` and `/retest` via GitHub interactions. Only use this command if you have a specific reason to trigger via REST API.

The command accepts:
- Job name (required)
- Organization (required, e.g., "openshift")
- Repository name (required, e.g., "origin")
- Base ref/branch (required, e.g., "master")
- Base SHA/commit hash (required)
- Pull request number (required)
- Pull request SHA/head commit (required)
- Environment variable overrides (optional, additional arguments in KEY=VALUE format)

It constructs the necessary JSON payload with refs and pulls structure and executes the curl command to trigger the job via the gangway REST API.

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

1. **Warn User**: Display a warning that presubmit jobs should typically use GitHub Prow commands (`/test`, `/retest`)

2. **Parse Arguments**:
   - $1: job name (required)
   - $2: organization (required)
   - $3: repository name (required)
   - $4: base ref/branch (required)
   - $5: base SHA (required)
   - $6: pull request number (required)
   - $7: pull request SHA (required)
   - $8-$N: environment variable overrides in KEY=VALUE format (optional)

4. **Construct JSON Payload**: Build the payload with refs and pulls structure:

   **Without overrides:**
   ```json
   {
     "job_name": "<JOB_NAME>",
     "job_execution_type": "3",
     "refs": {
       "org": "<ORG>",
       "repo": "<REPO>",
       "base_ref": "<BASE_REF>",
       "base_sha": "<BASE_SHA>",
       "pulls": [{
         "number": <PR_NUMBER>,
         "sha": "<PR_SHA>",
         "link": "https://github.com/<ORG>/<REPO>/pull/<PR_NUMBER>"
       }]
     }
   }
   ```

   **With overrides:**
   ```json
   {
     "job_name": "<JOB_NAME>",
     "job_execution_type": "3",
     "refs": {
       "org": "<ORG>",
       "repo": "<REPO>",
       "base_ref": "<BASE_REF>",
       "base_sha": "<BASE_SHA>",
       "pulls": [{
         "number": <PR_NUMBER>,
         "sha": "<PR_SHA>",
         "link": "https://github.com/<ORG>/<REPO>/pull/<PR_NUMBER>"
       }]
     },
     "pod_spec_options": {
       "envs": {"ENV_VAR": "value"}
     }
   }
   ```

5. **Save JSON to Temporary File**: Write the payload to a temp file (e.g., `/tmp/presubmit-spec.json`)

6. **Request User Confirmation**: Display the complete JSON payload and curl command to the user, then explicitly ask for confirmation before proceeding. Wait for affirmative user response.

7. **Execute Request**: Only after receiving user confirmation, run the curl command using the `oc-auth` skill's curl wrapper:
   ```bash
   # Use curl_with_token.sh from oc-auth skill - it automatically adds the OAuth token
   curl_with_token.sh app.ci -v -X POST \
     -d @/tmp/presubmit-spec.json \
     https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions
   ```
   The `curl_with_token.sh` wrapper retrieves the OAuth token from the app.ci cluster and adds it as an Authorization header automatically, without exposing the token.

8. **Clean Up**: Remove the temporary JSON file

9. **Display Results**: Show the API response including the execution ID

10. **Offer Follow-up**: Optionally offer to query the job status using `/query-job-status`

## Return Value
- **Success**: JSON response with execution ID and job details
- **Error**: HTTP error, authentication failure, or missing required arguments

**Important for Claude**:
1. Display the warning about using GitHub Prow commands instead
2. Validate all required arguments are provided
3. Parse the JSON response and extract the execution ID
4. Display the execution ID to the user
5. Offer to check job status with `/query-job-status`

## Examples

1. **Trigger a presubmit job without overrides**:
   ```
   /trigger-presubmit pull-ci-openshift-origin-master-e2e-aws openshift origin master abc123def456 1234 def456ghi789
   ```

2. **Trigger a presubmit job with environment override**:
   ```
   /trigger-presubmit my-presubmit-job openshift installer master 1a2b3c4d 5678 4d5e6f7g RELEASE_IMAGE_INITIAL=quay.io/image:test
   ```

3. **Trigger with multiple environment overrides**:
   ```
   /trigger-presubmit pull-ci-test openshift cluster-version-operator master abcdef12 999 fedcba98 MULTISTAGE_PARAM_OVERRIDE_TIMEOUT=5400 TEST_SUITE=custom
   ```

## Notes

- **Recommended Approach**: Use GitHub Prow commands (`/test <job-name>`, `/retest`) instead of this REST API
- **Job Execution Type**: For presubmit jobs, always use `"3"`
- **Rate Limits**: The REST API has rate limits; username is recorded in annotations
- **Authentication**: Tokens expire and may need to be refreshed via browser login
- **Refs Structure**: The refs object with pulls array is required for presubmit jobs
- **Pull Link**: Automatically constructed as `https://github.com/<org>/<repo>/pull/<pr-number>`
- **Execution ID**: Save the execution ID from the response to query job status later

## Arguments
- **$1** (job-name): The name of the presubmit job to trigger (required)
- **$2** (org): GitHub organization (e.g., "openshift") (required)
- **$3** (repo): Repository name (e.g., "origin") (required)
- **$4** (base-ref): Base branch/ref (e.g., "master") (required)
- **$5** (base-sha): Base commit SHA hash (required)
- **$6** (pr-number): Pull request number (required)
- **$7** (pr-sha): Pull request head commit SHA (required)
- **$8-$N** (ENV_VAR=value): Optional environment variable overrides in KEY=VALUE format
