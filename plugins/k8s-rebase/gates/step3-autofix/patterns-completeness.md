EVIDENCE (read before judging): if `.rebase-tmp/gates/step3-patterns-completeness.evidence` exists,
run `git rev-parse HEAD` and compare it to the file's `HEAD:` line.
- Match: Read the file first and treat its `SUMMARY:`/facts as ground truth for this gate.
- Differ or file absent: evidence is stale/missing — judge from scratch using the checks
  below. Do NOT PASS on the strength of absent or stale evidence.

Read the evidence. If SUMMARY shows 0 issues and all modules report
BUILD-OK, verdict is PASS. If SUMMARY shows issues or any module
reports BUILD-FAIL, proceed to the checks below using the evidence
as the source of findings.

If evidence is stale or absent, run the checks below from scratch.

--- Checks ---

1. Build verification (primary check):
   Find modules: `find . -name go.mod -not -path '*/vendor/*' -exec dirname {} \;`
   In each: `go build ./... 2>&1` (add `-mod=vendor` if vendor/ exists)
   Any build error means an incomplete transformation. Report
   each error with file:line.

2. Import consistency:
   `git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' | grep '^[+-].*"' | grep -v '^\+\+\+\|^---'`
   Check if any import was added that has a newer version in
   vendor/ (e.g., importing v1 when vendor has v2).

3. Struct field completeness:
   For each non-vendor Go file changed in the diff, check if
   it constructs structs from vendor/k8s.io/ types. If a struct
   literal has fields that were renamed or removed in vendor,
   the build check (step 1) catches it. Focus on fields that
   were ADDED in vendor but not populated in the constructor
   (these compile fine but may be semantically wrong).

4. If a patterns doc exists, cross-reference:
   `find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-patterns.md" -path "*/k8s-rebase/docs/*" 2>/dev/null | head -1`
   If found, read it and check any pattern not covered by
   sibling gates. If not found, rely on steps 1-3 above.

CRITICAL: If `go build` returns ANY error, the verdict is FAIL.
Never attribute build failures to caching — run `go clean -cache`
first if you suspect stale cache. Build errors are real regressions.

MANDATORY pre-existing check for ALL non-build findings. Run this
BEFORE reporting ANY finding from checks 2, 3, or 4:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file>:<line>, check base branch:
base_count=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<pattern>')
curr_count=$(grep -c '<pattern>' "<file>")
# NEW only if curr_count > base_count
```

If the finding exists on the base branch (base_count > 0 and
base_count >= curr_count), it is PRE-EXISTING — report as
"INFO (pre-existing)" and do NOT count in ISSUES. Only findings
where curr_count > base_count (or file doesn't exist on base)
are NEW and count toward FAIL.

VERDICT: FAIL if any build error or rebase-introduced issue
exists. PASS if build succeeds and no NEW issues found.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
if [ -n "$SCRIPT" ]; then
  bash "$SCRIPT" "$REPO" step3-patterns-completeness PASS 0 "your one-line summary" \
    "detail line 1" "detail line 2"
else
  mkdir -p "$REPO/.rebase-tmp/gates"
  printf 'VERDICT: PASS\nISSUES: 0\nSUMMARY: your one-line summary\nDETAILS:\ndetail line 1\ndetail line 2\n' \
    > "$REPO/.rebase-tmp/gates/step3-patterns-completeness.report"
fi
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
