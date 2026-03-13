---
name: Stage Payload Reverts
description: Create TRT JIRA bugs, open revert PRs, and trigger payload jobs for high-confidence revert candidates
---

# Stage Payload Reverts

This skill automates the full revert-staging workflow for payload regressions: creating TRT JIRA bugs, opening revert PRs, and triggering payload validation jobs.

## When to Use This Skill

Use this skill when revert candidates have already been identified with high confidence by the `analyze-payload` skill. The caller passes all required context in-memory — this skill does not perform its own analysis.

**Inputs** (passed in-context by the caller):

- `results_yaml_path`: Path to the payload results YAML file (e.g., `./payload-results-{tag}.yaml`)
- `payload_tag`: The full payload tag being analyzed
- `version`, `stream`, `architecture`: Parsed from the payload tag
- `release_controller_url`: URL to the payload on the release controller
- `revert_candidates`: List of PRs to revert, each with:
  - `pr_url`, `pr_number`, `component`, `confidence_score`, `rationale`
  - `originating_payload_tag`: The payload where this candidate PR first caused failures
  - `failing_jobs`: List of `{job_name, prow_url, is_aggregated, underlying_job_name}`

## Required Skills

Before starting, you **MUST** load the following skills (they define output schemas used when updating results):

1. **`payload-results-yaml`** — schema for the payload results YAML file
2. **`payload-autodl-json`** — schema for the autodl JSON data file

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

See the `trigger-payload-job` skill for exact command syntax. The skill enforces format requirements.

Record the `payload_test_url` and individual `prow_url`s from the skill's return data.

## Subagent Return Format

Each subagent should use the `payload-results-yaml` skill to update the results YAML, then return a brief status summary (success/partial/failed with any error descriptions) for the caller to print.

Collect all subagent results.

### Update Payload Results YAML

After all subagents complete, use the `payload-results-yaml` skill to append an action to each processed candidate's `actions` array in the results file at `results_yaml_path`:

- `type`: `"revert"`
- `status`: `"staged"` (or `"failed"` if the revert PR could not be created)
- `revert_pr_url`, `revert_pr_state`, `jira_key`, `jira_url`, `result_summary`, `payload_jobs`

See the `payload-results-yaml` skill for the full schema.

### Update HTML Report

After updating the results YAML, update the HTML report (`payload-analysis-{sanitized_tag}-summary.html` in the current working directory) to include links to the staged reverts.

Find the existing "Recommended Reverts" section in the HTML. For each candidate that was successfully staged, add a new row to the table or update the existing row to include:

- **Revert PR**: Link to the revert PR (e.g., `<a href="{revert_pr_url}">#{revert_pr_number}</a>`)
- **JIRA**: Link to the TRT issue (e.g., `<a href="{jira_url}">{jira_key}</a>`)
- **Payload Jobs**: Link to the pr-payload-tests URL (e.g., `<a href="{payload_test_url}">Payload Test</a>`)
- **Status**: Badge showing `Revert Staged` (use the `badge-rejected` class for visual consistency)

If the report has no "Recommended Reverts" section (all candidates scored below 85 during analysis), add one before the per-job details section, using the same HTML structure as described in `analyze-payload` Step 7.4.

### Update autodl JSON

After updating the HTML report, use the `payload-autodl-json` skill's "Update Revert Status" operation to update the autodl JSON file for each candidate that was successfully staged.

Return results to the caller for inclusion in the report.

## Error Handling

- If JIRA creation fails, continue with the revert PR and note the error.
- If the revert PR fails (e.g., merge conflicts), record the error and skip payload job triggering for that candidate.
- If payload job triggering fails, record the error but keep the JIRA and revert PR.
- Do not let one failed candidate block processing of others.

## See Also

- Related Skill: `payload-results-yaml` - Schema and operations for the payload results YAML
- Related Skill: `revert-pr` - The git revert workflow (`plugins/ci/skills/revert-pr/SKILL.md`)
- Related Skill: `trigger-payload-job` - Triggers payload jobs and collects URLs (`plugins/ci/skills/trigger-payload-job/SKILL.md`)
- Related Skill: `analyze-payload` - Identifies revert candidates (`plugins/ci/skills/analyze-payload/SKILL.md`)
- Related Command: `/ci:payload-revert` - Command for staging reverts (`plugins/ci/commands/payload-revert.md`)
