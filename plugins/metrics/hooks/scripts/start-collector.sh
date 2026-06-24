#!/usr/bin/env bash
# Start otelcol-contrib as a background process for this Claude Code session.
# Called by the SessionStart hook. Idempotent: kills any stale instance
# before starting a fresh one.
#
# First run: if OTLP env vars are not set, merges them into
# ~/.claude/settings.json so the next Claude Code session emits telemetry.
# No shell profile changes — vars are scoped to Claude Code only.

METRICS_DIR="${HOME}/.local/share/claude-metrics"
PID_FILE="${METRICS_DIR}/otelcol.pid"
LOG_FILE="${METRICS_DIR}/otelcol.log"
CONFIG="${CLAUDE_PLUGIN_ROOT}/config/otelcol.yaml"
CLAUDE_SETTINGS="${HOME}/.claude/settings.local.json"

if ! command -v otelcol >/dev/null 2>&1; then
  echo "metrics plugin: otelcol-contrib not found, skipping collector start" >&2
  exit 0
fi

mkdir -p "${METRICS_DIR}"

# Kill any stale instance from a previous session.
if [[ -f "${PID_FILE}" ]]; then
  OLD_PID=$(cat "${PID_FILE}")
  if kill -0 "${OLD_PID}" 2>/dev/null; then
    kill -TERM "${OLD_PID}" 2>/dev/null || true
    sleep 1
    kill -KILL "${OLD_PID}" 2>/dev/null || true
  fi
  rm -f "${PID_FILE}"
fi

# Merge OTLP env vars into ~/.claude/settings.json when not already active.
# Claude Code applies the settings.json `env` block to its own process, so
# no shell profile edits are needed. Takes effect on next session start.
if [[ -z "${CLAUDE_CODE_ENABLE_TELEMETRY}" ]]; then
  python3 - "${CLAUDE_SETTINGS}" <<'PYEOF'
import json, os, sys

settings_path = sys.argv[1]
otlp_env = {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",
    "OTEL_TRACES_EXPORTER": "otlp",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318",
    "OTEL_SERVICE_NAME": "claude-code-agent",
}

settings = {}
if os.path.exists(settings_path):
    with open(settings_path) as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            pass

env = settings.setdefault("env", {})
if all(env.get(k) == v for k, v in otlp_env.items()):
    sys.exit(0)  # already configured

env.update(otlp_env)
os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"metrics plugin: OTLP env vars added to {settings_path}", file=sys.stderr)
print("metrics plugin: Restart Claude Code to activate telemetry collection", file=sys.stderr)
PYEOF
fi

CLAUDE_METRICS_LOG_DIR="${METRICS_DIR}" \
  otelcol-contrib --config "${CONFIG}" \
  >>"${LOG_FILE}" 2>&1 &

echo $! >"${PID_FILE}"
