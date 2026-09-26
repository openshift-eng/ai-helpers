If e2e infrastructure was modified (kind-common or kind-common.sh, kind.yaml.j2,
e2e-kind.sh, install-kind.sh, CI workflows), verify the changes
are consistent with the target k8s version.

For each modified e2e file, check:

- Do version references (k8s version strings, kindest/node tags)
  match the target version from go.mod?
  `grep -rn 'kindest/node\|K8S_VERSION\|KIND_VERSION' . | grep -v vendor/`

- KIND binary version: search the web for "kind releases" to
  find which KIND version supports the target k8s version.
  Each KIND release supports specific k8s versions — using an
  old KIND with a new k8s will fail. Report the fix command:
  `sed -i 's/KIND_VERSION=v<old>/KIND_VERSION=v<new>/' <file>`

- Are external tool versions consistent across all CI files?
- CI dependency versions (MetalLB, KubeVirt, etc.): k8s version
  bumps tighten CRD validation. Check pinned versions:
  `grep -rn 'metallb_version\|KUBEVIRT_VERSION' . --include='*.sh' --include='*.yaml' --include='*.yml' | grep -v vendor/`
  If a pinned version predates the target k8s release, its CRDs
  may fail stricter validation (schema constraints, required
  fields, enum values). Search the web for the latest release of
  each dependency and compare with the pinned version.

- Do configuration formats (e.g., kubeadm config apiVersion)
  match what the new k8s version requires? Search the web for
  "k8s <version> kubeadm config" if unsure about required format.

List each item checked and whether it passes. Report issues.

Run this check FIRST — if nothing matches, write a SKIP report and stop:

```bash
REPO="<the absolute repo path from reviewer context>"
E2E_FILES=$(grep -rln 'kindest/node\|K8S_VERSION\|KIND_VERSION\|kind-common\|e2e-kind\|install-kind' "$REPO" --include='*.sh' --include='*.yaml' --include='*.yml' --include='*.j2' --include='kind-common' 2>/dev/null | grep -v vendor/ | head -20)
if [ -z "$E2E_FILES" ]; then
  echo "No e2e infrastructure files found — SKIP"
fi
```

If no e2e infrastructure files exist, write a SKIP report and stop.

MANDATORY pre-existing check — run for EVERY finding:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file> with a stale version string:
modified=$(git diff --name-only "$BASE"..HEAD -- "<file>" | wc -l)
# If modified==0: PRE-EXISTING (file not touched by this branch)
# If modified>0: NEW (rebase touched this file; stale version should have been updated)
```

Do NOT use "old version string appears on base" as the pre-existing
signal — the old version WAS correct on base, so it appears in every
file. Only files MODIFIED by this branch are in scope.
If ALL findings are in unmodified files, verdict MUST be PASS.

VERDICT: FAIL only if NEW e2e infrastructure issues exist (not
on base branch). PASS if all issues are pre-existing or all
e2e infra is consistent.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line
for any issues.

After your analysis, write your report using the helper script.
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
SCRIPT="$PLUGIN_ROOT/scripts/write-gate-report.sh"
bash "$SCRIPT" "$REPO" step3-e2e-infra PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
