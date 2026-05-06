#!/bin/bash
set -euo pipefail

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

if [[ -n "$file_path" ]]; then
  gofmt -w -s "$file_path"
fi
