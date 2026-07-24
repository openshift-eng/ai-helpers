---
name: create-jira-from-file
description: Create Jira issues from a markdown file (project-agnostic)
argument-hint: "<path-to-markdown-file>"
---

## Name

create-jira-from-file - Create Jira issues from a markdown file

## Synopsis

```bash
/jira:create-jira-from-file <path-to-markdown-file>
```

## Description

Create one or more Jira issues from a markdown file. Required metadata (project key) and any optional fields (component, version, type, parent) must be specified in the markdown file itself. Issue type can be set explicitly or auto-detected from content.

### Required Metadata

Each issue must specify:
- `**Project:** <project-key>` — REQUIRED

### Strongly Recommended Metadata

- `**Type:** <issue-type>` — Story, Bug, Task, Epic, Feature, Initiative, or Sub-task. If omitted, the skill auto-detects from content patterns and confirms with the user when ambiguous.

### Optional Metadata

- `**Component:** <component-name>`
- `**Version:** <version>`
- `**Parent:** <parent-issue-key>`
- `**Priority:** <priority-name>`
- `**Labels:** <label1>, <label2>`

## Examples

### Single Issue

```bash
/jira:create-jira-from-file feature-spec.md
```

### Batch Mode

```bash
/jira:create-jira-from-file sprint-planning.md
```

## Markdown Format

### Single Issue Example

```markdown
# Enable autoscaling for clusters

**Project:** PLATFORM
**Type:** Story
**Component:** Infrastructure
**Version:** 2.5

As a cluster admin, I want to configure autoscaling, so that I can handle traffic spikes.

## Acceptance Criteria
- [ ] Scales up when CPU > 80%
- [ ] Scales down when CPU < 30%
```

### Batch Mode Example

```markdown
## Story: Add user dashboard
**Project:** FRONTEND
**Component:** Console

As a developer, I want a dashboard to monitor applications.

### Acceptance Criteria
- [ ] Shows running pods

---

## Bug: API returns 500 error
**Project:** BACKEND
**Priority:** High

Description: API crashes on special characters.

Steps to Reproduce:
1. Create resource with special chars
2. Observe 500 error

Expected: 400 with validation error
```

## Features

- **Project-agnostic:** Works with any Jira project
- **Batch processing:** Create multiple issues from one file
- **Security scanning:** Detects and blocks credential exposure
- **Type auto-detection:** Infers issue type from content patterns
- **Parent linking:** Validates and links parent-child relationships
- **Error handling:** Reports missing components and versions with suggestions, logs permission errors, and continues batch processing on per-issue failures

## Notes

- The skill makes no assumptions about projects or components
- Metadata should be provided in the markdown file; missing required fields are prompted interactively
- Batch mode is auto-detected from file structure (multiple type-prefixed or non-content H2 headers; `---` alone is not enough)

## Arguments

- **path-to-markdown-file** (required): Path to the markdown file containing Jira issue definitions
  - File must contain issue metadata fields (**Project**, **Type**, etc.)
  - Can contain single issue or multiple issues (for batch processing)
  - Example: `feature-spec.md`, `sprint-planning.md`

Invokes the `create-jira-from-file` skill.
