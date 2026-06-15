#!/bin/bash
set -euo pipefail

if [[ -z "${ARTIFACT_DIR:-}" ]] || [[ -z "${CLAUDE_OUTPUT_LOG:-}" ]]; then
  exit 0
fi

if [[ ! -f "$CLAUDE_OUTPUT_LOG" ]]; then
  exit 0
fi

# Drain stdin so the hook doesn't block
cat > /dev/null

script_dir="$(cd "$(dirname "$0")" && pwd)"
output_path="${ARTIFACT_DIR}/claude-session-metrics-autodl.json"

python3 "${script_dir}/extract_metrics.py" "$CLAUDE_OUTPUT_LOG" "$output_path"
