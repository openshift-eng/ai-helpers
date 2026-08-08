Identify fix commits (not rebase infrastructure):
  `git log --oneline $(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)..HEAD`
Skip commits that only touch go.mod/go.sum/vendor.
For each remaining commit's diff, check every Go function modified:

(a) Read the FULL function after the change (not just the diff).
(b) Trace every added statement — if a value is assigned, is it
    later read? If it's read in one code path, is it read in ALL
    paths?
(c) Check for logical gaps: a field set but not compared, a field
    compared but not propagated when the struct is copied, a
    variable assigned but never used.

Scope: flag a function as "partial" if the change is logically
inconsistent WITHIN the function (set-but-not-read, missing
error path, incomplete field mapping). Do not flag functions
just because callers weren't updated — that's a separate concern.
Check the current file state (not just the diff) to verify
deletions aren't pre-existing upstream changes.

List each function you checked and your finding. For each
finding, check the base branch:
  `BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`
  `git show $BASE:<file> 2>/dev/null | grep -c '<pattern>'`
If the same logical gap exists on the base branch, it is
pre-existing — report as INFO but do NOT count toward FAIL.

Count functions with genuinely NEW partial changes. FAIL if any
function has a logically incomplete change (count > 0). PASS if
all modified functions are logically consistent or only have
pre-existing issues.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific counts, not "looks good." You are
read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. For each partial change, describe the missing logic needed. Cite file:line for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step3-logical-completeness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
