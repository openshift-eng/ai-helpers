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

# Keep flags/quoted subcommands covered, but do not mistake pre-push filenames
# for the push subcommand when cleanup is rendered on one line.
pull_write=false
if echo "$CMD" | tr '\n' ' ' | grep -qE 'gh\s+api\b.*\bpulls'; then
  # PR metadata GETs are required to inspect an upstream compatibility fix.
  # Fields/input imply POST unless an explicit read method is supplied.
  if ! python3 - "$CMD" <<'PY'
import re
import shlex
import sys

try:
    lexer = shlex.shlex(sys.argv[1].replace("\\\n", ""), posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    tokens = list(lexer)
    found = False
    for index in range(len(tokens) - 1):
        if tokens[index:index + 2] != ["gh", "api"]:
            continue
        args = []
        for token in tokens[index + 2:]:
            if token and all(c in ";&|()<>\n" for c in token):
                break
            args.append(token)
        if not any(re.search(r"(?:^|/)pulls(?:[/?]|$)", arg) for arg in args):
            continue
        found = True
        explicit_read, body = False, False
        for offset, arg in enumerate(args):
            method = None
            if arg in ("-X", "--method"):
                method = args[offset + 1] if offset + 1 < len(args) else ""
            elif arg.startswith("--method="):
                method = arg.split("=", 1)[1]
            elif arg.startswith("-X"):
                method = arg[2:]
            if method is not None:
                if method.upper() not in ("GET", "HEAD"):
                    sys.exit(1)
                explicit_read = True
            if arg.startswith(("-f", "-F", "--field", "--raw-field", "--input")):
                body = True
        if body and not explicit_read:
            sys.exit(1)
    sys.exit(0 if found else 1)
except ValueError:
    sys.exit(1)
PY
  then
    pull_write=true
  fi
fi
if [[ "$pull_write" == true ]] || echo "$CMD" | grep -qE '(git\b.*[^[:alnum:]_-]push\b|git-push\b|git\s+send-pack|gh\s+pr\s+create)'; then
  jq -n --arg reason "$(cat <<'MSG'
BLOCKED: The k8s-rebase skill does not push or create PRs.
To push manually: git push origin <branch>
To create PR: gh pr create --title "..." --body "..."
MSG
)" '{"decision":"block","reason":$reason}'
  exit 0
fi

exit 0
