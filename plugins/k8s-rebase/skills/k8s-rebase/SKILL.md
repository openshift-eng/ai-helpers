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

**Never add test skips to make CI green.** If a test fails,
investigate and fix the root cause. Adding skip regexes or
`t.Skip()` to suppress failures hides real issues and erodes
maintainer trust. If the failure is pre-existing (same test
fails on the base branch), note it in the commit message but
do not skip it.

**Git operations:** Never use negated pathspecs with `git add`
(e.g., `git add -A -- . ':!dir'`). They fail when the path
is gitignored. Use plain `git add -A` instead.

**AI disclosure:** All commits must include the trailer
`Assisted-by: Claude Code <noreply@anthropic.com>`.
The scripts add it automatically. For manual commits use:
`git commit -s --trailer "Assisted-by: Claude Code <noreply@anthropic.com>"`
When amending, check `git log --oneline -1` first to confirm
HEAD is the commit you intend to amend. Use `--no-edit` to
preserve existing trailers. Do NOT re-pass `-s` or `--trailer`.

**Config file hygiene:** Do not add inline comments to config
files (`.ci-operator.yaml`, `Dockerfile`) explaining why a
version changed. The commit message is the explanation.

**Commit message cross-references:** Do not use `org/repo#N`
syntax in commit messages. It causes GitHub notification spam
on every force-push. Use plain text in commit messages; put
PR/issue links in the PR body instead.

**Replace directive tracking:** If a `replace` directive is
added for a temporary fork, add a go.mod comment noting that
a tracking ticket is needed for its removal (e.g.,
`// TODO: remove replace when upstream merges — track via Jira`).

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

**Check** (run every 3-5 minutes until done):
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

**Gate:** After the script finishes (or is killed), verify the
rebase is complete before proceeding:
```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 \
  -path "*/k8s-rebase/gates/step1-rebase" -type d 2>/dev/null | head -1)
```
Gate files:
- `rebase-completeness.md` (count)

If any check fails, fix the issue (commit staged changes,
re-run codegen, etc.) before proceeding.

Also check `.rebase-tmp/summary.txt` for `## CODEGEN FAILURE`.
If present, fix the codegen script (e.g., remove dropped flags),
re-run codegen, commit, and re-verify.

---

## Steps 2–5: Validation and Fixes

Every step ends with subagent verification. The step is not
complete until all subagents report zero issues.

**Subagent rules:**
- Report specific counts, not just "looks good."
- Judgment agents must cite the specific file:line or diff hunk
  for each concern — "no issues found" requires listing what
  was actually checked.
- Gate subagents are read-only — they verify and report, but
  must NOT edit files. The main agent applies fixes.
- If ANY judgment agent flags a concern, the main agent MUST
  investigate and either fix it or explain why it's not an
  issue before proceeding. Do not dismiss judgment concerns.
- Give subagents the repo path and tell them to use
  `podman run --userns=keep-id` with the golang container if
  they need Go tools (build, vet, lint, test).
- If you cannot launch subagents, run the gate checks inline.

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

Fix compilation errors from ALL modules (find all go.mod files).
Note: some modules (e.g., `test/e2e`) have gitignored vendor
directories and won't compile locally. Errors in those modules
(like unused variables) only surface in CI. Review `git diff`
for changes to those modules before pushing.

If errors appear in `/go/pkg/mod/` paths (not the project's own
code), a direct dependency is incompatible with the bumped k8s
packages. Extract the module path (between `/go/pkg/mod/` and
`@`) and fix with `go get <module>@latest && go mod tidy`.

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
wave. Prepend the repo path to each prompt so the subagent
knows where to look.
```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 \
  -path "*/k8s-rebase/gates/step2-compilation" -type d 2>/dev/null | head -1)
cat "$GATE_DIR/build-vet.md"  # read this, use as subagent prompt
```
Gate files:
- `build-vet.md` (count)
- `version-consistency.md` (count)
- `diff-scope.md` (count)
- `type-conversions.md` (judge)
- `fix-correctness.md` (judge)

Count gates must report 0. Judge gates must cite evidence.
Investigate all concerns before proceeding. To add a gate:
create a new `.md` file in `step2-compilation/` and add it
to this list.

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
**Verify the script actually ran** — if the output is empty or
the script wasn't found, the autofix was skipped and all its
fixes are missing. If FAIL, check `git log` for autofix commits
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
All in one parallel wave. Prepend the repo path to each prompt.
```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 \
  -path "*/k8s-rebase/gates/step3-autofix" -type d 2>/dev/null | head -1)
```
Gate files:
- `autofix-result.md` (count)
- `deprecated-api-remnants.md` (count)
- `feature-gates.md` (count)
- `autofix-diff-review.md` (judge)
- `crd-validation.md` (count)
- `logical-completeness.md` (count)
- `e2e-infra.md` (judge)
- `dep-release-notes.md` (judge)
- `patterns-completeness.md` (judge)

Count gates must report 0. Judge gates must cite evidence.
Investigate all concerns before proceeding.

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

**Nilness dead code:** The bumped golangci-lint catches `if err
!= nil` blocks where err is guaranteed nil. Remove the entire
dead block. Do not simplify or restructure.

**Error string casing (ST1005):** When lowercasing error strings
for ST1005, grep for the OLD string in all Go files (not just
tests). Both test assertions and production `strings.Contains`
checks will break if the error text changes without updating
the match.

**Test caching:** Always use `-count=1` when running tests
manually. Go's test cache can return stale passes.

Iterate with `--quick` for build+vet, `--no-test` to include
lint. Repeat until `--no-test` exits 0.

**4b. Verification wave:** Once 4a passes,
launch ALL of the following subagents in one parallel wave.
No modifications happen after this point — everything runs
simultaneously.

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
Check with: `kill -0 $(cat .rebase-tmp/test-ovn.pid) 2>/dev/null && echo running || echo done`
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
at ~30k test lines. Run 4 sequential agents:
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

**32GB+ RAM:** run 3 agents in parallel, including the biggest
via nohup:
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
Prepend the repo path to each prompt.
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

You MUST proceed to Step 5 and present a `gh pr create` command.
Do NOT stop here — the rebase is incomplete without the PR command.

### Step 5: PR and cleanup

**5a. Gather data and detect downstream:**

```bash
K8S_VER=$(grep 'k8s.io/api ' go.mod 2>/dev/null | grep -oE 'v[0-9.]+' | head -1)
GO_VER=$(grep '^go ' go.mod | awk '{print $2}')
IS_DOWNSTREAM=$(git remote -v 2>/dev/null | grep -q 'openshift/' && echo true || echo false)
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
```

If `IS_DOWNSTREAM` is true, ask the user for the Jira ticket key
before generating the PR command. OpenShift merge bots require
`jira/valid-reference` to allow merge. If the user does not have
one, use `REPLACE-WITH-JIRA-KEY:` as the title prefix so the
placeholder is impossible to overlook.

**5b. Generate `gh pr create` command.** Do NOT execute this
command yourself. Print the complete, ready-to-paste command
for the user.

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

**5c. Suggest CI monitoring and clean up:**

`/loop 5m check CI on the PR, explore any failures max carefully, find root causes`

```bash
rm -rf .rebase-tmp/
```
