---
name: Stage Payload Reverts
description: Create TRT JIRA bugs, open revert PRs, and trigger payload jobs for high-confidence revert candidates
---

# Stage Payload Reverts

This skill automates the full revert-staging workflow for payload regressions: creating TRT JIRA bugs, opening revert PRs, and triggering payload validation jobs.

## When to Use This Skill

Use this skill when revert candidates have already been identified with high confidence by the `analyze-payload` skill. The caller passes all required context in-memory — this skill does not perform its own analysis.

**Inputs** (passed in-context by the caller):

- `payload_tag`: The full payload tag being analyzed
- `version`, `stream`, `architecture`: Parsed from the payload tag
- `release_controller_url`: URL to the payload on the release controller
- `revert_candidates`: List of PRs to revert, each with:
  - `pr_url`, `pr_number`, `component`, `confidence_score`, `rationale`
  - `failing_jobs`: List of `{job_name, prow_url, is_aggregated, underlying_job_name}`

## Prerequisites

1. **GitHub CLI (`gh`)**: Installed and authenticated
2. **JIRA MCP**: Configured for creating TRT issues
3. **Repository Access**: User must have push access to their fork of each target repository

## Implementation Steps

For each qualifying revert candidate, launch a **parallel subagent** (Task tool, `subagent_type: "general-purpose"`, do NOT set the `model` parameter). Each subagent executes three substeps in order:

### Substep 1: Create TRT JIRA Bug

Use `mcp__jira__jira_create_issue` to create a TRT bug:

- `project_key`: `"TRT"`
- `issue_type`: `"Bug"`
- `summary`: A concise description of the problem (the symptom, not the solution). Summarize which jobs are failing and the failure mode. For example: `"aws-ovn and aws-ovn-upgrade jobs failing with KAS crashloop in {stream} {architecture} payload"`. Do NOT use "Revert ..." as the summary — the revert is the action, not the problem.
- `description` (Jira wiki markup):
  ```
  h2. Payload Regression

  PR {pr_url} is causing blocking job failures in the {stream} {architecture} payload.

  h2. Evidence

  * Payload: [{payload_tag}|{release_controller_url}]
  * Failing blocking jobs:
  ** [{job_name_1}|{prow_url_1}]
  ** [{job_name_2}|{prow_url_2}]
  * Originating payload: {originating_payload_tag}
  * {rationale}

  h2. Action

  Revert PR {pr_url} to restore payload acceptance.
  ```
- `additional_fields`:
  - `labels`: `["trt-incident", "ai-generated-jira"]`

Record the created JIRA key.

### Substep 2: Open Revert PR

Load the `revert-pr` skill (`plugins/ci/skills/revert-pr/SKILL.md`) and follow its workflow:

- PR URL: the offending PR
- JIRA ticket: the TRT key from Substep 1
- Context (use `--context`): "This PR is causing blocking job failures ({job names}) in the {stream} {architecture} payload [{payload_tag}]({release_controller_url})."
- Do NOT prompt the user for any input

Record the revert PR URL.

### Substep 3: Trigger Payload Jobs and Collect Run URLs

Post a comment on the revert PR with payload test commands for each failing blocking job attributed to this PR. Use the correct command based on whether the job is aggregated:

- **Aggregated jobs** (job name has `aggregated-` prefix): Use `/payload-aggregate <underlying-job-name> <count>`. The underlying job name comes from the caller's analysis data (extracted from the aggregated job's junit artifacts — it cannot be derived from the aggregated job name). Choose a count of up to 10 runs — use judgement based on the total number of jobs being triggered (fewer runs per job when triggering many jobs to limit resource consumption; more runs when only one or two jobs need validation).
- **Non-aggregated jobs**: Use `/payload-job <job-name>`.

```bash
# Example with a mix of aggregated and non-aggregated jobs:
gh pr comment "{revert_pr_url}" --body "/payload-aggregate {underlying_job_name_1} {count}
/payload-job {job_name_2}
..."
```

One command per line for each failing blocking job attributed to this PR.

After posting the comment, wait ~30 seconds and poll for the `openshift-ci[bot]` reply containing the `pr-payload-tests` URL:

```bash
# Poll for the bot reply containing the pr-payload-tests URL
gh api "repos/<org>/<repo>/issues/<pr_number>/comments" \
  --jq '[.[] | select(.user.login == "openshift-ci[bot]" and (.body | contains("pr-payload-tests")))] | last | .body'
```

Extract the `pr-payload-tests.ci.openshift.org/runs/ci/<uuid>` URL from the reply. This URL is the primary endpoint for checking job completion status (the page shows "AllJobsFinished" when done).

Fetch the pr-payload-tests page to extract the actual prow job URL(s):

```bash
# The page contains prow job links like:
# https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job-slug>/<build-id>
```

Record both the `payload_test_url` and individual `prow_url`s in the return data.

## Subagent Return Format

Each subagent should return its results in this format:

```
STAGED_REVERT_RESULT:
- original_pr_url: ...
- original_pr_number: ...
- component: ...
- jira_key: TRT-XXXX
- jira_url: https://issues.redhat.com/browse/TRT-XXXX
- revert_pr_url: https://github.com/org/repo/pull/YYYY
- payload_test_url: https://pr-payload-tests.ci.openshift.org/runs/ci/...
- payload_jobs_triggered: job1, job2, ...
- status: success|partial|failed
- error: none|description
```

Collect all subagent results. Return to the caller for inclusion in the report.

## Error Handling

- If JIRA creation fails, continue with the revert PR and note the error.
- If the revert PR fails (e.g., merge conflicts), record the error and skip payload job triggering for that candidate.
- If payload job triggering fails, record the error but keep the JIRA and revert PR.
- Do not let one failed candidate block processing of others.

## See Also

- Related Skill: `revert-pr` - The git revert workflow (`plugins/ci/skills/revert-pr/SKILL.md`)
- Related Skill: `analyze-payload` - Identifies revert candidates (`plugins/ci/skills/analyze-payload/SKILL.md`)
- Related Command: `/ci:payload-agent` - Autonomous orchestrator that uses this skill (`plugins/ci/commands/payload-agent.md`)
