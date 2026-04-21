---
description: Triage recent Jira activity — surface what needs attention, filter out noise
argument-hint: "[N | --days N] [--no-cache]"
---

## Name
jira:catch-me-up

## Synopsis
```text
/jira:catch-me-up [14] [--days 7] [--no-cache]
```

## Description

Fetches recent activity on Jira issues where you are assignee or watcher, then classifies each event into three tiers: needs attention, unsure, or noise. Uses a map/reduce approach — fast model classifies batches in parallel, then a review pass catches cross-event patterns.

## Prerequisites

- `JIRA_API_TOKEN` and `JIRA_USERNAME` environment variables set
- `uv` ([astral.sh/uv](https://astral.sh/uv)) — the gather script is run via `uv run --with aiohttp`
- `JIRA_URL` defaults to `https://redhat.atlassian.net`

## Implementation

### Step 1: Parse arguments

Default `--days` to 7 if not specified. The user may pass a number directly (e.g., `/jira:catch-me-up 14` means 14 days).

### Step 2: Check subagent permissions

Read `.claude/settings.local.json`. If the file exists, check whether `Read(.work/catch-me-up/**)` is in the `permissions.allow` array.

If present, continue silently.

If missing (or the file doesn't exist), append `Read(.work/catch-me-up/**)` to the `permissions.allow` array. Preserve all existing content — only add this one entry. Tell the user:

> Added `Read(.work/catch-me-up/**)` to `.claude/settings.local.json` — subagents need this to read batch files.

### Step 3: Gather data

Run the data gathering script. Use `uv run` to handle the aiohttp dependency automatically.

```bash
uv run --with aiohttp plugins/jira/skills/catch-me-up/scripts/gather.py --days <N> -v --output-dir .work/catch-me-up/runs
```

If the user passed `--no-cache`, append `--no-cache` to the command above.

Check the output stats. If there are 0 events, tell the user and stop. Read the output file path from stderr.

### Step 4: Split into batches

```bash
python3 plugins/jira/skills/catch-me-up/scripts/split_batches.py .work/catch-me-up/runs/<date>-<days>d/events.json 5
```

This creates batch files and prints a JSON manifest with `batch_files` paths.

### Step 5: Classify batches in parallel

Spawn one Agent per batch file, **all in a single message** so they run in parallel. Use `model: "haiku"` for each agent.

Each agent's prompt must be exactly:

```text
You are classifying Jira activity events for triage. The user is <JIRA_USERNAME> — they are the assignee or watcher on these issues. Any events authored by the user themselves should be tier 3 (noise) since they already know about their own actions.

Read <batch_file_path>. The file contains a batch of events plus a `context` field showing author/field frequency counts and the user's Jira username (`jira_username`).

Classify each event into one of three tiers:

**Tier 1 — Needs attention:** Someone @mentions the user, asks them a question, assigns something to them, raises a blocker on their issue, or posts a substantive comment on their bug. Human priority/severity escalations.

**Tier 2 — Unsure:** Ambiguous — could be signal or noise. Humans doing mechanical/formulaic work, field changes that might imply a decision, bot actions that might carry meaning.

**Tier 3 — Noise:** Mechanical process work, formulaic status updates, link churn, release process bookkeeping, bot-like behavior regardless of actor.

Output ONLY a JSON array. Each element must have exactly these fields:
{
  "tier": 1,
  "date": "2026-04-17",
  "issue_key": "OCPBUGS-12345",
  "title": "the Jira issue title, copied verbatim from the event data",
  "author": "Person Name",
  "summary": "one-line description of what happened and why it's in this tier"
}

List every event. Do not skip, summarize, or group.
```

### Step 6: Collect and merge results

Parse the JSON arrays returned by each agent. Merge into a single list. If any agent returned non-JSON output, try to extract the JSON portion.

Group by tier:
- Count of tier 1, tier 2, tier 3 events
- Sort tier 1 and tier 2 by date descending
- Condense tier 3 into one line per event: `ISSUE-KEY | author | summary` (no full JSON, just scannable text)

### Step 7: Review pass

Spawn a single review Agent with `model: "opus"` to synthesize per-event classifications into per-issue narratives.

```text
You are reviewing classified Jira events. The initial classification was done per-batch, per-event. Your job is to synthesize these into per-issue narratives grouped by tier.

Tier 1 and tier 2 events (full detail):
<paste merged tier 1 and tier 2 as JSON>

Tier 3 events (condensed — scan for false negatives):
<for each tier 3 event, one line: "ISSUE-KEY | author | summary">

Your tasks:
1. Group events by issue key. For each issue, write a summary of what happened and what (if anything) needs the user's action. Default to 1-2 sentences — only go longer when the situation is genuinely complex (e.g., multiple people disagreeing, a subtle root cause, a decision with non-obvious tradeoffs). Omit triage churn, field-change play-by-play, and intermediate states that were superseded. Name people only when the user needs to respond to them specifically.
2. Assign each issue (not event) a tier. An issue is tier 1 if any of its events need the user's attention. An issue is tier 2 if the activity is ambiguous but worth knowing about.
3. Demote to tier 3: authors doing purely mechanical work across many issues, duplicate events (e.g., status change that just echoes a comment), superseded actions (e.g., priority escalation reversed the next day).
4. Promote from tier 3: scan the condensed tier 3 list for events that look like they were wrongly classified as noise — substantive comments, @mentions, or escalations that Haiku missed.

Output JSON:
{
  "tier_1": [
    {
      "issue_key": "OCPBUGS-12345",
      "title": "Jira issue title from the classified events",
      "summary": "What happened and why it matters. 1-2 sentences unless complexity demands more.",
      "action": "One concrete next step."
    }
  ],
  "tier_2": [
    {
      "issue_key": "OCPBUGS-12345",
      "title": "Jira issue title from the classified events",
      "summary": "What happened. 1-2 sentences.",
      "reason": "Why worth a glance"
    }
  ],
  "demoted_to_tier_3": ["OCPBUGS-xxxxx: reason", ...]
}
```

### Step 8: Present results

Display to the user in this format:

```markdown
## Needs your attention (N issues)

### ISSUE-KEY: issue summary
narrative — what happened, who's involved, the arc
→ **Action:** what you should do

### ISSUE-KEY: issue summary
...

## Worth a glance (N issues)

### ISSUE-KEY: issue summary
narrative
→ reason it's ambiguous

## Filtered out (N events across M issues)
  Summary by category, e.g.:
  23 link changes (various contributors)
  12 status transitions
   8 field housekeeping
```

### Step 9: Save classified output

Write the full classification (all three tiers with individual events) to `.work/catch-me-up/runs/<date>-<days>d/classified.json` for later inspection.
