EVIDENCE (read before judging): if `.rebase-tmp/gates/step4-go-version-check.evidence` exists,
run `git rev-parse HEAD` and compare it to the file's `HEAD:` line.
- Match: Read the file first and treat its `SUMMARY:`/facts as ground truth for this gate.
- Differ or file absent: evidence is stale/missing — judge from scratch using the checks
  below. Do NOT PASS on the strength of absent or stale evidence.

When evidence is fresh: if SUMMARY shows 0 Go version issues, skip
the manual checks below and write PASS. When NEW_ISSUES > 0: analyze
all detail lines in the evidence — the script excludes pre-existing
references and version-correct references at collection time so every
detail line is a version mismatch in a branch-modified file.
There are no "PRE-EXISTING" lines in the evidence file.

If evidence is stale or absent, fall back to manual checks:

The rebase bumped the Go version. Verify consistency across
the repo and check for implications.

1. go directive: are all go.mod files at the same Go version?
   git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD -- '*/go.mod' 'go.mod' | grep '^[+-]go '

2. toolchain directive: was it added, removed, or changed?
   git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD -- '*/go.mod' 'go.mod' | grep '^[+-]toolchain'

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

MANDATORY pre-existing check: For each Makefile/Dockerfile finding,
check the base branch before counting:
  BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
  modified=$(git diff --name-only "$BASE"..HEAD -- "<file>" | wc -l)
  If modified==0: PRE-EXISTING (file not touched by this branch) — do NOT count.
  If modified>0: NEW (rebase touched this file; any remaining Go version mismatch
  should have been updated). Do NOT use "version string appears on base" as a
  pre-existing signal — the old Go version WAS correct on base; its presence there
  does not make a post-bump mismatch pre-existing.
  If ALL findings are in unmodified files, verdict MUST be PASS with 0 issues.

VERDICT criteria: FAIL if go.mod files have inconsistent Go
versions, or Makefiles/Dockerfiles use a Go version that
doesn't match go.mod AND the mismatch is NEW (not present on
the base branch). Migration opportunities (x/ packages,
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
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step4-go-version-check PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
