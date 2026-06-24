#!/usr/bin/env bash
# Start otelcol-contrib as a background process for this Claude Code session.
# Called by the SessionStart hook. Idempotent: kills any stale instance first.
# Run scripts/install.sh once before using this plugin.

METRICS_DIR="${HOME}/.local/share/claude-metrics"
PID_FILE="${METRICS_DIR}/otelcol.pid"
LOG_FILE="${METRICS_DIR}/otelcol.log"
CONFIG="${CLAUDE_PLUGIN_ROOT}/config/otelcol.yaml"

if ! command -v otelcol-contrib >/dev/null 2>&1; then
  echo "metrics plugin: otelcol-contrib not found — run scripts/install.sh first" >&2
  exit 0
fi

mkdir -p "${METRICS_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID=$(cat "${PID_FILE}")
  if kill -0 "${OLD_PID}" 2>/dev/null; then
    kill -TERM "${OLD_PID}" 2>/dev/null || true
    sleep 1
    kill -KILL "${OLD_PID}" 2>/dev/null || true
  fi
  rm -f "${PID_FILE}"
fi

CLAUDE_METRICS_LOG_DIR="${METRICS_DIR}" \
  otelcol-contrib --config "${CONFIG}" \
  >>"${LOG_FILE}" 2>&1 &

echo $! >"${PID_FILE}"
