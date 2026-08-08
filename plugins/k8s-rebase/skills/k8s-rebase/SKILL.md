---
name: k8s-rebase
description: Rebase a Go project to a new Kubernetes version by bumping all k8s.io/* dependencies, running codegen, updating version references, fixing build breakage with antagonistic review, and presenting a gh pr create command.
argument-hint: "[--bump-tools] <version> (e.g., 1.36.0 or --bump-tools 1.36.0)"
user-invocable: true
allowed-tools: Bash, Read, Agent
---

# Kubernetes Rebase

Automates the k8s dependency rebase for Go projects that consume
`k8s.io/*` packages. The automated rebase script handles
mechanical work (dep bumps, codegen, version refs). The agent
handles compilation errors, autofix patterns, lint, testing,
and review. **The rebase is NOT finished until you present a
`gh pr create` command to the user in Step 5.** Steps 1-4
are preparation. Step 5 is the deliverable.

**Arguments:** $ARGUMENTS

**Use subagents freely.** Every step has a Gate that launches
subagents to verify work. Beyond the gates, spawn additional
subagents whenever useful — to investigate errors, review
diffs, run tests, or get a second opinion. Subagents are cheap
and catch mistakes the main agent misses because they see the
code fresh without prior assumptions.

**Container commands:** When running containers, prefer
`podman` with `--userns=keep-id`. The scripts fall back to
`docker` when podman is absent, but docker creates root-owned
files in bind mounts that may need manual cleanup.
`--security-opt label=disable` is required for SELinux hosts
(container writes to bind-mounted repo dirs fail without it).
```
podman run --rm --security-opt label=disable --userns=keep-id -v "$(pwd):$(pwd)" -w "$(pwd)" docker.io/library/golang:VERSION ...
```

**Feature gates:** SetFromMap validates parent-dep consistency —
disabling a parent without its deps causes a validation error.
ALL gates (parents + deps) must go in SetFromMap AND in env vars
(`os.Setenv`/`t.Setenv`/`export KUBE_FEATURE_*`). The autofix
script handles this; do not remove gates from its SetFromMap
calls.

**Rebase report:** After completing each numbered step, append
a checkpoint to `.rebase-tmp/rebase-report.md`. Include the
step number, what broke, what you tried, what worked, iteration
counts, and anything surprising. Keep each checkpoint under 15
lines. Before recording an issue, verify it's real:
`git show $(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main):<file>`
— if the same issue exists on the base branch, note it as
pre-existing, not a regression. The final synthesis step (5d)
reads these checkpoints.

**Never add test skips to make CI green.** If a test fails,
investigate and fix the root cause. Adding skip regexes or
`t.Skip()` to suppress failures hides real issues and erodes
maintainer trust. If the failure is pre-existing (same test
fails on the base branch), note it in the commit message but
do not skip it.

**Scope and semantic preservation:** Every change must be
directly required by the k8s version bump — does build, vet, or
lint fail without it? Do not refactor, add features, or touch
files that compile cleanly. Do not add struct tags (like
omitempty), merge functions, rename interfaces, or restructure
packages. If a deprecated API has a 1:1 replacement and the
compiler/linter flags it, use the replacement; if it requires
architectural changes, note it as out-of-scope and move on.
Fix ONLY the cited issue at the cited location. When fixing
compilation errors from API changes:
- Preserve behavior: never replace label selectors with
  `reflect.DeepEqual`, never change security flag defaults
  (`secureMetrics`, `SecureServing`), never swap `errors.Is` for
  `==`.
- Preserve nil semantics: `*int32` nil means "server default",
  `int32` zero means "set to 0" — use `ptr.To[int32](val)`.
  Same for nil map vs empty map.
- Adapt type signatures without altering surrounding logic.
- Verify against base: `git show $(git merge-base HEAD master
  2>/dev/null || git merge-base HEAD main):<file>`.

**Commits and git:** Body lines ≤72 chars. Each commit gets
exactly one `Signed-off-by` and one `Assisted-by: Claude Code
<noreply@anthropic.com>` trailer (scripts add automatically).
Do not amend — create new commits on top. Use `git add -A` (no
negated pathspecs). No `org/repo#N` in commit messages (causes notification
spam — put PR/issue links in the PR body instead). No inline
comments in config files. If adding a `replace` directive, add
`// TODO: remove replace when upstream merges — track via Jira`.

---

## Step 1: Deterministic Rebase

Run from the default branch (master/main). The script creates a
new timestamped branch. Do not reuse branches from prior runs.

**Recovery:** If a run fails mid-way through Steps 2-4, check
`git log` on the rebase branch. The mechanical rebase commits
from Step 1 are always safe. To resume: start a new session on
the same branch and continue from the failed step. To restart:
`git checkout master && git branch -D <branch>` and re-run.

**Important:** This script takes 5-30 minutes (longer if it
auto-containerizes). Launch it as a detached process so it is
not killed by Bash tool timeouts:

**Launch** (returns immediately):
```bash
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && echo "ERROR: Not in a git repo" && exit 1
if ! [[ -f "$REPO_ROOT/go.mod" || -f "$REPO_ROOT/go-controller/go.mod" ]]; then
  echo "ERROR: $REPO_ROOT has no go.mod — are you in a workspace root instead of the target repo?"
  exit 1
fi
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
[ -z "$SCRIPT" ] && echo "ERROR: k8s-rebase.sh not found" && exit 1
[ -z "$ARGUMENTS" ] && echo "ERROR: Version argument required (e.g., 1.36.0)" && exit 1
mkdir -p "$REPO_ROOT/.rebase-tmp"
nohup bash "$SCRIPT" $ARGUMENTS > "$REPO_ROOT/.rebase-tmp/step1.log" 2>&1 &
echo $! > "$REPO_ROOT/.rebase-tmp/step1.pid"
echo "Launched PID $(cat "$REPO_ROOT/.rebase-tmp/step1.pid")"
```

**Check** (use `run_in_background: true` on Bash, NOT sleep loops):
Do NOT use `sleep` commands to poll for completion. Each sleep +
check cycle wastes context budget. Instead, run the check command
with `run_in_background: true` and `timeout: 300000` — the system
notifies you when it finishes. If you must check manually, run
the check ONCE, not in a loop.
```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
if kill -0 $(cat "$REPO_ROOT/.rebase-tmp/step1.pid" 2>/dev/null) 2>/dev/null; then
  echo "Still running..."; tail -3 "$REPO_ROOT/.rebase-tmp/step1.log"
else
  echo "Done"; cat "$REPO_ROOT/.rebase-tmp/step1-result.txt" 2>/dev/null; tail -10 "$REPO_ROOT/.rebase-tmp/step1.log"
fi
```

When the check shows "Done", look at the last lines of the log.
**Exit 0** = already at target version, nothing to do — stop.
**Exit 2** = success — proceed to validation. **Exit 1** = error.
Check `cat .rebase-tmp/step1-result.txt` — if it says "EXIT 2",
the script completed all phases. **If the file is missing**, the
script crashed mid-run. Check `tail -20 .rebase-tmp/step1.log`
for the error. If `git log` shows the dep bump and codegen
commits, those are safe. Manually verify version references
(Dockerfiles, CI configs, lint version) since the script may
have crashed before updating them, then proceed to Step 2.

Do NOT re-run the script. Do NOT run the autofix script
or make manual go.mod changes before the rebase script completes — the
rebase script handles all module bumps, codegen, and version
references. Running autofix early creates duplicate commits.
Do NOT manually update K8S_VERSION or other version references.
The rebase script sets version refs to the go.mod version
(e.g., v1.36.2). On repos where K8S_VERSION controls the KIND
image (any file has both K8S_VERSION and kindest/node), the
autofix adjusts K8S_VERSION to match the latest available
kindest/node tag (e.g., v1.36.1). On other repos, K8S_VERSION
stays at the go.mod version for kubectl/envtest downloads.

If the output says "Could not detect OCP target", check the
repo's CI config in `openshift/release` or compare with an
existing manual rebase PR for the correct `openshift-X.Y`
version in `.ci-operator.yaml` and Dockerfiles.

**Gate:** Find the gate prompt directory, read each file listed
below with `cat`, and launch one subagent per file with the
file's contents as the prompt. Prepend the repo path and the
module safety rule: "You must NEVER run go mod tidy, go get,
go mod vendor, go mod edit, go generate, or go run. Only
go build, go vet, go test are permitted (with -mod=vendor if
vendor/ exists). Also allowed: go mod verify, go doc,
go install <tool>@<version>, go clean -cache."
```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 \
  -path "*/k8s-rebase/gates/step1-rebase" -type d 2>/dev/null | head -1)
cat "$GATE_DIR/rebase-completeness.md"  # read this, use as subagent prompt
```
Gate files:
- `rebase-completeness.md` (count)

**Gate-fix loop:** If the gate reports FAIL:
1. **Fix**: For each failing check (missing codegen, uncommitted
   changes, stale replace directives, wrong dep versions),
   fix the issue and commit.
2. **Re-run** (mandatory — never skip): Delete the old gate report
   (`rm .rebase-tmp/gates/step1-rebase-completeness.report`),
   then re-launch the gate subagent with a fresh prompt. Stale
   FAIL reports cause auto-record to mark the run as failed even
   if the fix worked.
Repeat up to 3 times. If it still fails, stop and report the
remaining issues — step 1 failures are structural and proceeding
would cause cascading problems in later steps.

Also check `.rebase-tmp/summary.txt` for `## CODEGEN FAILURE`.
If present, fix the codegen script (e.g., remove dropped flags),
re-run codegen, commit, and re-verify.

**When step1 gate passes, proceed to Step 2.**

---

## Steps 2–5: Validation and Fixes

Every step ends with subagent verification. The step is not
complete until all subagents report zero issues.

**Subagent rules:**
- Report specific counts, not just "looks good."
- Judgment agents must cite the specific file:line or diff hunk
  for each concern — "no issues found" requires listing what
  was actually checked.
- Gate subagents are read-only — they must NOT edit repo files.
  Their sole permitted write is their gate report file under
  `.rebase-tmp/gates/`. The main agent applies fixes.
- **Module safety:** Gate subagents must NEVER run `go mod tidy`,
  `go get`, `go mod vendor`, `go mod edit`, `go generate`, or
  `go run`. Allowed go commands: `go build`, `go vet`, `go test`
  (with `-mod=vendor` when vendor/ exists), `go mod verify`,
  `go doc`, `go install <tool>@<version>`, `go clean -cache`.
  Include this rule when constructing each gate subagent prompt.
- **Gate-fix sequencing:** In the gate-fix loop, commit ALL
  fixes before re-launching ANY gates. Gates read the branch
  tip at launch — if you launch a gate while a fix is still
  uncommitted, it sees stale code and reports a false FAIL.
  Pattern: read all FAIL reports, fix all issues, commit all
  fixes, then re-run all failed gates in one parallel wave.
- **Context budget:** Never burn main-agent context on build
  monitoring. Use `run_in_background: true` for long commands,
  or launch builds in subagents. NEVER use `sleep` commands to
  poll — each sleep+check cycle wastes ~1K tokens of context
  that you need for gates. One wasted polling loop of 20 checks
  costs more than launching all 33 gate subagents combined.
- If ANY judgment agent flags a concern, the main agent MUST
  investigate and either fix it or explain why it's not an
  issue before proceeding. Do not dismiss judgment concerns.
- Give subagents the repo path and tell them to use
  `podman run --userns=keep-id` with the golang container if
  they need Go tools (build, vet, lint, test).
- If you cannot launch subagents, run the gate checks inline.
- **Companion gate scripts:** Some gates have `.sh` files alongside
  the `.md` prompt. Run the `.sh` script FIRST — it provides
  mechanical check results (build status, pre-existing findings).
  Include the script output in the subagent prompt so it can
  use the results for its verdict instead of re-running checks.

**Commit discipline:**
- One commit per distinct fix. Don't bundle unrelated changes.
- The scripts auto-detect the project's commit message convention
  from CONTRIBUTING.md. If the project requires `subcomponent:`
  prefixes, script commits use generic categories (`deps:`,
  `codegen:`, `ci:`, `test:`). For your own commits, read
  CONTRIBUTING.md and use specific sub-component names matching
  the code you changed (e.g., `e2e:`, `hybrid-overlay:`).
- Each commit should compile independently (`go build ./...`).

### Step 2: Fix compilation errors

Use `timeout: 600000` (10 min) for validation commands. If lint
auto-containerizes, it may take 12+ min — use nohup like Step 1.

```bash
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-validate.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
if [ -n "$SCRIPT" ]; then
  bash "$SCRIPT" --quick
else
  make 2>&1 | tee /tmp/rebase-build.log
fi
```

Exit 0: no errors. Exit 1: errors in `.rebase-tmp/summary.txt`.
Use `--quick` (~1 min, build + vet only) during fix iterations.
`--quick` runs `go vet` (fast). `--no-test` adds
`go test -run='^$'` which catches stricter format string
issues (e.g., Eventf arg count mismatches) that standalone
`go vet` misses — without running any tests.

**Migration direction rule:** When fixing compilation errors, always
use the NEWEST available API. Never introduce usage of a deprecated
package to fix a compilation error. Check `// Deprecated:` comments
in vendored source (`grep -r 'Deprecated:' vendor/<pkg>/`) to find
the replacement. Common anti-patterns to avoid:
- `golang.org/x/net/context` instead of stdlib `context`
- `k8s.io/utils/strings/slices` instead of stdlib `slices`
- `k8s.io/utils/pointer` instead of `k8s.io/utils/ptr`
- `admission.CustomValidator` instead of `admission.Validator[T]`

**Common API migrations** (use when the compiler flags a removed API):
- `pointer.Int32(v)` → `ptr.To[int32](v)` (k8s.io/utils/ptr)
- `sets.NewString(...)` → `sets.New[string](...)`
- `context.Context` added as first parameter: pass `ctx` from
  the caller, not `context.TODO()`.
- `context.WithTimeout`/`WithCancel`: always capture the cancel
  function (`ctx, cancel := ...`) and `defer cancel()`.
  `ctx, _ := ...` leaks the context and fails `go vet`'s
  `lostcancel` analyzer.
- `ioutil.ReadFile`/`ReadDir` → `os.ReadFile`/`os.ReadDir`
- `k8s.io/klog` → `k8s.io/klog/v2` (klog v1 removed in k8s
  1.35+; also remove `k8s.io/klog` from go.mod if present)
- `webhook.WithCustomValidator(scheme, &T{}, &V{})` →
  `webhook.WithValidator[T](&V{})` (controller-runtime v0.23+,
  the old `CustomValidator` interface is removed)

After ANY `go get`, `go mod tidy`, or go.mod change, re-vendor
if the module has a vendor directory: `go mod vendor`. Failing
to re-vendor leaves stale packages that cause CI failures.

Fix compilation errors from ALL modules (find all go.mod files).
Note: some modules (e.g., `test/e2e`) have gitignored vendor
directories. Compile them with `-mod=mod` to download deps:
`cd test/e2e && go build -mod=mod ./...`
Fix any errors — API signature changes (new parameters,
renamed functions) are common in test helpers. These errors
only surface in CI if not fixed locally.

If errors appear in `/go/pkg/mod/` paths (not the project's own
code), a direct dependency is incompatible with the bumped k8s
packages. Extract the module path (between `/go/pkg/mod/` and
`@`) and fix with `go get <module>@latest && go mod tidy`.

**For OpenShift deps** (`openshift/api`, `openshift/client-go`,
`openshift/library-go`): use the correct release branch per the
OCP mapping in Step 5d (k8s 1.N → OCP 4.(N-13), or 5.(N-36)
for k8s ≥1.36). Do NOT escalate to a newer release branch to
fix dependency conflicts — find newer commits on the correct
branch instead. Wrong branch = MVS pulls k8s deps to the wrong
version, which the version-consistency gate will catch.

**Do NOT bump non-k8s dependencies** in other modules (e.g.,
`test/conformance/`) unless the build actually fails. The
conformance module may intentionally use a different version of
`network-policy-api` than go-controller — bumping it to match
can break CI (v0.2.0 conformance creates ClusterNetworkPolicy
resources that the controller doesn't support yet).
**NEVER modify files under vendor/ directly.** CI runs
`go mod vendor` which regenerates vendor from source, erasing
hand-patches. If a vendored dependency is missing a method or
interface (e.g., library-go's SharedIndexInformer), search for
an active upstream rebase PR that bumps that dep. If found,
identify the branch or fork it uses and add a `replace` directive:
`replace github.com/openshift/library-go => github.com/ORG/library-go v0.0.0-DATE-HASH`
Add a tracking comment: `// TODO: remove replace when official library-go merges k8s bump`.
Re-run `go mod tidy` and `go mod vendor` after adding the replace.
In multi-module repos, add the replace to each module that depends
on the affected package (Go replace directives do not propagate
across module boundaries).
If no active PR or fork exists, report it as a blocker and move on.
Do NOT vendor-patch; verify-deps CI will reject it.

**Import deduplication:** If a file imports the same package
twice (bare + aliased, e.g., `"k8s.io/.../errors"` and
`k8serrors "k8s.io/.../errors"`), remove the duplicate and
update references. **Do NOT use `replace_all`** unless the old
and new strings are completely disjoint. It matches already-
modified lines and doubles up:
- `v1alpha1.` → `infv1alpha1.` also hits `infv1alpha1.` →
  `infinfv1alpha1.`
- Adding `_, _ =` prefix hits lines already prefixed →
  `_, _ = _, _ = fmt.Fprintf(...)`
- `k8serrors` → `k8sk8serrors` (import alias doubling)
Use targeted per-line edits or `sed` with anchored patterns
instead.

When converting types, read the FULL struct definition and map
ALL fields. Check test files for the same type changes — test
files often use the same types as source files. Create separate
`--signoff` commits per fix category. After fixing type
definitions, re-run `make generate` (if available) and commit
any regenerated files (e.g., `zz_generated.deepcopy.go`).

Expect multiple validate cycles — vet can only check files that
compile, so fixing build errors reveals new vet errors.

**Parallel investigation:** If summary.txt has multiple error
categories, launch read-only Explore subagents to investigate
each in parallel. Give each subagent the errors and ask it to
read the relevant source AND test files and vendored types,
then report what changed and what the fix should be.
Investigation subagents must NOT edit files — apply fixes
yourself based on their findings.

**Type conversion review:** After each commit that converts
between struct types, launch a subagent: "Read the diff of
this commit. For each struct conversion, read the FULL struct
definition in vendor and list ALL fields. Compare against the
conversion code. Report any fields present in the struct but
missing from the conversion."

**Gate:** Find the gate prompt directory, read each file listed
below with `cat`, and launch one subagent per file with the
file's contents as the prompt. Launch all in a single parallel
wave. Prepend the repo path and the module safety rule (see
Step 1 gate launch for the full text) to each prompt.
Do not skip, batch, or defer any gate — launch all 6 in a
single message. Gate subagents run independently and do not
consume your context window.
```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 \
  -path "*/k8s-rebase/gates/step2-compilation" -type d 2>/dev/null | head -1)
cat "$GATE_DIR/build-vet.md"  # read this, use as subagent prompt
```
Gate files:
- `build-vet.md` (count)
- `version-consistency.md` (count)
- `diff-scope.md` (count)
- `test-compilation.md` (count)
- `type-conversions.md` (judge)
- `fix-correctness.md` (judge)

Count gates must report 0. Judge gates must cite evidence.

**Gate-fix loop:** If ANY gate reports FAIL:
1. **Triage**: Read each FAIL report. Check base branch:
   `git show $(git merge-base HEAD master 2>/dev/null ||
   git merge-base HEAD main):<file>` — skip pre-existing issues.
2. **Fix**: Fix the cited issue at the cited location. Commit.
3. **Re-validate**: After any code-changing fix, re-run
   `validate.sh --quick` to confirm build+vet still pass. Fix
   commits can introduce new regressions — catch them here before
   re-running the gate.
4. **Re-run** (mandatory — never skip): Delete the old gate report
   (`rm .rebase-tmp/gates/<gate>.report`), then re-launch the
   gate subagent with a fresh prompt. Stale FAIL reports cause
   auto-record to mark the run as failed even if the fix worked.
Repeat up to 3 times per gate. If it still fails, report
remaining issues and proceed.

**You MUST run all 6 step2 gates even if there were zero
compilation errors.** Gates check more than compilation — they
verify version consistency, diff scope, and type conversions.
When all pass, proceed to Step 3 immediately. Do NOT stop —
Steps 3-5 are mandatory even with zero compilation errors.

To add a gate: create a new `.md` file in `step2-compilation/`
and add it to this list.

### Step 3: Apply autofix patterns

Use `timeout: 600000` — the autofix auto-containerizes and
runs go vet internally.

```bash
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-autofix.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
[ -n "$SCRIPT" ] && bash "$SCRIPT"
```

Applies known fix patterns (code fixes, feature gates, lint
version, CRD validation fixes, AND e2e infra: MetalLB, KubeVirt,
RelaxedServiceNameValidation, kubeadm v1beta4).
Outputs RESULT: PASS or FAIL to terminal. The autofix does not
write to summary.txt (that file comes from the validate script).
FAIL is normal when the repo has patterns the autofix documents
but cannot fix automatically (e.g., KubeVirt test changes) — the
agent handles those in Step 4.

**If autofix is unavailable or skips a repo**, check these
manually (derive the k8s version from go.mod `k8s.io/api`).
Skip any item the autofix already committed (`git log --oneline`
shows autofix commits with "Applied:" in the message):
- KIND image: `grep -rn 'kindest/node:' . --include='*.sh' --include='*.yaml' --include='*.yml' | grep -v vendor/` — update to `v<k8s-version>`
  (e.g., v1.36.1 for k8s 1.36). Check https://hub.docker.com/r/kindest/node/tags for the latest patch.
- kubeadm v1beta4: `grep -rn 'extraArgs:' . --include='*.yaml' --include='*.yml' --include='*.sh' | grep -v vendor/` — if the format is `extraArgs:\n    key: value` (flat map), convert to `extraArgs:\n- name: key\n  value: "value"` (list-of-objects). Required for k8s >= 1.31.
- CI dependency versions: `grep -rniE '_VERSION\s*=' . --include='*.sh' | grep -v vendor/` — pinned CI tool versions (MetalLB, KubeVirt, etc.) may need bumping when k8s tightens CRD validation. Get the latest release tag and update. See the patterns doc for project-specific details (e.g., MetalLB FRR companion image).
- Feature gate exports: `grep -rn 'KUBE_FEATURE_' . --include='*.sh' | grep -v vendor/` — check the rebase script output for new default-true gates. Add `export KUBE_FEATURE_<name>=false` to `hack/test-go.sh` if the repo's tests use fake clientsets with informers.

**Verify the script actually ran** — if the output is empty or
the script wasn't found, the autofix was skipped and all its
fixes are missing. If the autofix reports PASS with no commits,
that means there were no patterns to fix — this is normal for
repos with few k8s dependencies. **You must still run the step3
gates below** — they discover issues the autofix doesn't cover.
If FAIL, check `git log` for autofix commits
— if any groups already committed, fix remaining items manually
rather than re-running. Re-running duplicates the committed
groups (new commits, not amends). Check output for MetalLB FRR
image warnings —
if the autofix bumped MetalLB, verify the FRR image variable
matches what the new MetalLB version ships. Read the patterns doc
for unfamiliar patterns:
```bash
PATTERNS=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-patterns.md" -path "*/k8s-rebase/docs/*" 2>/dev/null | head -1)
[ -n "$PATTERNS" ] && cat "$PATTERNS"
```

**Gate:** Find the gate prompt directory, `cat` each file below,
and launch one subagent per file with its contents as the prompt.
All in one parallel wave. Prepend the repo path and the module
safety rule (see Step 1 gate launch) to each prompt.
Do not skip, batch, or defer any gate — launch all 11 in a
single message. Gate subagents run independently and do not
consume your context window.
```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 \
  -path "*/k8s-rebase/gates/step3-autofix" -type d 2>/dev/null | head -1)
```
Gate files:
- `autofix-result.md` (count)
- `deprecated-api-remnants.md` (count)
- `feature-gates.md` (count)
- `major-version-imports.md` (count)
- `deprecated-calls.md` (count)
- `autofix-diff-review.md` (judge)
- `crd-validation.md` (count)
- `logical-completeness.md` (count)
- `e2e-infra.md` (judge)
- `dep-release-notes.md` (judge)
- `patterns-completeness.md` (judge)

Count gates must report 0. Judge gates must cite evidence.

**Gate-fix loop:** If ANY gate reports FAIL (count gate with
issues > 0, OR judge gate with verdict FAIL):

1. **Triage**: Read each FAIL gate report (DETAILS with
   file:line). For each finding, check the base branch:
   `BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`
   `git show $BASE:<file>` — if the same issue exists on the
   base branch, it's pre-existing. If the file doesn't exist
   on base (new file), the finding IS new. Skip pre-existing
   findings.

2. **Fix**: For each NEW finding, fix the cited issue and
   commit.

3. **Re-run** (mandatory — never skip this step): Delete the
   old gate report first (`rm .rebase-tmp/gates/<gate>.report`),
   then re-run the gate (cat the gate file, launch a fresh
   subagent with its contents). The old report MUST be deleted
   before re-running — if the agent fixes code but skips
   re-running, stale FAIL reports persist and auto-record will
   report FAIL even though the issue was fixed.

Repeat up to 3 times per gate. If it still fails after 3
attempts, report remaining issues and proceed. This loop
discovers and fixes deprecated-but-compiling patterns without
needing pre-existing autofix knowledge.

Before proceeding: if you modified any go.mod in steps 2-3
(gate-fix loop, manual dep bumps), re-run `go mod tidy &&
go mod vendor` in each affected module directory. Stale vendor
causes CI failures.

**When all step3 gates pass (or remaining issues are reported
after 3 attempts), proceed to Step 4 immediately.** Do NOT stop
or declare the rebase "done" — Steps 4 and 5 are mandatory.

### Step 4: Lint, test, and review

Fix lint issues first (they're fast to iterate on), then launch
one parallel wave that verifies everything at once.

**4a. Lint iteration:**

```bash
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-validate.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
[ -n "$SCRIPT" ] && bash "$SCRIPT" --no-test   # build + vet + lint (~5 min)
# For faster build/vet iteration: bash "$SCRIPT" --quick  (~1 min)
```

Fix every reported issue. The lint version bump surfaces
pre-existing issues — fix them all, they will block CI.
golangci-lint v2 defaults to showing only 3 instances of each
error type. The validate script overrides this with
`--max-same-issues 0` so all issues appear in one run.

**Lint strategy:** Run lint once, analyze ALL errors before
fixing any. Group by category (ST1005, QF1001, ioutil, errcheck,
etc.) and fix each category in one commit — not one fix per
iteration. Fixing one issue can unmask others, so expect 2-3
re-runs, but each re-run should surface NEW categories, not
the same ones fixed piecemeal. For errcheck exclusions, grep
the project first (see patterns doc for the grep command and
common exclusions template).

**Creating `.golangci.yml`:** If the project has no config file
and errcheck flags many unchecked `fmt.Fprintf`/`.Close()` calls,
create a `.golangci.yml` with `exclude-functions` rather than
adding per-line `//nolint:errcheck` directives. Use
`default: standard` (not `default: none`) to preserve the full
default linter set — `default: none` silently disables linters
that would otherwise run.

**Staticcheck suppressions:** When staticcheck flags deprecated
API calls that cannot be fixed in this rebase (e.g., the
replacement is not yet available in vendored deps), use selective
suppressions — either `//nolint:staticcheck` on the specific
line, or `exclude-rules` in `.golangci.yml` with the check code
and text pattern. Never disable staticcheck entirely — selective
suppressions preserve coverage for other checks.

**Nilness dead code:** The bumped golangci-lint catches `if err
!= nil` blocks where err is guaranteed nil. Remove the entire
dead block. Do not simplify or restructure.

**Error string casing (ST1005):** When lowercasing error strings
for ST1005, preserve acronyms — lowercase only the first letter,
not the entire string: `"VIPs cannot"` → `"vIPs cannot"` is
WRONG, `"vips cannot"` or keeping `"VIPs"` with a nolint
directive is correct. Also grep for the OLD string in all Go
files (not just tests) — test assertions and `strings.Contains`
checks break if the error text changes without updating the
match.

**Test caching:** Always use `-count=1` when running tests
manually. Go's test cache can return stale passes.

Iterate with `--quick` for build+vet, `--no-test` to include
lint. Repeat until `--no-test` exits 0.

**4b. Verification wave:** Once 4a passes,
launch ALL of the following subagents in one parallel wave.
Do not skip, batch, or defer any gate — launch all 15 in a
single message. Subagents run independently and do not consume
your context. No modifications happen after this point.

First, discover test packages:

```bash
TEST_GO_SH=$(find . -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" | head -1)
ROOT_PKGS=""
[ -n "$TEST_GO_SH" ] && ROOT_PKGS=$(sed -n '/root_pkgs=(/,/)/p' "$TEST_GO_SH" | grep -oE 'pkg/[^"]+' | tr '\n' '|')
for mod_dir in $(find . -name "go.mod" -not -path "*/vendor/*" -exec dirname {} \; | sort); do
  echo "=== $mod_dir ==="
  for pkg in $(cd "$mod_dir" && find . -name "*_test.go" -not -path "*/vendor/*" -exec dirname {} \; | sort -u); do
    [ -n "$ROOT_PKGS" ] && echo "$pkg" | grep -qE "^\./(${ROOT_PKGS%|})" && continue
    echo "$pkg"
  done
done
```

**Test agents** (count-check, all must report 0 FAIL):
Use ONLY the packages from the discovery snippet above — it
filters out `root_pkgs` which need CAP_NET_ADMIN (network
namespaces) and will always fail with "permission denied" in
unprivileged containers. Do NOT pass `./pkg/...` or `./...`
directly. Some repos (especially CNI plugins) have tests
requiring privileges but don't define `root_pkgs`. If a test
package fails with "operation not permitted" or "permission
denied", skip that package — it needs capabilities (e.g.,
CAP_NET_ADMIN) that containers lack. Similarly, `test/e2e`
suites with BeforeSuite that require a live cluster (kubeconfig,
MCP_MODE, etc.) always fail locally — these are pre-existing
infrastructure requirements, not rebase issues. Other packages
in the same repo may still pass. Each agent uses the validate script's `--test-only`
flag, which handles containerization, feature gate exports,
timeout scaling, and output capture automatically.

Tests can take 10-60 minutes. Use `timeout: 600000` for small
package groups. For packages over ~20k test lines, use nohup
to avoid the 10-minute Bash timeout:
```bash
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-validate.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
REPO_ROOT=$(git rev-parse --show-toplevel)
nohup bash "$SCRIPT" --test-only ./pkg/ovn > "$REPO_ROOT/.rebase-tmp/test-ovn.log" 2>&1 &
echo $! > "$REPO_ROOT/.rebase-tmp/test-ovn.pid"
```
Check ONCE (do not poll in a loop): `kill -0 $(cat .rebase-tmp/test-ovn.pid) 2>/dev/null && echo running || echo done`
The nohup log (`test-ovn.log`) has the PASS/FAIL verdict.
Detailed test output is in `.rebase-tmp/test-only-*.log`.

Split packages across agents by test line count (`wc -l
*_test.go`). Each containerized `go test` compilation uses
~5GB RAM. Check available memory (`free -h`) first:

**<=16GB RAM:** run test agents sequentially (gate read-only
agents can still run in parallel — they don't compile).
On constrained machines, running 1 representative test group
locally and relying on CI for full coverage is acceptable —
the compile-only vet (go test -run='^$') in Step 3 already
catches format string and type issues.
pkg/ovn is prone to OVSDB timeout flakes under memory
pressure — these are
container timing issues, not rebase bugs. The validate
script automatically limits compiler parallelism (GOMAXPROCS=2)
for large packages to reduce memory pressure. Cap each agent
at ~30k test lines. Example split for ovn-kubernetes (adapt
paths from discovery output above for other repos):
```bash
# Agent 1: biggest package alone (~56k lines, nohup — takes ~16 min)
nohup bash "$SCRIPT" --test-only ./pkg/ovn > .rebase-tmp/test-ovn.log 2>&1 &
# Agent 2: ovn sub-packages (~30k lines), timeout: 600000
bash "$SCRIPT" --test-only ./pkg/ovn/controller/... ./pkg/ovn/topology/...
# Agent 3: clustermanager (~33k lines), timeout: 600000
bash "$SCRIPT" --test-only ./pkg/clustermanager/...
# Agent 4: everything else (~42k lines), timeout: 600000
bash "$SCRIPT" --test-only ./pkg/util/... ./pkg/factory/... ./pkg/cni/...
```

**32GB+ RAM:** example parallel split for ovn-kubernetes:
```bash
# Agent 1: biggest package alone (nohup — takes 10-30+ min)
nohup bash "$SCRIPT" --test-only ./pkg/ovn > .rebase-tmp/test-ovn.log 2>&1 &
# Agent 2: sub-packages, timeout: 600000
bash "$SCRIPT" --test-only ./pkg/ovn/controller/... ./pkg/ovn/topology/...
# Agent 3: everything else, timeout: 600000
bash "$SCRIPT" --test-only ./pkg/util/... ./pkg/clustermanager/...
```

Results are in `.rebase-tmp/test-only-*.log`. Do NOT run raw
`go test` inside containers — stdout piping across container
boundaries loses output. The `--test-only` flag writes to a log
file on the mounted volume, so results are always readable.

The following gate agents are read-only (no compilation) and
can run alongside test agents without adding memory pressure.
Find the gate prompt directory, `cat` each file below, and
launch one subagent per file with its contents as the prompt.
Prepend the repo path and the module safety rule (see Step 1
gate launch) to each prompt.
```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 \
  -path "*/k8s-rebase/gates/step4-verification" -type d 2>/dev/null | head -1)
```
Gate files:
- `cleanliness.md` (count)
- `correctness.md` (count)
- `version-completeness.md` (count)
- `maintainer-review.md` (judge)
- `ci-prediction.md` (judge)
- `build-vet-recheck.md` (count)
- `skill-improvement.md` (judge)
- `logical-consistency.md` (judge)
- `ci-readiness.md` (judge)
- `gomod-diff-analysis.md` (judge)
- `deprecated-imports.md` (count)
- `go-version-check.md` (count)
- `k8s-changelog.md` (judge)
- `dep-cve-check.md` (judge)
- `commit-messages.md` (count)

All count-checks must be 0. Investigate judgment concerns.

**Gate-fix loop:** If ANY gate reports FAIL:
1. **Triage**: Check each finding against the base branch:
   `git show $(git merge-base HEAD master 2>/dev/null ||
   git merge-base HEAD main):<file>` — if the same issue
   exists on the base branch, it's pre-existing (skip it).
   If the file was NOT modified by this branch (`git diff
   $BASE..HEAD -- <file>` is empty), it's pre-existing.
2. **Fix**: Fix each NEW finding at the cited location. Commit.
3. **Re-validate**: After any code-changing fix, re-run
   `validate.sh --no-test` to confirm build+vet+lint still pass.
   Fix commits can introduce new build/lint regressions — catch
   them here before re-running the gate.
4. **Re-run** (mandatory — never skip): Delete the old gate report
   (`rm .rebase-tmp/gates/<gate>.report`), then re-launch the
   gate subagent with a fresh prompt. The old report MUST be
   deleted before re-running — if you fix code but skip
   re-running, stale FAIL reports persist and auto-record will
   report FAIL even though the issue was fixed.
Repeat up to 3 times per gate. If it still fails, report
remaining issues and proceed.

If any test agent reports failures or timeouts:
- **Timeout** likely means a feature gate issue (informer hang).
  Check that all gates from the `GATE_DEPS` map in
  `k8s-rebase-autofix.sh` are disabled in the
  failing package's test suite.
- **Flaky failure**: re-run the specific failing test individually
  (`go test -count=1 -run TestName ./pkg/...`). If it passes on
  retry, it's a flake — not a rebase issue. Large test suites
  (pkg/ovn) are prone to flakes in full-suite runs.
- **Container timing flake**: tests with tight timing margins
  (e.g., 1s context timeout racing a 5×200ms retry loop) flake
  in containers but pass on bare metal CI. Check if the test
  code changed in the rebase (use
  `git diff $(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main) -- path/to/test.go`).
  If identical on the base branch, it's pre-existing — fix it
  if it blocks you (increase timeout, not relax assertion) but
  note it's pre-existing in the commit message so the maintainer
  can split it out.
- **Pre-existing failure**: if it fails consistently, check if the
  same test file changed in the rebase (same merge-base diff).
  If unchanged, it's pre-existing — don't fix. Do NOT checkout
  master/main — switching branches corrupts later steps.
- Fix genuine rebase failures and re-run from 4a.

**4c. Independent review:** Once 4b passes, run the antagonistic
review script. This invokes a separate Claude instance with fresh
context for a truly independent second opinion:

```bash
REVIEW=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-review.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
if [ -n "$REVIEW" ]; then
  bash "$REVIEW" "$(git rev-parse HEAD)" "k8s rebase"
fi
```

APPROVE means proceed. REJECT means investigate the stated reason.

Once all Step 4 checks pass (4a lint clean, 4b gates report zero
issues, 4c review approves), proceed to Step 4d if `--bump-tools`
was passed, otherwise go directly to Step 5.

**4d. Non-k8s Go module updates (--bump-tools only):**

If `--bump-tools` was passed, discover outdated non-k8s direct
Go dependencies and bump them. The Makefile tool versions
(Node, NPM, NVM) are handled by the script. This step handles
Go module deps that the script cannot safely bump (go mod tidy
could corrupt k8s version pins via MVS).

Find the module directory (the one with k8s.io deps in go.mod)
and list outdated non-k8s direct deps:

```bash
MODDIR=$(dirname $(find . -name go.mod -not -path '*/vendor/*' -exec grep -l 'k8s.io/' {} \; | head -1))
cd "$MODDIR"
go list -mod=readonly -m -u -json -e all 2>/dev/null | \
  python3 -c "
import json, sys
for block in sys.stdin.read().replace('}\n{', '}|{').split('|'):
  try:
    obj = json.loads(block)
    if 'Update' in obj and not obj.get('Indirect'):
      p = obj['Path']
      if not any(x in p for x in ['k8s.io/','sigs.k8s.io/','openshift/']):
        print(f'{p} {obj[\"Version\"]} -> {obj[\"Update\"][\"Version\"]}')
  except: pass
"
```

For each outdated dep:
- Skip deps in replace directives (`grep "=>" go.mod`)
- Skip deps pinned to commit hashes or pre-release versions
- Run `go get dep@latest` then verify k8s pins are intact:
  `grep 'k8s.io/api ' go.mod` should still show the target version
- If k8s pins changed, revert that bump and note which dep
  pulled in a conflicting k8s version
- If the dep is `github.com/onsi/ginkgo/v2` and the Makefile
  has GINKGO_VERSION, update it to match the new go.mod version
  (ginkgo CLI must match the library to avoid flag parsing errors)
- One commit per dep for clean blame

If `--bump-tools` was not passed, skip this step.

**Proceed to Step 5 immediately.** Do NOT stop — the rebase is
incomplete without the PR command from Step 5.

---

**MANDATORY CHECKPOINT — run this before Step 5 regardless of
--bump-tools:**

```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 \
  -path "*/k8s-rebase/gates" -type d 2>/dev/null | head -1)
EXPECTED=$(find "$GATE_DIR" -name '*.md' 2>/dev/null | wc -l)
ACTUAL=$(ls .rebase-tmp/gates/*.report 2>/dev/null | wc -l)
echo "Gate reports: $ACTUAL / $EXPECTED"
```

If ACTUAL < EXPECTED, go back and launch the missing gates. To
find which are missing, check each gate .md file against the
reports in `.rebase-tmp/gates/`. Do NOT proceed to Step 5 until
ACTUAL >= EXPECTED — the test harness will record FAIL.

---

### Step 5: PR and cleanup

**CRITICAL: NEVER run `git push` or `gh pr create` yourself. Only
print commands for the user to copy-paste. You must not push to any
remote or create any PR — the user does this manually.**

**5a. Gather data and detect downstream:**

```bash
PRIMARY_GOMOD=$(find . -name go.mod -not -path '*/vendor/*' -not -path '*/.claude/*' -exec grep -l 'k8s.io/' {} \; 2>/dev/null | head -1)
K8S_VER=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -oE 'v[0-9.]+' | head -1)
GO_VER=$(grep '^go ' "$PRIMARY_GOMOD" 2>/dev/null | awk '{print $2}')
IS_DOWNSTREAM=$(git remote -v 2>/dev/null | grep -q 'openshift/' && echo true || echo false)
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
```

**OCP version for downstream repos:** The k8s-to-OCP mapping is:
k8s 1.N → OCP 4.(N-13) for k8s ≤1.35 (e.g., 1.34→4.21, 1.35→4.22).
OCP 4.23 was rebranded as 5.0, so for k8s 1.36+:
k8s 1.N → OCP 5.(N-36) (e.g., 1.36→5.0, 1.37→5.1, 1.38→5.2).
Use `release-5.X` branches and `openshift-5.X` in CI image refs.
Use this to determine the correct release branch for
`openshift/api`, `openshift/client-go`, and `openshift/library-go`.
Do NOT escalate to a newer release branch to fix dependency
conflicts — find newer commits on the CORRECT branch instead.
Also read the OCP version from existing `.ci-operator.yaml` or
Dockerfiles to confirm (`grep -rn 'openshift-[0-9]' .`).

If `IS_DOWNSTREAM` is true, the PR title needs a Jira ticket key
(OpenShift merge bots require `jira/valid-reference`). If the user
is interactive, ask for the key. If running in background mode
(no interactive user), use `REPLACE-WITH-JIRA-KEY:` as the title
prefix — do NOT prompt or wait for input.

**5b. Generate `gh pr create` command.** Do NOT execute this
command yourself — NEVER run `git push` or `gh pr create`.
Print the complete, ready-to-paste command for the user.
The user will push and create the PR themselves.

Run `git log --oneline $BASE..HEAD` to get the commit list.
Write a PR body that includes:
- One-line summary: k8s version, Go version
- What changed: list the fix categories from the commit subjects
- Commit table: paste the git log output, note which are mechanical
- Verification: what passed locally (build, vet, lint, tests)
- Footer: "All commits carry `Assisted-by: Claude Code` trailers."

Output the complete `gh pr create --title "..." --body "..."` command
using a heredoc for the body. If any data is unavailable, use what
you have — a PR command with partial data is better than no command.

Adapt the title to the project's convention (check CONTRIBUTING.md).
If the PR already exists, suggest `gh pr edit`.

**5c. Suggest CI monitoring:**

`/loop 5m check CI on the PR, explore any failures max carefully, find root causes`

**5d. Write rebase report.** Read `.rebase-tmp/rebase-report.md`
(your checkpoints from each step) and synthesize a final report.
Before recording any issue, verify it's real: check if it exists
on the base branch, confirm the fix actually works, and note the
root cause. Write the report to `.rebase-tmp/rebase-report.json`:

```json
{
  "repo": "<repo name>",
  "from_version": "<previous k8s version from base branch>",
  "to_version": "<target k8s version>",
  "steps": {
    "1_deps": {"duration_estimate": "fast|medium|slow", "issues": []},
    "2_compilation": {
      "total_errors": 0,
      "error_categories": {"type_mismatch": 0, "missing_field": 0, "removed_api": 0},
      "files_modified": 0,
      "gate_iterations": 0
    },
    "3_autofix": {
      "patterns_applied": [],
      "manual_fixes": [],
      "gate_fix_loops": 0
    },
    "4_lint_test": {
      "lint_issues_fixed": 0,
      "test_failures": [],
      "gate_results": {}
    }
  },
  "discoveries": [
    {"description": "...", "category": "deprecation|api_change|tooling|pattern", "verified": true}
  ],
  "unresolved": [
    {"description": "...", "reason": "pre-existing|out-of-scope|needs-human"}
  ],
  "skill_improvements": [
    {"area": "gate|autofix|script|skill", "suggestion": "...", "evidence": "..."}
  ]
}
```

Fill in actual data from the rebase. For `skill_improvements`,
focus on concrete, actionable suggestions backed by what you
observed — not generic advice. Each suggestion should reference
the specific issue that prompted it.

**5e. Clean up:**

```bash
rm -rf .rebase-tmp/step*.log .rebase-tmp/step*.pid .rebase-tmp/*.log \
       .rebase-tmp/*.txt .rebase-tmp/*.pid .rebase-tmp/rebase-report.md \
       .rebase-tmp/crd-pre-codegen/
```

Do NOT delete `.rebase-tmp/gates/` or `.rebase-tmp/rebase-report.json`
— the test harness reads gate reports for auto-recording, and the
rebase report is the deliverable from step 5d.
