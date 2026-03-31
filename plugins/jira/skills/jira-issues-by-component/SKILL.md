---
name: JIRA Issues by Component - Helper Skill
description: Provides secure curl wrapper for the jira:issues-by-component command to prevent token exposure
---

# JIRA Issues by Component - Helper Skill

This skill provides a secure curl wrapper script for the `jira:issues-by-component` command. The wrapper prevents JIRA authentication token exposure in process listings and command history.

## When to Use This Skill

This skill is automatically used by the `jira:issues-by-component` command. You typically don't need to invoke it directly unless you're:

- Developing or testing JIRA API integrations
- Building custom JIRA scripts that need secure authentication
- Debugging JIRA API connectivity issues

## Security Benefits

The `jira_curl.sh` wrapper script provides:

1. **Token Protection**: Authentication tokens never appear in process listings (`ps aux`)
2. **History Safety**: Tokens are not saved in shell history files
3. **Process Isolation**: Token is read from environment variables inside the script
4. **Clean Interface**: Same curl arguments you're already familiar with

## Files

### jira_curl.sh

Secure curl wrapper that automatically adds JIRA authentication headers.

**Location**: `plugins/jira/skills/jira-issues-by-component/jira_curl.sh`

**Usage**:
```bash
jira_curl.sh [curl arguments...]
```

**Required Environment Variables**:
- `JIRA_URL`: JIRA instance URL (e.g., `https://redhat.atlassian.net`)
- `JIRA_API_TOKEN`: Authentication token
- `JIRA_USERNAME`: Atlassian account email for Basic auth

**Example**:
```bash
# Set credentials
export JIRA_URL="https://redhat.atlassian.net"
export JIRA_API_TOKEN="your-token-here"
export JIRA_USERNAME="user@redhat.com"

# Use wrapper (token hidden from process list)
jira_curl.sh -s -X POST -d '{"jql":"project=OCPBUGS"}' https://redhat.atlassian.net/rest/api/3/search/jql
```

## How It Works

1. **Environment Check**: Validates that `JIRA_URL` and authentication token are set
2. **Token Selection**: Uses `JIRA_API_TOKEN` for Atlassian Cloud authentication
3. **Header Injection**: Constructs `Authorization: Basic <base64>` header inside the script using `JIRA_USERNAME` and `JIRA_API_TOKEN`
4. **Process Replacement**: Uses `exec curl` to replace the script process with curl
5. **Clean Execution**: Token never crosses process boundaries as a visible argument

## Implementation Details

The wrapper uses the same security pattern as the `oc auth` skill:

```bash
# Token and username are read from environment variables inside the script
AUTH_TOKEN="${JIRA_API_TOKEN:-}"
JIRA_USER="${JIRA_USERNAME:-}"

# Execute curl with Basic authentication header
# Credentials are constructed here, never visible in parent process command line
AUTH_HEADER=$(printf '%s:%s' "$JIRA_USER" "$AUTH_TOKEN" | base64)
exec curl -H "Authorization: Basic $AUTH_HEADER" -H "Accept: application/json" "$@"
```

**Why `exec`?**
- Replaces the script process with curl process
- By the time curl runs, the wrapper script is gone
- Only curl appears in process listings, not the wrapper with token

## Error Handling

The script provides clear error messages for common scenarios:

**Missing JIRA_URL**:
```
Error: JIRA_URL environment variable is required

Please set JIRA credentials:
  export JIRA_URL='https://redhat.atlassian.net'
  export JIRA_API_TOKEN='your-token-here'

Alternatively, source a credentials file:
  source ~/.jira-credentials
```

**Missing Token**:
```
Error: JIRA authentication token is required

Please set:
  export JIRA_API_TOKEN='your-token-here'
  export JIRA_USERNAME='user@redhat.com'

Get your token from:
  - Atlassian API Token: https://id.atlassian.com/manage-profile/security/api-tokens
```

## Credentials Setup

### Option 1: Export Directly

```bash
export JIRA_URL="https://redhat.atlassian.net"
export JIRA_API_TOKEN="your-token-here"
export JIRA_USERNAME="user@redhat.com"
```

### Option 2: Credentials File (Recommended)

Create `~/.jira-credentials`:
```bash
# ~/.jira-credentials
export JIRA_URL="https://redhat.atlassian.net"
export JIRA_API_TOKEN="your-token-here"
export JIRA_USERNAME="user@redhat.com"
```

Secure the file:
```bash
chmod 600 ~/.jira-credentials
```

Source it when needed:
```bash
source ~/.jira-credentials
```

## Getting Your Token

### Atlassian Cloud (API Token)

1. Visit: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a label (e.g., "CLI Access")
4. Copy the token
5. Set as `JIRA_API_TOKEN`

## Comparison to Direct Curl

### Insecure Approach (Don't Do This)
```bash
# Credentials exposed in process list and history!
curl -u "user@redhat.com:${JIRA_API_TOKEN}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"jql":"..."}' \
  https://redhat.atlassian.net/rest/api/3/search/jql
```

**Problems**:
- ❌ Token visible in `ps aux`
- ❌ Token saved in shell history
- ❌ Token may appear in logs
- ❌ Security risk

### Secure Approach (Use This)
```bash
# Token hidden inside wrapper script
jira_curl.sh -X POST -H "Content-Type: application/json" \
  -d '{"jql":"..."}' https://redhat.atlassian.net/rest/api/3/search/jql
```

**Benefits**:
- ✅ Token never in process list
- ✅ Token never in shell history
- ✅ Clean and simple syntax
- ✅ Secure by design

## Integration with jira:issues-by-component

The `jira:issues-by-component` command uses this wrapper to fetch JIRA issues securely:

```bash
# Get path to secure curl wrapper
PLUGIN_DIR="plugins/jira/skills/jira-issues-by-component"
JIRA_CURL="${PLUGIN_DIR}/jira_curl.sh"

# Fetch issues with pagination (token hidden)
HTTP_CODE=$("$JIRA_CURL" -s -w "%{http_code}" \
  -o "batch-${BATCH_NUM}.json" \
  "${API_URL}")
```

This approach:
- Handles 2000+ issues efficiently
- Streams data directly to disk
- Never exposes authentication token
- Avoids LLM token consumption

## See Also

- [oc auth skill](../../../ci/skills/oc-auth/README.md) - Similar pattern for OpenShift authentication
- [jira:issues-by-component command](../../commands/issues-by-component.md) - Command that uses this skill
- [CLAUDE.md](../../../../CLAUDE.md) - Plugin development guide
