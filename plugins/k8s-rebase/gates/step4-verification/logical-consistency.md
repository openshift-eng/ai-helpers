Read ALL fix commits (autofix + agent). For EVERY function
modified in the diff, read the full function body and trace
data flow. Do not skip or sample — check every modified function.

Flag:
- Struct copies that drop fields (FAIL)
- Error values checked in one path but ignored in another (FAIL)
- Fields set but never read — verify usage across the full module
  (`grep -rn '<field>' --include='*.go' . | grep -v vendor/`)
  before flagging. Only FAIL if truly unused repo-wide. (FAIL)
- Fields compared in one code path but not another (FAIL)
- Incomplete transformations: if a fix commit changed a pattern
  in some places but the same pattern remains elsewhere in the
  modified files, grep for the old pattern and flag each instance
  with file:line. Any single remaining instance is a finding. (FAIL)
- Variables assigned but never used (INFO — compiler catches these, do not count toward FAIL)

Scope: flag issues WITHIN modified functions or files — not
unrelated code. Code removed in the diff may reflect upstream
changes — check the current file state, not just the diff.

The autofix applies documented patterns that are intentionally
targeted changes. Do not flag autofix patterns as incomplete
unless the autofix demonstrably missed instances in files it
touched.

List EVERY function you checked and your finding for each. Do
not just say "no issues" — show what you traced. This is the
primary correctness gate — thoroughness matters more than speed.

For each finding, check the base branch:
  `BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`
  `git show $BASE:<file> 2>/dev/null | grep -c '<pattern>'`
If the same issue exists on the base branch, it is pre-existing —
report as INFO but do NOT count toward FAIL. Only issues
introduced by the rebase trigger FAIL.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. For each issue, state the specific
fix needed. Cite file:line.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step4-logical-consistency PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
