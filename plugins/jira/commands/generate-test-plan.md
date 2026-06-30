---
description: Generate test steps for a JIRA issue
argument-hint: "[JIRA issue key] [GitHub PR URLs] [--reproducer]"
---

## Name
jira:generate-test-plan

## Synopsis
```
/jira:generate-test-plan [JIRA issue key] [GitHub PR URLs] [--reproducer]
```

## Description

The `jira:generate-test-plan` command takes a JIRA issue key and optionally a list of PR URLs. It fetches the JIRA issue details, retrieves all related PRs (or uses the provided PR list), analyzes the changes, and generates a comprehensive manual testing guide.

Pass `--reproducer` to generate a bug reproducer report instead of a full test plan. For reproducer-focused workflows, `/jira:generate-bug-reproducer` is an equivalent alias.

**JIRA Issue Test Guide Generator**

## Implementation

Invoke the **Generate Test Plan** skill (`plugins/jira/skills/generate-test-plan/SKILL.md`) with:

- **Mode**: `test-plan` (default) or `reproducer` when `--reproducer` is present
- **JIRA issue key**: `$1`
- **PR URLs**: remaining arguments except `--reproducer`

The skill handles JIRA fetching, PR discovery, change analysis, report generation, and output presentation. See the skill for full implementation details including report templates, PR filtering, and error handling.

## Return Value

- **Test plan mode**: Markdown report at `.work/jira/generate-test-plan/{JIRA_KEY}/test-plan.md`
- **Reproducer mode**: Markdown report at `.work/jira/generate-test-plan/{JIRA_KEY}/reproducer-report.md`

## Examples

1. **Generate test steps for JIRA with auto-discovered PRs**:
   ```
   /jira:generate-test-plan CNTRLPLANE-205
   ```

2. **Generate test steps for JIRA with specific PRs only**:
   ```
   /jira:generate-test-plan CNTRLPLANE-205 https://github.com/openshift/hypershift/pull/6888
   ```

3. **Generate reproducer report via flag**:
   ```
   /jira:generate-test-plan OCPBUGS-12345 --reproducer
   ```

4. **Generate reproducer via alias command**:
   ```
   /jira:generate-bug-reproducer OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888
   ```

## Arguments

- **$1**: JIRA issue key (required) — e.g., `CNTRLPLANE-205`, `OCPBUGS-12345`
- **$2, $3, ..., $N**: Optional GitHub PR URLs or `--reproducer` flag
  - PR URLs: if provided, only these PRs are analyzed; if omitted, PRs linked to the JIRA are discovered automatically
  - `--reproducer`: switch to reproducer mode (same as `/jira:generate-bug-reproducer`)

## Smart Features

1. **Automatic PR Discovery** — scans JIRA issue links, development panel, and comments
2. **Selective PR Testing** — manual override to analyze specific PRs only
3. **Context-Aware Generation** — bugs, features, and refactors each get appropriate coverage
4. **Reproducer Inference** — in reproducer mode, derives missing steps from fix PR diffs
5. **Multi-PR Integration** — integrated scenarios when multiple PRs fix one issue
6. **Build/Deploy Exclusion** — assumes environment is already set up
7. **Cleanup Exclusion** — focuses on test execution and verification
