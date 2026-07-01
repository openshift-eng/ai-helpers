---
description: Generate bug reproduction steps from a JIRA issue and fix PR analysis
argument-hint: [JIRA issue key] [GitHub PR URLs] [--apply]
---

## Name
jira:generate-bug-reproducer

## Synopsis
```
/jira:generate-bug-reproducer [JIRA issue key] [GitHub PR URLs] [--apply]
```

## Description

The `jira:generate-bug-reproducer` command analyzes a bug's JIRA description and fix PR code changes to produce a structured reproducer report. The report includes pre-fix reproduction steps (inferred from the PR diff when JIRA lacks them), post-fix verification steps, and a confidence assessment.

This command is an alias for `/jira:generate-test-plan --reproducer`. Both invoke the same **Generate Test Plan** skill in reproducer mode.

Use this command when QE or a developer needs to validate a bug fix without back-and-forth with the PR author or bug reporter.

Pass `--apply` to execute the reproducer steps against a live OpenShift cluster after generating (or reusing) the report. The agent verifies cluster connectivity, classifies each step as read-only or write, and uses a hybrid confirmation model: one upfront confirmation for all read-only commands, individual confirmation before each write command.

## Implementation

Invoke the **Generate Test Plan** skill (`plugins/jira/skills/generate-test-plan/SKILL.md`) with:

- **Mode**: `reproducer`
- **JIRA issue key**: `$1`
- **PR URLs**: `$2`, `$3`, ... (optional; auto-discovered from JIRA if omitted)
- **Apply mode**: `true` when `--apply` is present, `false` otherwise

The skill handles JIRA fetching, PR discovery, diff analysis, report generation, and output presentation. When `--apply` is set, it also executes the reproducer steps against the connected cluster (see Step 8 in the skill).

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

4. **Generate reproducer and apply to live cluster**:
   ```
   /jira:generate-bug-reproducer OCPBUGS-12345 --apply
   ```

5. **Apply with specific fix PRs**:
   ```
   /jira:generate-bug-reproducer OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888 --apply
   ```

## Arguments

- **$1**: JIRA issue key (required) — e.g., `OCPBUGS-12345`, `CNTRLPLANE-205`
- **$2, $3, ..., $N**: Optional GitHub PR URLs
  - If provided: only these PRs are analyzed
  - If omitted: PRs linked to the JIRA are discovered automatically
- **--apply**: Execute the reproducer steps against a live OpenShift cluster after generating (or reusing) the report. Requires `oc` CLI and active cluster connectivity. Uses hybrid confirmation: bulk approval for read-only commands, individual approval for write commands.
