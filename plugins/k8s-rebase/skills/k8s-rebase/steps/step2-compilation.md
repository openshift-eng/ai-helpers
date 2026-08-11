# Step 2: Fix Compilation Errors

PROGRESS: 40% complete

Read `${PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` first.

## Validate

Validation can auto-containerize; allow at least 10 minutes and wait for
actual completion as described in rules.md.

```bash
bash "$PLUGIN_ROOT/scripts/k8s-rebase-validate.sh" --quick
```

Exit 0: no errors. Exit 1: errors in `.rebase-tmp/summary.txt`.
Use `--quick` (build + vet only) during fix iterations. `--no-test` adds lint and
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
categories, use read-only native workers to investigate
each sequentially. Give each subagent the errors and ask it to
read the relevant source AND test files and vendored types, then
report what changed and what the fix should be. Investigation
subagents must NOT edit files — apply fixes yourself based on
their findings. If workers are unavailable, investigate inline.

Create separate `--signoff` commits per fix category. After fixing
type definitions, re-run `make generate` (if available) and commit
any regenerated files (e.g., `zz_generated.deepcopy.go`).

## API Migration Guidance

**Migration direction rule:** Use the non-deprecated API available in the
pinned dependencies. Never introduce usage of a deprecated package.
Check `// Deprecated:` comments in vendored
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

## OpenShift Dependencies

**For OpenShift deps** (`openshift/api`, `openshift/client-go`,
`openshift/library-go`): use the release branch from rules.md's OCP
mapping. A wrong branch lets MVS pull Kubernetes deps to the wrong
version, which the version-consistency gate will catch.

The correct release branch may still declare the previous Kubernetes minor
during a staged rebase. Step 1 accepts those minimum requirements, while
rejecting newer minors. This establishes only a candidate: verify the resolved
target pins and build every consumer module. If removed APIs break the
dependency, use the upstream-fix procedure below; an older requirement floor
alone is neither proof of compatibility nor a blocker.

**Do NOT bump non-k8s dependencies** in other modules (e.g.,
`test/conformance/`) unless the build actually fails. The
conformance module may intentionally use a different version of
`network-policy-api` than go-controller — bumping it to match
can break CI.

If errors appear in `/go/pkg/mod/` paths (not the project's own
code), a direct dependency is incompatible with the bumped k8s
packages. Extract the module path (between `/go/pkg/mod/` and
`@`) and fix with:
`bash "$PLUGIN_ROOT/scripts/k8s-rebase-depfix.sh" <module>@<compatible-version>`
Run it in the affected module and verify Kubernetes pins afterward.

**NEVER modify files under vendor/ directly.** CI runs
`go mod vendor` which regenerates vendor from source, erasing
hand-patches. If a vendored dependency is missing a method or
interface, search for an active upstream rebase PR that bumps
that dep. For Kubernetes 1.37, consult `docs/k8s-1.37.md` for the
known OpenShift plumbing changes, then refresh its upstream evidence.
Read structured PR metadata to distinguish its proposed head from the base
release branch. For example, with the actual upstream repository and PR:

```bash
gh api "repos/<upstream-repo>/pulls/<number>" --jq \
  '{state, merged, head: {repo: .head.repo.full_name, ref: .head.ref, sha: .head.sha}, base: {ref: .base.ref, sha: .base.sha}}'
```

Inspect the failing source file and go.mod at that exact **head SHA**, using
a read-only API/blob request or separate upstream clone. A release-branch
SHA in the compatibility table is not the PR head. A PR title, webpage
summary, or unchanged base file does not establish that the fix is absent.
Before declaring no compatible fix exists, record the head inspected and
the relevant symbols/diff. Unavailable metadata or source is an unresolved
investigation, not proof that upstream has no fix.

If the proposed source fixes the incompatibility, pin its verified commit
through the compatible upstream module version or a `replace` directive:
`replace github.com/openshift/library-go => github.com/ORG/library-go v0.0.0-DATE-HASH`
Add a tracking comment, such as
`// TODO: remove replace when official library-go merges k8s bump`.
In multi-module repos, add the replace to each module that depends
on the affected package (Go replace directives do not propagate
across module boundaries). Then, in each of those modules, run
`bash "$PLUGIN_ROOT/scripts/k8s-rebase-depfix.sh" --sync`.
Also inspect the dependency PR's own replacements: they do not propagate
to consumers either. Apply required companion replacements at verified
commits in every affected consumer, then build and recheck the target pins.
If no active PR or fork exists, report it as a blocker and move on.
Do NOT vendor-patch; verify-deps CI will reject it.

## Import and Type Fix Rules

**Import deduplication:** If a file imports the same package
twice (bare + aliased), remove the duplicate and update
references. **Do NOT use unrestricted bulk replacement** unless the old and new
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
between struct types, use a read-only worker (or check inline): "Read the diff of this
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

Follow the gate procedure in rules.md. Delegate PENDING gates one at a time
when workers are available, or review inline if no worker tool exists. Supply the absolute repo
and plugin paths, version, module safety and verdict rules, and the gate prompt path.
Inspect cached non-PASS verdicts as well as pending work.

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

Use each gate's verdict criteria; report counts and cite evidence.

## Gate-fix loop

Follow rules.md's shared loop and three-iteration budget. Re-validate fixes
with `--quick` before refreshing all current-step evidence and reviews.
Return remaining issues and consumed iterations to the parent.

**All 6 step2 gate verdicts are required even if there were zero
compilation errors.** Gates check more than compilation — they
verify version consistency, diff scope, and type conversions.
The orchestrator run above identifies which gates need subagents;
RESOLVED gates have verdicts, not necessarily PASS. Return results for the
parent's advancement decision. Do NOT declare completion — Steps 3-5 are mandatory even
with zero compilation errors.

## Advance

Return gate outcomes, remaining issues, and retry counts to the parent.
Only the parent advances, using the protocol in SKILL.md.
