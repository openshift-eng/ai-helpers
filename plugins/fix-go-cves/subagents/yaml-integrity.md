# YAML Integrity Verification: ${REPO} ${BRANCH}

You are read-only. Do not edit files or run commands.

## Companion Evidence

${COMPANION_EVIDENCE}

## Task

Evaluate the companion script output above. The script validates newly added
content and audits the complete current ignore list, checking for:

- Vulnerability IDs matching CVE-/GHSA-/GO- patterns
- Non-empty package names
- fix-state values limited to "not-fixed", "unknown", or "wont-fix"
- No blank lines with trailing whitespace
- Comment lines preceding each entry
- No broad vulnerability-only or package-only selectors: every ignore entry must
  identify both a vulnerability and a package

## Verdict

- **PASS** if `NEW_ISSUES=0`
- **FAIL** if `NEW_ISSUES` is greater than 0

Include every issue line from the evidence in your detail output.

## Report

Return only this report shape on stdout (do not call a script):

```text
VERDICT: VERDICT
ISSUES: ISSUE_COUNT
SUMMARY: one-line summary
DETAILS:
detail lines
```

Where:

- VERDICT is PASS or FAIL
- ISSUE_COUNT is the integer from NEW_ISSUES
- summary is a one-line description
- detail_lines are optional, one per issue found

Example:

```text
  VERDICT: PASS
  ISSUES: 0
  SUMMARY: All .grype.yaml entries are well-formed
  DETAILS:
```
