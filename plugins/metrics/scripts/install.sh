#!/usr/bin/env bash
# One-time setup for the metrics plugin.
# Installs otelcol-contrib and writes OTLP env vars to ~/.claude/settings.json.
# Run once after installing the plugin.

set -euo pipefail

OTELCOL_VERSION="0.155.0"
INSTALL_DIR="/usr/local/bin"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

python3 "${SCRIPT_DIR}/configure_settings.py"
echo "Takes effect on next Claude Code startup (no shell restart needed)."
