---
name: Payload Retest Helper Scripts
description: Helper scripts for analyzing and retesting failed payload CI jobs on pull requests
---

# Payload Retest Helper Scripts

This skill provides bash scripts that power the `/ci:payload-retest` command. These scripts fetch and analyze payload job failures from OpenShift-specific payload test runs.

## When to Use This Skill

This skill is automatically invoked by the `/ci:payload-retest` command. You typically don't need to call these scripts directly.

## Components

### 1. `payload-retest.sh`
Interactive script that:
- Searches PR comments for payload run URLs
- Downloads all payload run pages in parallel
- Identifies the most recent run by Created timestamp
- Parses failed, successful, and running jobs
- Tracks consecutive failures across multiple runs
- Presents interactive options to retest selected or all failed jobs
- Posts `/payload-job <job-name>` comments to GitHub

**Usage:**
```bash
./payload-retest.sh [repo] <pr-number>
```

### 2. `fetch-payload-data.sh`
Non-interactive data fetching script that:
- Fetches payload URLs from PR comments
- Downloads and parses payload run pages
- Outputs structured JSON with failed and running jobs
- Used by the command implementation for data collection

**Usage:**
```bash
./fetch-payload-data.sh [repo] <pr-number>
```

**Output Format:**
```json
{
  "repo": "org/repo",
  "pr_number": 123,
  "payload_runs": 2,
  "failed_jobs": [
    {
      "name": "periodic-ci-job-name",
      "consecutive": 3
    }
  ],
  "running_jobs": ["periodic-ci-job-name"]
}
```

## Implementation Details

### HTML Parsing
The scripts parse pr-payload-tests dashboard HTML to extract job statuses. The HTML structure assumptions are documented in the code:
- Failed jobs: `<span class="text-danger">job-name</span>`
- Success jobs: `<span class="text-success">job-name</span>`
- Running jobs: `<span class="">job-name</span>`
- Job names start with: `periodic-ci-`

**Validation:** If no jobs are found but payload runs exist, the script warns that HTML structure may have changed.

### Parallel Fetching
Multiple payload run pages are downloaded in parallel using background processes for performance.

### Consecutive Failure Tracking
The script tracks job status across multiple payload runs:
1. Sorts all job entries by timestamp (newest first)
2. For each unique job, identifies most recent status
3. Counts consecutive failures from most recent backward
4. Stops counting at first non-failure result

### JSON Construction
Scripts use `jq` for safe JSON construction to handle special characters in job names and prevent injection issues.

### Error Handling
- Validates `gh pr view` succeeds before parsing
- Checks that payload URLs are found
- Provides clear error messages on failure
- Gracefully exits if no payload runs exist for PR

## Prerequisites

- `gh` CLI (GitHub CLI)
- `jq` (JSON processor)
- `curl`
- Authenticated with GitHub (`gh auth login`)

## Repository Detection

Scripts accept repository in multiple formats:
- **No argument**: Auto-detect from current directory's git remote
- **Repo name only**: Assumes `openshift/<repo>` (e.g., `ovn-kubernetes` → `openshift/ovn-kubernetes`)
- **Full org/repo**: Use any GitHub repository (e.g., `openshift/origin`)

## Notes

- Payload jobs are OpenShift-specific and may not exist for all PRs
- Command gracefully exits if no payload runs found
- Analyzes ALL payload runs to track job history across multiple runs
- Handles jobs that don't appear in every run
