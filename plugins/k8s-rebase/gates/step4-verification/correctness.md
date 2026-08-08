This gate owns mechanical correctness checks that other gates
do NOT cover. Do not duplicate semantic review (logical-consistency
handles that). Focus on these unique checks:

1. Change classification: For each non-vendor commit on the
   rebase branch (`git log --oneline <merge-base>..HEAD`),
   verify the change is required by the rebase. Valid changes:
   version bumps, type conversions, API renames, format string
   fixes, import reordering, codegen output, feature gates,
   deprecated API migrations, dead code removal from stricter
   linters, and any pattern documented in the patterns doc
   (find k8s-rebase-patterns.md). Flag anything else as suspect.
2. Format strings: Scan ALL non-vendor Go files changed in the
   diff for wrong format verbs (e.g., %d for a string, %s for
   an int). Run: `git diff <merge-base>..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' | grep '^\+.*fmt\.\|^\+.*Sprintf\|^\+.*Fprintf\|^\+.*Errorf' | head -30`
3. Eventf calls: Check for bare .Error() args without format
   directives. Run: `grep -rn '\.Eventf\|\.Event(' --include='*.go' . | grep -v vendor/ | grep '\.Error()' | head -20`
4. Test assertion weakening: Check if `assert.Equal` was changed
   to `assert.EqualValues` in the diff. Prefer updating expected
   value literals to match new types over weakening the assertion.
   Run: `git diff $(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)..HEAD -- '*_test.go' | grep -E '^\-.*assert\.Equal\b|^\+.*assert\.EqualValues' | head -20`
   Flag new EqualValues introductions for review. Pre-existing
   EqualValues usage (on the base branch) is excluded.

Report per-commit findings and current-code scan results.

MANDATORY pre-existing check — run for EVERY finding:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file> with <pattern>:
base_has=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<pattern>')
# If base_has > 0, the issue is PRE-EXISTING — do NOT count it
```

If the issue exists on the base branch, it is pre-existing —
report as "INFO (pre-existing)" but do NOT include in the ISSUES
count. Only issues NOT on the base branch are NEW and count
toward FAIL. If ALL findings are pre-existing, verdict MUST be
PASS.

VERDICT: FAIL if any NEW remaining bug is found in fix commits
(wrong logic, data loss, missing error handling). PASS if all
fix commits are correct or all findings are pre-existing.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific counts, not "looks good." You are
read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. For each wrong format verb, report the correct one. Cite file:line for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step4-correctness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
