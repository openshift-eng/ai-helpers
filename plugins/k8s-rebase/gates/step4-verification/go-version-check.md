<!-- markdownlint-disable MD013 -->
EVIDENCE (read before judging): if `.rebase-tmp/gates/step4-go-version-check.evidence` exists,
run `git rev-parse HEAD` and compare it to the file's `HEAD:` line.

- Match: Read the file first and treat its `SUMMARY:`/facts as ground truth for this gate.
- Differ or file absent: evidence is stale/missing — judge from scratch using the checks
  below. Do NOT PASS on the strength of absent or stale evidence.

When evidence is fresh: if SUMMARY shows 0 Go version issues, skip
the manual checks below and write PASS. When NEW_ISSUES > 0: analyze
the `NEW MISMATCH:` detail lines. `INFO PRE-EXISTING:` lines and the
base/result Go directives provide context and do not increase the count.

If evidence is stale or absent, fall back to manual checks:

First compare the base and result Go directives; dependency changes in
go.mod do not establish a Go version bump. Verify consistency across
the repo and check the implications of any actual directive change.

1. go directive: are all go.mod files at the same Go version?
   BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1; git diff "$BASE"..HEAD -- '*/go.mod' 'go.mod' | grep '^[+-]go '

2. toolchain directive: was it added, removed, or changed?
   BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1; git diff "$BASE"..HEAD -- '*/go.mod' 'go.mod' | grep '^[+-]toolchain'

3. Makefiles: do all GO_VERSION / GOLANG_VERSION vars match?
   grep -rn 'GO_VERSION.*=\|GOLANG_VERSION.*=' --include='Makefile*' . | grep -v vendor

4. Dockerfiles: do all golang: image tags and Go version ARGs match?
   grep -rn 'golang:' --include='Dockerfile*' . | grep -v vendor
   grep -rn 'GOVERSION\|GO_VERSION' --include='Dockerfile*' . | grep -v vendor

5. CI workflows: do they use go-version-file (dynamic) or
   hardcoded versions?
   grep -rn 'go-version' --include='*.yml' --include='*.yaml' .github/

6. x/ package opportunities: this is checked by the
   deprecated-imports gate — do not duplicate that check here.
   Just note the Go version bump and its implications for
   stdlib additions.

MANDATORY pre-existing check: For each module, Makefile, Dockerfile, or
workflow finding, compare the actual directives and reference versions
on the base branch before counting. Use the reference's nearest enclosing
module; repository-level references use the primary module. Check every
literal workflow matrix entry, including entries after the first:
  BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1
  git show "$BASE:<owning-go.mod-path>"
  git show "$BASE:<file>"

- A reference already mismatched on base is PRE-EXISTING when its version is
  unchanged, even if dependencies or other content in its file changed.
- A reference valid on base that becomes stale after an actual Go directive
  bump is NEW, including in an unmodified file.
- An added or changed stale reference is NEW. A new occurrence cannot inherit
  the pre-existing status of an older occurrence in the same file.
- Inconsistent module directives are pre-existing when those directives are
  unchanged; editing their dependency requirements alone does not make the
  inconsistency new.

VERDICT criteria: FAIL for NEW inconsistent Go directives, NEW
Makefile/Dockerfile version mismatches, or NEW workflow Go versions below
the go.mod minimum. Workflow matrices may exercise newer Go versions.
Migration opportunities (x/ packages,
CI workflow improvements) are informational — report them
in DETAILS but do not FAIL for them alone.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else.

After your analysis, write your report using the helper script.
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
bash "${PLUGIN_ROOT}/scripts/write-gate-report.sh" \
  "$REPO" step4-go-version-check PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
