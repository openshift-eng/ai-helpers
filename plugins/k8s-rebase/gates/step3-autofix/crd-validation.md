EVIDENCE (read before judging): if `.rebase-tmp/gates/step3-crd-validation.evidence` exists,
run `git rev-parse HEAD` and compare it to the file's `HEAD:` line.
- Match: Read the file first and treat its `SUMMARY:`/facts as ground truth for this gate.
- Differ or file absent: evidence is stale/missing — judge from scratch using the checks
  below. Do NOT PASS on the strength of absent or stale evidence.

If the evidence SUMMARY contains 'no base branch' or any detail line
starts with 'NO_BASE:', write SKIP with a note that CRD comparison was
impossible because no merge base could be determined. Do not write PASS.

If the evidence SUMMARY starts with 'SKIP:', write SKIP — no CRDs exist
in this repository. Do not write PASS.

Read the evidence. When NEW_ISSUES > 0: focus your analysis on CRDs
the evidence marked "CHANGED-VALIDATION" or "ALL-NEW". Skip CRDs
marked "IDENTICAL" or "NO-VALIDATION-CHANGES" — the companion script
confirmed they are unchanged. If the total CRD count in the evidence
seems lower than expected for this repo, run the manual checks below
to ensure nothing was missed.

If evidence is stale or absent, run the manual checks below for
each CRD schema file in the repository.
Find CRD files: `find . -name '*.yaml' -not -path '*/vendor/*' | xargs grep -l 'kind: CustomResourceDefinition' 2>/dev/null`
For each CRD, compare `git show $BASE:<path>` against the working copy and
flag any newly removed or weakened validation constraint (deleted pattern,
format, minimum/maximum, enum, or required entries, or relaxed values).
If $BASE is empty, do not compare — defer without a self-comparison; never
PASS on a self-comparison. Never PASS on unexamined output.

For each CRD the evidence marked "CHANGED-VALIDATION" or "ALL-NEW"
(or found manually when evidence is absent):

1. Compare each CRD to the base branch version. Use
   `git show $BASE:<path>` to check the original.
   Flag any validation constraint removed or weakened vs the
   base: deleted pattern, format, minimum/maximum, enum, or
   required entries, or relaxed values.

2. Check for schema inconsistencies: integer fields where the
   format doesn't match the range (e.g., format: int32 with a
   maximum exceeding 2^31-1, which needs format: int64).

VERDICT: FAIL if any NEW issue found. PASS if at least one CRD was
examined and all issues are pre-existing. SKIP if no CRDs exist in
the repo (gate does not apply).

Count ONLY new issues in your ISSUES field. Pre-existing issues
go in DETAILS as "INFO (pre-existing):" entries.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
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
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
if [ -n "$SCRIPT" ]; then
  bash "$SCRIPT" "$REPO" step3-crd-validation PASS|FAIL|SKIP 0 "your one-line summary" \
    "detail line 1" "detail line 2"
else
  mkdir -p "$REPO/.rebase-tmp/gates"
  printf 'VERDICT: <PASS|FAIL|SKIP>\nISSUES: 0\nSUMMARY: your one-line summary\nDETAILS:\ndetail line 1\ndetail line 2\n' \
    > "$REPO/.rebase-tmp/gates/step3-crd-validation.report"
fi
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
