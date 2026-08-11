Run this check FIRST — if nothing matches, SKIP immediately:
```bash
REPO="<the repo path from the first line of your prompt>"
FG_REFS=$(grep -rn 'KUBE_FEATURE_\|SetFromMap' "$REPO" --include='*.sh' --include='Makefile*' --include='*.go' 2>/dev/null | grep -v vendor/ | head -20)
if [ -z "$FG_REFS" ]; then
  echo "No feature gate references found — SKIP"
fi
```
If no SetFromMap or KUBE_FEATURE_ references exist, write a SKIP
report and stop.

If references ARE found: check if feature gates referenced in
test files (SetFromMap calls, os.Setenv/t.Setenv with
KUBE_FEATURE_ vars, shell script exports) still exist in
vendor/k8s.io/ (grep for the quoted gate name). Report any
gates that are referenced but missing from vendor.

Search the entire repo for KUBE_FEATURE_ references:
  `grep -rn 'KUBE_FEATURE_' --include='*.sh' --include='Makefile*' --include='*.go' "$REPO" | grep -v vendor/`
This covers shell exports, Makefile variables, AND Go code
(os.Setenv, t.Setenv, SetFromMap calls). Report count of
files with missing or stale gates.

MANDATORY pre-existing check — run for EVERY finding:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file> with <gate_name>:
base_has=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<gate_name>')
# If base_has > 0, PRE-EXISTING — do NOT count it
```

If the same gate issue exists on base, report as "INFO
(pre-existing)" and do NOT include in ISSUES. Only gate issues
NOT on base are NEW. If ALL findings are pre-existing, verdict
MUST be PASS.

VERDICT: FAIL if count of files with missing or stale feature
gates > 0 (excluding pre-existing). PASS if all feature gates
are current.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific counts, not "looks good." You are
read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line for any issues. For each missing gate, report the gate name and the fix needed.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
if [ -n "$SCRIPT" ]; then
  bash "$SCRIPT" "$REPO" step3-feature-gates PASS 0 "your one-line summary" \
    "detail line 1" "detail line 2"
else
  mkdir -p "$REPO/.rebase-tmp/gates"
  printf 'VERDICT: PASS\nISSUES: 0\nSUMMARY: your one-line summary\nDETAILS:\ndetail line 1\ndetail line 2\n' \
    > "$REPO/.rebase-tmp/gates/step3-feature-gates.report"
fi
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
