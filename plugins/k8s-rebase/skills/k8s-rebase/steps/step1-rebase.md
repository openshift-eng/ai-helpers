PROGRESS: 20% complete

Read rules.md first — it contains shared rules for all steps.

# Step 1: Deterministic Rebase

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
# PLUGIN_ROOT is passed by the boot loader in the prompt.
SCRIPT="$PLUGIN_ROOT/scripts/k8s-rebase.sh"
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

## Gate

Run the orchestrator to collect companion evidence and discover gate state:
```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-orchestrator.sh" gates "$REPO_ROOT" 1
```

Launch subagents only for PENDING gates. The subagent prompt must
include: repo path, module safety rule (from rules.md), and
"Read `$PLUGIN_ROOT/gates/step1-rebase/<filename>` and follow
its instructions." Do NOT cat the gate file yourself — let the
subagent read it.

Gate file:
- `rebase-completeness.md` (count)

**Gate-fix loop:** If the gate reports FAIL:
1. **Fix**: For each failing check (missing codegen, uncommitted
   changes, stale replace directives, wrong dep versions),
   fix the issue and commit.
2. **Re-run** (mandatory — never skip): Re-run the orchestrator
   gates command to refresh evidence, then delete the old gate
   report (`rm .rebase-tmp/gates/step1-rebase-completeness.report`)
   and re-launch the gate subagent with a fresh prompt. Stale
   FAIL reports cause auto-record to mark the run as failed even
   if the fix worked.
Repeat up to 3 times. If it still fails, stop and report the
remaining issues — step 1 failures are structural and proceeding
would cause cascading problems in later steps.

Also check `.rebase-tmp/summary.txt` for `## CODEGEN FAILURE`.
If present, fix the codegen script (e.g., remove dropped flags),
re-run codegen, commit, and re-verify.

## Advance

When step 1 gate passes, run orchestrator.sh advance:
```bash
bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" advance "$REPO_ROOT"
```
