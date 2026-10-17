# Existing Entries Audit: ${REPO} ${BRANCH}

You are read-only. Do not edit files or run commands.

## Companion Evidence

${COMPANION_EVIDENCE}

## Task

Evaluate the companion script output above. The script audited pre-existing .grype.yaml
entries (those present on origin/${BRANCH} before this fix run) to check for staleness.

Every emitted finding requires deterministic remediation:

### STALE

A permanent ignore entry where grype no longer reports the CVE for that package at
all (e.g. a false-positive was corrected in the grype DB). The entry is dead weight.

The correct action is to **remove the ignore entry**. Include the STALE line verbatim
in your detail output so the deterministic fix handler can delete the entry.

### FIX-AVAILABLE

A permanent ignore (no fix-state) where grype now reports a known fix version.
This means the entry's rationale is factually wrong — a real fix exists.

The correct action is to **fix the package** (bump its version), not to convert
the entry to `fix-state: not-fixed`. Include the FIX-AVAILABLE line verbatim in
your detail output so the deterministic fix handler can apply the fix.

### FIX-NOW-AVAILABLE

An entry marked `fix-state: not-fixed` or `unknown` is still installed below a fix
version that grype explicitly reports for the same CVE, package, and module scope.
The entry must be fixed or left for review; it is not merely informational.

### SCOPE-AVAILABLE

An auto-expiring unscoped ignore has a no-fix finding in exactly one Grype-reported
Go module. The repository-wide policy is unnecessarily broad. The deterministic
handler narrows the existing ignore to that exact `go.mod`; it must not be converted
into a permanent ignore. Dependency-graph presence in another module does not add a
scope unless Grype reports the same CVE/package there too. The handler preserves the
effective scanner state (`not-fixed`, `unknown`, or `wont-fix`) so the migrated rule
continues to match the finding.

## Verdict

- **PASS** only if `NEW_ISSUES=0`.
- **FAIL** if any `STALE`, `FIX-AVAILABLE`, `FIX-NOW-AVAILABLE`, or
  `SCOPE-AVAILABLE` entry exists.

Include every finding line from the evidence verbatim in your detail output.

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
- ISSUE_COUNT is the count of entries that genuinely need updating
- summary is a one-line description of the verdict
- detail_lines provide context for each finding

Example:

```text
  VERDICT: FAIL
  ISSUES: 1
  SUMMARY: 1 permanent ignore has a real fix available
  DETAILS:
FIX-AVAILABLE: github.com/klauspost/compress 1.17.11 -> 1.18.7 CVEs:GO-2026-5841
```
