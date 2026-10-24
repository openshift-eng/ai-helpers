# Step 1: Deterministic Rebase

PROGRESS: 20% complete

Read `${PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` first.

For Kubernetes 1.37, read `${PLUGIN_ROOT}/docs/k8s-1.37.md` before starting:
it records the upstream toolchain, downstream dependency readiness, and test
baselines. Recheck moving branches and PRs; the recorded snapshot is not proof
that an upstream fix has merged.

For a fresh run, start from the working branch (normally master/main).
The script creates a new timestamped rebase branch; do not reuse branches
from prior runs.

**Recovery:** If a run fails mid-way through Steps 2-4, check
`git log` on the rebase branch and retain completed Step 1 commits.
To resume: start a new session on the same branch and use the SKILL.md
recovery checks. Preserve the interrupted branch, reports, and logs.

**Important:** This script takes 5–30 minutes (longer if it
auto-containerizes). Use the runtime's supported long-running command
session and wait for its completion. Bind PLUGIN_ROOT, REPO_ROOT,
VERSION, and BUMP_TOOLS from the verified invocation in this call:

After bootstrap and before launching Step 1, retain the original pre-push
hook state under `.rebase-tmp/`: observed absence, or its bytes and mode.
This makes the final restoration check verifiable. On resume, preserve an
existing snapshot and report a missing original observation as a limit; do
not infer the preimage from the helper's backup convention.

Also bind and export the host's `AI_TRAILER` as specified in rules.md before
launching the script so its generated commits identify the actual assistant.

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
Never end your turn while the script runs, and do not launch it as a
background task to be notified later: a headless session ends with its turn
and no notification arrives, abandoning the rebase. If a command call returns
or times out first, keep waiting in the foreground with repeated
`timeout 570 tail --pid="$(cat "$REPO_ROOT/.rebase-tmp/step1.pid")" -f /dev/null`
calls until the process exits.
On recovery, inspect the recorded process and log before any new launch.

After process completion, retain the actual producer PID, completed native
wait result and exit status in the handoff, and verify the producer is absent.
A later metadata writer's PID cannot establish which original producer ran.
Check the log's last lines as well.
**Exit 0** = already at the target minor, nothing to do — stop without
advancement or a PR command. The script deletes `.rebase-tmp/`, including
state, the session marker, and this log, and restores the pre-push hook.
**Exit 2** = success — proceed to the gate. **Exit 1** = error.
The `step1-result.txt` marker is written before optional tooling finishes;
even `EXIT 2` there is not proof of process completion. If the result is
missing or the exit failed, inspect `tail -20 .rebase-tmp/step1.log`
for the error. Preserve completed dep bump and codegen commits.
Manually verify version references
(Dockerfiles, CI configs, lint version) since the script may
have crashed before updating them, then complete the Step 1 gate below.
Only the parent can advance to Step 2 after that handoff.

If `.rebase-tmp/summary.txt` contains `## CODEGEN FAILURE`, fix the codegen
script (for example, remove a dropped flag), rerun the repo's codegen target,
and commit before the gate.

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

Before the first gate, trace delegated CI launchers through their actual
external checkout, assignments and node-image consumer. In MCP, the local
Makefile pin selects kubectl; the delegated OVN installer can unconditionally
overwrite `K8S_VERSION` before launching KIND. A caller export alone cannot
override that assignment. Inspect immutable primary source and verify a
published target-minor node image separately from client/test-binary assets.
After the helper completes, a confirmed mismatch may require a scoped
repo-owned launcher compatibility repair before review. Prefer an override
supported by the actual external consumer; otherwise validate a bounded,
maintainable adapter against that consumer and reject unknown layouts.
Preserve upstream tracked files and document unpinned external-source limits.
This exception does not authorize manual dependency edits or another helper
run. Verify effective selection before spending Step 4's validation budget;
selection checks and offline tests do not establish live-cluster coverage.

If the output reports an unconfirmed OCP stream or an unavailable/unverifiable
image, check the repo's target-release CI config in `openshift/release` and
the candidate registry image. Keep unresolved verification visible in the
gate report; another rebase PR's tag alone does not establish availability.

## Gate

Run the orchestrator to collect companion evidence and discover gate state:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-orchestrator.sh" gates "$REPO_ROOT" 1
```

Follow the gate procedure in rules.md, including cached non-PASS verdicts.
Delegate PENDING gates when available, or review inline. The reviewer context must
include: repo path, the module safety and verdict rules from rules.md, and
"Read `$PLUGIN_ROOT/gates/step1-rebase/<filename>` and follow
its instructions." Include the absolute plugin root and version too.

Gate file:

- `rebase-completeness.md` (count)

Use rules.md's shared gate-fix loop for missing codegen, uncommitted changes,
stale replacements, or incorrect dependency versions. If the gate remains
unresolved after that budget, stop and report the structural failure.

## Advance

When the Step 1 gate passes, return the results to the parent for advancement
as described in SKILL.md. A step worker must not call `advance` itself.
On structural failure, return the stop result instead: neither worker nor
parent may call `advance` to record the failure or reach a force-advance threshold.
