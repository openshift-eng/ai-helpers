---
name: ready-to-solve
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

1. **Deterministic checks** via a Python script that verifies structural requirements: required sections exist, are non-empty, and have adequate content.
2. **AI qualitative assessment** that evaluates whether the acceptance criteria are specific and testable, whether there is enough implementation context, and whether clear success/failure conditions exist.

On pass, the label `ready-to-solve` is added to the issue. On fail, `not-ready-to-solve` is added. The stale opposite label is removed if present.

With `--fix`, when validation fails the command generates a revised description that adds or improves the failing sections, shows the proposed changes to the user for approval, and updates the Jira issue description upon confirmation.

## Prerequisites

- Jira MCP server configured (Atlassian Rovo MCP)
- Python 3.8+ (`which python3`)

## Implementation

### Phase 1: Fetch Issue Data

Fetch the issue via `getJiraIssue` with the issue key.

Extract from the response:
- `fields.description` -- full description text
- `fields.summary` -- issue title
- `fields.labels` -- current labels array (needed for label updates)
- `fields.status.name` -- current status
- `fields.issuetype.name` -- issue type

If `description` is null or empty, skip to Phase 4 with an automatic FAIL verdict.

### Phase 2: Run Deterministic Checks

Pipe the description to the Python script:

```bash
echo '{"description": "<description_content>"}' | python3 plugins/jira/skills/ready-to-solve/scripts/check_sections.py
```

For verbose output (includes matched content):
```bash
echo '{"description": "<description_content>"}' | python3 plugins/jira/skills/ready-to-solve/scripts/check_sections.py --verbose
```

**Important**: Construct the JSON input carefully. The description may contain quotes, newlines, and special characters. Use Python or `jq` to safely serialize:

```bash
echo "$DESCRIPTION" | jq -Rs '{"description": .}' | python3 plugins/jira/skills/ready-to-solve/scripts/check_sections.py
```

The script outputs JSON with per-check results. Parse the output to get:
- `overall_pass`: boolean -- whether all REQUIRED checks passed
- `checks`: array of individual check results
- `stats`: summary counts

**Deterministic checks performed by the script:**

| Check ID | Name | Pass Condition | Severity |
|----------|------|----------------|----------|
| `has_context` | Context section present | Heading matching: Context, Description, Background, Overview, or Why | REQUIRED |
| `has_ac` | Acceptance Criteria present | Heading matching: Acceptance Criteria, AC, or Definition of Done | REQUIRED |
| `context_not_empty` | Context has content | At least 50 characters below the heading | REQUIRED |
| `ac_not_empty` | AC has content | At least 30 characters below the heading | REQUIRED |
| `has_tech` | Technical Details present | Heading matching: Technical Details, Technical Context, Implementation Details, Implementation Notes, or Technical Notes | REQUIRED |
| `tech_not_empty` | Technical Details has content | At least 30 characters below the heading | REQUIRED |
| `ac_has_items` | AC has multiple items | Warns if fewer than 2 bullet points or numbered items | WARNING |
| `min_description_length` | Adequate overall length | Total description at least 200 characters | WARNING |

**Note:** WARNING checks are reported but do not block the overall verdict. Only REQUIRED checks must pass for the issue to be considered ready.

### Phase 3: AI Qualitative Assessment

Read the full description and evaluate three dimensions. For each, produce a verdict (PASS or FAIL) and a 1-2 sentence justification.

1. **AC Specificity and Testability**: Are acceptance criteria specific enough to write tests against? Do they describe observable behavior rather than vague goals?
   - FAIL: no acceptance criteria, or criteria are vague ("it should work", "system performs well")
   - PASS: criteria describe observable behavior ("when X happens, Y returns Z", "API returns 404 for missing resources")

2. **Implementation Context Sufficiency**: Is there enough description of the problem, affected code area, or desired behavior that `/jira:solve` could identify relevant files and implement a solution?
   - FAIL: a codebase search would be ambiguous (no component, file, or feature area mentioned)
   - PASS: the description points to a specific area of the codebase, component, or behavior

3. **Clear Success/Failure Conditions**: Can a reviewer determine whether a proposed solution addresses the issue?
   - FAIL: no way to tell if a solution is correct (no expected behavior, no test criteria)
   - PASS: conditions are explicit enough to verify a solution

### Phase 4: Aggregate Verdict

```text
overall_pass = (all REQUIRED deterministic checks pass) AND (no AI check has verdict FAIL)
```

Collect all failures and warnings into a list for the report.

### Phase 5: Fix Failing Checks (if `--fix`)

Skip if `--fix` is not set or if validation already passed.

When validation fails and `--fix` is set, generate a revised description that fixes the failing checks:

1. **Identify failures**: Collect all failed deterministic checks and AI qualitative FAILs from phases 2-4.

2. **Generate revised description**: Preserve ALL existing content from the original description. Only add or expand sections -- never remove or rewrite content the user wrote. For each failure:

   - **Missing Context/Why section**: Generate an `h2. Why` section from the issue summary and any context in the existing description text.
   - **Missing Acceptance Criteria**: Generate an `h2. Acceptance Criteria` section with concrete, testable bullet points derived from the description context.
   - **Missing Technical Details**: Generate an `h2. Technical Details` section from any code references, file paths, component mentions, or technical context in the description.
   - **Section too short**: Expand the existing section with additional relevant detail while preserving the original content.
   - **AC lacks list items**: Restructure the existing AC text into proper bullet points and add additional criteria if needed.
   - **Vague acceptance criteria**: Rewrite vague criteria to be specific and testable (e.g., "works" becomes "returns 200 on valid input").
   - **Insufficient implementation context**: Add implementation pointers -- component names, likely file paths, related features.
   - **Unclear success conditions**: Add explicit done criteria and edge cases.

3. **Present proposed changes to the user**: Show the full proposed description, clearly indicating what was added or changed (e.g., mark new sections with a note). Ask the user: "Here is the proposed updated description. Apply this to the Jira issue? (yes/no)"

4. **If confirmed**: Update the issue description via `editJiraIssue`, setting the `description` field to the revised text with `contentFormat: "markdown"`.

5. **Re-run validation**: After updating, re-run phases 2-4 on the new description to confirm the issue now passes. Report the re-validation results.

6. **If declined**: Skip the update and proceed to label application and reporting with the original validation result.

### Phase 6: Comment on Result

Skip if `--dry-run` is set.

Post or update a Jira comment reflecting the validation result so the ticket author knows the outcome without running the check themselves.

#### Step 1: Check for existing automated comment

Fetch the issue with comments included via `getJiraIssue` and search for one whose body starts with `**Automated Readiness Check`. Save its `comment_id` if found.

#### Step 2: Build comment body

**On FAIL**: Reuse the same report format defined in Phase 8 (Generate Report), filtered to only show failed and warning checks. Wrap it with:
- Header: `**Automated Readiness Check — FAILED**` followed by "Please update the issue description to address the REQUIRED items below."
- Footer: `*These checks can also be auto-fixed by running '/jira:ready-to-solve {issue-key} --fix' in Claude Code.*`
- If `--fix` was attempted but the issue still fails, replace the footer with:
  ```text
  *Auto-fix was attempted but could not fully resolve all issues. Please address the remaining items manually.*
  ```

**On PASS**: If an existing automated comment was found in Step 1, use a brief body. If no existing comment was found, skip to Phase 7 — no comment is needed for a first-time PASS.

```markdown
**Automated Readiness Check — PASSED**

All checks passed. This issue is ready for `/jira:solve`.
```

#### Step 3: Post or edit the comment

If an existing automated comment was found (Step 1), the Atlassian Rovo MCP does not support editing comments directly. Post a new comment instead.

Post the comment via `addCommentToJiraIssue` with the issue key, the comment body, and `contentFormat: "markdown"`.

If no existing comment was found and the verdict is PASS, do nothing.

### Phase 7: Apply Jira Label

Skip if `--dry-run` is set.

1. Get current labels from the fetched issue data
2. Build the updated label list:
   - If PASS: remove `not-ready-to-solve` (if present), add `ready-to-solve`
   - If FAIL: remove `ready-to-solve` (if present), add `not-ready-to-solve`
3. Skip update if labels haven't changed
4. Apply via `editJiraIssue`, setting the `labels` field to the updated labels list. Note: The `labels` field replaces the entire array, so always include all existing labels plus the new one.

### Phase 8: Generate Report

Output format:

```markdown
## Readiness Validation: {issue-key}
**Summary**: {summary} | **Verdict**: PASS/FAIL

### Deterministic Checks

| Check | Result | Details |
|-------|--------|---------|
| Context section present | PASS/FAIL | {details} |
| Acceptance Criteria present | PASS/FAIL | {details} |
| ... | ... | ... |

### AI Qualitative Assessment

**AC Specificity and Testability**: PASS/FAIL
{reasoning}

**Implementation Context Sufficiency**: PASS/FAIL
{reasoning}

**Clear Success/Failure Conditions**: PASS/FAIL
{reasoning}

### Overall Verdict: PASS/FAIL

{Summary of failures or confirmation that issue is ready}

**Label Applied**: `ready-to-solve` / `not-ready-to-solve` / _(dry run -- no label applied)_
```

## Return Value
- **Format**: Structured markdown report with deterministic check results table, AI qualitative assessment (3 dimensions with verdicts and reasoning), overall PASS/FAIL verdict, and label applied.
- **PASS**: All required checks pass, no AI FAIL verdicts.
- **FAIL**: At least one required check failed or AI flagged a critical issue.

## Error Handling

| Error | Handling |
|-------|----------|
| Issue not found | "Could not find issue {key}. Verify the issue key is correct." |
| MCP unavailable | Display error: "Jira MCP server required. Check plugin README for setup." |
| Python not available | "Python 3 is required. Check: `which python3`" |
| `check_sections.py` fails | Display script error, proceed with AI-only assessment, note in report |
| Description is null/empty | Automatic FAIL: "Issue has no description. Add Context and Acceptance Criteria sections." |
| Comment post/edit fails | Display warning but still proceed with label application and report. Non-fatal. |
| Label update fails | Display warning but still show report. Non-fatal. |
| Description update fails (`--fix`) | Display error, report original validation result. Non-fatal. |
| User declines fix (`--fix`) | Skip update, proceed with original validation result. |
| Re-validation fails after fix | Report the new failures. The fix improved but did not fully resolve all issues. |

## Examples

1. **Basic usage**:
   ```bash
   /jira:ready-to-solve OCPBUGS-12345
   ```

2. **Dry run (no label changes)**:
   ```bash
   /jira:ready-to-solve OCPBUGS-12345 --dry-run
   ```

3. **Verbose output**:
   ```bash
   /jira:ready-to-solve OCPBUGS-12345 --verbose
   ```

4. **Validate and fix failing checks**:
   ```bash
   /jira:ready-to-solve OCPBUGS-12345 --fix
   ```

## Arguments:
- $1: Jira issue key (required). Examples: `OCPBUGS-12345`, `HOSTEDCP-999`, `GCP-456`.
- `--dry-run`: Optional. Skip label application and comment posting, only report results.
- `--verbose`: Optional. Show full per-check details including matched section content.
- `--fix`: Optional. When validation fails, generate a revised description fixing the failing checks.

## See Also

- [/jira:solve](../../commands/solve.md) -- the command this validates readiness for
