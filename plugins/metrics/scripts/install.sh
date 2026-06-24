#!/usr/bin/env bash
# One-time setup for the metrics plugin.
# Installs otelcol-contrib and configures OTLP env vars in your shell profile.
# Run once after installing the plugin, then restart your terminal.

set -euo pipefail

OTELCOL_VERSION="0.155.0"
INSTALL_DIR="/usr/local/bin"
MARKER="# Claude Code metrics plugin — OTLP telemetry"

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

# ── OTLP env vars ──────────────────────────────────────────────────────────────

case "${SHELL:-}" in
  */zsh)  PROFILE="${HOME}/.zshrc" ;;
  */bash) PROFILE="${HOME}/.bashrc" ;;
  *)      PROFILE="${HOME}/.profile" ;;
esac

if grep -qF "${MARKER}" "${PROFILE}" 2>/dev/null; then
  echo "OTLP env vars already present in ${PROFILE}"
else
  cat >> "${PROFILE}" <<'EOF'

# Claude Code metrics plugin — OTLP telemetry
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
export OTEL_SERVICE_NAME=claude-code-agent
EOF
  echo "OTLP env vars added to ${PROFILE}"
fi

echo ""
echo "Setup complete. Apply the new env vars without restarting:"
echo "  source ${PROFILE}"
