MANDATORY FIRST STEP — run the companion gate script:

```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -path "*/k8s-rebase/gates/step3-autofix" -type d 2>/dev/null | head -1)
bash "$GATE_DIR/crd-validation.sh" "$(pwd)"
```

Read the output carefully. Apply these rules in order:

RULE 1 — FAST-PATH: If NEW_ISSUES=0, set verdict=PASS immediately.
Write the PASS report and stop. Do NOT run checks 1-2 below.

RULE 2 — PER-CRD FILTER (when NEW_ISSUES>0): You MUST still skip
CRDs the script marked "IDENTICAL" or "NO-VALIDATION-CHANGES".
Only analyze CRDs the script marked "CHANGED-VALIDATION" or
"ALL-NEW". This rule applies regardless of NEW_ISSUES count.
Do NOT open, read, or analyze any file the script marked IDENTICAL.

For each CRD the script marked "CHANGED-VALIDATION" or "ALL-NEW":

1. Compare each CRD to the base branch version. Use
   `git show $BASE:<path>` to check the original.
   Flag any validation constraint removed or weakened vs the
   base: deleted pattern, format, minimum/maximum, enum, or
   required entries, or relaxed values.

2. Check for schema inconsistencies: integer fields where the
   format doesn't match the range (e.g., format: int32 with a
   maximum exceeding 2^31-1, which needs format: int64).

VERDICT: FAIL if any NEW issue found (not in the PRE-EXISTING
output). PASS if all issues are pre-existing or no CRDs exist.
SKIP if no CRDs in repo.

Count ONLY new issues in your ISSUES field. Pre-existing issues
go in DETAILS as "INFO (pre-existing):" entries.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step3-crd-validation PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
