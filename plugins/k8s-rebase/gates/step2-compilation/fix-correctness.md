Review the fix commits for correctness. Did the agent understand
WHY each change was needed, or did it just make the compiler
happy? Flag fixes that compile but would behave incorrectly at
runtime. Examples: wrong format verb, wrong field mapping,
missing error check, silently swallowed error.

List each fix you reviewed and your assessment. Do not just say
"all correct" — show your reasoning for each.

VERDICT criteria: FAIL if any fix compiles but would behave
incorrectly at runtime (wrong type conversion, silent data loss,
inverted logic). PASS if all fixes are semantically correct.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line
for any issues.

After your analysis, write your report using the helper script.
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
bash "${PLUGIN_ROOT}/scripts/write-gate-report.sh" \
  "$REPO" step2-fix-correctness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
