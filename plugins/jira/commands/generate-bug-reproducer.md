---
description: Generate bug reproduction steps from a JIRA issue and fix PR analysis
argument-hint: [JIRA issue key] [GitHub PR URLs]
---

## Name
jira:generate-bug-reproducer

## Synopsis
```
/jira:generate-bug-reproducer [JIRA issue key] [GitHub PR URLs]
```

## Description

The `jira:generate-bug-reproducer` command analyzes a bug's JIRA description and fix PR code changes to produce a structured reproducer report. The report includes pre-fix reproduction steps (inferred from the PR diff when JIRA lacks them), post-fix verification steps, and a confidence assessment.

This command is an alias for `/jira:generate-test-plan --reproducer`. Both invoke the same **Generate Test Plan** skill in reproducer mode.

Use this command when QE or a developer needs to validate a bug fix without back-and-forth with the PR author or bug reporter.

## Implementation

Invoke the **Generate Test Plan** skill (`plugins/jira/skills/generate-test-plan/SKILL.md`) with:

- **Mode**: `reproducer`
- **JIRA issue key**: `$1`
- **PR URLs**: `$2`, `$3`, ... (optional; auto-discovered from JIRA if omitted)

The skill handles JIRA fetching, PR discovery, diff analysis, report generation, and output presentation.

## Return Value

- **Format**: Markdown report saved to `.work/jira/generate-test-plan/{JIRA_KEY}/reproducer-report.md`
- **Summary**: Bug summary, root cause analysis, pre-fix reproducer steps, post-fix verification, confidence level, and open questions

## Examples

1. **Generate reproducer with auto-discovered PRs**:
   ```
   /jira:generate-bug-reproducer OCPBUGS-12345
   ```

2. **Generate reproducer for specific fix PRs**:
   ```
   /jira:generate-bug-reproducer OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888
   ```

3. **Equivalent using the test-plan command with flag**:
   ```
   /jira:generate-test-plan OCPBUGS-12345 --reproducer
   ```

## Arguments

- **$1**: JIRA issue key (required) — e.g., `OCPBUGS-12345`, `CNTRLPLANE-205`
- **$2, $3, ..., $N**: Optional GitHub PR URLs
  - If provided: only these PRs are analyzed
  - If omitted: PRs linked to the JIRA are discovered automatically
