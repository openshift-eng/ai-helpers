---
name: docs-workflow-create-jira
description: Create a linked JIRA ticket for documentation work. No agent dispatch. Uses direct JIRA REST API calls via a shell script. Checks for existing links, handles public/private project visibility, converts markdown to JIRA wiki markup.
model: claude-haiku-4-5@20251001
argument-hint: <ticket> --base-path <path> --project <PROJECT>
allowed-tools: Read, Write, Bash
---

# Create JIRA Step

Step skill for the docs-orchestrator pipeline. Follows the step skill contract: **parse args → do work → write output**.

Unlike other step skills, this skill does **not** dispatch an agent. It runs `scripts/create-jira-ticket.sh` directly.

**Output**: `null` (produces a JIRA URL, not a file)

## Arguments

- `$1` — Parent JIRA ticket ID (required)
- `--base-path <path>` — Base output path (e.g., `.agent_workspace/proj-123`)
- `--project <PROJECT>` — Target JIRA project key for the new ticket (required)

## Input

```
<base-path>/planning/plan.md
```

## Environment

Requires `JIRA_API_TOKEN` (or the backward-compatible alias `JIRA_AUTH_TOKEN`) and `JIRA_EMAIL` in the environment. `create-jira-ticket.sh` sources `~/.env` then `<project-root>/.env`, where the project root is resolved from the `PLAN_FILE` location.

## Execution

Run the create-jira-ticket script:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/create-jira-ticket.sh "$TICKET" "$PROJECT" "${BASE_PATH}/planning/plan.md"
```

The script handles all steps:

1. **Check for existing link** — if a "Document" link already exists on the parent ticket, exits early
2. **Check project visibility** — unauthenticated probe to determine public vs private
3. **Extract description** — pulls JTBD sections from the plan, appends dated footer
4. **Convert to JIRA wiki markup** — calls `scripts/md2wiki.py` for markdown → wiki conversion
5. **Create JIRA ticket** — POST to JIRA REST API with `[ccs] Docs -` prefix
6. **Link to parent** — creates a "Document" issue link (singular, not "Documents")
7. **Attach plan** — attaches the full plan file (private projects only)

The script prints the JIRA URL on success (e.g., `https://redhat.atlassian.net/browse/DOCS-456`), or a skip message if a linked ticket already exists.

### Write step-result.json

After the script completes, write the sidecar to `${BASE_PATH}/create-jira/step-result.json`:

```bash
mkdir -p "${BASE_PATH}/create-jira"
```

If the script created a new ticket (output contains a JIRA URL like `https://...atlassian.net/browse/DOCS-456`):

```json
{
  "schema_version": 1,
  "step": "create-jira",
  "ticket": "<TICKET>",
  "completed_at": "<current ISO 8601 timestamp>",
  "jira_url": "https://redhat.atlassian.net/browse/DOCS-456",
  "jira_key": "DOCS-456",
  "action": "created",
  "skipped": false,
  "skip_reason": null
}
```

If the script found an existing linked ticket (output contains "already exists"):

```json
{
  "schema_version": 1,
  "step": "create-jira",
  "ticket": "<TICKET>",
  "completed_at": "<current ISO 8601 timestamp>",
  "jira_url": null,
  "jira_key": "<linked-key from output>",
  "action": "found_existing",
  "skipped": false,
  "skip_reason": null
}
```

Extract `jira_key` and `jira_url` from the script's stdout. If the script fails (non-zero exit), write the sidecar with `action: "skipped"`, `skipped: true`, and `skip_reason: "create_failed"`.
