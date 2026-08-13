# Kubernetes Rebase Breakage Patterns

Common breakage patterns from k8s rebases. Update after each
rebase with new patterns discovered.

<!-- LINE BUDGET: 300. Trim version-specific content before
     adding new patterns. Run: wc -l docs/k8s-rebase-patterns.md -->

## Extending

When a rebase surfaces a new breakage pattern:

1. **Pattern Table** — add a row (one-liner: category, symptom,
   fix). This is the primary entry point; most patterns belong
   here and nowhere else.
2. **Detailed section below the table** — add a `### Title
   (recurring)` section only if the fix needs multi-step
   instructions, code examples, or caveats that cannot fit a
   single table row.
3. **`scripts/k8s-rebase.sh`** — only if the mechanical rebase
   needs changes (unlikely — it is version-generic).

**Criteria for inclusion:** patterns must be generic — they
apply (or could apply) to any Go project that vendors k8s.
If a fix only fires for one or two specific repos, put it in
that repo's `CLAUDE.md` or `AGENTS.md`, not here.

**How to discover patterns:** run the skill on a repo and
observe what breaks. Common sources: renamed/removed API
symbols, stricter `go vet` or lint checks, new default-true
feature gates, KIND/MetalLB/KubeVirt version skew, and
codegen output changes.

## Pattern Table

| Category | What breaks | How to fix |
| --- | --- | --- |
| Function renamed | `undefined: <OldName>` | Search-replace + import update |
| Signature changed | `too many/few arguments` | Add missing param (often logger) |
| Type divergence | `cannot use X as Y` | Convert ALL fields (check struct def) |
| go vet format string | `non-constant format string` | `"%v", err` (prefer `%v` over `"%s", err.Error()`) |
| go vet format type | `%q has arg of wrong type` | Use `%v` for non-string types |
| Deprecated API | `SA1019: X is deprecated` | Check vendored `// Deprecated:` comment |
| NewSimpleClientset | `SA1019` on generated fakes | Replace with `NewClientset` — check vendored source for `// Deprecated:` first (not all fakes deprecate it) |
| x/exp migration | `cannot find package "golang.org/x/exp/..."` | Migrate to stdlib `maps`/`slices`/`cmp` |
| govet inline analyzer | `inline: cannot inline <call>` | Disable `inline` analyzer in `.golangci.yml` (common fix); or fix call site if feasible. Only affects repos with govet `enable-all: true` |
| Nilness dead code | `nilness: impossible condition` | Remove dead `if err != nil` blocks |
| Codegen flag removed | `unknown flag: --bounding-dirs` | Remove flag from script, re-run codegen |
| Codegen field removed | `unknown field X in struct literal` | Remove field from Go code, re-run codegen |
| Feature gate (existing) | Tests hang (gate files exist) | Add new gate + dependents to existing setup |
| Feature gate (missing) | Tests hang (no gate setup) | Add `t.Setenv` for all gates to suite file |
| golangci-lint version | `Go language version...lower` | Bump VERSION in lint.sh AND test.yml |
| golangci-lint v1/v2 | v2 config rejected by v1 binary | Makefile may use v1 import path while lint.sh uses v2 container — update both if migrating |
| ST1005 error string casing | Lowercased error string breaks matching code | Before fixing ST1005, grep for the OLD error string in all Go files — update matches too |
| golangci-lint v1 + Go 1.26 | container image can't parse Go 1.26 | Replace Makefile no-op else with `go install @$(VERSION) && golangci-lint run` |
| CI builder image | `not found` for `golang-X.Y-openshift-Z.W` | New Go versions may only exist for newer OCP streams (e.g., 1.26 → openshift-5.0, not 4.22) |
| KIND binary version | e2e cluster creation fails | Bump KIND URL in install-kind.sh to latest |
| KubeVirt version | VM readiness timeouts in kv-live-migration CI | Bump to latest stable patch within same minor; nightly as last resort |
| MetalLB CRD validation | `Maximum boundary value must be of type integer` | Bump MetalLB version in e2e setup script; update FRR image variable separately |
| library-go interface | `does not implement SharedIndexInformer` | Bump library-go to latest; if still missing, use replace directive pointing to a fork (see Cross-repo dependency ordering below) |
| Snyk vendor scan | `ci/prow/security` fails (often pre-existing) | Check `.snyk` strategy: `vendor/**` glob is safe; per-file exclusions need updating |
| sudo PATH not preserved (often pre-existing) | `go: command not found` under sudo in CI scripts | In bash: `sudo env "PATH=$PATH" <cmd>` to preserve Go toolchain PATH |
| Transitive dep compat | `too many/few arguments` in `/go/pkg/mod/` path | Bump the dependency (`go get pkg@latest`), then `go mod tidy` |
| k8s.io/kubernetes staging | `unknown revision v0.0.0` for k8s.io/* | Script auto-resolves; if manual: `go get k8s.io/<pkg>@v0.XX.0` |
| CRD name validation lost | Resource with invalid name accepted (should be rejected) | Re-insert hand-edited `metadata.name` pattern constraints after codegen |
| CRD codegen annotation | `verify-update-codegen` fails (`git diff`) | Re-run codegen to update `controller-gen.kubebuilder.io/version` |
| Webhook builder API | `too many arguments` in NewWebhookManagedBy | Move object from .For() to constructor arg (now generic) |
| Vendor verify in container | `vendor not in sync` (container-only) | False positive — re-run on host to confirm |
| e2e framework API | `undefined` in test/e2e | Rename functions, add params to match new signatures |

## Feature Gates (recurring)

Each k8s release may enable gates that break fake clientsets.
Add gate AND ALL dependents to ALL three mechanisms:
1. `hack/test-go.sh` env var exports
2. `os.Setenv`/`t.Setenv` in test files
3. `SetFromMap` in test files

**Missing gate packages:** Some test packages use fake clientsets
but have NO gate setup. These work until a new gate enables
informer behavior (like WatchList) that fake clientsets don't
support. Symptoms: tests hang or timeout on informer cache sync.
Fix: add `t.Setenv("KUBE_FEATURE_<gate>", "false")` to the
suite's `TestX` function. The autofix warns about these packages
but doesn't auto-fix (not all fake clientset tests need gates).

**envtest suites do NOT need gate disabling.** `envtest.Environment`
starts a real kube-apiserver binary that handles feature gates
natively. Only tests using fake clientsets need manual gate
disabling — the autofix detects these automatically.

SetFromMap validates parent-dep consistency — disabling a parent
without its deps causes a validation error. All gates must be in
SetFromMap, but only add gates that exist in vendored k8s code
(removed gates cause "unrecognized feature gate" errors).

**Known problematic gates:**
- **WatchListClient** (k8s 1.35) — in `k8s.io/client-go`. Changes
  the initial list mechanism to streaming lists. Fake clientsets
  don't implement this protocol, causing informer hangs.

  SetFromMap example:
```go
if err := utilfeature.DefaultMutableFeatureGate.SetFromMap(map[string]bool{
    "WatchListClient": false,
}); err != nil {
    t.Fatalf("Failed to disable feature gates: %v", err)
}
```

## Recurring Patterns

### AddToScheme → Install (SA1019)

Vendored packages may fix misspelled `Depreciated` → `Deprecated`
annotations, newly surfacing SA1019. Check vendored source; if
`Install` exists, use it. Project-internal CRD register.go is
NOT deprecated.

### controller-gen version annotation mismatch (recurring)

When `sigs.k8s.io/controller-tools` is bumped (e.g. v0.20.1 →
v0.21.0), `controller-gen` writes the new version into CRD YAML
annotations. If codegen isn't re-run and committed, CI's
`verify-update-codegen` (or `make verify`) detects the stale
annotation via `git diff --exit-code`. Repos that build
controller-gen from vendor (like CNO) are affected whenever
controller-tools bumps; repos that pin a version in the codegen
script (like ovnk's `@v0.19.0`) are not.

Fix: `k8s-rebase.sh` Phase 2 runs codegen and commits the output.
If the CRD manifest diff only shows the version annotation, that's
expected and correct.

### golang.org/x/exp → stdlib

- `maps.Keys(m)` → `slices.Collect(maps.Keys(m))`
- `maps.Values(m)` → `slices.Collect(maps.Values(m))`
- `maps.Copy/Clone` → same, change import
- `maps.Clear(m)` → `clear(m)`
- `constraints.Ordered` → `cmp.Ordered`

**Import placement:** `"maps"`, `"slices"`, `"cmp"` are stdlib
but end up in the third-party import group after replacement.
Run `goimports -w` to fix grouping.

### Deprecated stdlib/apimachinery symbols (recurring)

These deprecations often surface during k8s rebases but are
not x/exp-related:

- `reflect.Ptr` → `reflect.Pointer` (Go 1.18+ deprecated alias)
- `.FieldsV1.Raw` → `.FieldsV1.GetRawBytes()` (read access)
- `&metav1.FieldsV1{Raw: []byte(...)}` → `metav1.NewFieldsV1(...)` (construction)

- `"k8s.io/klog"` → `"k8s.io/klog/v2"` (check `klog.V()` boolean
  usage and implicit `init()` flag registration, which changed in v2)

**Map iteration ordering:** stdlib `maps.Keys()` returns
`iter.Seq[T]` (materialized via `slices.Collect`), which may
produce different concrete order than x/exp. Tests depending on
map iteration order may flake — pre-existing fragility, not a
rebase bug.

### Transitive dependency compatibility

When controller-runtime or another k8s ecosystem package bumps,
other direct dependencies that consume it may break. Build errors
appear in `/go/pkg/mod/` paths (not in the project's own code).

Fix: `go get <broken-dep>@latest` then `go mod tidy`.

### Snyk vendor scan failures (recurring)

`ci/prow/security` (Snyk) scans vendored code and flags CVEs in
transitive dependencies. This is often pre-existing (fails on
main too), but it blocks rebase PRs. Re-vendoring may also add
new transitive deps that introduce additional findings.

The fix depends on the repo's `.snyk` strategy:

- **`vendor/**` glob** (CNO, INF, ovnk): safe after re-vendoring.
  If the repo has no `.snyk`, the fix is in `openshift/release`
  (exclude vendor from Snyk). See CORENET-7277.
- **Per-file exclusions** (CNCC, multus): fragile — new vendor
  files aren't covered. Either add new exclusions to `.snyk` or
  switch to the `vendor/**` glob (the dominant pattern, used by
  4 of 6 networking repos).

Check `.snyk` if it exists. Per-file repos will likely fail
`ci/prow/security` after re-vendoring.

### Vendor verification false positives in containers (recurring)

When the validate script auto-containerizes (Go version mismatch),
`make verify-go-mod-vendor` may report vendor drift that doesn't
exist on the host. The container's empty module cache resolves
slightly different dependency trees. The validate script flags
these with a NOTE. Re-run `make verify-go-mod-vendor` on the host
to confirm before treating it as a real error.

### Cross-repo dependency ordering (recurring)

Downstream OpenShift repos form a dependency chain:
1. **Plumbing repos first**: `openshift/api`, `openshift/library-go`,
   `openshift/client-go` — these must merge their k8s bump before
   consumers can vendor them.
2. **Consumer repos next**: CNO, CNCC, multus, ovnk — these `go get`
   the bumped plumbing repos.
3. **OTE last**: the downstream `openshift/` module in ovnk has its
   own go.mod and may depend on consumer repo changes.

If `go mod tidy`/`go mod vendor` diffs library-go files, or build
errors show `does not implement` against library-go interfaces,
the plumbing repo hasn't merged yet. This is an upstream BLOCKER.

**Replace directive workaround:** Add to go.mod:
`replace github.com/openshift/library-go => github.com/FORK/library-go v0.0.0-DATE-HASH`
Remove when official library-go merges.

**Do NOT hand-patch vendor/** — CI runs `go mod vendor` which
regenerates from source, erasing patches.

### Operator Framework repos (recurring)

Repos using operator-sdk have additional version refs:
`CONTROLLER_TOOLS_VERSION`, `OPERATOR_SDK_VERSION`, `VERSION`
in Makefile, plus bundle manifests (`bundle/`, `config/`).
Detection: check for a `PROJECT` file or `operator-sdk` in
Makefile. If present, bump controller-tools and operator-sdk
to latest compatible versions, then `make bundle`.

### ST1005 error string casing vs test assertions (recurring)

staticcheck ST1005 requires error strings to not be capitalized.
Rebases can surface this when lint config changes enable
staticcheck or remove exclusions. Lowercasing an error string
is a lint fix but can break test assertions that match the old
string:
```go
// Old
return fmt.Errorf("Failed to create: %v", err)

// New (ST1005 fix)
return fmt.Errorf("failed to create: %v", err)

// Test — BROKEN (still expects old capitalization)
Expect(err.Error()).To(ContainSubstring("Failed to create"))
```

Before lowercasing any error string for ST1005, grep for the OLD
string in all Go files — not just tests. Production code may use
`strings.Contains(err.Error(), "...")` for control flow. This is
a semantic change, not just a lint fix.

### golangci-lint v1→v2 config migration (recurring)

When upgrading golangci-lint from v1 to v2, the config format
changes:
- Add `version: "2"` header
- `linters-settings` → nested under `linters.settings`
- Add `default: standard` under `linters` (replaces v1's
  implicit default set; `enable`/`disable` are additive on top)

Separately, any lint version bump (even within v1 or within v2)
can pull in stricter checks that surface new findings unrelated
to the rebase. `--fix` auto-fix is incomplete for some checks.

The skill's `fix_lint_version` bumps the lint tool version
but does not migrate the `.golangci.yml` config. Config migration
is left to the agent in Step 4 because the changes are project-
specific. When facing config issues: fix the config to match the
new version's expectations rather than suppressing new warnings.

**errcheck exclusions for v2:** golangci-lint v2's errcheck matches
concrete types, not just interfaces — `(io.Closer).Close` does NOT
cover `(*os.File).Close`. Before creating exclusions, grep the
project for unchecked Close/Flush calls:
`grep -rn '\.Close()\|\.Flush()' --include='*.go' . | grep -v vendor | grep -v 'if.*err'`
Common exclusions: `fmt.Fprintf`, `fmt.Fprintln`,
`(*os.File).Close`, `(*io.PipeWriter).Close`,
`(*crypto/tls.Conn).Close`, `(io.Closer).Close`,
`(io.WriteCloser).Close`, `(net.Conn).Close`,
`(net.Listener).Close`, `(*bufio.Writer).Flush`.

### Webhook builder API change (controller-runtime v0.24)

`ctrl.NewWebhookManagedBy` is now generic — the object moves
from `.For()` into the constructor as a type parameter:
```go
// Old: ctrl.NewWebhookManagedBy(mgr).For(&MyType{}).WithValidator(v).Complete()
// New: ctrl.NewWebhookManagedBy(mgr, &MyType{}).WithValidator(v).Complete()
```
`.For()` is removed. `WithValidator` now takes generic
`admission.Validator[T]`. `WithCustomValidator` still exists
but is deprecated.

