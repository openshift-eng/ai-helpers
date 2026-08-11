#!/bin/bash
# PreToolUse hook: block git push and gh pr create during active
# k8s-rebase sessions. Only fires when .rebase-tmp/.session-active
# exists — harmless in non-rebase sessions.
set -euo pipefail
command -v jq >/dev/null 2>&1 || { printf '{"decision":"block","reason":"jq required"}\n'; exit 0; }

INPUT=$(cat)

REPO_CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[[ -f "$REPO_CWD/.rebase-tmp/.session-active" ]] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -z "$CMD" ]] && exit 0

# Match git push even with flags between git and push (e.g., git -c key=val push)
if echo "$CMD" | grep -qE '(git\b.*\bpush\b|git\s+send-pack|gh\s+pr\s+create|gh\s+api\b.*\bpulls)'; then
  jq -n --arg reason "$(cat <<'MSG'
BLOCKED: The k8s-rebase skill does not push or create PRs.
To push manually: git push origin <branch>
To create PR: gh pr create --title "..." --body "..."
MSG
)" '{"decision":"block","reason":$reason}'
  exit 0
fi

exit 0
