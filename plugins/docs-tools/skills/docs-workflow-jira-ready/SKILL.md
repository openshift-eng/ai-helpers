---
name: docs-workflow-jira-ready
description: Check whether a JIRA query returns tickets ready for the docs workflow. Queries JIRA via jira_reader.py, filters out tickets that already have a workflow progress file or a "docs-workflow-started" label, and outputs a JSON list of actionable ticket IDs. Designed as the entry point for cron-triggered or CI-triggered docs-orchestrator runs.
model: claude-haiku-4-5@20251001
argument-hint: --jql <query> [--base-path <path>] [--label <label>] [--dry-run]
allowed-tools: Read, Bash, Glob, Grep
---

# JIRA Ready Check

This skill is a **check-and-return** gate — it does not dispatch the orchestrator. The caller (cron script, CI workflow, or human) decides what to do with the returned ticket list.
Unlike other step skills, this skill does **not** dispatch an agent. 

Gate skill for automated docs-orchestrator runs. Checks JIRA for new tickets matching a query, filters out already-processed tickets, and outputs actionable ticket IDs.

## Arguments

- `--jql <query>` — JQL query string (required). Wrap in quotes.
- `--base-path <path>` — Directory to check for existing progress files (default: `artifacts`)
- `--label <label>` — JIRA label that marks a ticket as already started (default: `docs-workflow-started`)
- `--dry-run` — Show what would be returned without adding labels or side effects (default behavior; included for explicitness)
- `--add-label` — After returning results, add the `--label` value to each returned ticket in JIRA (opt-in, prevents re-processing on next run)
- `--max-results <n>` — Maximum number of JIRA results to fetch (default: 5, passed through to jira_reader.py)

## Environment

Requires `JIRA_API_TOKEN` (or the backward-compatible alias `JIRA_AUTH_TOKEN`) and `JIRA_EMAIL` in the environment. `jira-ready-check.sh` loads `~/.env` then `<project-root>/.env` using a safe key/value parser (no shell execution). Both variables are validated before any API calls.

## Execution

Run the check script:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/jira-ready-check.sh \
  --jql "project=PROJ AND labels=docs-needed AND labels != docs-workflow-started" \
  --base-path artifacts \
  --label docs-workflow-started
```

The script:

1. Queries JIRA using `jira_reader.py --jql` (fast summary mode)
2. For each returned ticket, checks whether a workflow progress file already exists at `<base-path>/<ticket-lower>/workflow/*.json`
3. Outputs a JSON array of ticket IDs that pass the filter (label exclusion is handled by the JQL query itself)

### Output format

```json
{
  "query": "project=PROJ AND labels=docs-needed AND labels != docs-workflow-started",
  "total_matched": 5,
  "filtered_out": 2,
  "ready": [
    "PROJ-101",
    "PROJ-204",
    "PROJ-317"
  ],
  "filtered": {
    "PROJ-102": "progress_file_exists",
    "PROJ-199": "progress_file_exists"
  }
}
```

### With `--add-label`

When `--add-label` is passed, the script adds the tracking label to each ticket in the `ready` list via the JIRA REST API after outputting results. This prevents the same tickets from appearing on the next cron run.

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/jira-ready-check.sh \
  --jql "project=PROJ AND labels=docs-needed" \
  --add-label
```
