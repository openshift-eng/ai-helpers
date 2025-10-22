---
name: OC Authentication Helper
description: Helper skill to retrieve OAuth tokens from the correct OpenShift cluster context when multiple clusters are configured
---

# OC Authentication Helper

This skill provides a centralized way to retrieve OAuth tokens from specific OpenShift clusters when multiple cluster contexts are configured in the user's kubeconfig.

## When to Use This Skill

Use this skill whenever you need to:
- Get an OAuth token for API authentication from a specific OpenShift cluster
- Verify authentication to a specific cluster
- Work with multiple OpenShift cluster contexts simultaneously

This skill is used by all commands that need to authenticate with OpenShift clusters:
- `ask-sippy` command (DPCR cluster)
- `trigger-periodic`, `trigger-postsubmit`, `trigger-presubmit` commands (app.ci cluster)
- `query-job-status` command (app.ci cluster)

The skill provides a single `curl_with_token.sh` script that wraps curl and automatically handles OAuth token retrieval and injection, preventing accidental token exposure.

**Due to a known Claude Code bug with git-installed marketplace plugins:**

  When referencing files from this skill (scripts, configuration files, etc.), you MUST:

  1. **Always use the "Base directory" path** provided at the top of this skill prompt
  2. **Never assume** skills are located in `~/.claude/plugins/`
  3. **Construct full absolute paths** by combining the base directory with the relative file path

  **Example:**
  - ❌ WRONG: `~/.claude/plugins/ci/skills/oc-auth/curl_with_token.sh`
  - ✅ CORRECT: Use the base directory shown above + `/curl_with_token.sh`

  If you see "no such file or directory" errors, verify you're using the base directory path, not the assumed marketplace cache location.

## Prerequisites

1. **oc CLI Installation**
   - Check if installed: `which oc`
   - If not installed, provide instructions for the user's platform
   - Installation guide: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html

2. **User Authentication**
   - User must be logged in to the target cluster via browser-based authentication
   - Each `oc login` creates a new context in the kubeconfig

## How It Works

The `oc` CLI maintains multiple cluster contexts in `~/.kube/config`. When a user runs `oc login` to different clusters, each login creates a separate context. This skill:

1. Lists all available contexts
2. Searches for the context matching the target cluster by API server URL
3. Retrieves the OAuth token from that specific context
4. Returns the token for use in API calls

## Common Clusters

Here are commonly used OpenShift clusters:

### 1. `app.ci` - OpenShift CI Cluster
- **Console URL**: https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/
- **API Server**: https://api.ci.l2s4.p1.openshiftapps.com:6443
- **Used by**: trigger-periodic, trigger-postsubmit, trigger-presubmit, query-job-status

### 2. `dpcr` - DPCR Cluster
- **Console URL**: https://console-openshift-console.apps.cr.j7t7.p1.openshiftapps.com/
- **API Server**: https://api.cr.j7t7.p1.openshiftapps.com:6443
- **Used by**: ask-sippy

**Note**: The skill supports any OpenShift cluster - simply provide the cluster's API server URL.

## Usage

### Script: `curl_with_token.sh`

A curl wrapper that automatically retrieves the OAuth token and adds it to the request, preventing token exposure.

```bash
curl_with_token.sh <cluster_api_url> [curl arguments...]
```

**Parameters:**
- `<cluster_api_url>`: Full cluster API server URL (e.g., `https://api.ci.l2s4.p1.openshiftapps.com:6443`)
- `[curl arguments...]`: All standard curl arguments (URL, headers, data, etc.)

**How it works:**
1. Finds the oc context matching the specified cluster API URL
2. Retrieves OAuth token from that cluster context
3. Adds `Authorization: Bearer <token>` header automatically
4. Executes curl with all provided arguments
5. Token never appears in output or command history

**Exit Codes:**
- `0`: Success
- `1`: Invalid cluster_id or missing arguments
- `2`: No context found for the specified cluster
- `3`: Failed to retrieve token from context
- Other: curl exit codes

### Example Usage in Commands

Use the curl wrapper instead of regular curl for authenticated requests:

```bash
# Query app.ci API
curl_with_token.sh https://api.ci.l2s4.p1.openshiftapps.com:6443 -X POST \
  -d '{"job_name": "my-job", "job_execution_type": "1"}' \
  https://gangway-ci.apps.ci.l2s4.p1.openshiftapps.com/v1/executions

# Query Sippy API (DPCR cluster)
curl_with_token.sh https://api.cr.j7t7.p1.openshiftapps.com:6443 -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"message": "question", "chat_history": []}' \
  https://sippy-auth.dptools.openshift.org/api/chat

# Query any other OpenShift cluster API
curl_with_token.sh https://api.your-cluster.example.com:6443 -X GET \
  https://your-api.example.com/endpoint
```

**Benefits:**
- Token never exposed in logs or output
- Automatic authentication error handling
- Same curl arguments you're already familiar with
- Works with any curl flags (-v, -s, -X, -H, -d, etc.)

## Error Handling

The script provides clear error messages for common scenarios:

1. **Missing or invalid arguments**
   - Error: "Usage: curl_with_token.sh <cluster_api_url> [curl arguments...]"
   - Shows example usage

2. **No context found**
   - Error: "No oc context found for cluster with API server: {url}"
   - Provides authentication instructions

3. **Token retrieval failed**
   - Error: "Failed to retrieve token from context {context}"
   - Suggests re-authenticating to the cluster

## Authentication Instructions

### General Authentication Process:
```
Please authenticate first:
1. Visit the cluster's console URL in your browser
2. Log in through the browser with your credentials
3. Click on username → 'Copy login command'
4. Paste and execute the 'oc login' command in terminal

Verify authentication with:
  oc config get-contexts
  oc cluster-info
```

### Examples:

**For app.ci cluster:**
1. Visit https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/
2. Follow the authentication process above
3. Verify with `oc cluster-info` - should show API server: https://api.ci.l2s4.p1.openshiftapps.com:6443

**For DPCR cluster:**
1. Visit https://console-openshift-console.apps.cr.j7t7.p1.openshiftapps.com/
2. Follow the authentication process above
3. Verify with `oc cluster-info` - should show API server: https://api.cr.j7t7.p1.openshiftapps.com:6443

## Benefits

1. **Single Source of Truth**: All context discovery logic is in one place
2. **Consistency**: All commands use the same authentication method
3. **Maintainability**: Changes to cluster names or patterns only need to be updated in one place
4. **Error Handling**: Centralized error messages and authentication instructions
5. **Multi-Cluster Support**: Users can be authenticated to multiple clusters simultaneously

## Implementation Details

The script uses the following approach:

1. **Get all context names**
   ```bash
   oc config get-contexts -o name
   ```

2. **Find matching context by API server URL**
   ```bash
   for ctx in $contexts; do
     cluster_name=$(oc config view -o jsonpath="{.contexts[?(@.name=='$ctx')].context.cluster}")
     server=$(oc config view -o jsonpath="{.clusters[?(@.name=='$cluster_name')].cluster.server}")
     if [ "$server" = "$target_url" ]; then
       echo "$ctx"
       break
     fi
   done
   ```

3. **Retrieve token from context**
   ```bash
   oc whoami -t --context=$context_name
   ```

This ensures we get the token from the correct cluster by matching the exact API server URL, even when multiple cluster contexts exist.

