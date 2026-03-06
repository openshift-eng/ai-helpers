---
description: Investigate a failing CI job, file a Jira bug, and open a PR to fix it
argument-hint: "<job-name> <release>"
---

## Name

ci:fix-job

## Synopsis

```
/ci:fix-job <job-name> <release>
```

## Description

The `ci:fix-job` command is the action-oriented counterpart to `investigate-job`. It investigates a failing job, searches Jira for existing bugs, files a new OCPBUGS issue if needed, and attempts to create a fix PR for High and Medium fixability issues.

This command ties investigation to action -- it answers "what's wrong and what can we do about it?"

### Key Features

- **Full investigation**: Runs `investigate-job` first to understand the failure
- **Jira deduplication**: Searches OCPBUGS for existing bugs before filing new ones
- **Smart bug filing**: Creates well-structured OCPBUGS with impact data, root cause, and proposed fix
- **Automated fixes**: For High/Medium fixability issues, clones the component repo and attempts a fix
- **PR creation**: Opens PRs with descriptive commit messages and links to Jira bugs

## Implementation

Load the "Fix Job" skill and follow its implementation steps.

## Return Value

- **Format**: Summary of actions taken
- **Contents**:
  - Investigation result (from `investigate-job`)
  - Jira search results (existing bugs found or new bug filed)
  - Fix attempt result (PR opened, or "manual fix needed" with guidance)
  - Links to all created artifacts (Jira bugs, PRs)

## Examples

1. **Investigate and fix a failing job**:
   ```
   /ci:fix-job periodic-ci-openshift-release-main-nightly-4.22-e2e-vsphere-ovn-techpreview 4.22
   ```

2. **Fix a metal installation failure**:
   ```
   /ci:fix-job periodic-ci-openshift-release-main-nightly-4.22-e2e-metal-ipi-ovn-ipv6 4.22
   ```

## Arguments

- $1: Full Prow job name (required)
- $2: OpenShift release version (required, e.g., "4.22")

## Skills Used

- `fix-job`: Orchestrates the fix workflow
- `investigate-job`: Deep investigation of the failing job
- Jira MCP tools: Search and create OCPBUGS issues
- GitHub CLI (`gh`): Clone repos, create PRs
