# Bug

Type-specific guidance for creating Jira bug reports.

## Summary Guidelines

Concise (one sentence), identifies the problem clearly, avoids vague terms.

- Good: "API server returns 500 error when creating namespaces"
- Bad: "Things are broken"

## Bug Description Template

```plaintext
Description of problem:
<Clear, detailed description of the issue>

Version-Release number of selected component (if applicable):
<e.g., 4.21.0, openshift-client-4.20.5>

How reproducible:
<Always | Sometimes | Rarely>

Steps to Reproduce:
1. <First step - be specific>
2. <Second step>
3. <Third step>

Actual results:
<What actually happens - include error messages>

Expected results:
<What should happen instead>

Additional info:
<Logs, screenshots, stack traces, related issues, workarounds>
```

## Interactive Workflow

### 1. Problem Description

**Prompt:** "What is the problem? Describe it clearly and in detail."

Include: context (what you were trying to do), component/feature affected, impact (who, severity).

### 2. Version Information

**Prompt:** "Which version exhibits this issue? (e.g., 4.21.0, 4.20.5)"

Use project default if not provided.

### 3. Reproducibility

**Prompt:** "How reproducible is this issue?"

- **Always** — every time following the steps
- **Sometimes** — intermittent (may be timing/race condition)
- **Rarely** — hard to reproduce

### 4. Steps to Reproduce

**Prompt:** "What are the exact steps to reproduce? Be specific."

Guidelines: number each step, use exact commands, include prerequisites, use code blocks.

### 5. Actual Results

**Prompt:** "What actually happens?"

Include: error messages (full text), symptoms, relevant logs, timing.

### 6. Expected Results

**Prompt:** "What should happen instead?"

Must differ from actual results.

### 7. Additional Information (Optional)

**Prompt:** "Any additional context?"

Helpful: full logs, screenshots, stack traces, related issues, workarounds, environment specifics.

## Version Fields

### OCPBUGS

- **Affects Version/s** (`versions`): version where bug was found — `[{"name": "4.21"}]`
- **Target Version** (`customfield_10855`): version where fix is targeted — `"openshift-4.21"`
- **Never set** Fix Version/s (`fixVersions`)

### General Projects

May only have Affects Version/s. Check project configuration.

## Description Formatting

Use Markdown with `contentFormat: "markdown"`. For reference, see [Markdown for Jira](markdown-for-jira.md).
