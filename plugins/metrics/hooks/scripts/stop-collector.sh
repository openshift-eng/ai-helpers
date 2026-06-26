#!/usr/bin/env bash
# Stop the otelcol-contrib process started by start-collector.sh.
# Called by the SessionEnd hook. Sends SIGTERM for a graceful flush,
# then SIGKILL if the process does not exit within 10 seconds.

METRICS_DIR="${HOME}/.local/share/claude-metrics"
PID_FILE="${METRICS_DIR}/otelcol.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  exit 0
fi

PID=$(cat "${PID_FILE}")
rm -f "${PID_FILE}"

if ! kill -0 "${PID}" 2>/dev/null; then
  exit 0
fi

kill -TERM "${PID}" 2>/dev/null || exit 0

for _ in $(seq 1 10); do
  if ! kill -0 "${PID}" 2>/dev/null; then
    exit 0
  fi
  sleep 1
done

kill -KILL "${PID}" 2>/dev/null || true
