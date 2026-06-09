#!/bin/bash
set -euo pipefail

title="${1:?usage: notify.sh TITLE MESSAGE}"
message="${2:?usage: notify.sh TITLE MESSAGE}"

if command -v osascript >/dev/null 2>&1; then
  escaped_title="${title//\\/\\\\}"
  escaped_title="${escaped_title//\"/\\\"}"
  escaped_message="${message//\\/\\\\}"
  escaped_message="${escaped_message//\"/\\\"}"
  osascript -e "display notification \"$escaped_message\" with title \"$escaped_title\""
elif command -v notify-send >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  notify-send "$title" "$message"
else
  printf '\a'
fi
