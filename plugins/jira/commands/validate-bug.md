---
description: Diagnose and fix jira/invalid-bug on PRs — runs the same 7 checks as the jira-lifecycle-plugin
argument-hint: "<PR-URL | PR-number | JIRA-key> [--branch release-4.X]"
---

## Name
jira:validate-bug

## Synopsis
```bash
/jira:validate-bug <PR-URL | PR-number | JIRA-key> [--branch release-4.X]
```

## Description
The `jira:validate-bug` command diagnoses why the Prow `jira/invalid-bug` label was applied to a PR. It runs the same 7 validation checks as the [jira-lifecycle-plugin](https://github.com/openshift-eng/jira-lifecycle-plugin), reports pass/fail for each check, and offers to fix failing checks via JIRA MCP tools.

This command is essential for:
- Diagnosing why a PR is stuck with `jira/invalid-bug`
- Understanding which JIRA fields need correction
- Fixing JIRA bugs in-place without manual field hunting
- Batch-diagnosing multiple blocked PRs

## Key Features

- **7-Check Validation** — Same checks as the Prow plugin: open state, target version, valid status, release notes, dependent bug states, dependent target versions, dependents exist
- **PR-Aware** — Accepts PR URLs/numbers, auto-extracts JIRA key from title and branch context
- **Fix Mode** — After diagnosis, offers to fix failing checks via JIRA MCP tools
- **Branch-Aware** — Computes expected target version and dependent version from the PR's base branch

## Implementation

For detailed implementation guidance, see the [validate-bug skill](../skills/validate-bug/SKILL.md).

### High-Level Workflow

1. **Resolve Input** — Parse PR URL/number or JIRA key. Extract JIRA key from PR title and target branch via `gh pr view`.
2. **Gather Data** — Fetch the JIRA bug with all fields via MCP. Follow issue links to find dependent bugs.
3. **Validate** — Run all 7 checks against the branch-specific expected values. Produce a pass/fail results table.
4. **Report** — Render results matching the jira-lifecycle-plugin bot comment format, with fix instructions for each failure.
5. **Offer Fixes** — List fixable failures, ask for confirmation, then apply fixes via MCP tools.

## Usage Examples

### From PR URL
```bash
/jira:validate-bug https://github.com/openshift/hypershift/pull/8811
```

### From PR number (in a repo context)
```bash
/jira:validate-bug 8811
```

### From JIRA key with branch
```bash
/jira:validate-bug OCPBUGS-85778 --branch release-4.20
```

## Arguments

### Core Arguments

- **$1 — input** *(required)*
  PR URL, PR number, or JIRA issue key.
  - PR URL: `https://github.com/{org}/{repo}/pull/{number}`
  - PR number: plain integer (requires current directory to be inside a git repo)
  - JIRA key: `OCPBUGS-12345`, `DFBUGS-456`, `PROJQUAY-789`

- **--branch** *(optional)*
  Target branch override. Required when input is a JIRA key (no PR context). Format: `release-4.X`, `main`, or `master`.

## Output Format

```text
Validating OCPBUGS-85778 against branch release-4.20...

| # | Check                        | Expected              | Actual           | Result |
|---|------------------------------|-----------------------|------------------|--------|
| 1 | Bug is open                  | Open                  | Open             | PASS   |
| 2 | Target version               | 4.20.z                | 5.0              | FAIL   |
| 3 | Valid state                  | NEW/ASSIGNED/POST     | Verified         | FAIL   |
| 4 | Release notes                | Set (not template)    | Not set          | FAIL   |
| 5 | Dependent bug states         | VERIFIED/CLOSED/...   | —                | SKIP   |
| 6 | Dependent bug target version | 4.21.0 or 4.21.z     | —                | SKIP   |
| 7 | Dependents exist             | At least one          | None             | FAIL   |

Failures:
1. Target version: Set to 4.20.z (current: 5.0)
2. Status: Transition to NEW, ASSIGNED, or POST (current: Verified)
3. Release notes: Set release note text (current: empty)
4. Dependents: Create or link a dependent bug targeting 4.21.0 or 4.21.z

Fix 4 issues? [y/N]
```

## Prerequisites

- `gh` CLI authenticated with GitHub
- Jira MCP server configured (Atlassian Rovo MCP)
- Read access to JIRA (for diagnosis)
- Write access to JIRA (for fix mode)

## Return Value

- **Markdown Report**: Validation results table with fix instructions
- On fix: updated JIRA fields, confirmation to run `/jira refresh` on the PR
