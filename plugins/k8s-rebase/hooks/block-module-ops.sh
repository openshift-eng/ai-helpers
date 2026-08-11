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

# Report summaries/details are literal data, even when they describe forbidden
# operations. Exempt only arguments to this plugin's verified report helper;
# keep substitutions, compound commands and unknown paths under the old guard.
FILTERED_CMD=$(python3 - "$CMD" "$(dirname "${BASH_SOURCE[0]}")/../scripts/write-gate-report.sh" <<'PY'
import os
import re
import shlex
import sys

original, helper = sys.argv[1:]
try:
    lexer = shlex.shlex(original.replace("\\\n", ""), posix=True,
                        punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    # '#' inside a shell word or parameter expansion does not start a comment.
    # Retain all text so executable suffixes remain under the original guard.
    lexer.commenters = ""
    tokens = list(lexer)
    raw_lexer = shlex.shlex(original.replace("\\\n", ""), posix=False,
                            punctuation_chars=";&|()<>\n")
    raw_lexer.whitespace = " \t\r"
    raw_lexer.whitespace_split = True
    raw_lexer.commenters = ""
    raw_tokens = list(raw_lexer)
    if len(raw_tokens) != len(tokens):
        raise ValueError("unsupported shell quoting")
    filtered = list(tokens)
    bindings = {}
    may_acquire = True
    start = 0
    for end in range(len(tokens) + 1):
        if end < len(tokens) and not (tokens[end] and
                                      all(c in ";&|()<>\n" for c in tokens[end])):
            continue
        segment = tokens[start:end]
        raw_segment = raw_tokens[start:end]
        assignments = [re.fullmatch(r"([A-Za-z_]\w*)=([^$`]+)", t) for t in segment]
        if may_acquire and segment and all(assignments) and all(
                raw.startswith(m[1] + "=") for raw, m in zip(raw_segment, assignments)):
            bindings.update({m[1]: m[2] for m in assignments})
        elif len(segment) >= 7 and segment[0] in ("bash", "sh"):
            may_acquire = False
            path = segment[1]
            variable = re.fullmatch(r"\$(?:\{(\w+)\}|(\w+))(/.*)", path)
            if variable and raw_segment[1] in (path, '"' + path + '"'):
                path = bindings.get(variable[1] or variable[2], "") + variable[3]
            if os.path.isabs(path) and os.path.realpath(path) == os.path.realpath(helper):
                # bash helper repo gate verdict issues summary [details...]
                for index in range(start + 6, end):
                    if "$(" not in tokens[index] and "`" not in tokens[index]:
                        filtered[index] = "REPORT_LITERAL"
            bindings.clear()
        else:
            may_acquire = False
            head_check = (len(segment) == 5 and segment[:3] ==
                          ["[", "$(git rev-parse HEAD)", "="] and segment[4] == "]" and
                          re.fullmatch(r"[A-Za-z0-9_-]+", segment[3]))
            # Unknown commands/rebindings may change variables. Only the
            # captured read-only HEAD comparison may retain a prior binding.
            if not head_check:
                bindings.clear()
        if end < len(tokens) and tokens[end] not in (";", "&&", "||", "\n"):
            # Pipeline/background/subshell processes do not share assignments.
            bindings.clear()
        if end < len(tokens) and tokens[end] not in (";", "\n"):
            # An assignment later in a conditional/pipeline may never execute.
            may_acquire = False
        start = end + 1
    print(" ".join(filtered))
except ValueError:
    # An unsupported/malformed shell expression receives the original guard.
    print(original)
PY
) || FILTERED_CMD="$CMD"

# Block direct go module operations (unanchored to catch compound
# commands like "cd /tmp && go mod tidy" or "sudo go get foo")
if echo "$FILTERED_CMD" | grep -qE '\bgo\s+(mod\s+(tidy|edit|vendor|download|init)|get|generate|run|work\s+sync)\b'; then
  jq -n --arg reason "$(cat <<'MSG'
BLOCKED: Direct go module operations are forbidden during k8s-rebase.
Module operations (go mod tidy, go get, go mod vendor) are handled
by k8s-rebase.sh and k8s-rebase-autofix.sh. Running them directly
corrupts k8s version pins via MVS resolution. For repairs, run
scripts/k8s-rebase-depfix.sh <module>@<version> (or --sync after
adding a replace) in the affected module, then verify k8s pins.

Allowed: go build, go vet, go test, go mod verify, go doc,
go install <tool>@<version>, go clean -cache.
MSG
)" '{"decision":"block","reason":$reason}'
  exit 0
fi

exit 0
