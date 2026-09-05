# Step 3: Apply autofix patterns

PROGRESS: 60% complete

Read `${PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` first.

## Run the autofix script

Use `timeout: 600000` -- the autofix auto-containerizes and
runs go vet internally.

The autofix outputs RESULT: PASS or RESULT: FAIL.
FAIL is normal -- it means some checks found issues the autofix
could not fix automatically (e.g., complex test refactors).
The agent handles those in Step 4.
Regardless of output, proceed to gates.

```bash
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-autofix.sh"
```

Applies known fix patterns for the target k8s version.
The autofix does not write to summary.txt (that file comes from
the validate script).

If the autofix reports FAIL, the remaining issues will be
caught by the gates below. If remaining issues include feature
gates, read the GATE_DEPS map near the top of the autofix
script to discover which gates need entries. Each gate requires
three layers: (1) `export KUBE_FEATURE_<gate>=false` in
hack/test-go.sh, (2) os.Setenv/t.Setenv calls in test files
that already reference KUBE_FEATURE_ env vars, and (3) a key
in SetFromMap calls in test suite files. Check existing
patterns in each file for the insertion format. Only add gates
that exist in the vendored k8s.io/ code.

## Verify the script actually ran

If the output is empty or the script was not found, the autofix
was skipped and all its fixes are missing. If the autofix reports
PASS with no commits, that means there were no patterns to fix --
this is normal for repos with few k8s dependencies.

**You must still run the step3 gates below** -- they discover
issues the autofix does not cover.

If FAIL, check `git log` for autofix commits -- if any
groups already committed, fix remaining items manually rather than
re-running. Re-running duplicates the committed groups (new
commits, not amends). Read the patterns doc for unfamiliar
patterns:

```bash
cat "${PLUGIN_ROOT}/docs/k8s-rebase-patterns.md"
```

## Gates

Run the orchestrator to collect companion evidence and discover gate state:
```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-orchestrator.sh" gates "$REPO_ROOT" 3
```

Then launch one subagent per PENDING gate only. All PENDING gates in one
parallel wave. Each subagent prompt: repo path + module safety rule (from
rules.md) + "Read `<GATE_DIR>/<filename>` and follow its instructions."
Do NOT Read the gate files yourself -- let the subagent Read the gate file.

Gate directory: `${PLUGIN_ROOT}/gates/step3-autofix`

Gate files:
- `autofix-result.md` (count)
- `deprecated-api-remnants.md` (count)
- `feature-gates.md` (count)
- `major-version-imports.md` (count)
- `deprecated-calls.md` (count)
- `autofix-diff-review.md` (judge)
- `crd-validation.md` (count)
- `e2e-infra.md` (judge)
- `dep-release-notes.md` (judge)
- `patterns-completeness.md` (judge)

Count gates must report 0. Judge gates must cite evidence.

## Gate-fix loop

If ANY gate reports FAIL (count gate with issues > 0, OR judge
gate with verdict FAIL):

1. **Triage**: Read each FAIL gate report (DETAILS with
   file:line). For each finding, check the base branch:
   `BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`
   `git show $BASE:<file>` -- if the same issue exists on the
   base branch, it is pre-existing. If the file does not exist
   on base (new file), the finding IS new. Skip pre-existing
   findings.

2. **Fix**: For each NEW finding, fix the cited issue and
   commit.

3. **Re-validate**: After any code-changing fix, re-run
   `bash "$PLUGIN_ROOT/scripts/k8s-rebase-validate.sh" --quick`
   to confirm build+vet still pass. Fix commits can introduce
   new regressions -- catch them here before re-running the gate.

4. **Re-run** (mandatory -- never skip this step): Re-run the
   orchestrator gates command to refresh evidence, then delete
   ONLY the specific failing gate's report file
   (`rm .rebase-tmp/gates/step3-<gate>.report`) and re-run that
   gate. **NEVER delete step2-*.report files from step 3** —
   the orchestrator is forward-only and cannot regenerate step-2
   reports. If HEAD moves (new commit), step-2 reports remain
   valid; the orchestrator's own HEAD-stamp check handles
   staleness automatically. Deleting prior-step reports is
   permanent data loss.

Repeat up to 3 times per gate. If it still fails after 3
attempts, report remaining issues and proceed. This loop
discovers and fixes deprecated-but-compiling patterns without
needing pre-existing autofix knowledge.

## Before advancing

If you modified any go.mod in steps 2-3 (gate-fix loop, manual
dep bumps), re-run `go mod tidy && go mod vendor` in each
affected module directory. Stale vendor causes CI failures.

When all step3 gates pass (or remaining issues are reported after
3 attempts), proceed immediately. Do NOT stop or declare the
rebase "done" -- Steps 4 and 5 are mandatory.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-orchestrator.sh" advance "$REPO_ROOT"
```
