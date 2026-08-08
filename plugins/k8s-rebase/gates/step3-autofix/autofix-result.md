Check whether the autofix produced meaningful results by
examining the commit history after the initial rebase.

1. Determine the base:
   `BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`

2. List post-rebase commits:
   `git log --oneline $BASE..HEAD`
   Count total commits. Identify which are rebase infrastructure
   (go.mod/vendor changes) vs fix commits (code changes).

3. Check for autofix markers:
   - Commits with "Applied:" in the body: `git log --grep='Applied:' --oneline $BASE..HEAD`
   - Commits with "Assisted-by:" trailer: `git log --grep='Assisted-by:' --oneline $BASE..HEAD`

4. If zero fix commits exist, verify the repo doesn't need any:
   - `go build ./...` — does it compile?
   - `go vet ./...` — any warnings?
   If both pass, the repo may genuinely need no fixes beyond
   the dependency bump itself. Report PASS with note.
   If either fails, report FAIL — fixes were needed but not
   applied.

Ignore stale vendor in gitignored directories
(`git check-ignore -q <dir>/vendor`) — these are expected and
not maintained by the rebase. Do NOT escalate gitignored vendor
staleness as a blocker.

Report total issues.

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
  "$REPO" step3-autofix-result PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
