---
description: Verify that GitHub and Jira tokens are valid and the environment is ready for Node team workflows
argument-hint: "[--fix]"
---

## Name
node-team:preflight

## Synopsis
```text
/node-team:preflight [--fix]
```

## Description

Tests all authentication tokens and CLI tools required by Node team workflows
in a single pass. Reports pass/fail for each check so you can fix all auth
issues at once instead of discovering them one at a time.

Run this before `/node-team:setup`, `/node-cve:triage`, or `/node-bug:triage`
to catch expired or missing credentials early.

## Implementation

Run these checks in order and collect results:

### 1. GitHub CLI (`gh`)

```bash
gh auth status
```

- Pass: output contains "Logged in to github.com"
- Fail: not installed, not logged in, or token expired

### 2. GitHub API access

```bash
gh api user -q .login
```

- Pass: returns a username
- Fail: token lacks required scopes or is expired

### 3. Jira API token

Resolve the token using the same chain as
[jira.md](../skills/node/references/jira.md) (env var, macOS Keychain,
Linux secret-tool):

```bash
JIRA_API_TOKEN="${JIRA_API_TOKEN:-$(security find-generic-password -s "JIRA_API_TOKEN" -w 2>/dev/null || secret-tool lookup service redhat key JIRA_API_TOKEN 2>/dev/null)}"
```

- Pass: non-empty value resolved
- Fail: no token found in any source

### 4. Jira API connectivity

```bash
curl -s -o /dev/null -w "%{http_code}" -u "$JIRA_USER:$JIRA_API_TOKEN" \
  "https://redhat.atlassian.net/rest/api/3/myself"
```

- Pass: HTTP 200
- Fail: 401 (bad token), 403 (permissions), or connection error

### 5. Jira CLI (`jira`)

```bash
jira me
```

- Pass: returns current user info
- Fail: not installed or not configured (required by `node-cve`;
  `node-team` and `node-bug` use `curl` directly)

### Summary

Print a table of results:

```text
Check                 Status
-----                 ------
GitHub CLI            PASS
GitHub API            PASS
Jira API token        PASS
Jira API connectivity PASS
Jira CLI              PASS (node-cve only)
```

If any required check fails and `--fix` is specified, print the remediation
steps for each failure (e.g., `gh auth login`, how to set `JIRA_API_TOKEN`).
If `--fix` is not specified, print a hint to re-run with `--fix` for guidance.

## Return Value

- Summary table with pass/fail status for each check
- Exit status: all required checks pass or list of failures with remediation

## Examples

1. **Quick check**:
   ```text
   /node-team:preflight
   ```

2. **Check with remediation guidance**:
   ```text
   /node-team:preflight --fix
   ```

## Arguments

- `--fix`: Show remediation steps for each failing check. Optional.
