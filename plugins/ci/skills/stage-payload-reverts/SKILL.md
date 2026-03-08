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
  - `originating_payload_tag`: The payload where this suspect PR first caused failures
  - `failing_jobs`: List of `{job_name, prow_url, is_aggregated, underlying_job_name}`

## Prerequisites

1. **GitHub CLI (`gh`)**: Installed and authenticated
2. **JIRA MCP**: Configured for creating TRT issues
3. **Repository Access**: User must have push access to their fork of each target repository

## Implementation Steps

For each qualifying revert candidate, launch a **parallel subagent** (do NOT set the `model` parameter). Each subagent executes three substeps in order:

### Substep 1: Create TRT JIRA Bug (with idempotency check)

**Preflight**: Before creating a new issue, search for an existing TRT bug for this PR:

```
jql: project = TRT AND labels = "trt-incident" AND description ~ "{pr_url}" ORDER BY created DESC
```

Use `mcp__jira__jira_search` with this JQL. If a matching issue is found, reuse its key and URL — skip creation and proceed to Substep 2.

**Create** (only if no existing issue found): Use `mcp__jira__jira_create_issue`:

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

Record the created (or reused) JIRA key and URL.

### Substep 2: Open Revert PR (with idempotency check)

**Preflight**: Before opening a new revert PR, check whether one already exists:

```bash
gh pr list --repo <org>/<repo> --search "revert <pr_number>" --json number,title,url,state --limit 5
```

If an open or draft revert PR is found for this PR number, reuse its URL — skip the revert-pr skill and proceed to Substep 3.

**Create** (only if no existing revert PR found): Load the `revert-pr` skill (`plugins/ci/skills/revert-pr/SKILL.md`) and follow its workflow:

- PR URL: the offending PR
- JIRA ticket: the TRT key from Substep 1
- Context (use `--context`): "This PR is causing blocking job failures ({job names}) in the {stream} {architecture} payload [{payload_tag}]({release_controller_url})."
- Do NOT prompt the user for any input

Record the revert PR URL (created or reused).

### Substep 3: Trigger Payload Jobs and Collect Run URLs

Use the `trigger-payload-job` skill (`plugins/ci/skills/trigger-payload-job/SKILL.md`) to trigger payload validation jobs on the revert PR and collect the resulting URLs. Pass:

- `pr_url`: The revert PR URL from Substep 2
- `jobs`: The `failing_jobs` list for this candidate (includes `job_name`, `is_aggregated`, `underlying_job_name` for each job)

The skill handles idempotency (checking for existing bot replies), correct command selection, polling, and URL extraction.

**IMPORTANT — correct payload command syntax** (read `trigger-payload-job` skill for the full procedure):

- **Non-aggregated jobs**: `/payload-job <full-periodic-job-name>` (e.g., `/payload-job periodic-ci-openshift-release-main-nightly-4.22-e2e-aws-ovn-serial-1of2`)
- **Aggregated jobs**: `/payload-aggregate <underlying-periodic-job-name> <count>` (e.g., `/payload-aggregate periodic-ci-openshift-hypershift-release-4.22-periodics-e2e-aws-ovn-conformance 10`)

Commands must follow these exact formats — no other syntax is accepted.

Record the `payload_test_url` and individual `prow_url`s from the skill's return data.

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
- reused: none|jira|revert_pr|payload_jobs|all
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
- Related Skill: `trigger-payload-job` - Triggers payload jobs and collects URLs (`plugins/ci/skills/trigger-payload-job/SKILL.md`)
- Related Skill: `analyze-payload` - Identifies revert candidates (`plugins/ci/skills/analyze-payload/SKILL.md`)
- Related Command: `/ci:payload-agent` - Autonomous orchestrator that uses this skill (`plugins/ci/commands/payload-agent.md`)
