#!/bin/bash
# PreToolUse hook: block deletion of gate reports from completed prior steps.
#
# The orchestrator is forward-only: once step N advances to N+1, there is
# no path back to regenerate step-N reports. A model that runs
# `rm .rebase-tmp/gates/step2-*.report` from step 3 or 4 permanently loses
# those verdicts, causing "missing N of 33 gates" at court time.
#
# This hook reads state.json to determine the current step and blocks any
# rm command that would delete a report from a lower (already-completed) step.
# Only fires when .rebase-tmp/.session-active exists.

set -euo pipefail
command -v jq >/dev/null 2>&1 || { printf '{"decision":"block","reason":"jq required by block-prior-step-rm hook"}\n'; exit 0; }

INPUT=$(cat)

REPO_CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[[ -f "$REPO_CWD/.rebase-tmp/.session-active" ]] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -z "$CMD" ]] && exit 0

# Only inspect rm commands touching .report files in the gates directory
echo "$CMD" | grep -qE '\brm\b' || exit 0
echo "$CMD" | grep -qE 'step[0-9].*\.report|gates/\*' || exit 0

STATE_FILE="$REPO_CWD/.rebase-tmp/state.json"
[[ -f "$STATE_FILE" ]] || exit 0
CURRENT_STEP=$(jq -r '.current_step // empty' "$STATE_FILE" 2>/dev/null)
[[ -z "$CURRENT_STEP" || "$CURRENT_STEP" == "null" ]] && exit 0

# Extract step numbers referenced in the rm command
BLOCKED=""
while IFS= read -r token; do
  [[ "$token" =~ ^step([0-9]+) ]] || continue
  step_num="${BASH_REMATCH[1]}"
  if [[ "$step_num" -lt "$CURRENT_STEP" ]]; then
    BLOCKED="${BLOCKED}step${step_num}-*.report (orchestrator is at step $CURRENT_STEP)\n"
  fi
done < <(echo "$CMD" | grep -oE 'step[0-9]+[^[:space:]"'"'"']*\.report' | sort -u)

# Also block glob patterns like .rebase-tmp/gates/*.report (removes ALL steps)
if [[ -z "$BLOCKED" ]] && echo "$CMD" | grep -qE 'gates/\*\.report|gates/\*'; then
  BLOCKED="glob matching all gates (orchestrator is at step $CURRENT_STEP)\n"
fi

if [[ -n "$BLOCKED" ]]; then
  jq -n --arg reason "$(printf \
    "BLOCKED: Deleting gate reports from a prior completed step.\n\nThe orchestrator is forward-only — once a step advances, its\nreports cannot be regenerated. Blocked pattern(s):\n  ${BLOCKED}\nOnly delete the SPECIFIC report you are re-running:\n  rm .rebase-tmp/gates/step${CURRENT_STEP}-<gate>.report\n\nPrior-step staleness is detected via HEAD stamps on individual\nreports — you do not need to delete them manually.")" \
    '{"decision":"block","reason":$reason}'
  exit 0
fi

exit 0
