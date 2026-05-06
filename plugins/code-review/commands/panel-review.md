---
description: "Comprehensive multi-perspective code review with architecture, security, consistency, QA, and adversarial analysis"
argument-hint: "[--serial] [--comment] [--coderabbit] [pr-url-or-number]"
---

## Name
code-review:panel-review

## Synopsis
```
/code-review:panel-review [--serial] [--comment] [--coderabbit] [pr-url-or-number]
```

## Description
The `panel-review` command runs a multi-specialist review panel. Seven specialist reviewers each examine the changes through a different lens. Optionally, external review tools (like CodeRabbit) run alongside them. After all reviewers complete, an arbiter synthesizes findings, resolves disagreements, and produces a single verdict.

By default, each specialist runs as a parallel sub-agent. Pass `--serial` to run all specialists inline in the main agent instead — this is significantly cheaper since the codebase context is derived once and shared across all specialists, but reviews run sequentially rather than concurrently.

This panel is best suited for complex or risky changes. For routine changes, consider `/code-review:pre-commit-review` instead.

This command does not perform build verification. Use `/code-review:pr` if build verification is needed.

No arguments are required. By default, the command diffs the current branch against its upstream merge base. Language and profile skills are auto-detected.

## Implementation

### Step 1 — Parse Arguments

Split `$ARGUMENTS` on whitespace. Classify each token:

- A **PR URL** (contains `github.com` and `/pull/`) or **PR number** (bare integer) — pass to the skill as the PR identifier.
- `--serial` — enable serial execution mode (all specialists run inline instead of as sub-agents).
- `--comment` — post the verdict as a comment on the PR after the review completes. Requires a PR identifier.
- `--coderabbit` — include CodeRabbit as an external reviewer.
- **Anything else** — warn and ignore.

If more than one PR identifier is found, error and exit.

### Step 2 — Execute the Review Panel

Read `skills/review-panel/SKILL.md` relative to the plugin root directory. Follow its instructions for all remaining work — diff resolution, language detection, sub-agent dispatch, arbitration, and verdict.

Pass to the skill:
- The PR identifier (if any)
- The list of requested external reviewers (if any)
- Whether serial mode was requested
- Whether comment mode was requested

If `--comment` is passed without a PR identifier, error and exit — a PR is required to post a comment.

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
   /code-review:panel-review --coderabbit
   ```

3. **Review current branch in serial mode (cheaper)**:
   ```
   /code-review:panel-review --serial
   ```

4. **Review a PR and post the verdict as a comment**:
   ```
   /code-review:panel-review --comment 456
   ```

5. **Review a specific PR with CodeRabbit**:
   ```
   /code-review:panel-review https://github.com/openshift/hypershift/pull/789 --coderabbit
   ```

6. **Review by PR number in current repo**:
   ```
   /code-review:panel-review 456
   ```

## See Also
- `/code-review:pr` — single-reviewer analysis with build verification, language-specific idiom checks, and SOLID/DRY compliance
- `/code-review:pre-commit-review` — lightweight pre-commit review of staged changes

## Arguments:
- PR identifier (optional): Full GitHub PR URL or PR number. If omitted, diffs current branch against its upstream merge base.
- `--serial` (optional): Run all specialists inline in the main agent instead of as parallel sub-agents. Cheaper but sequential.
- `--comment` (optional): Post the verdict as a comment on the PR. Requires a PR identifier.
- `--coderabbit` (optional): Include CodeRabbit as an external reviewer. Runs in parallel with (or alongside, in serial mode) internal specialists.
