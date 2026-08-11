Determine the previous k8s version: read the base branch's primary go.mod
(`BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1; git show "$BASE:<path>"`),
the first non-vendor go.mod that requires k8s.io/api, which may be nested
(for example `go-controller/go.mod`), and extract the k8s.io/api version.
If unavailable, derive from the target version (if target is 1.NN,
previous is 1.NN-1).

Count stale version refs from the PREVIOUS k8s version only.
Check yml/yaml/sh/Makefile/Dockerfile files (go.mod and .go
files are covered by go-version-check and compilation gates).
Also inspect runnable commands in Markdown/code blocks. For example,
`setup-envtest use 1.x.y` selects Kubernetes test-server binaries, not the
independently versioned setup-envtest tool. Trace the consumer before excluding
an old version as prose or a tool tag.
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

For OpenShift consumers, also inspect `.ci-operator.yaml` and Dockerfiles
for `openshift-X.Y` and `ocp/X.Y:` streams. Compare with the mapped target
release and that repository's target-branch CI configuration. First identify
the image's role: a Go builder or RHEL base image does not select the Kubernetes
API version linked into the application. Neither the dependency-branch mapping
nor CI's cluster integration stream requires matching builder/base labels.
To call a reference stale, identify the actual unmet requirement (for example,
an insufficient Go version, a Kubernetes test-server version, or an image
explicitly required by the target build configuration). An older stream can
remain valid when the target branch explicitly uses those exact references, its retained
CI image-build evidence confirms them, and their toolchain/base requirements
still satisfy the rebased project. Cite the configuration, CI revision/job,
image references, and target Go floor. This establishes the reference choice,
not a successful image build or cluster test of the rebased candidate.

OpenShift release automation (ART) owns many repositories' builder and base
references. Check `git log --format='%h %an %s' -- <file>`: commits by
`AOS Automation Release Team` or subjects containing `consistent with ART`
mean ART reconciles that file from ocp-build-data. Retain those references
unless the rebase raises the Go minor above the image's Go version; cite the
ART commit and the unchanged Go floor. This is sufficient support for
retention without image-build evidence, and a rebase must not preempt ART's
stream update.

When a replacement is required, verify that it exists. Check this even if Go
is unchanged; unchanged source alone does not justify retaining a reference.
An unavailable image or unresolved release configuration is missing verification: report it
as INCONCLUSIVE rather than inventing a tag or calling the check passed.
List every applicable image reference with its base stream, target stream,
replacement verification or supported retention, and file:line. If an older
stream lacks the target-branch/toolchain evidence above, it remains unresolved:
use FAIL when the required replacement is verified and still missing, or
INCONCLUSIVE when the replacement cannot be verified. This image-specific rule
takes precedence over the general stale-reference count below. Neither case is PASS.

MANDATORY pre-existing check — run for EVERY finding before
counting it. Skip this check and your verdict is WRONG.

```bash
BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1
git show "$BASE:<file>"
git show "$BASE:<primary-go.mod-path>"
# Compare whether the reference was valid for the BASE dependencies/config
# and whether the requested target makes it stale now.
```

A reference that was correct for the base but is stale for the requested
target is NEW, including in an unmodified file: omission is a rebase defect.
Count older unrelated debt as INFO. Neither an unchanged file nor the old
version string's presence on base proves the finding was pre-existing.

For each verified stale reference, report the file:line, replacement, and
supporting evidence so the gate-fix loop can apply it. An image candidate
whose existence is unverified is missing evidence, not an edit instruction:
keep it INCONCLUSIVE and retain the existing reference until verified.

Report count of NEW genuinely stale previous-version references
plus count of un-bumped Makefile version variables.

VERDICT: FAIL if either count is nonzero; INCONCLUSIVE if applicable target
or image verification could not complete; otherwise PASS.

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
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
bash "${PLUGIN_ROOT}/scripts/write-gate-report.sh" \
  "$REPO" step4-version-completeness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
