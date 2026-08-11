MANDATORY FIRST STEP — run the companion gate script:

```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -path "*/k8s-rebase/gates/step2-compilation" -type d 2>/dev/null | head -1)
bash "$GATE_DIR/build-vet.sh" "$(pwd)"
```

Read the output carefully. Apply these rules in order:

RULE 1 — FAST-PATH: If NEW_ISSUES=0, set verdict=PASS immediately.
Write the PASS report and stop. Do NOT run the checks below.

RULE 2 — PER-ISSUE FILTER (when NEW_ISSUES>0): Only analyze issues
the script marked as "NEW". Ignore "PRE-EXISTING" lines. For each
NEW issue, determine if it is a real problem or a false positive.

If the companion script is not found, fall back to running the
checks manually:

Run `go build ./...` and `go vet ./...` in each module.
Use this exact loop to find modules and skip gitignored vendors:

```bash
for mod_dir in $(find . -name "go.mod" -not -path "*/vendor/*" -exec dirname {} \; | sort); do
  if [[ -d "$mod_dir/vendor" ]] && git check-ignore -q "$mod_dir/vendor" 2>/dev/null; then
    echo "SKIP $mod_dir (vendor is gitignored)"
    continue
  fi
  echo "CHECK $mod_dir"
  (cd "$mod_dir" && go build ./... 2>&1 && go vet ./... 2>&1)
  # Count errors: non-zero exit = build or vet failed
done
```

Do NOT run build/vet on modules you skipped — their vendor is
stale and will produce false errors. Use `podman run --userns=keep-id`
with the golang container if the local Go version is too old.
Count errors: each module where `go build` or `go vet` exits
non-zero is 1 error. Report the total across all non-skipped
modules.

For pre-existing issues: if the base branch also fails the same
build/vet check, report those errors as INFO (pre-existing) and
only count NEW errors introduced by the rebase toward FAIL.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific counts, not "looks good." You are
read-only — do not edit repo files. Your sole permitted write
is your gate report file under .rebase-tmp/gates/. Do not write
anywhere else. Cite file:line for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step2-build-vet PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
