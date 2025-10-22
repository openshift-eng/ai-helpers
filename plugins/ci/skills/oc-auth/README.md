# OC Authentication Helper Skill

A centralized skill for authenticated curl requests to OpenShift cluster APIs using OAuth tokens from multiple cluster contexts.

## Overview

This skill provides a curl wrapper that automatically handles OAuth token retrieval and injection, eliminating code duplication and preventing accidental token exposure.

## Components

### `curl_with_token.sh`

Curl wrapper that automatically retrieves OAuth tokens and adds them to requests.

**Usage:**
```bash
curl_with_token.sh <cluster_api_url> [curl arguments...]
```

**Parameters:**
- `cluster_api_url`: Full cluster API server URL (e.g., `https://api.ci.l2s4.p1.openshiftapps.com:6443`)
- `[curl arguments...]`: All standard curl arguments

**How it works:**
- Finds the correct oc context matching the specified cluster API URL
- Retrieves OAuth token using `oc whoami -t --context=<context>`
- Adds `Authorization: Bearer <token>` header automatically
- Executes curl with all provided arguments
- Token never appears in output

**Exit Codes:**
- `0`: Success
- `1`: Invalid cluster_id
- `2`: No context found for cluster
- `3`: Failed to retrieve token

## Common Clusters

### app.ci - OpenShift CI Cluster
- **Console**: https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/
- **API Server**: https://api.ci.l2s4.p1.openshiftapps.com:6443
- **Used by**: trigger-periodic, trigger-postsubmit, trigger-presubmit, query-job-status

### dpcr - DPCR Cluster
- **Console**: https://console-openshift-console.apps.cr.j7t7.p1.openshiftapps.com/
- **API Server**: https://api.cr.j7t7.p1.openshiftapps.com:6443
- **Used by**: ask-sippy

**Note**: This skill supports any OpenShift cluster - simply provide the cluster's API server URL.

## Example Usage

```bash
#!/bin/bash

# Make authenticated API call to app.ci cluster
curl_with_token.sh https://api.ci.l2s4.p1.openshiftapps.com:6443 -X POST \
  -d '{"job_name": "my-job"}' \
  https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions

# Make authenticated API call to DPCR cluster
curl_with_token.sh https://api.cr.j7t7.p1.openshiftapps.com:6443 -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"message": "question"}' \
  https://sippy-auth.dptools.openshift.org/api/chat

# Make authenticated API call to any other OpenShift cluster
curl_with_token.sh https://api.your-cluster.example.com:6443 -X GET \
  https://your-api.example.com/endpoint
```

## How It Works

1. **Context Discovery**: Lists all `oc` contexts and finds the one matching the cluster API server URL
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

