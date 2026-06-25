#!/usr/bin/env bash
# One-time setup for the metrics plugin.
# Installs otelcol-contrib and writes OTLP env vars to ~/.claude/settings.json.
# Run once after installing the plugin.

set -euo pipefail

OTELCOL_VERSION="0.155.0"
INSTALL_DIR="/usr/local/bin"
SETTINGS_FILE="${HOME}/.claude/settings.json"

# ── otelcol-contrib ────────────────────────────────────────────────────────────

if command -v otelcol-contrib >/dev/null 2>&1; then
  echo "otelcol-contrib already installed: $(command -v otelcol-contrib)"
else
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  case "$(uname -m)" in
    x86_64)        ARCH="amd64" ;;
    arm64|aarch64) ARCH="arm64" ;;
    *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
  esac
  case "$OS" in
    darwin|linux) ;;
    *) echo "Unsupported OS: $OS" >&2; exit 1 ;;
  esac

  TARBALL="otelcol-contrib_${OTELCOL_VERSION}_${OS}_${ARCH}.tar.gz"
  URL="https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${OTELCOL_VERSION}/${TARBALL}"
  TMP_DIR=$(mktemp -d)
  trap 'rm -rf "$TMP_DIR"' EXIT

  echo "Downloading otelcol-contrib ${OTELCOL_VERSION} (${OS}/${ARCH})..."
  curl -fsSL "$URL" -o "${TMP_DIR}/${TARBALL}"
  tar -xzf "${TMP_DIR}/${TARBALL}" -C "$TMP_DIR"
  sudo mv "${TMP_DIR}/otelcol-contrib" "${INSTALL_DIR}/otelcol-contrib"
  echo "Installed: ${INSTALL_DIR}/otelcol-contrib"
fi

# ── OTel env vars in ~/.claude/settings.json ──────────────────────────────────

mkdir -p "${HOME}/.claude"

if command -v jq >/dev/null 2>&1; then
  # If the existing file has invalid JSON, treat it as {} rather than aborting
  # and zeroing it (the > redirect truncates before jq can read stdin).
  EXISTING="{}"
  if [[ -f "${SETTINGS_FILE}" ]]; then
    jq empty "${SETTINGS_FILE}" 2>/dev/null && EXISTING=$(< "${SETTINGS_FILE}") || true
  fi
  # Write atomically: produce output to a temp file, then rename over the target.
  TMP=$(mktemp "${HOME}/.claude/.settings.json.XXXXXX")
  printf '%s' "${EXISTING}" \
    | jq '. * {"env": ({
        "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
        "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",
        "OTEL_TRACES_EXPORTER": "otlp",
        "OTEL_METRICS_EXPORTER": "otlp",
        "OTEL_LOGS_EXPORTER": "otlp",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318",
        "OTEL_SERVICE_NAME": "claude-code-agent"
      } + (.env // {}))}' \
    > "$TMP" \
    && mv -f "$TMP" "${SETTINGS_FILE}" \
    || { rm -f "$TMP"; echo "metrics plugin: failed to write ${SETTINGS_FILE}" >&2; exit 1; }
else
  python3 - "${SETTINGS_FILE}" <<'PYEOF'
import json, sys, os, tempfile

path = sys.argv[1]
defaults = {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",
    "OTEL_TRACES_EXPORTER": "otlp",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318",
    "OTEL_SERVICE_NAME": "claude-code-agent",
    "OTEL_LOG_RAW_API_BODIES": "1",
}
try:
    with open(path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}
# Existing env keys take precedence so user overrides are preserved.
settings["env"] = {**defaults, **settings.get("env", {})}
# Write atomically: temp file in same directory, then os.replace (rename).
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)))
try:
    with os.fdopen(fd, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
except Exception:
    os.unlink(tmp)
    raise
PYEOF
fi

echo "OTel env vars written to ${SETTINGS_FILE}"
echo "Takes effect on next Claude Code startup (no shell restart needed)."
