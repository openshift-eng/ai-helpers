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

Run this check FIRST — if nothing matches, SKIP immediately:
```bash
REPO="<the repo path from the first line of your prompt>"
E2E_FILES=$(grep -rln 'kindest/node\|K8S_VERSION\|KIND_VERSION\|kind-common\|e2e-kind\|install-kind' "$REPO" --include='*.sh' --include='*.yaml' --include='*.yml' --include='*.j2' --include='kind-common' 2>/dev/null | grep -v vendor/ | head -20)
if [ -z "$E2E_FILES" ]; then
  echo "No e2e infrastructure files found — SKIP"
fi
```
If no e2e infrastructure files exist, write a SKIP report and stop.

MANDATORY pre-existing check — run for EVERY finding:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file> with <version_string>:
base_has=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<version_string>')
# If base_has > 0, PRE-EXISTING — do NOT count it
```

If a version issue exists on the base branch, report as "INFO
(pre-existing)" and do NOT include in ISSUES. Only issues NOT
on base are NEW. If ALL findings are pre-existing, verdict MUST
be PASS.

VERDICT: FAIL only if NEW e2e infrastructure issues exist (not
on base branch). PASS if all issues are pre-existing or all
e2e infra is consistent.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line
for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
if [ -n "$SCRIPT" ]; then
  bash "$SCRIPT" "$REPO" step3-e2e-infra PASS 0 "your one-line summary" \
    "detail line 1" "detail line 2"
else
  mkdir -p "$REPO/.rebase-tmp/gates"
  printf 'VERDICT: PASS\nISSUES: 0\nSUMMARY: your one-line summary\nDETAILS:\ndetail line 1\ndetail line 2\n' \
    > "$REPO/.rebase-tmp/gates/step3-e2e-infra.report"
fi
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
