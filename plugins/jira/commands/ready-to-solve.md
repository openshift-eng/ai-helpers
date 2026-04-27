---
description: Check whether a Jira issue is well-groomed and ready for /jira:solve
argument-hint: <jira-issue-key> [--dry-run] [--verbose] [--fix]
---

## Name
jira:ready-to-solve

## Synopsis
```bash
/jira:ready-to-solve <jira-issue-key> [--dry-run] [--verbose] [--fix]
```

## Description

The `jira:ready-to-solve` command checks whether a Jira issue has sufficient grooming for `/jira:solve` to produce a quality solution.

It runs a two-phase validation:

1. **Deterministic checks** via a Python script that verifies structural requirements: required sections exist, are non-empty, have adequate content, and contain no placeholder text.
2. **AI qualitative assessment** that evaluates whether the acceptance criteria are specific and testable, whether there is enough implementation context, and whether clear success/failure conditions exist.

On pass, the label `ready-to-solve` is added to the issue. On fail, `not-ready-to-solve` is added. The stale opposite label is removed if present.

With `--fix`, when validation fails the command generates a revised description that adds or improves the failing sections, shows the proposed changes to the user for approval, and updates the Jira issue description upon confirmation. After fixing, validation is re-run to confirm the issue now passes.

## Implementation

Load the skill file for detailed implementation guidance:

```text
plugins/jira/skills/ready-to-solve/SKILL.md
```

### Process Flow

1. **Fetch Issue**: Use `mcp__atlassian__jira_get_issue` to retrieve the issue. Extract `description`, `summary`, `labels`, `status`, and `issuetype`. If MCP is unavailable, fall back to curl with `JIRA_PERSONAL_TOKEN`.

2. **Deterministic Checks**: Pipe the description as JSON to the section checker script:
   ```bash
   echo "$DESCRIPTION" | jq -Rs '{"description": .}' | python3 plugins/jira/skills/ready-to-solve/check_sections.py
   ```
   The script validates:
   - Context/Description section exists and has >= 50 characters
   - Acceptance Criteria section exists and has >= 30 characters
   - Technical Details section exists and has >= 30 characters
   - AC has multiple list items (warning)
   - Overall description length >= 200 characters (warning)

3. **AI Qualitative Assessment**: Evaluate three dimensions using the full description content:
   - **AC Specificity**: Are criteria concrete and testable, not vague?
   - **Implementation Context**: Is there enough detail to identify relevant code?
   - **Success/Failure Conditions**: Can a reviewer tell if the solution is correct?

   Each dimension gets PASS, FAIL, or WARNING with a 1-2 sentence justification.

4. **Aggregate Verdict**: The issue passes only if all REQUIRED deterministic checks pass AND no AI check returns FAIL. Warnings are reported but do not block.

5. **Fix (if `--fix` and validation failed)**: If the `--fix` flag is set and the issue failed validation:
   - Analyze which checks failed (deterministic and AI qualitative)
   - Generate a revised description that preserves all existing content and adds or improves the failing sections:
     - Missing Context/Why section: generate from the issue summary, existing description text, and issue metadata
     - Missing Acceptance Criteria: generate concrete, testable criteria from the description context
     - Missing Technical Details: generate from any code references, file paths, or component mentions in the description
     - Sections too short: expand with additional relevant detail
     - AC lacks list items: restructure into proper bullet points
     - AI qualitative failures: improve vague AC to be specific and testable, add implementation pointers, clarify success/failure conditions
   - Present the proposed new description to the user, clearly showing what was added or changed
   - Ask the user for confirmation before applying
   - If confirmed, update the issue description via `mcp__atlassian__jira_update_issue` or curl fallback
   - Re-run validation (steps 2-4) on the updated description to confirm the issue now passes
   - If the user declines, skip the update and report the original validation result

6. **Apply Label**: Unless `--dry-run`, update the issue labels via `mcp__atlassian__jira_update_issue`. Fetch current labels first, remove the stale opposite label, add the new label, and PUT the full array in a single call.

7. **Report**: Display a structured markdown report with per-check results, AI assessments, overall verdict, and label applied.

## Return Value

- **Format**: Structured markdown report with:
  - Deterministic check results table (per-check pass/fail with details)
  - AI qualitative assessment (3 dimensions with verdicts and reasoning)
  - Overall PASS/FAIL verdict
  - Label applied (or dry-run indication)
- **PASS**: All required checks pass, no AI FAIL verdicts
- **FAIL**: At least one required check failed or AI flagged a critical issue

## Examples

1. **Check readiness of an issue**:
   ```bash
   /jira:ready-to-solve OCPBUGS-12345
   ```

2. **Preview without applying labels**:
   ```bash
   /jira:ready-to-solve OCPBUGS-12345 --dry-run
   ```

3. **Get detailed output with section content**:
   ```bash
   /jira:ready-to-solve OCPBUGS-12345 --verbose
   ```

4. **Validate and fix failing checks**:
   ```bash
   /jira:ready-to-solve OCPBUGS-12345 --fix
   ```

## Arguments:
- $1: Jira issue key (required). Examples: `OCPBUGS-12345`, `HOSTEDCP-999`, `GCP-456`.
- `--dry-run`: Optional. Skip label application, only report results.
- `--verbose`: Optional. Show full per-check details including matched section content.
- `--fix`: Optional. When validation fails, generate a revised description fixing the failing checks, show the proposed changes, and update the issue upon user confirmation.
