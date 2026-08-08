Run this check FIRST to decide if this gate applies:
```bash
REPO="<the repo path from the first line of your prompt>"
BASE=$(cd "$REPO" && git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
TYPE_CONV=$(cd "$REPO" && git diff "$BASE"..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' | grep -E '^\+.*(\(\w+\)\(|\.(\w+)\{|type assertion|\.\(\*?\w+\))' | head -20)
if [ -z "$TYPE_CONV" ]; then
  echo "No type conversions in fix commits — SKIP"
fi
```
If no fix commits touch struct conversions or type assertions,
write a SKIP report and stop immediately.

If type conversions ARE found: for each struct conversion, read
the FULL struct definition in vendor and list ALL fields.
Compare against the conversion code. Are any fields silently
dropped? Could any conversion lose data at runtime?

List each struct you checked and your finding. Do not just say
"no issues" -- show your work.

VERDICT criteria: FAIL if any struct conversion silently drops
fields or could lose data at runtime. SKIP if no fix commits
involve type conversions. PASS if all conversions are complete.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line
for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
if [ -n "$SCRIPT" ]; then
  bash "$SCRIPT" "$REPO" step2-type-conversions PASS 0 "your one-line summary" \
    "detail line 1" "detail line 2"
else
  mkdir -p "$REPO/.rebase-tmp/gates"
  printf 'VERDICT: PASS\nISSUES: 0\nSUMMARY: your one-line summary\nDETAILS:\ndetail line 1\ndetail line 2\n' \
    > "$REPO/.rebase-tmp/gates/step2-type-conversions.report"
fi
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
