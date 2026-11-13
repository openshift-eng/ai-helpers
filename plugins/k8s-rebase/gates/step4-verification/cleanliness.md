Run on the host, NOT in a container. Count:

1. Uncommitted tracked files: `git status --short | grep -v '^[?]' | wc -l`
2. Root-owned files outside .git and vendor:
   `find . -type f -not -path './.git/*' -not -path '*/vendor/*' -user root 2>/dev/null | wc -l`

3. .rebase-tmp files tracked by git: `git ls-files .rebase-tmp | wc -l`

Report all three counts. FAIL if any count is non-zero.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific counts, not "looks good." You are
read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line for any issues.

After your analysis, write your report using the helper script.
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
bash "${PLUGIN_ROOT}/scripts/write-gate-report.sh" \
  "$REPO" step4-cleanliness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
