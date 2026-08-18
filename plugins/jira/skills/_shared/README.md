# Shared Jira Skills Logic

This directory contains common validation and execution logic shared across multiple Jira creation skills (`create`, `create-jira-from-file`, etc.).

## Files

- **`validation-common.md`** — Security credential scanning, summary validation, parent hierarchy checks, component/version validation
- **`execution-common.md`** — Universal defaults, custom field ID resolution, MCP error handling patterns, jira-conventions invocation

## Usage

Skills include these files via reference in their SKILL.md:

```markdown
## Phase 4: Validate

**Load and follow:** [`../_shared/validation-common.md`](../_shared/validation-common.md)
```

## Maintenance

When updating validation or execution logic that applies to ALL Jira creation workflows, update the shared files here. Skill-specific logic (CLI parsing, file ingestion, batch handling) stays in the individual skill directories.
