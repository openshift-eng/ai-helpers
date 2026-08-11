EVIDENCE (read before judging): if `.rebase-tmp/gates/step2-build-vet.evidence` exists,
run `git rev-parse HEAD` and compare it to the file's `HEAD:` line.
- Match: Read the file first and treat its `SUMMARY:`/facts as ground truth for this gate.
  If the summary appears inconsistent with what you know about this repo (e.g., reports
  0 modules checked in a multi-module repo), run the manual checks below instead.
- Differ or file absent: evidence is stale/missing — judge from scratch using the checks
  below. Do NOT PASS on the strength of absent or stale evidence.

When evidence is fresh: if SUMMARY shows 0 errors, verdict is PASS. If SUMMARY shows
errors, analyze each BUILD or VET line in the evidence (format: 'BUILD <mod_dir>: <error>'
or 'VET <mod_dir>: <error>'). For each error, determine
whether it was introduced by the rebase or was pre-existing:

```bash
BASE=$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)
# For a compile error referencing <missing_symbol> in a vendored package:
git show "$BASE:vendor/<pkg>/<file>.go" 2>/dev/null | grep -c '<missing_symbol>'
# > 0: symbol existed before → rebase removed it → error is NEW
# == 0: symbol was already absent → error is PRE-EXISTING
```

Do NOT treat "source file is present on base" as proof the error is pre-existing.
A dependency API removal breaks unmodified source files — the source file exists on
base but the vendored API it calls was removed by the bump. Check vendor, not source.
Count only errors newly introduced by the rebase. Pre-existing errors: report as
INFO (pre-existing) and do NOT count toward FAIL.

If evidence is stale or absent, run these checks manually:

Run `go build ./...` and `go vet ./...` in each module.
Use this exact loop to find modules and skip gitignored vendors:

```bash
for mod_dir in $(find . -name "go.mod" -not -path "*/vendor/*" -exec dirname {} \; | sort); do
  if [[ -d "$mod_dir/vendor" ]] && git check-ignore -q "$mod_dir/vendor" 2>/dev/null; then
    echo "SKIP $mod_dir (vendor is gitignored)"
    continue
  fi
  echo "CHECK $mod_dir"
  (cd "$mod_dir" && go build ./... 2>&1)
  (cd "$mod_dir" && go vet ./... 2>&1)
  # Count errors: non-zero exit from either command = issue found
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

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

When your report hints at fixing a renamed API symbol, include this hint:
`grep -rn 'OldSymbolName' --include='*.go' .` to find ALL call sites — do not assume one location covers all uses.

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
