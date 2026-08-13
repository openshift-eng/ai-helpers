Detect deprecated function and type usage via static analysis.
This catches deprecated-but-compiling code that go build and
go vet miss — the most common cause of gate failures.

Step 1 — Try staticcheck (most reliable):
  If `staticcheck` is available, run:
  `staticcheck -checks SA1019 ./... 2>&1`
  (add `-mod=vendor` to go flags if vendor/ exists)
  SA1019 detects calls to functions/types marked `// Deprecated:`
  in their source. This is the Go ecosystem's standard
  deprecation checker and catches ALL deprecated API usage
  including cross-module deprecations in vendor.

  If staticcheck is not installed, try:
  `go install honnef.co/go/tools/cmd/staticcheck@latest 2>/dev/null`

Step 2 — Non-standard deprecation scan:
  Some projects (notably OpenShift API) use `// DEPRECATED`
  instead of the Go-standard `// Deprecated:` format. SA1019
  misses these. Find deprecated declarations in vendor:
  `grep -rh -A2 '// Deprecated:\|// DEPRECATED' vendor/ --include='*.go' 2>/dev/null | grep -E '^\s*func |^\s*type |^\s*var |^\s*const ' | grep -oP '(?<!\w)(?:func|type|var|const)\s+\K\w+' | sort -u`
  This looks at the lines AFTER the deprecation comment to find
  the actual declaration name. For each deprecated symbol, check
  non-vendor usage:
  `grep -rn '<symbol>' --include='*.go' . | grep -v vendor/ | grep -v .cache/`

Step 3 — Fallback (if staticcheck unavailable and no vendor):
  Use `go vet ./...` as a minimal check. It won't catch
  deprecated APIs but will catch format string issues and
  other vet-detectable problems.

Find module directories:
  `find . -name go.mod -not -path '*/vendor/*' -exec dirname {} \;`

Run the check in each module directory.

Report each deprecated call with file:line and what to replace
it with (if the deprecation comment says). FAIL if any NEW
deprecated calls exist. PASS if clean or only pre-existing.
SKIP if neither staticcheck nor Go is available.

MANDATORY pre-existing check — run for EVERY finding before
counting it:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file>:<line> with <symbol>:
base_has=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<symbol>')
# If base_has > 0, the issue is PRE-EXISTING — do NOT count it
```

If the deprecated call exists on the base branch, it is
pre-existing — report as "INFO (pre-existing)" but do NOT
include in the ISSUES count. Only calls NOT on the base branch
are NEW and count toward FAIL. If ALL findings are pre-existing,
verdict MUST be PASS.

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
  "$REPO" step3-deprecated-calls PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
