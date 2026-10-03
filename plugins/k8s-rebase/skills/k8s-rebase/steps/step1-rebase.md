PROGRESS: 20% complete

Read rules.md first — it contains shared rules for all steps.

# Step 1: Deterministic Rebase

Run from the default branch (master/main). The script creates a
new timestamped branch. Do not reuse branches from prior runs.

**Recovery:** If a run fails mid-way through Steps 2-4, check
`git log` on the rebase branch. The mechanical rebase commits
from Step 1 are always safe. To resume: start a new session on
the same branch and use the SKILL.md recovery checks. Do not delete the
interrupted branch or evidence as part of automatic recovery.

**Important:** This script takes 5–30 minutes (longer if it
auto-containerizes). Use the runtime's supported long-running command
session and wait for its completion. Bind PLUGIN_ROOT, REPO_ROOT,
VERSION, and BUMP_TOOLS from the verified invocation in this call:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && echo "ERROR: Not in a git repo" && exit 1
if ! [[ -f "$REPO_ROOT/go.mod" || -f "$REPO_ROOT/go-controller/go.mod" ]]; then
  echo "ERROR: $REPO_ROOT has no go.mod — are you in a workspace root instead of the target repo?"
  exit 1
fi
SCRIPT="$PLUGIN_ROOT/scripts/k8s-rebase.sh"
ARGS=("$VERSION")
[[ "$BUMP_TOOLS" == true ]] && ARGS=(--bump-tools "${ARGS[@]}")
mkdir -p "$REPO_ROOT/.rebase-tmp"
cd "$REPO_ROOT" || exit 1
bash "$SCRIPT" "${ARGS[@]}" > "$REPO_ROOT/.rebase-tmp/step1.log" 2>&1 &
echo $! > "$REPO_ROOT/.rebase-tmp/step1.pid"
wait "$!"
```

The shell waits for the child, preserving its exit status; keep that shell
session alive with native waiting, rather than imposing a short timeout.
If the runtime cannot retain a command session, use a detached `nohup`
launch with the same quoted argv, log, and PID paths; check the process
until it actually exits. A "still running" check is not a notification.
On recovery, inspect the recorded process and log before any new launch.

After process completion, look at the last lines of the log.
**Exit 0** = already at target version, nothing to do — stop without
advancement or a PR command. The script removes its temporary state and
restores the pre-push hook on this path.
**Exit 2** = success — proceed to validation. **Exit 1** = error.
The `step1-result.txt` marker is written before optional tooling finishes;
even `EXIT 2` there is not proof of process completion. If the result is
missing or the exit failed, inspect `tail -20 .rebase-tmp/step1.log`
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

Follow the gate procedure in rules.md, including cached non-PASS verdicts.
Delegate PENDING gates when available, or review inline. The reviewer context must
include: repo path, module safety rule (from rules.md), and
"Read `$PLUGIN_ROOT/gates/step1-rebase/<filename>` and follow
its instructions." Include the absolute plugin root and version too.

Gate file:

- `rebase-completeness.md` (count)

**Gate-fix loop:** If the gate reports FAIL:

1. **Fix**: For each failing check (missing codegen, uncommitted
   changes, stale replace directives, wrong dep versions),
   fix the issue and commit.

2. **Re-run** (mandatory): Follow rules.md to refresh companion evidence
   and complete stale/pending reviews after the commit. Do not delete the
   newly refreshed report.
Repeat up to 3 times. If it still fails, stop and report the
remaining issues — step 1 failures are structural and proceeding
would cause cascading problems in later steps.

Also check `.rebase-tmp/summary.txt` for `## CODEGEN FAILURE`.
If present, fix the codegen script (e.g., remove dropped flags),
re-run codegen, commit, and re-verify.

## Advance

When the Step 1 gate passes, return the results to the parent for advancement
as described in SKILL.md. A step worker must not call `advance` itself.
On structural failure, return the stop result instead: neither worker nor
parent may call `advance` to record the failure or reach a force-advance threshold.
