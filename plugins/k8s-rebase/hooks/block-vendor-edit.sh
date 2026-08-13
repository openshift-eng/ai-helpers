#!/bin/bash
# PreToolUse hook: block direct edits to vendor/ during active
# k8s-rebase sessions. Only fires when .rebase-tmp/.session-active
# exists — harmless in non-rebase sessions.
set -euo pipefail
command -v jq >/dev/null 2>&1 || { printf '{"decision":"block","reason":"jq required"}\n'; exit 0; }

INPUT=$(cat)

REPO_CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[[ -f "$REPO_CWD/.rebase-tmp/.session-active" ]] || exit 0

FILEPATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILEPATH" ]] && exit 0

if echo "$FILEPATH" | grep -qF '/vendor/'; then
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

exit 0
