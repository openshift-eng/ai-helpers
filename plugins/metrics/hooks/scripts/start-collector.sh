#!/usr/bin/env bash
# Start otelcol-contrib as a background process for this Claude Code session.
# Called by the SessionStart hook. Idempotent: kills any stale instance first.
# Run scripts/install.sh once before using this plugin.

METRICS_DIR="${HOME}/.local/share/claude-metrics"
PID_FILE="${METRICS_DIR}/otelcol.pid"
LOG_FILE="${METRICS_DIR}/otelcol.log"
CONFIG="${CLAUDE_PLUGIN_ROOT}/config/otelcol.yaml"

if ! command -v otelcol-contrib >/dev/null 2>&1; then
  # Binary not installed — guide user to run install.sh.
  INSTALL_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/install.sh"
  if [[ ! -f "${INSTALL_SCRIPT}" ]]; then
    INSTALL_SCRIPT=$(ls "${HOME}/.claude/plugins/cache/"*/metrics/*/scripts/install.sh 2>/dev/null | head -1)
  fi
  if [[ -n "${INSTALL_SCRIPT}" ]]; then
    echo "metrics plugin: run 'bash ${INSTALL_SCRIPT}' once, then restart Claude Code" >&2
  else
    echo "metrics plugin: run 'bash \$(ls ~/.claude/plugins/cache/*/metrics/*/scripts/install.sh)' once, then restart Claude Code" >&2
  fi
  exit 1
fi

if [[ -z "${CLAUDE_PLUGIN_ROOT}" ]] || [[ ! -f "${CONFIG}" ]]; then
  echo "metrics plugin: config not found at ${CONFIG:-/config/otelcol.yaml}" >&2
  exit 0
fi

mkdir -p "${METRICS_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID=$(cat "${PID_FILE}")
  if [[ "${OLD_PID}" =~ ^[0-9]+$ ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    # Verify the process is actually otelcol-contrib — guards against PID reuse.
    if ps -p "${OLD_PID}" -o args= 2>/dev/null | grep -qF "otelcol-contrib"; then
      kill -TERM "${OLD_PID}" 2>/dev/null || true
      sleep 1
      # Only escalate to SIGKILL if graceful shutdown did not complete.
      if kill -0 "${OLD_PID}" 2>/dev/null; then
        kill -KILL "${OLD_PID}" 2>/dev/null || true
      fi
    fi
  fi
  rm -f "${PID_FILE}"
fi

CLAUDE_METRICS_LOG_DIR="${METRICS_DIR}" \
  otelcol-contrib --config "${CONFIG}" \
  >>"${LOG_FILE}" 2>&1 &
COLLECTOR_PID=$!

# Write PID file only after confirming the process is still alive.
# A 0.5s pause catches immediate failures (bad config, port conflict, etc.).
sleep 0.5
if ! kill -0 "${COLLECTOR_PID}" 2>/dev/null; then
  echo "metrics plugin: collector failed to start — check ${LOG_FILE}" >&2
  exit 0
fi

echo "${COLLECTOR_PID}" >"${PID_FILE}"
