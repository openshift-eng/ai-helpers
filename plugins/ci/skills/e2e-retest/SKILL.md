---
name: E2E Retest Helper Scripts
description: Helper scripts for analyzing and retesting failed e2e CI jobs on pull requests
---

# E2E Retest Helper Scripts

This skill provides bash scripts that power the `/ci:e2e-retest` command. These scripts fetch and analyze e2e job failures from GitHub PR status checks and prow history.

## When to Use This Skill

This skill is automatically invoked by the `/ci:e2e-retest` command. You typically don't need to call these scripts directly.

## Components

### 1. `e2e-retest.sh`
Interactive script that:
- Fetches PR status checks and prow history in parallel
- Parses failed and running e2e jobs
- Counts consecutive failures and recent job statistics
- Presents interactive options to retest selected or all failed jobs
- Posts `/test <job-name>` comments to GitHub

**Usage:**
```bash
./e2e-retest.sh [repo] <pr-number>
```

### 2. `fetch-e2e-data.sh`
Non-interactive data fetching script that:
- Fetches PR status and prow history
- Outputs structured JSON with failed and running jobs
- Used by the command implementation for data collection

**Usage:**
```bash
./fetch-e2e-data.sh [repo] <pr-number>
```

**Output Format:**
```json
{
  "repo": "org/repo",
  "pr_number": 123,
  "failed_jobs": [
    {
      "name": "job-name",
      "consecutive": 3,
      "fail": 5,
      "pass": 2,
      "abort": 1
    }
  ],
  "running_jobs": ["job-name"]
}
```

### 3. `common.sh`
Shared utility functions:
- `count_consecutive_failures()`: Parses prow history HTML to count consecutive failures and total run statistics

**Note:** This file must be sourced by other scripts: `source "$(dirname "$0")/common.sh"`

## Implementation Details

### HTML Parsing
The scripts parse prow history HTML to extract job run statuses. The HTML structure assumptions are documented in the code:
- Job rows: `>${job_name}<`
- Run status classes: `run-success`, `run-failure`, `run-aborted`, `run-pending`

If prow HTML structure changes, these patterns may need updating.

### JSON Construction
Scripts use `jq` for safe JSON construction to handle special characters in job names and prevent injection issues.

### Error Handling
- Validates `gh pr view` succeeds before parsing
- Checks that fetched files are non-empty
- Provides clear error messages on failure

## Prerequisites

- `gh` CLI (GitHub CLI)
- `jq` (JSON processor)
- `curl`
- Authenticated with GitHub (`gh auth login`)

## Repository Detection

Scripts accept repository in multiple formats:
- **No argument**: Auto-detect from current directory's git remote
- **Repo name only**: Assumes `openshift/<repo>` (e.g., `origin` → `openshift/origin`)
- **Full org/repo**: Use any GitHub repository (e.g., `openshift/origin`)
