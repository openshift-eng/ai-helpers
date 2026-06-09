#!/bin/bash
set -u

title="${1:?usage: notify.sh TITLE MESSAGE}"
message="${2:?usage: notify.sh TITLE MESSAGE}"

if command -v osascript >/dev/null 2>&1; then
  escaped_title="${title//\\/\\\\}"
  escaped_title="${escaped_title//\"/\\\"}"
  escaped_message="${message//\\/\\\\}"
  escaped_message="${escaped_message//\"/\\\"}"
  osascript -e "display notification \"$escaped_message\" with title \"$escaped_title\"" || true
elif command -v notify-send >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  notify-send "$title" "$message" || true
else
  printf '\a'
fi
