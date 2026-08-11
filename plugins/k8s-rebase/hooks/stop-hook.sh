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

# Delegate to orchestrator
STATUS=$(bash "$ORCH" status "$CWD" 2>/dev/null) || true

if [[ "$STATUS" == *"DONE: true"* ]]; then
  exit 0
fi

# Block with actionable reason
jq -n --arg reason "$STATUS" '{"decision":"block","reason":$reason}'
exit 0
