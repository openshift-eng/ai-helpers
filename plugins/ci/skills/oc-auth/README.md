# OC Authentication Helper Skill

A centralized skill for authenticated curl requests to OpenShift cluster APIs using OAuth tokens from multiple cluster contexts.

## Overview

This skill provides a curl wrapper that automatically handles OAuth token retrieval and injection, eliminating code duplication and preventing accidental token exposure.

## Components

### `curl_with_token.sh`

Curl wrapper that automatically retrieves OAuth tokens and adds them to requests.

**Usage:**
```bash
curl_with_token.sh <cluster_id> [curl arguments...]
```

**Parameters:**
- `cluster_id`: Either `app.ci` or `dpcr`
- `[curl arguments...]`: All standard curl arguments

**How it works:**
- Finds the correct oc context for the specified cluster
- Retrieves OAuth token using `oc whoami -t --context=<context>`
- Adds `Authorization: Bearer <token>` header automatically
- Executes curl with all provided arguments
- Token never appears in output

**Exit Codes:**
- `0`: Success
- `1`: Invalid cluster_id
- `2`: No context found for cluster
- `3`: Failed to retrieve token

## Supported Clusters

### app.ci
- **Pattern**: `ci-l2s4-p1`
- **Console**: https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/
- **Used by**: trigger-periodic, trigger-postsubmit, trigger-presubmit, query-job-status

### dpcr
- **Pattern**: `cr-j7t7-p1`
- **Console**: https://console-openshift-console.apps.cr.j7t7.p1.openshiftapps.com/
- **Used by**: ask-sippy

## Example Usage

```bash
#!/bin/bash

# Make authenticated API call to app.ci cluster
curl_with_token.sh app.ci -X POST \
  -d '{"job_name": "my-job"}' \
  https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions

# Make authenticated API call to DPCR cluster
curl_with_token.sh dpcr -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"message": "question"}' \
  https://sippy-auth.dptools.openshift.org/api/chat
```

## How It Works

1. **Context Discovery**: Lists all `oc` contexts and finds the one matching the cluster pattern
2. **Token Retrieval**: Uses `oc whoami -t --context=<context>` to get the token from the correct cluster
3. **Token Injection**: Automatically adds `Authorization: Bearer <token>` header to curl
4. **Execution**: Runs curl with all provided arguments
5. **Token Protection**: Token never appears in output or logs

## Benefits

- **No Token Exposure**: Token never shown in command output or logs
- **No Duplication**: Single source of truth for authentication logic
- **Simple Usage**: Just prefix curl commands with `curl_with_token.sh <cluster>`
- **Consistent Errors**: All commands show the same error messages
- **Easy Maintenance**: Update cluster patterns in one place
- **Multi-Cluster**: Supports multiple simultaneous cluster authentications

## See Also

- [SKILL.md](./SKILL.md) - Detailed skill documentation
- [CI Plugin README](../../README.md) - Parent plugin documentation

