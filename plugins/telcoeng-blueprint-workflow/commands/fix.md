---
description: Generate fix proposals and diffs for non-compliant blueprint sections, with optional auto-apply and JIRA integration
argument-hint: <blueprint-path> [--partner <name>] [--auto] [--jira]
---

## Name

telcoeng-blueprint-workflow:fix

## Synopsis

```text
/telcoeng-blueprint-workflow:fix <blueprint-path> [--partner <name>] [--auto] [--jira]
```

## Description

The `fix` command compares a non-compliant blueprint against `telcoeng-blueprint-standards` and proposes concrete fixes as diffs. It automates the remediation cycle: validate → propose → apply → re-validate.

This implements NOW #5 (Automated Fix Proposals and Diffs) from the prioritization matrix. It builds on the `validate` command's compliance report to generate actionable patches.

### Key Features

- Runs validation internally to identify all non-compliant sections
- Generates specific fix proposals with before/after diffs
- Presents proposals for user review and selective approval
- Applies approved fixes and re-validates to confirm improvement
- Optionally creates or updates ECOPS JIRA tickets for tracked issues
- Saves a fix log for audit trail

## Implementation

### Phase 1: Run Validation

1. Invoke the `validate` command internally on the provided `<blueprint-path>`
2. If `--partner` is provided, pass it through
3. Capture the compliance report: overall score, section-by-section findings, and recommendations
4. If the blueprint scores 90+ (Excellent), inform the user and exit — no fixes needed

### Phase 2: Generate Fix Proposals

For each non-compliant finding from the validation report:

1. Invoke the `content-generation` skill using the Skill tool to generate compliant replacement content
2. Invoke the `blueprint-structure` skill using the Skill tool to ensure the fix matches current standards
3. For each fix proposal, produce:
   - **Section**: The blueprint section being fixed
   - **Issue**: What the validation found wrong
   - **Current content**: The existing text (or "missing" if the section is absent)
   - **Proposed fix**: The standards-compliant replacement
   - **Impact**: How many compliance points this fix would recover
   - **Diff**: A unified diff showing the exact changes

Prioritize proposals by point impact (highest first).

### Phase 3: Present Fix Proposals

Display proposals to the user in order of impact:

```text
Fix Proposals for <partner-name> (Current Score: XX/100)

## Proposal 1: Add missing S-BOM table (+5 points)
Section: Software and Configuration > S-BOM
Issue: S-BOM section exists but contains no version table

--- current
+++ proposed
@@ -1,2 +1,10 @@
 ## Software Bill of Materials (S-BOM)
-No content.
+| Component | Version | Minimum Patch Level |
+|-----------|---------|-------------------|
+| OpenShift Container Platform | <!-- TODO: version --> | <!-- TODO: patch level --> |
+| Advanced Cluster Management | <!-- TODO: version --> | <!-- TODO: patch level --> |

Apply this fix? [y/n/edit]
```

For each proposal, allow:
- **y**: Apply the fix as proposed
- **n**: Skip this fix
- **edit**: Let the user modify the proposed fix before applying

If `--auto` is provided, apply all fixes without prompting (but still display them).

### Phase 4: Apply Approved Fixes

For each approved fix:

1. Read the current blueprint file
2. Locate the target section using heading matching
3. Apply the proposed change:
   - For missing sections: Insert at the correct position per standards hierarchy
   - For incomplete sections: Replace the section content
   - For malformed tables: Replace the table with the corrected version
4. Write the updated blueprint back to disk
5. Track applied fixes for the summary

### Phase 5: Re-Validate

1. Run validation again on the updated blueprint
2. Compare the new score against the original score
3. Display the improvement:
   ```text
   Score improved: 52/100 → 78/100 (+26 points)
   Fixes applied: 4/6 proposals
   Remaining issues: 2 (skipped by user)
   ```

### Phase 6: JIRA Integration (Optional)

If `--jira` flag is provided:

1. For each applied fix, check if an ECOPS ticket already exists
2. If a ticket exists: Add a comment noting the fix was applied, with the diff
3. If no ticket exists and fixes remain unapplied: Offer to create an ECOPS ticket
4. Use the `jira` plugin with:
   - Project: ECOPS
   - Summary: `[Blueprint Fix] <partner-name> - <section> - <issue>`
   - Description: Include the proposed fix content and diff
   - Labels: blueprint, fix-proposal, <partner-name>
5. Always ask for user confirmation before creating or updating tickets

### Phase 7: Save Fix Log

Save the complete fix session to `.work/blueprints/<partner-name>/fix-log.md`:

```text
# Fix Log — <partner-name>
## Date: <timestamp>
## Original Score: XX/100
## Final Score: YY/100

| # | Section | Issue | Proposed Fix | Status |
|---|---------|-------|-------------|--------|
| 1 | S-BOM | Missing version table | Added template table | Applied |
| 2 | Deviations | No SUPPORTEX links | Added ticket references | Applied |
| 3 | Networking | Missing NAD table | Generated NAD table | Skipped |

## Applied Diffs
<full diffs for all applied fixes>
```

## Return Value

- **Original score**: Score before fixes
- **New score**: Score after fixes
- **Improvement**: Point difference
- **Proposals generated**: Total number of fix proposals
- **Proposals applied**: Number of fixes the user approved and applied
- **Proposals skipped**: Number of fixes the user declined
- **Fix log path**: `.work/blueprints/<partner-name>/fix-log.md`
- **JIRA tickets**: Created or updated ticket IDs (if `--jira` was used)

## Examples

1. **Interactive fix session**:
   ```text
   /telcoeng-blueprint-workflow:fix .work/blueprints/acme-telecom/blueprint.md --partner acme-telecom
   ```
   Output: Displays proposals one by one, applies approved fixes, shows score improvement.

2. **Auto-apply all fixes**:
   ```text
   /telcoeng-blueprint-workflow:fix ./blueprint.md --partner samsung --auto
   ```
   Output: Applies all generated fixes without prompting, displays summary.

3. **Fix with JIRA ticket tracking**:
   ```text
   /telcoeng-blueprint-workflow:fix ./blueprint.md --partner softbank --jira
   ```
   Output: Applies fixes and creates/updates ECOPS tickets for each finding.

4. **Fix a freshly ingested blueprint**:
   ```text
   /telcoeng-blueprint-workflow:fix .work/blueprints/partner-x/blueprint.md
   ```

## Arguments

- `$1` (`<blueprint-path>`): Path to the blueprint Markdown file to fix.
- `--partner <name>`: Partner name for report naming, file paths, and JIRA labels. If omitted, derived from file path or prompted.
- `--auto`: Apply all fix proposals without interactive confirmation. Fixes are still displayed for review.
- `--jira`: Enable JIRA integration to create or update ECOPS tickets for findings. Requires user confirmation per ticket.

## Error Handling

- **Blueprint not found**: Display error, suggest running `ingest` if the source is Word/PDF
- **Blueprint not Markdown**: Inform user to run `ingest` first
- **Already compliant (90+)**: Inform user, suggest minor improvements if any exist
- **No fixable issues**: Some compliance gaps may require manual input (e.g., partner-specific data); list these separately
- **Fix application failure**: Roll back the individual fix, continue with remaining proposals
- **Standards not found**: Fall back to `reference/blueprint-sections.md`, warn about potentially stale fixes
- **JIRA not configured**: Skip ticket operations, note in fix log
