MANDATORY FIRST STEP — run the companion gate script:

```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -path "*/k8s-rebase/gates/step3-autofix" -type d 2>/dev/null | head -1)
bash "$GATE_DIR/major-version-imports.sh" "$(pwd)"
```

Read the output carefully. Apply these rules in order:

RULE 1 — FAST-PATH: If NEW_ISSUES=0, set verdict=PASS immediately.
Write the PASS report and stop. Do NOT run the checks below.

RULE 2 — PER-ISSUE FILTER (when NEW_ISSUES>0): Only analyze issues
the script marked as "NEW". Ignore "PRE-EXISTING" lines.

If the companion script is not found, fall back to manual checks:

Check for stale major-version Go module imports. These are
entire module path changes where v1 is abandoned in favor of
v2+ — NOT deprecated symbols (those are caught by other gates).

MANDATORY first action — run these before any analysis:
  `grep -rn '"k8s.io/klog"' --include='*.go' . | grep -v vendor/ | grep -v .cache/ | grep -v '/v2'`
If that produces ANY output, count those as FAIL findings
immediately (file:line details required). Do NOT skip this step.

Step 1 — Discover major-version modules from go.mod:
  `grep -E '/v[0-9]+' go.mod | grep -v '^//' | sed 's|.*\([a-z].*\/v[0-9]*\).*|\1|' | sort -u`
  For each versioned module path (e.g., k8s.io/klog/v2), check
  if non-vendor code still imports the unversioned path:
  `grep -rn '"k8s.io/klog"' --include='*.go' . | grep -v vendor/ | grep -v .cache/ | grep -v '/v2'`

Step 2 — Check go.mod require lines:
  `grep -E 'require' go.mod`
  Look for any direct dependency that uses a pre-v2 path when
  a v2+ version is available. Cross-reference with vendor/:
  `find vendor/ -type d -regex '.*/v[0-9]+$' | sort`

Report each stale import with file:line AND the correct
versioned path (e.g., k8s.io/klog -> k8s.io/klog/v2).

For each finding, check the base branch:
  `BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`
  `git show $BASE:<file> 2>/dev/null | grep -c '<bare-import>'`
If the same stale import exists on the base branch, it is
pre-existing — report as INFO but do NOT count toward FAIL.
Only imports introduced by the rebase trigger FAIL.

FAIL if any NEW stale imports remain. PASS if clean or
only pre-existing. If no major-version deps, PASS.

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
  "$REPO" step3-major-version-imports PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
