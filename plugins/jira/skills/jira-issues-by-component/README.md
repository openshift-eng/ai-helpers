# JIRA Issues by Component - Secure Curl Wrapper

This directory contains a secure curl wrapper script used by the `jira:issues-by-component` command to prevent JIRA authentication token exposure.

## Files

- **jira_curl.sh**: Secure curl wrapper that reads JIRA credentials from environment variables and executes curl with the Authorization header without exposing the token in process listings or command history.

## Why This Wrapper Exists

When using curl directly with authentication tokens in command line arguments, the tokens become visible in:
- Process listings (`ps aux`)
- Shell history files
- Process monitoring tools
- System logs

This wrapper script solves this security issue by:
1. Reading credentials from environment variables
2. Constructing the Authorization header inside the script
3. Using `exec curl` to replace the script process with curl
4. Ensuring the token never appears in process arguments

## Usage

```bash
jira_curl.sh [curl arguments...]
```

**Example:**
```bash
# Instead of exposing token in command line:
curl -H "Authorization: Bearer ${JIRA_PERSONAL_TOKEN}" https://jira.example.com/api

# Use wrapper (token hidden):
jira_curl.sh https://jira.example.com/api
```

## Required Environment Variables

- `JIRA_URL`: JIRA instance URL (e.g., `https://issues.redhat.com`)
- `JIRA_PERSONAL_TOKEN` or `JIRA_API_TOKEN`: Authentication token

The wrapper will use `JIRA_PERSONAL_TOKEN` if available (preferred for Red Hat JIRA), otherwise falls back to `JIRA_API_TOKEN`.

## Security Benefits

✅ **Token never exposed**: Stays inside the script process
✅ **Clean history**: Shell history shows only the wrapper script path
✅ **Process safety**: `ps aux` doesn't reveal the token
✅ **Consistent pattern**: Mirrors the `oc auth` skill's security approach

## See Also

- [oc auth skill](../../../ci/skills/oc-auth/README.md) - Similar pattern for OpenShift authentication
- [jira:issues-by-component command](../../commands/issues-by-component.md) - Command documentation
