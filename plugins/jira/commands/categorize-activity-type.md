---
description: Categorize JIRA tickets into activity types using AI
argument-hint: <issue-key> [--auto-apply]
---

## Name
jira:categorize-activity-type

## Synopsis
```bash
/jira:categorize-activity-type <issue-key> [--auto-apply]
```

## Description

Analyzes a single JIRA ticket and assigns an Activity Type category based on ticket content, issue type, labels, and parent context. Classification logic is shared with `/jira:batch-categorize-activity-types` via the `categorize-activity-types` skill.

## Implementation

### Phase 1: Fetch Ticket Data

Use MCP to fetch the issue by key. Delegate to the `categorize-activity-types` skill in **single-issue mode**.

See [skills/categorize-activity-types/SKILL.md](../skills/categorize-activity-types/SKILL.md) for the full classification methodology, including fields to fetch, classification rules, validation, and reporting.

### Phase 2: Apply Update (Conditional)

**Auto-apply logic:**

- If `--auto-apply` flag present AND confidence is **High**:
  - Automatically update Activity Type field
  - Display confirmation to user

- Otherwise (no flag OR confidence is Medium/Low):
  - Present suggestion to user
  - Ask for confirmation before applying
  - If user confirms, proceed with update
  - If user declines, exit without changes

## Arguments

- **$1 - issue-key** (required)
  - JIRA issue key to categorize
  - Format: PROJECT-NUMBER (e.g., ROX-12345, OCPBUGS-67890)

- **--auto-apply** (optional)
  - Automatically apply Activity Type when confidence is High
  - Without this flag, always prompts user for confirmation
  - Medium/Low confidence always requires manual confirmation

## Examples

1. **Basic categorization (manual confirmation):**
   ```bash
   /jira:categorize-activity-type ROX-12345
   ```

2. **Auto-apply for high confidence:**
   ```bash
   /jira:categorize-activity-type ROX-12345 --auto-apply
   ```

3. **Process security vulnerability:**
   ```bash
   /jira:categorize-activity-type ROX-28072 --auto-apply
   ```
   Expected: Issue Type = Vulnerability -> "Security & Compliance" (High confidence, auto-applied)

## See Also

- `jira:batch-categorize-activity-types` - Batch classification (shares the same classification skill)
