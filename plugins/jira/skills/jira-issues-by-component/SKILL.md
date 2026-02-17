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
- `JIRA_URL`: JIRA instance URL (e.g., `https://issues.redhat.com`)
- `JIRA_PERSONAL_TOKEN` or `JIRA_API_TOKEN`: Authentication token

**Example**:
```bash
# Set credentials
export JIRA_URL="https://issues.redhat.com"
export JIRA_PERSONAL_TOKEN="your-token-here"

# Use wrapper (token hidden from process list)
jira_curl.sh -s https://issues.redhat.com/rest/api/2/search?jql=project=OCPBUGS
```

## How It Works

1. **Environment Check**: Validates that `JIRA_URL` and authentication token are set
2. **Token Selection**: Prefers `JIRA_PERSONAL_TOKEN` (Red Hat JIRA), falls back to `JIRA_API_TOKEN` (JIRA Cloud)
3. **Header Injection**: Constructs `Authorization: Bearer <token>` header inside the script
4. **Process Replacement**: Uses `exec curl` to replace the script process with curl
5. **Clean Execution**: Token never crosses process boundaries as a visible argument

## Implementation Details

The wrapper uses the same security pattern as the `oc auth` skill:

```bash
# Token is read from environment variable inside the script
AUTH_TOKEN="${JIRA_PERSONAL_TOKEN:-${JIRA_API_TOKEN:-}}"

# Execute curl with the Authorization header
# Token is added here, never visible in parent process command line
exec curl -H "Authorization: Bearer $AUTH_TOKEN" -H "Accept: application/json" "$@"
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
  export JIRA_URL='https://issues.redhat.com'
  export JIRA_PERSONAL_TOKEN='your-token-here'

Alternatively, source a credentials file:
  source ~/.jira-credentials
```

**Missing Token**:
```
Error: JIRA authentication token is required

Please set either:
  export JIRA_PERSONAL_TOKEN='your-token-here'  # Preferred for Red Hat JIRA
  export JIRA_API_TOKEN='your-token-here'       # For JIRA Cloud

Get your token from:
  - Red Hat JIRA PAT: https://issues.redhat.com/secure/ViewProfile.jspa?...
  - Atlassian API Token: https://id.atlassian.com/manage-profile/security/api-tokens
```

## Credentials Setup

### Option 1: Export Directly

```bash
export JIRA_URL="https://issues.redhat.com"
export JIRA_PERSONAL_TOKEN="your-token-here"
```

### Option 2: Credentials File (Recommended)

Create `~/.jira-credentials`:
```bash
# ~/.jira-credentials
export JIRA_URL="https://issues.redhat.com"
export JIRA_PERSONAL_TOKEN="your-token-here"
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

### Red Hat JIRA (Personal Access Token)

1. Visit: https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens
2. Click "Create token"
3. Give it a name (e.g., "CLI Access")
4. Copy the token (shown only once)
5. Set as `JIRA_PERSONAL_TOKEN`

### JIRA Cloud (API Token)

1. Visit: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a label (e.g., "CLI Access")
4. Copy the token
5. Set as `JIRA_API_TOKEN`

## Comparison to Direct Curl

### Insecure Approach (Don't Do This)
```bash
# Token exposed in process list and history!
curl -H "Authorization: Bearer ${JIRA_PERSONAL_TOKEN}" \
  https://issues.redhat.com/rest/api/2/search
```

**Problems**:
- ❌ Token visible in `ps aux`
- ❌ Token saved in shell history
- ❌ Token may appear in logs
- ❌ Security risk

### Secure Approach (Use This)
```bash
# Token hidden inside wrapper script
jira_curl.sh https://issues.redhat.com/rest/api/2/search
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
