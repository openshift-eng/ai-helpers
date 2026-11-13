#!/bin/bash
# Stop hook for k8s-rebase — delegates to orchestrator.
# Blocks session exit unless the orchestrator reports DONE.
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ORCH="$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh"

# Multi-hook safety: yield if another hook already blocked
ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)
[[ "$ACTIVE" == "true" ]] && exit 0

# Get session working directory (worktree, not repo root)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[[ -z "$CWD" ]] && exit 0

# Activation guard: only enforce during active rebase sessions
[[ -f "$CWD/.rebase-tmp/.session-active" ]] || exit 0

# While the step1 script runs, do not let the session end. A headless
# session (claude -p) exits when its turn ends and no background-task
# notification arrives, which abandons Step 1 and the rest of the workflow.
# The block reason tells the agent how to wait. The script's result marker
# precedes optional work, so it must not end the wait; once the child exits,
# fall through to normal gate checks. A retained PID must not block later steps.
STEP1_PID_FILE="$CWD/.rebase-tmp/step1.pid"
if [[ -f "$STEP1_PID_FILE" ]] &&
   [[ "$(jq -r '.current_step // empty' "$CWD/.rebase-tmp/state.json" 2>/dev/null)" == 1 ]]; then
  STEP1_PID=$(cat "$STEP1_PID_FILE" 2>/dev/null)
  # kill -0 also succeeds for exited, unreaped children (zombies).
  if [[ "$STEP1_PID" =~ ^[1-9][0-9]*$ ]] && kill -0 "$STEP1_PID" 2>/dev/null &&
     STEP1_STATUS=$(ps -p "$STEP1_PID" -o stat= 2>/dev/null) &&
     [[ -n "$STEP1_STATUS" && ! "$STEP1_STATUS" =~ ^[[:space:]]*Z ]]; then
    jq -n --arg reason "Step 1's rebase script (PID $STEP1_PID) is still running. Do not end your turn: wait in the foreground by repeating 'timeout 570 tail --pid=$STEP1_PID -f /dev/null' until the process exits, then read .rebase-tmp/step1.log and step1-result.txt and continue the skill." \
      '{"decision":"block","reason":$reason}'
    exit 0
  fi
fi

# Delegate to orchestrator
STATUS=$(bash "$ORCH" status "$CWD" 2>/dev/null) || true

if [[ "$STATUS" == *"DONE: true"* ]]; then
  exit 0
fi

# Block with actionable reason
jq -n --arg reason "$STATUS" '{"decision":"block","reason":$reason}'
exit 0
