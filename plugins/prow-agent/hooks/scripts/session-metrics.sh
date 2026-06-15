#!/bin/bash
set -euo pipefail

if [[ -z "${ARTIFACT_DIR:-}" ]]; then
  exit 0
fi

log_file="${ARTIFACT_DIR}/claude-output.log"
if [[ ! -f "$log_file" ]]; then
  exit 0
fi

# Drain stdin so the hook doesn't block
cat > /dev/null

script_dir="$(cd "$(dirname "$0")" && pwd)"
output_path="${ARTIFACT_DIR}/claude-session-metrics-autodl.json"

python3 "${script_dir}/extract_metrics.py" "$log_file" "$output_path"
