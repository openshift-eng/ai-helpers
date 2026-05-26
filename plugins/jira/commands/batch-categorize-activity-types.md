---
description: Batch-categorize Jira issues into Activity Types using AI and apply updates via MCP
argument-hint: "<project-key> [--type Epic] [--limit 100] [--jql 'extra filters'] [--dry-run]"
---

## Name
jira:batch-categorize-activity-types

## Synopsis
```bash
/jira:batch-categorize-activity-types <project-key> [--type Epic] [--limit 100] [--jql 'AND status != Closed'] [--dry-run]
```

## Description

Fetches all Jira issues in a project that have no Activity Type set, categorizes each into one of six Sankey capacity allocation categories, validates results, generates a report, and (with user approval) applies the updates back to Jira.

Classification logic is shared with `/jira:categorize-activity-type` via the `categorize-activity-types` skill.

## Implementation

Delegate to the `categorize-activity-types` skill in **batch mode**. The skill handles all phases: gather, classify, validate, report, apply, and iterate.

See [skills/categorize-activity-types/SKILL.md](../skills/categorize-activity-types/SKILL.md) for the full workflow.

If `--dry-run` is set, instruct the skill to skip Phase 4 (apply).

## Arguments

- **$1 - project-key** (required)
  - Jira project key (e.g., OCM, ARO, ROX)

- **--type \<issue-type\>** (optional, default: Epic)
  - Issue type to filter. Supports: Epic, Story, Task, Bug, etc.

- **--limit \<number\>** (optional, default: 100)
  - Maximum number of issues to fetch and classify per batch

- **--jql \<conditions\>** (optional)
  - Additional JQL conditions appended to the base query
  - Example: `'AND resolved >= "2025-01-01"'`
  - Example: `'AND status != Closed'`

- **--dry-run** (optional)
  - Run classification and generate report without applying updates to Jira

## Examples

1. **Classify all Epics in OCM:**
   ```bash
   /jira:batch-categorize-activity-types OCM
   ```

2. **Classify Stories instead of Epics:**
   ```bash
   /jira:batch-categorize-activity-types ARO --type Story
   ```

3. **Add JQL filter:**
   ```bash
   /jira:batch-categorize-activity-types OCM --jql 'AND resolved >= "2025-01-01"'
   ```

4. **Dry run (classify and report, don't apply):**
   ```bash
   /jira:batch-categorize-activity-types ROX --dry-run
   ```

## See Also

- `jira:categorize-activity-type` - Single-issue classification (shares the same classification skill)

## Notes

- **Prerequisites**: `jq` (for validation script), Python 3 (for report generation)
