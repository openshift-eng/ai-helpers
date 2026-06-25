# Task

Type-specific guidance for creating Jira tasks for technical and operational work.

## Tasks vs Stories

Use a **Task** when work is:
- **Technical/operational** — infrastructure, refactoring, configuration
- **Not user-facing** — no direct end-user functionality
- **Internal improvement** — code quality, performance, maintenance
- **Enabler work** — supports future stories but isn't user-visible

Use a **Story** when work delivers user-facing functionality expressible as "As a... I want... so that..."

**Decision rule:** "Would an end user notice or care?" Yes → Story. No → Task.

## Summary Guidelines

Use action verbs, identify what's changing:

- Good: "Update autoscaling documentation for 4.21 release"
- Good: "Refactor scaling controller to reduce code duplication"
- Bad: "Do some work on docs" (too vague)
- Bad: "Technical debt" (not specific)

## Description Structure

1. **What** needs to be done — clear statement of the work
2. **Why** it's needed — context or motivation
3. **Acceptance criteria** (optional but recommended) — how to know it's done
4. **Technical details** (if helpful) — specific files, commands, approaches

## Interactive Workflow

### 1. Task Description

**Prompt:** "What work needs to be done? Be specific about what you'll change or update."

### 2. Motivation / Context

**Prompt:** "Why is this task needed? What problem does it solve?"

### 3. Acceptance Criteria (Optional)

**Prompt:** "How will you know this is complete? (Optional: skip if obvious)"

For technical tasks: tests passing, documentation updated, code review completed.

### 4. Parent Link (Optional)

**Prompt:** "Is this task part of a larger story or epic?"

### 5. Technical Details (Optional)

**Prompt:** "Any technical details? (files to change, dependencies, approach)"

## Description Template

```markdown
<What needs to be done>

## Why

<Context, motivation, problem this solves>

## Acceptance Criteria

- <Criterion 1>
- <Criterion 2>

## Technical Details

### Files to Modify
- `path/to/file.go`

### Dependencies
- Must complete after PROJ-100

### Approach
<Suggested implementation approach>
```

For formatting reference, see [Markdown for Jira](markdown-for-jira.md).

## Anti-Patterns

- Vague summaries ("Update stuff", "Fix things") → be specific
- User-facing work as tasks ("Add user dashboard") → should be a Story
- Too large ("Refactor entire codebase") → break into smaller, focused tasks
- No context (empty description) → always explain why and what
