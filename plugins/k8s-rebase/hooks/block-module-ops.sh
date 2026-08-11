#!/bin/bash
# PreToolUse hook: block direct go module operations during active
# k8s-rebase sessions. Only fires when .rebase-tmp/.session-active
# exists — harmless in non-rebase sessions.
set -euo pipefail
command -v jq >/dev/null 2>&1 || { printf '{"decision":"block","reason":"jq required"}\n'; exit 0; }

INPUT=$(cat)

REPO_CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[[ -f "$REPO_CWD/.rebase-tmp/.session-active" ]] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -z "$CMD" ]] && exit 0

# Allow script wrappers — but ONLY if the entire command is a script
# invocation (not "bash fix.sh && go mod tidy")
echo "$CMD" | grep -qE '^\s*(bash|sh)\s+[A-Za-z0-9_./@:-]+\.sh(\s+[A-Za-z0-9_./@:=-]+)*\s*$' && exit 0

# Block direct go module operations (unanchored to catch compound
# commands like "cd /tmp && go mod tidy" or "sudo go get foo")
if echo "$CMD" | grep -qE '\bgo\s+(mod\s+(tidy|edit|vendor|download|init)|get|generate|run|work\s+sync)\b'; then
  jq -n --arg reason "$(cat <<'MSG'
BLOCKED: Direct go module operations are forbidden during k8s-rebase.
Module operations (go mod tidy, go get, go mod vendor) are handled
by k8s-rebase.sh and k8s-rebase-autofix.sh. Running them directly
corrupts k8s version pins via MVS resolution.

Allowed: go build, go vet, go test, go mod verify, go doc,
go install <tool>@<version>, go clean -cache.
MSG
)" '{"decision":"block","reason":$reason}'
  exit 0
fi

exit 0
