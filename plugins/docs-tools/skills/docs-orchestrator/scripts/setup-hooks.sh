#!/bin/bash
# setup-hooks.sh
#
# Install docs-orchestrator hooks into .claude/settings.json:
#   - Stop hook: blocks Claude from stopping while a workflow is in progress
#   - PostToolUse hook: deterministic post-requirements source resolution
#
# Safe to run multiple times — skips hooks that are already installed.

set -e

SETTINGS_FILE=".claude/settings.json"
HOOKS_DIR=".claude/hooks"

# Derive plugin root from script location if CLAUDE_PLUGIN_ROOT is not set
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
HOOKS_SRC="${PLUGIN_ROOT}/skills/docs-orchestrator/hooks"

# Copy hook scripts into the project
mkdir -p "$HOOKS_DIR"
cp "$HOOKS_SRC/workflow-completion-check.sh" "$HOOKS_DIR/"
cp "$HOOKS_SRC/post-requirements-source-resolve.sh" "$HOOKS_DIR/"
chmod +x "$HOOKS_DIR/workflow-completion-check.sh"
chmod +x "$HOOKS_DIR/post-requirements-source-resolve.sh"

# Write conf file so the PostToolUse hook can find resolve_source.py
cat > "$HOOKS_DIR/docs-orchestrator.conf" <<EOF
PLUGIN_ROOT="$PLUGIN_ROOT"
EOF

# Create settings file if missing
if [ ! -f "$SETTINGS_FILE" ]; then
  echo '{}' > "$SETTINGS_FILE"
fi

# --- Stop hook ---
HAS_WORKFLOW_HOOK=$(jq '[(.hooks.Stop // []) | .[] | .hooks // [] | .[] | select(.command? | contains("workflow-completion-check"))] | length' "$SETTINGS_FILE" 2>/dev/null || echo 0)

if [ "$HAS_WORKFLOW_HOOK" -gt 0 ]; then
  echo "Workflow completion Stop hook already installed."
else
  jq '.hooks.Stop = (.hooks.Stop // []) + [{
    "matcher": "",
    "hooks": [{
      "type": "command",
      "command": "bash ${CLAUDE_PROJECT_DIR}/.claude/hooks/workflow-completion-check.sh",
      "timeout": 10
    }]
  }]' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
  echo "Installed workflow completion Stop hook."
fi

# --- PostToolUse hook ---
HAS_SOURCE_HOOK=$(jq '[(.hooks.PostToolUse // []) | .[] | .hooks // [] | .[] | select(.command? | contains("post-requirements-source-resolve"))] | length' "$SETTINGS_FILE" 2>/dev/null || echo 0)

if [ "$HAS_SOURCE_HOOK" -gt 0 ]; then
  echo "Post-requirements source resolution hook already installed."
else
  jq '.hooks.PostToolUse = (.hooks.PostToolUse // []) + [{
    "matcher": "Write|Edit",
    "hooks": [{
      "type": "command",
      "command": "bash ${CLAUDE_PROJECT_DIR}/.claude/hooks/post-requirements-source-resolve.sh",
      "timeout": 120
    }]
  }]' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
  echo "Installed post-requirements source resolution PostToolUse hook."
fi

echo ""
echo "Setup complete. Hooks installed in $SETTINGS_FILE"
echo "Run /hooks in Claude Code to verify."
