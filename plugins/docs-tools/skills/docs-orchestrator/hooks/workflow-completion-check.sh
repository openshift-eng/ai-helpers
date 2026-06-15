#!/bin/bash
# workflow-completion-check.sh
#
# Stop hook: blocks Claude from stopping while the ACTIVE workflow
# is still running. Only checks the workflow identified by the
# .active-workflow marker — stale workflows from other sessions
# are ignored.
#
# Exit codes:
#   0 = allow stop
#   2 = block stop (reason sent to stderr)
#
# Requires: jq

set -u

INPUT=$(cat)

if ! cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null; then
  echo "Cannot access project directory; cannot verify workflow status." >&2
  exit 2
fi

# Look for progress files
shopt -s nullglob
PROGRESS_FILES=(.agent_workspace/*/workflow/*.json)
shopt -u nullglob
if [ ${#PROGRESS_FILES[@]} -eq 0 ]; then
  exit 0
fi

MARKER=".agent_workspace/.active-workflow"

# No marker → no active workflow → allow stop
if [ ! -f "$MARKER" ]; then
  exit 0
fi

# Read the marker — fail closed on parse errors
PROGRESS_FILE=$(jq -r '.progress_file // empty' "$MARKER" 2>/dev/null)
JQ_RC_PF=$?
TICKET=$(jq -r '.ticket // empty' "$MARKER" 2>/dev/null)
JQ_RC_TK=$?

if [ "$JQ_RC_PF" -ne 0 ] || [ "$JQ_RC_TK" -ne 0 ]; then
  echo "Failed to parse $MARKER; refusing to stop (fail closed)." >&2
  exit 2
fi

# Marker parsed successfully but fields are empty → stale marker → clean up
if [ -z "$PROGRESS_FILE" ] || [ -z "$TICKET" ]; then
  rm -f "$MARKER"
  exit 0
fi

# Progress file doesn't exist → stale marker → clean up and allow stop
if [ ! -f "$PROGRESS_FILE" ]; then
  rm -f "$MARKER"
  exit 0
fi

# Check the workflow status — only block for in_progress workflows
WORKFLOW_STATUS=$(jq -r '.status' "$PROGRESS_FILE" 2>/dev/null)

if [ "$WORKFLOW_STATUS" != "in_progress" ]; then
  rm -f "$MARKER"
  exit 0
fi

WORKFLOW_TYPE=$(jq -r '.workflow_type' "$PROGRESS_FILE" 2>/dev/null)

# Anti-loop guard: per-workflow counter prevents infinite blocking
COUNTER_FILE="${PROGRESS_FILE}.stop_count"
if [ -f "$COUNTER_FILE" ]; then
  COUNT=$(cat "$COUNTER_FILE")
else
  COUNT=0
fi
if [ "$COUNT" -ge 5 ]; then
  rm -f "$COUNTER_FILE"
  rm -f "$MARKER"
  exit 0
fi

# Get step order from the progress file
mapfile -t STEP_ORDER < <(jq -r '.step_order[]' "$PROGRESS_FILE" 2>/dev/null)

if [ ${#STEP_ORDER[@]} -eq 0 ]; then
  mapfile -t STEP_ORDER < <(jq -r '.steps | keys[]' "$PROGRESS_FILE" 2>/dev/null)
fi

# Find the first incomplete step
NEXT_STEP=""
for step in "${STEP_ORDER[@]}"; do
  STEP_STATUS=$(jq -r --arg s "$step" '.steps[$s].status // "missing"' "$PROGRESS_FILE")
  case "$STEP_STATUS" in
    completed|skipped|deferred) continue ;;
    *) NEXT_STEP="$step"; break ;;
  esac
done

if [ -n "$NEXT_STEP" ]; then
  echo "$((COUNT + 1))" > "$COUNTER_FILE"
  echo "Documentation workflow '$WORKFLOW_TYPE' for $TICKET is not complete. Next step: $NEXT_STEP. Read the progress file at $PROGRESS_FILE then continue the workflow." >&2
  exit 2
fi

# All steps done — clean up and allow stop
rm -f "$COUNTER_FILE"
rm -f "$MARKER"
exit 0
