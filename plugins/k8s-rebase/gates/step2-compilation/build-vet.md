EVIDENCE (read before judging): if `.rebase-tmp/gates/step2-build-vet.evidence` exists,
run `git rev-parse HEAD` and compare it to the file's `HEAD:` line.

- Match: Read the file first and treat its `SUMMARY:`/facts as ground truth for this gate.
  If the summary appears inconsistent with what you know about this repo (e.g., reports
  0 modules checked in a multi-module repo), run the manual checks below instead.

- Differ or file absent: evidence is stale/missing — judge from scratch using the checks
  below. Do NOT PASS on the strength of absent or stale evidence.

Before accepting a fresh zero count, account for every module: checked or
explicitly excluded. A `VET_TIMEOUT` detail or companion crash means the run
was incomplete, even when SUMMARY says 0 errors. Run the incomplete checks
and any unvisited modules manually below; if they cannot complete, report
INCONCLUSIVE with the missing coverage. A timeout does not establish a code defect.
Read each command's `RESULT` exit even when there are no diagnostic lines.
A nonzero exit without enough evidence to attribute the failure is
INCONCLUSIVE, never a zero-error PASS; retain the failure and investigate it.

For each BUILD or VET diagnostic (format: `BUILD <mod_dir>: <error>` or
`VET <mod_dir>: <error>`), decide whether the rebase introduced it:

- On a line the branch changed: NEW.
- On an unchanged line: NEW if the dependency API it uses changed, or, for
  VET, if the Go version bump added the check. A dependency API removal
  breaks unmodified callers, so check the whole vendored package on base,
  not the caller's source:

  ```bash
  BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1
  git grep -c '<symbol>' "$BASE" -- '<mod_dir>/vendor/<pkg>/'
  # matches: the symbol existed before the bump, so the error is NEW
  ```

- Otherwise PRE-EXISTING: report as INFO, not toward FAIL.

If you cannot tell which case applies, report INCONCLUSIVE rather than
assuming the error was pre-existing.

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
  build_rc=0
  (cd "$mod_dir" && go build ./... 2>&1) || build_rc=$?
  vet_rc=0
  (cd "$mod_dir" && go vet ./... 2>&1) || vet_rc=$?
  printf 'RESULT %s: build=%s vet=%s\n' "$mod_dir" "$build_rc" "$vet_rc"
done
```

Do NOT run build/vet on modules you skipped — their vendor is
stale and will produce false errors. Use `podman run --userns=keep-id`
with the golang container if the local Go version is too old.
Count errors: each module where `go build` or `go vet` exits
non-zero is 1 error. Report the total across all non-skipped
modules.

PASS requires completed checks with no new build/vet errors. Keep exclusions
and pre-existing findings in the report; missing coverage is not a zero count.

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
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
bash "${PLUGIN_ROOT}/scripts/write-gate-report.sh" \
  "$REPO" step2-build-vet PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
