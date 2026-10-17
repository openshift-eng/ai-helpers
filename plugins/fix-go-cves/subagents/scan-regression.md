# Scan Regression Verification: ${REPO} ${BRANCH}

You are read-only. Do not edit files or run commands.

## Companion Evidence

${COMPANION_EVIDENCE}

## Task

Evaluate the companion script output above. The script compared the initial CVE scan
(taken before any fixes) with a final scan (taken after all fixes and ignores) to
detect regressions.

Three categories of findings:

### NEW

CVEs that appear in the final scan but were NOT in the initial scan. These are
regressions -- a dependency update introduced a new vulnerability.

### UNRESOLVED

CVEs that were in the initial scan and are still in the final scan without a
corresponding .grype.yaml ignore entry. These were neither fixed nor ignored.

### NEEDS_REVIEW

CVEs that were in the initial scan and are still present after a deterministic fix
attempt reached a policy boundary, such as requiring a Go version newer than the
detected builder/compiler or a prohibited Kubernetes minor bump. A Go directive
minor bump is not itself breaking when the detected builder supports it. These
items need team approval. They do NOT count toward UNRESOLVED and do NOT cause FAIL.

## Verdict

- **PASS** if `NEW_CVES=0` AND `UNRESOLVED=0` AND there is no `SCAN_FAILED=1` line
  (NEEDS_REVIEW lines do not affect this verdict)
- **FAIL** if either count is greater than 0
- **SKIP** if the companion reported SKIP or `SCAN_FAILED=1` (e.g. missing initial
  scan, or the final scan failed) — never PASS when the scan is unreliable

Include every NEW, UNRESOLVED, and NEEDS_REVIEW line from the evidence in your detail output.

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

- VERDICT is PASS, FAIL, or SKIP
- ISSUE_COUNT is NEW_CVES + UNRESOLVED (NEEDS_REVIEW items do not count)
- summary is a one-line description
- detail_lines list each NEW, UNRESOLVED, and NEEDS_REVIEW CVE

Examples:

```text
  VERDICT: FAIL
  ISSUES: 1
  SUMMARY: 1 new CVE introduced
  DETAILS:
NEW: GHSA-xxxx-xxxx-xxxx (golang.org/x/text v0.14.0 High 0.15.0) location:/go.mod
```
