# Fix Availability Verification: ${REPO} ${BRANCH}

You are read-only. Do not edit files or run commands.

## Companion Evidence

${COMPANION_EVIDENCE}

## Task

Evaluate the companion script output above. The script cross-referenced .grype.yaml
entries marked with `fix-state: not-fixed` or `fix-state: unknown` against
the current Grype scan's ignoredMatches to check whether a published fix is
available.

For each `FIX-AVAILABLE` entry:

- Grype explicitly reports a fix version for the same CVE, package, and module
  scope, and the installed version remains below it
- The existing `fix-state` entry is stale or was added prematurely
- The package should be fixed rather than ignored

## Verdict

- **PASS** if `NEW_ISSUES=0` -- grype reports no actionable fix for these entries
- **FAIL** if any `FIX-AVAILABLE` or `RESOLUTION_FAILED` entries exist

Include every FIX-AVAILABLE and RESOLUTION_FAILED line from the evidence in your detail output.

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
- detail_lines are one per FIX-AVAILABLE or RESOLUTION_FAILED finding

Example:

```text
  VERDICT: FAIL
  ISSUES: 2
  SUMMARY: 2 packages have fixes available
  DETAILS:
FIX-AVAILABLE: golang.org/x/net v0.20.0 -> v0.23.0 location:/go.mod CVEs:GHSA-xxxx
FIX-AVAILABLE: golang.org/x/crypto v0.18.0 -> v0.21.0 location:/tools/go.mod CVEs:GHSA-yyyy
```
