Run on the host, NOT in a container. Count:
1. Uncommitted tracked files: `git status --short | grep -v '^[?]' | wc -l`
2. Root-owned files outside .git and vendor:
   `find . -type f -not -path './.git/*' -not -path '*/vendor/*' -user root 2>/dev/null | wc -l`
3. .rebase-tmp files tracked by git: `git ls-files .rebase-tmp | wc -l`

Report all three counts. FAIL if any count is non-zero.

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
  "$REPO" step4-cleanliness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
