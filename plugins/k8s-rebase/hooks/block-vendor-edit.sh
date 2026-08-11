#!/bin/bash
# PreToolUse hook: block direct edits to vendor/ during active
# k8s-rebase sessions. Only fires when .rebase-tmp/.session-active
# exists — harmless in non-rebase sessions.
set -euo pipefail
command -v jq >/dev/null 2>&1 || { printf '{"decision":"block","reason":"jq required"}\n'; exit 0; }

INPUT=$(cat)

REPO_CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[[ -f "$REPO_CWD/.rebase-tmp/.session-active" ]] || exit 0

# Claude sends one file_path. Codex apply_patch sends the whole patch in
# command; only patch headers name affected files (not added/context lines).
# Include move destinations as well as sources, and inspect every file.
# Codex strips control characters from patch paths; preserve ordinary spaces.
PATHS=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
if [[ -z "$PATHS" ]]; then
  PATHS=$(echo "$INPUT" | jq -r '.tool_input.command // empty' | awk '
    /^\*\*\* (Add|Update|Delete) File: / { sub(/^\*\*\* (Add|Update|Delete) File: /, ""); gsub(/[[:cntrl:]]/, ""); print }
    /^\*\*\* Move to: / { sub(/^\*\*\* Move to: /, ""); gsub(/[[:cntrl:]]/, ""); print }
  ')
fi

while IFS= read -r filepath; do
  [[ -n "$filepath" ]] || continue
  if [[ "$filepath" == vendor/* || "$filepath" == */vendor/* ]]; then
  jq -n --arg reason "$(cat <<'MSG'
BLOCKED: Direct edits to vendor/ files are forbidden during k8s-rebase.
Vendor files are managed by go mod vendor inside the rebase scripts.
Any manual edits will be erased by the next vendor sync.

To fix vendored code: edit the upstream source in the dependency,
bump the dep version, and re-vendor.
MSG
)" '{"decision":"block","reason":$reason}'
  exit 0
  fi
done <<< "$PATHS"

exit 0
