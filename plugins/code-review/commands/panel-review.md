---
description: "Comprehensive multi-perspective code review with architecture, security, consistency, QA, and adversarial analysis"
argument-hint: "[pr-url-or-number] [coderabbit]"
---

## Name
code-review:panel-review

## Synopsis
```
/code-review:panel-review [pr-url-or-number] [external-reviewer...]
```

## Description
The `panel-review` command runs a multi-specialist review panel. Seven specialist reviewers execute in parallel as sub-agents, each examining the changes through a different lens. Optionally, external review tools (like CodeRabbit) run alongside them. After all reviewers complete, an arbiter synthesizes findings, resolves disagreements, and produces a single verdict.

This panel is best suited for complex or risky changes — it launches 7 parallel sub-agents and is quite resource-intensive. For routine changes, consider `/code-review:pre-commit-review` instead.

This command does not perform build verification. Use `/code-review:pr` if build verification is needed.

No arguments are required. By default, the command diffs the current branch against its upstream merge base. Language and profile skills are auto-detected.

## Implementation

### Step 1 — Parse Arguments

Split `$ARGUMENTS` on whitespace. Classify each token:

- A **PR URL** (contains `github.com` and `/pull/`) or **PR number** (bare integer) — pass to the skill as the PR identifier.
- A **known external reviewer name** (`coderabbit`) — pass to the skill.
- **Anything else** — warn and ignore.

If more than one PR identifier is found, error and exit.

### Step 2 — Execute the Review Panel

Read `skills/review-panel/SKILL.md` relative to the plugin root directory. Follow its instructions for all remaining work — diff resolution, language detection, sub-agent dispatch, arbitration, and verdict.

Pass to the skill:
- The PR identifier (if any)
- The list of requested external reviewers (if any)

## Return Value
- **Format**: Structured verdict using the template from `skills/review-panel/verdict-template.md`.
- **Success**: Verdict with APPROVE or NEEDS_DISCUSSION disposition.
- **Failure**: Verdict with REQUEST_CHANGES and blocking findings listed.

## Examples

1. **Review current branch (default)**:
   ```
   /code-review:panel-review
   ```

2. **Review with CodeRabbit**:
   ```
   /code-review:panel-review coderabbit
   ```

3. **Review a specific PR with CodeRabbit**:
   ```
   /code-review:panel-review https://github.com/openshift/hypershift/pull/789 coderabbit
   ```

4. **Review by PR number in current repo**:
   ```
   /code-review:panel-review 456
   ```

## See Also
- `/code-review:pr` — single-reviewer analysis with build verification, language-specific idiom checks, and SOLID/DRY compliance
- `/code-review:pre-commit-review` — lightweight pre-commit review of staged changes

## Arguments:
- PR identifier (optional): Full GitHub PR URL or PR number. If omitted, diffs current branch against its upstream merge base.
- External reviewers (optional, repeatable): Names of external review tools to include. Currently supported: `coderabbit`. Each runs in parallel with internal specialists.
