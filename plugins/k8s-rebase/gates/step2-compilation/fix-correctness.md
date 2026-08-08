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
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step2-fix-correctness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
