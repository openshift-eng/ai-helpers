---
name: Jira Issue Readiness Validator
description: Detailed implementation guide for checking Jira issue readiness for /jira:solve
command: /jira:ready-to-solve
---

# Jira Issue Readiness Validator

## When to Use This Skill

Invoked by `/jira:ready-to-solve`. Validates whether a Jira issue is well-groomed enough for `/jira:solve` to produce a quality solution.

## Prerequisites

- Jira MCP server configured, or `JIRA_PERSONAL_TOKEN` env var for CLI fallback
- Python 3.8+ (`which python3`)

**Reference Documentation:**
- [MCP Tools](../../reference/mcp-tools.md)
- [CLI Fallback](../../reference/cli-fallback.md)

## Implementation Steps

### Phase 1: Fetch Issue Data

Use MCP as primary method:

```python
issue = mcp__atlassian__jira_get_issue(issue_key="PROJ-123")
```

Extract from the response:
- `fields.description` -- full description text
- `fields.summary` -- issue title
- `fields.labels` -- current labels array (needed for label updates)
- `fields.status.name` -- current status
- `fields.issuetype.name` -- issue type

**CLI fallback** if MCP is unavailable:

```bash
curl -s -H "Authorization: Bearer $JIRA_PERSONAL_TOKEN" \
  "https://redhat.atlassian.net/rest/api/2/issue/{issue_key}?fields=description,summary,labels,status,issuetype"
```

If `description` is null or empty, skip to Phase 4 with an automatic FAIL verdict.

### Phase 2: Run Deterministic Checks

Pipe the description to the Python script:

```bash
echo '{"description": "<description_content>"}' | python3 plugins/jira/skills/ready-to-solve/check_sections.py
```

For verbose output (includes matched content):
```bash
echo '{"description": "<description_content>"}' | python3 plugins/jira/skills/ready-to-solve/check_sections.py --verbose
```

**Important**: Construct the JSON input carefully. The description may contain quotes, newlines, and special characters. Use Python or `jq` to safely serialize:

```bash
echo "$DESCRIPTION" | jq -Rs '{"description": .}' | python3 plugins/jira/skills/ready-to-solve/check_sections.py
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
| `ac_has_items` | AC has multiple items | At least 2 bullet points or numbered items | WARNING |
| `min_description_length` | Adequate overall length | Total description at least 200 characters | WARNING |

### Phase 3: AI Qualitative Assessment

Read the full description and evaluate three dimensions. For each, produce a verdict (PASS, FAIL, WARNING) and a 1-2 sentence justification.

1. **AC Specificity and Testability**: Are acceptance criteria specific enough to write tests against? Do they describe observable behavior rather than vague goals?
   - FAIL examples: "it should work properly", "system performs well", "user can do things"
   - PASS examples: "when X happens, Y returns Z", "API returns 404 for missing resources", "latency stays under 200ms"

2. **Implementation Context Sufficiency**: Is there enough description of the problem, affected code area, or desired behavior that `/jira:solve` could identify relevant files and implement a solution?
   - FAIL if a codebase search would be ambiguous (no component, file, or feature area mentioned)
   - PASS if the description points to a specific area of the codebase or behavior

3. **Clear Success/Failure Conditions**: Can a reviewer determine whether a proposed solution addresses the issue?
   - WARNING if AC exists but lacks edge cases
   - PASS if conditions are explicit and unambiguous

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
   - **Vague acceptance criteria**: Rewrite vague criteria to be specific and testable (e.g., "works properly" becomes "returns 200 on valid input").
   - **Insufficient implementation context**: Add implementation pointers -- component names, likely file paths, related features.
   - **Unclear success conditions**: Add explicit done criteria and edge cases.

3. **Present proposed changes to the user**: Show the full proposed description, clearly indicating what was added or changed (e.g., mark new sections with a note). Ask the user: "Here is the proposed updated description. Apply this to the Jira issue? (yes/no)"

4. **If confirmed**: Update the issue description via MCP:

```python
mcp__atlassian__jira_update_issue(
    issue_key="PROJ-123",
    fields={"description": revised_description},
    additional_fields={}
)
```

**CLI fallback:**
```bash
curl -s -u "$JIRA_USER:$JIRA_API_TOKEN" -H "Content-Type: application/json" \
  -X PUT "https://redhat.atlassian.net/rest/api/2/issue/PROJ-123" \
  -d '{"fields":{"description":"...revised description..."}}'
```

5. **Re-run validation**: After updating, re-run phases 2-4 on the new description to confirm the issue now passes. Report the re-validation results.

6. **If declined**: Skip the update and proceed to label application and reporting with the original validation result.

### Phase 6: Apply Jira Label

Skip if `--dry-run` is set.

1. Get current labels from the fetched issue data
2. Build the updated label list:
   - If PASS: remove `not-ready-to-solve` (if present), add `ready-to-solve`
   - If FAIL: remove `ready-to-solve` (if present), add `not-ready-to-solve`
3. Skip update if labels haven't changed
4. Apply via MCP (single API call to avoid partial updates):

```python
mcp__atlassian__jira_update_issue(
    issue_key="PROJ-123",
    fields={},
    additional_fields={
        "labels": updated_labels_list
    }
)
```

**CLI fallback:**
```bash
jira issue edit PROJ-123 -l "ready-to-solve"
```

Note: The `labels` field in Jira REST API replaces the entire array, so always include all existing labels plus the new one.

### Phase 7: Generate Report

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

**AC Specificity and Testability**: PASS/FAIL/WARNING
{reasoning}

**Implementation Context Sufficiency**: PASS/FAIL/WARNING
{reasoning}

**Clear Success/Failure Conditions**: PASS/FAIL/WARNING
{reasoning}

### Overall Verdict: PASS/FAIL

{Summary of failures or confirmation that issue is ready}

**Label Applied**: `ready-to-solve` / `not-ready-to-solve` / _(dry run -- no label applied)_
```

## Error Handling

| Error | Handling |
|-------|----------|
| Issue not found | "Could not find issue {key}. Verify the issue key is correct." |
| MCP unavailable | Fall back to curl for fetching, jira CLI for label update |
| Python not available | "Python 3 is required. Check: `which python3`" |
| `check_sections.py` fails | Display script error, proceed with AI-only assessment, note in report |
| Description is null/empty | Automatic FAIL: "Issue has no description. Add Context and Acceptance Criteria sections." |
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

## See Also

- [/jira:solve](../../commands/solve.md) -- the command this validates readiness for
