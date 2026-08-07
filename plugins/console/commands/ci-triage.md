---
description: Triage failing CI on an OpenShift Console PR — classify each failure as PR-related or unrelated
argument-hint: "[PR-number]"
---

## Name
console:ci-triage

## Synopsis
```text
/console:ci-triage [PR-number]
```

## Description
Triage CI failures on an OpenShift Console PR. Fetches Prow job logs, extracts specific error messages, cross-references them against the PR's changed files, and classifies each failure as PR-related or unrelated.

This command is designed for **OpenShift Console** contributors who need to understand why CI is red on their PR and what they need to fix versus what they can `/retest`.

The output is an actionable triage table — not raw logs. After the report, the user decides what to fix; this command does not attempt fixes itself.

## Implementation
- Load the "ci-triage" skill
- Proceed with the triage by following the implementation steps from the skill

The skill handles all the implementation details including:
- PR detection (from argument, branch, or worktree name)
- Fetching CI check status and openshift-ci bot comments
- Fetching Prow job artifacts (junit XML, build logs)
- Cross-referencing errors against the PR's changed files
- Classifying each failure with Console-specific pattern knowledge

## Return Value
- **Format**: Structured Markdown triage table
- **Columns**: CI Job, Required?, Error Type, Error Summary, PR-Related?, Reasoning
- **Sections**: Fix priority, common root causes, unrelated failures summary

## Examples

1. **Triage by PR number**:
   ```
   /console:ci-triage 16269
   ```

2. **Auto-detect PR from current branch**:
   ```
   /console:ci-triage
   ```

3. **From a worktree named `pr-16269`**:
   ```
   /console:ci-triage
   ```

## Arguments
- `$1`: PR number (optional) — if omitted, detected from the current branch or worktree name
