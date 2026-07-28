Verify that test files compile. `go build ./...` only compiles
non-test packages — tests can have their own import errors,
type mismatches, and missing symbols that build alone misses.

Find module directories:
  `find . -name go.mod -not -path '*/vendor/*' -not -path '*/.cache/*' -exec dirname {} \;`

For each module, compile tests without executing them:
  `go test -run='^$' -count=0 ./... 2>&1`
  (add `-mod=vendor` if vendor/ exists in the module)

The flags `-run='^$' -count=0` match zero tests and skip
execution — this only verifies compilation. Any compilation
error in a _test.go file is a finding.

Skip modules whose vendor/ directory is gitignored:
  `git check-ignore -q <dir>/vendor 2>/dev/null`
  Gitignored vendor dirs are not maintained by the rebase.

If Go is unavailable or wrong version, note as SKIPPED.

Report total test compilation errors.

For pre-existing issues: if the base branch also has test
compilation errors, exclude those from the count. Only report
NEW test compilation errors introduced by the rebase.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific counts, not "looks good." You are
read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step2-test-compilation PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
