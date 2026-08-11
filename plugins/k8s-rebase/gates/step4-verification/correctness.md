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
   (`find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-patterns.md" -path "*/k8s-rebase/*" 2>/dev/null | head -1`). Flag anything else as suspect.
2. Format strings: Scan ALL non-vendor Go files changed in the
   diff for wrong format verbs (e.g., %d for a string, %s for
   an int). Run:
   ```
   total=$(git diff <merge-base>..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' | grep -c '^\+.*fmt\.\|^\+.*Sprintf\|^\+.*Fprintf\|^\+.*Errorf' 2>/dev/null || echo 0)
   echo "Total format-string hits: $total"
   git diff <merge-base>..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' | grep '^\+.*fmt\.\|^\+.*Sprintf\|^\+.*Fprintf\|^\+.*Errorf' | head -30
   ```
   If total > 30, re-run without `head -30` and examine all $total lines before proceeding.
3. Eventf calls: Check for bare .Error() args without format
   directives. Run:
   ```
   total=$(grep -rn '\.Eventf\|\.Event(' --include='*.go' . | grep -v vendor/ | grep -c '\.Error()' 2>/dev/null || echo 0)
   echo "Total Eventf/.Error() hits: $total"
   grep -rn '\.Eventf\|\.Event(' --include='*.go' . | grep -v vendor/ | grep '\.Error()' | head -20
   ```
   If total > 20, re-run without `head -20` and examine all $total lines before proceeding.
4. Test assertion weakening: Check if `assert.Equal` was changed
   to `assert.EqualValues` in the diff. Prefer updating expected
   value literals to match new types over weakening the assertion.
   Run: `git diff $(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)..HEAD -- '*_test.go' | grep -E '^\-.*assert\.Equal\b|^\+.*assert\.EqualValues' | head -20`
   Flag new EqualValues introductions as INFO in DETAILS — do NOT
   count toward FAIL unless the change demonstrably loses type
   precision that would hide a real bug. Pre-existing EqualValues
   usage (on the base branch) is already excluded by the diff filter.
5. Map key format after API renames: When the diff changes how map
   keys are constructed from renamed struct fields (e.g., adding
   namespace qualification to a formerly simple name string), verify
   ALL consumers of that map still use the same key format. Run:
   ```
   git diff <merge-base>..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' | grep '^\+.*\[.*\+.*\]' | head -20
   ```
   For each new map write, find the corresponding lookup site (grep
   for the map variable name) and confirm the lookup key format
   matches. Flag any producer/consumer key format mismatch as FAIL —
   these cause silent runtime data loss (lookup always misses).

Report per-commit findings and current-code scan results.

MANDATORY pre-existing check — run for EVERY finding:

For check 3 (Eventf/Event scan — repo-wide grep, additive):
```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file> with <pattern>:
base_count=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<pattern>')
curr_count=$(grep -c '<pattern>' "<file>" 2>/dev/null)
net_new=$(( curr_count > base_count ? curr_count - base_count : 0 ))
# Only net_new > 0 occurrences count toward FAIL
```

For checks 1 and 2 (diff-scoped via `git diff | grep '^\+'`): the diff
already restricts scope to new lines — no base-file grep needed.

If ALL findings are pre-existing (net_new == 0 for check 3, no `+`
lines for checks 1+2), verdict MUST be PASS.

VERDICT: FAIL if any NEW remaining bug is found in fix commits
(wrong logic, data loss, missing error handling). PASS if all
fix commits are correct or all findings are pre-existing.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
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
