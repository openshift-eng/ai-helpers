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

Run these checks in order and collect results. Checks 1 to 4 are **required**.
Check 5 is **optional** (no Node team plugin needs the `jira` CLI; it is only a
convenience for ad hoc queries). Never print a
token; only test whether it is set.

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

### 3 and 4. Jira API token and connectivity

Shell variables do not persist between Bash tool calls, so resolve the
credentials and test them in a single invocation. The chain is the one from
[jira.md](../skills/node/references/jira.md) (env var, macOS Keychain, Linux
secret-tool for the token; `JIRA_USER`, `JIRA_EMAIL`, Keychain account,
`git config user.email` for the user):

```bash
JIRA_API_TOKEN="${JIRA_API_TOKEN:-$(security find-generic-password -s "JIRA_API_TOKEN" -w 2>/dev/null || secret-tool lookup service redhat key JIRA_API_TOKEN 2>/dev/null)}"
JIRA_USER="${JIRA_USER:-${JIRA_EMAIL:-$(security find-generic-password -s "JIRA_API_TOKEN" -g 2>&1 | grep acct | sed 's/.*="//;s/"//')}}"
JIRA_USER="${JIRA_USER:-$(git config user.email)}"
case "$JIRA_USER" in ""|*@*) ;; *) JIRA_USER="${JIRA_USER}@redhat.com" ;; esac

if [ -n "$JIRA_API_TOKEN" ]; then echo "token: PASS"; else echo "token: FAIL (not found in env, keychain or secret-tool)"; fi
if [ -n "$JIRA_USER" ]; then echo "user: PASS ($JIRA_USER)"; else echo "user: FAIL (set JIRA_USER or JIRA_EMAIL)"; fi

if [ -n "$JIRA_API_TOKEN" ] && [ -n "$JIRA_USER" ]; then
  code=$(printf 'user = "%s:%s"\n' "$JIRA_USER" "$JIRA_API_TOKEN" \
    | curl -s -K - -o /dev/null -w '%{http_code}' \
      "https://redhat.atlassian.net/rest/api/3/myself")
  echo "connectivity: HTTP $code"
else
  echo "connectivity: SKIPPED (no credentials)"
fi
```

- Check 3 passes when both `token` and `user` report PASS.
- Check 4 passes on HTTP 200. Fail: 401 (bad token or wrong user), 403
  (permissions), `000` (connection error), or skipped because check 3 failed.

The credentials go to curl through `-K -` on stdin so the token never shows
up in the process list.

### 5. Jira CLI (`jira`), optional

```bash
jira me
```

- Pass: returns current user info
- Fail: not installed or not configured. This is only a warning: all Node team
  plugins, including `node-cve`, use the Jira REST API through `curl`.

### Summary

Print a table of results:

```text
Check                 Required  Status
-----                 --------  ------
GitHub CLI            yes       PASS
GitHub API            yes       PASS
Jira API token        yes       PASS
Jira API connectivity yes       PASS
Jira CLI              no        PASS (optional)
```

The overall result is PASS when every required check passes. If any check
fails and `--fix` is specified, print the remediation steps for each failure
(e.g., `gh auth login`, how to set `JIRA_API_TOKEN` and `JIRA_USER`). If
`--fix` is not specified, print a hint to re-run with `--fix` for guidance.

Callers that only need part of the environment may ignore unrelated failures:
`/node-team:setup` needs the GitHub checks always and the Jira checks only
with `--ticket`.

## Return Value

- Summary table with pass/fail status for each check
- Overall PASS when all required checks pass, otherwise the list of failures
  (with remediation when `--fix` is given)

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
