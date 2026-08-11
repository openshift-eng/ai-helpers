Determine the previous k8s version: read go.mod on the base
branch (`git show $(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main):go.mod`)
and extract the k8s.io/api version. If unavailable, derive from
the target version (if target is 1.NN, previous is 1.NN-1).

Count stale version refs from the PREVIOUS k8s version only.
Check yml/yaml/sh/Makefile/Dockerfile files (go.mod and .go
files are covered by go-version-check and compilation gates).
Exclude:
- K8S_VERSION if the kindest/node image isn't published yet
- Lines where the version appears in prose (comments starting
  with //, #, or lines in README/CHANGELOG files) that are not
  assignments or image tags
- References inside vendor/ directories
- Ancient versions (1.16, 1.20, etc.) — those are pre-existing
  documentation debt, not rebase issues

Also check Makefile variable assignments (VAR ?=, VAR :=, VAR =)
for version-bearing variables: K8S_VERSION, GOLANG_VERSION,
GOLANGCI_LINT_VERSION, KIND_VERSION, KUSTOMIZE_VERSION. Also
grep for any `*_VERSION` or `*_VER` Makefile variable containing
the previous minor version number. Flag any that still reference
the previous k8s minor version or a Go version that does not
match the target release's Go toolchain.

MANDATORY pre-existing check — run for EVERY finding before
counting it. Skip this check and your verdict is WRONG.

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# Was this file modified by the rebase branch?
modified=$(git diff --name-only "$BASE"..HEAD -- "<file>" | wc -l)
# If modified==0: PRE-EXISTING (file untouched by this branch; stale ref predates rebase)
# If modified>0: NEW (rebase touched this file; any remaining stale ref should have been updated)
```

A finding is NEW only if the file was modified by this branch.
Do NOT use "old version string appears on base" as a pre-existing
signal — on the base branch, the old version WAS the current version
and was correctly set; its presence there does not make a stale ref
pre-existing. If ALL findings are in unmodified files, verdict MUST
be PASS with 0 issues.

For each stale reference, report the file:line and what the
correct value should be (the target k8s minor version).
This enables the gate-fix loop to sed-replace them.

Report count of NEW genuinely stale previous-version references
plus count of un-bumped Makefile version variables.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
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
  "$REPO" step4-version-completeness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
