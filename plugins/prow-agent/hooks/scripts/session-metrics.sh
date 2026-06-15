#!/bin/bash
set -euo pipefail

if [[ -z "${ARTIFACT_DIR:-}" ]]; then
  exit 0
fi

input=$(cat)
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')

if [[ -z "$transcript_path" ]] || [[ ! -f "$transcript_path" ]]; then
  exit 0
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"
output_path="${ARTIFACT_DIR}/claude-session-metrics-autodl.json"

python3 "${script_dir}/extract_metrics.py" "$transcript_path" "$output_path"
