---
name: Trigger Payload Job
description: Trigger payload validation jobs on a PR and collect the resulting Prow job URLs
---

# Trigger Payload Job

This skill triggers payload validation jobs on a GitHub PR by posting the correct Prow commands as PR comments, then polls for the bot response to collect the resulting job URLs.

## When to Use This Skill

Use this skill whenever you need to trigger payload testing on a PR (revert PR, draft bisect PR, or any PR that needs payload validation). It handles the differences between aggregated and non-aggregated jobs and collects the resulting URLs for downstream tracking.

**Inputs** (passed in-context by the caller):

- `pr_url`: The GitHub PR URL to trigger jobs on (e.g., `https://github.com/openshift/ovn-kubernetes/pull/3040`)
- `org`, `repo`, `pr_number`: Parsed from the PR URL
- `jobs`: List of jobs to trigger, each with:
  - `job_name`: The full job name (e.g., `aggregated-hypershift-ovn-conformance-4.22`)
  - `is_aggregated`: Whether this is an aggregated job (has `aggregated-` prefix)
  - `underlying_job_name`: For aggregated jobs only — the underlying periodic job name (e.g., `periodic-ci-openshift-hypershift-release-4.22-periodics-e2e-aws-ovn-conformance`). This MUST be extracted from the aggregated job's junit artifacts by the caller's analysis — it cannot be derived from the aggregated job name.
  - `count`: For aggregated jobs only — how many runs (default: 10). Use judgement: fewer runs when triggering many jobs to limit resource consumption, more when only one or two jobs need validation.

## Prerequisites

1. **GitHub CLI (`gh`)**: Installed and authenticated
2. **Repository Access**: User must have permission to comment on the PR

## Job Triggering Limits

The caller (typically `payload-agent`) is responsible for enforcing global limits before invoking this skill. However, this skill also enforces the following hard limits per invocation:

- **Non-aggregated jobs**: No more than 5 per comment
- **Aggregated jobs**: No more than 1 per comment. Aggregated jobs are expensive (they run many iterations), so only trigger one at a time. A second aggregated job should only be triggered after the first completes, and only if confirmation is needed.

If the `jobs` input exceeds these limits, trigger only the allowed number (prioritizing by the order provided) and return the remainder as `skipped` in the return format.

## Implementation Steps

### Step 1: Idempotency Check

Before posting new payload commands, check whether jobs were already triggered on this PR:

```bash
gh api "repos/<org>/<repo>/issues/<pr_number>/comments?per_page=100&sort=created&direction=desc" \
  --jq '[.[] | select(.user.login == "openshift-ci[bot]" and (.body | contains("pr-payload-tests")))] | .[0] | .body'
```

If a `pr-payload-tests.ci.openshift.org/runs/ci/<uuid>` URL is found, reuse it — skip to Step 3 to extract prow job URLs from that page.

### Step 2: Post Payload Commands

First, validate each job entry. If any job has `is_aggregated == true` but `underlying_job_name` is empty or null, skip that job and return an error for it — do NOT post a comment with an incomplete command.

Build the comment body with one command per line. Use the correct command for each job type:

- **Aggregated jobs** (`is_aggregated == true`): `/payload-aggregate <underlying_job_name> <count>`
- **Non-aggregated jobs** (`is_aggregated == false`): `/payload-job <job_name>`

```bash
gh pr comment "<pr_url>" --body "<commands>"
```

**Example** with a mix of job types:

```bash
gh pr comment "https://github.com/openshift/ovn-kubernetes/pull/3040" --body "/payload-aggregate periodic-ci-openshift-hypershift-release-4.22-periodics-e2e-aws-ovn-conformance 10
/payload-job periodic-ci-openshift-release-main-nightly-4.22-e2e-aws-ovn"
```

**Common mistakes to avoid**:
- Do NOT use `/payload <version> <stream> <filter>` — this triggers a different workflow and does NOT include the PR's changes in the payload
- Do NOT use the aggregated job name with `/payload-job` — aggregated jobs are not directly triggerable; you must use `/payload-aggregate` with the underlying job name
- Do NOT use `/payload-aggregate` for non-aggregated jobs

### Step 3: Poll for Bot Response

After posting the comment, wait ~30 seconds for the `openshift-ci[bot]` to process the commands, then poll for its reply:

```bash
sleep 30
gh api "repos/<org>/<repo>/issues/<pr_number>/comments?per_page=100&sort=created&direction=desc" \
  --jq '[.[] | select(.user.login == "openshift-ci[bot]" and (.body | contains("pr-payload-tests")))] | .[0] | .body'
```

If no reply is found, retry up to 3 times with 30-second intervals. If still no reply after ~2 minutes, record the comment URL and note that manual checking is required.

### Step 4: Extract URLs

From the bot reply, extract:

1. **`payload_test_url`**: The `pr-payload-tests.ci.openshift.org/runs/ci/<uuid>` URL. This is the primary endpoint for checking overall job completion status — the page shows "AllJobsFinished" when all triggered jobs have completed.

2. **Individual prow job URLs**: Fetch the `payload_test_url` page and extract prow job links:

```bash
curl -sL "<payload_test_url>" | grep -oE 'https://prow\.ci\.openshift\.org/view/gs/test-platform-results/logs/[^"]+' | sort -u
```

Each prow URL corresponds to one triggered job run.

## Return Format

Return the collected data in this format:

```
PAYLOAD_JOB_RESULT:
- pr_url: <the PR URL>
- comment_url: <URL of the comment posted>
- payload_test_url: <pr-payload-tests URL, or empty if not found>
- prow_jobs:
  - job_name: <job name>
    prow_url: <individual prow URL>
  - ...
- skipped_jobs:
  - job_name: <job name>
    reason: "job trigger limit reached (max 5 non-aggregated, max 1 aggregated per invocation)"
  - ...
- status: triggered|reused|failed
- error: none|<description>
```

## Error Handling

- If the bot never replies, return `status: triggered` with the comment URL so the caller can check manually later.
- If the PR doesn't exist or the user lacks permissions, return `status: failed` with the error message.
- Do not retry indefinitely — 3 poll attempts is the maximum.

## See Also

- Used by: `bisect-payload-suspects` — triggers payload jobs for draft bisect PRs
- Used by: `stage-payload-reverts` — triggers payload jobs for revert PRs
