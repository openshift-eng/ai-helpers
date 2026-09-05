PROGRESS: 40% complete

**Read `rules.md` first** — it defines scope, module safety, commit discipline, and gate-fix sequencing that apply to every step.

# Step 2: Fix Compilation Errors

## Validate

Use `timeout: 600000` (10 min) for validation commands. If lint
auto-containerizes, it may take 12+ min — use nohup like Step 1.

```bash
bash "$PLUGIN_ROOT/scripts/k8s-rebase-validate.sh" --quick
```

Exit 0: no errors. Exit 1: errors in `.rebase-tmp/summary.txt`.
Use `--quick` (~1 min, build + vet only) during fix iterations.
`--quick` runs build + vet only. `--no-test` adds lint and
`go test -run='^$'`, which catches stricter format string issues
(e.g., Eventf arg count mismatches) that standalone `go vet`
misses — without running any tests.

## Fix Loop

Fix compilation errors from ALL modules (find all go.mod files).
Some modules (e.g., `test/e2e`) have gitignored vendor directories.
Compile them with `-mod=mod` to download deps:
`cd test/e2e && go build -mod=mod ./...`
Fix any errors — API signature changes (new parameters, renamed
functions) are common in test helpers. These errors only surface
in CI if not fixed locally.

Expect multiple validate cycles — vet can only check files that
compile, so fixing build errors reveals new vet errors.

**Parallel investigation:** If summary.txt has multiple error
categories, launch read-only Explore subagents to investigate
each in parallel. Give each subagent the errors and ask it to
read the relevant source AND test files and vendored types, then
report what changed and what the fix should be. Investigation
subagents must NOT edit files — apply fixes yourself based on
their findings.

Create separate `--signoff` commits per fix category. After fixing
type definitions, re-run `make generate` (if available) and commit
any regenerated files (e.g., `zz_generated.deepcopy.go`).

## API Migration Guidance

**Migration direction rule:** When fixing compilation errors,
always use the NEWEST available API. Never introduce usage of a
deprecated package. Check `// Deprecated:` comments in vendored
source (`grep -r 'Deprecated:' vendor/<pkg>/`) to find the
replacement. For common k8s API migrations, check the patterns
doc if available.
Anti-patterns to avoid:
- `golang.org/x/net/context` instead of stdlib `context`
- `k8s.io/utils/strings/slices` instead of stdlib `slices`
- `k8s.io/utils/pointer` instead of `k8s.io/utils/ptr`
- `admission.CustomValidator` instead of `admission.Validator[T]`

**General fix patterns:**
- When a function requires `context.Context`: pass `ctx` from
  the caller, not `context.TODO()`.
- `context.WithTimeout`/`WithCancel`: always capture the cancel
  function (`ctx, cancel := ...`) and `defer cancel()`.
  `ctx, _ := ...` leaks the context and fails `go vet`'s
  `lostcancel` analyzer.
- `ioutil.ReadFile`/`ReadDir` -> `os.ReadFile`/`os.ReadDir`

After ANY `go get`, `go mod tidy`, or go.mod change, re-vendor
if the module has a vendor directory: `go mod vendor`. Failing
to re-vendor leaves stale packages that cause CI failures.

## OpenShift Dependencies

**For OpenShift deps** (`openshift/api`, `openshift/client-go`,
`openshift/library-go`): use the correct release branch per the
OCP mapping in rules.md (k8s 1.N -> OCP 4.(N-13), or 5.(N-36)
for k8s >=1.36). Do NOT escalate to a newer release branch to
fix dependency conflicts — find newer commits on the correct
branch instead. Wrong branch = MVS pulls k8s deps to the wrong
version, which the version-consistency gate will catch.

**Do NOT bump non-k8s dependencies** in other modules (e.g.,
`test/conformance/`) unless the build actually fails. The
conformance module may intentionally use a different version of
`network-policy-api` than go-controller — bumping it to match
can break CI.

If errors appear in `/go/pkg/mod/` paths (not the project's own
code), a direct dependency is incompatible with the bumped k8s
packages. Extract the module path (between `/go/pkg/mod/` and
`@`) and fix with:
`bash "$PLUGIN_ROOT/scripts/k8s-rebase-depfix.sh" <module>`

**NEVER modify files under vendor/ directly.** CI runs
`go mod vendor` which regenerates vendor from source, erasing
hand-patches. If a vendored dependency is missing a method or
interface, search for an active upstream rebase PR that bumps
that dep. If found, identify the branch or fork it uses and add
a `replace` directive:
`replace github.com/openshift/library-go => github.com/ORG/library-go v0.0.0-DATE-HASH`
Add a tracking comment: `// TODO: remove replace when official library-go merges k8s bump`.
Re-run `go mod tidy` and `go mod vendor` after adding the replace.
In multi-module repos, add the replace to each module that depends
on the affected package (Go replace directives do not propagate
across module boundaries).
If no active PR or fork exists, report it as a blocker and move on.
Do NOT vendor-patch; verify-deps CI will reject it.

## Import and Type Fix Rules

**Import deduplication:** If a file imports the same package
twice (bare + aliased), remove the duplicate and update
references. **Do NOT use `replace_all`** unless the old and new
strings are completely disjoint. It matches already-modified
lines and doubles up:
- `v1alpha1.` -> `infv1alpha1.` also hits `infv1alpha1.` ->
  `infinfv1alpha1.`
- Adding `_, _ =` prefix hits lines already prefixed
- `k8serrors` -> `k8sk8serrors` (import alias doubling)
Use targeted per-line edits or `sed` with anchored patterns.

When converting types, read the FULL struct definition and map
ALL fields. Check test files for the same type changes — test
files often use the same types as source files.

**Type conversion review:** After each commit that converts
between struct types, launch a subagent: "Read the diff of this
commit. For each struct conversion, read the FULL struct
definition in vendor and list ALL fields. Compare against the
conversion code. Report any fields present in the struct but
missing from the conversion."

## Gates

Run the orchestrator to collect companion evidence and discover gate state:
```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" gates "$REPO_ROOT" 2
```

Then launch one subagent per PENDING gate only. All PENDING gates in a single
parallel wave. Each subagent prompt: repo path + module safety rule (from
rules.md) + "Read `<GATE_DIR>/<filename>` and follow its instructions."
Do NOT cat the gate files yourself.

```bash
GATE_DIR="$PLUGIN_ROOT/gates/step2-compilation"
echo "$GATE_DIR"
```

Gate files:
- `build-vet.md` (count)
- `version-consistency.md` (count)
- `diff-scope.md` (count)
- `test-compilation.md` (count)
- `type-conversions.md` (judge)
- `fix-correctness.md` (judge)

Count gates must report 0. Judge gates must cite evidence.

## Gate-fix loop

If ANY gate reports FAIL (count gate with issues > 0, OR judge
gate with verdict FAIL):

1. **Triage**: Read each FAIL gate report (DETAILS with
   file:line). For each finding, check the base branch:
   `BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`
   `git show $BASE:<file>` — if the same issue exists on the
   base branch, it is pre-existing. If the file does not exist
   on base (new file), the finding IS new. Skip pre-existing
   findings.

2. **Fix**: For each NEW finding, fix the cited issue and
   commit.

3. **Re-validate**: After any code-changing fix, re-run
   `bash "$PLUGIN_ROOT/scripts/k8s-rebase-validate.sh" --quick`
   to confirm build+vet still pass. Fix commits can introduce
   new regressions — catch them here before re-running the gate.

4. **Re-run** (mandatory — never skip): Re-run the orchestrator
   gates command to refresh evidence, then delete ONLY the
   specific failing gate's report file
   (`rm .rebase-tmp/gates/step2-<gate>.report`) and re-run that
   gate. Stale FAIL reports cause auto-record to mark the run
   as failed even if the fix worked.

Repeat up to 3 times per gate. If it still fails after 3
attempts, report remaining issues and proceed.

**All 6 step2 gate verdicts are required even if there were zero
compilation errors.** Gates check more than compilation — they
verify version consistency, diff scope, and type conversions.
The orchestrator run above identifies which gates need subagents;
RESOLVED gates are already done. When all 6 have verdicts, proceed
to Step 3 immediately. Do NOT stop — Steps 3-5 are mandatory even
with zero compilation errors.

## Advance

When all 6 gates pass, run the orchestrator to advance:
```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" advance "$REPO_ROOT"
```
