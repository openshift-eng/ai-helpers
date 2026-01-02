#!/bin/bash
# List available workspace directories (includes preflight check)
# Usage: list.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run preflight check and capture output
if ! PREFLIGHT_OUTPUT=$("${SCRIPT_DIR}/../create/preflight.sh" "$@" 2>&1); then
    echo "$PREFLIGHT_OUTPUT"
    exit 1
fi
echo "$PREFLIGHT_OUTPUT"

# Source preflight to get environment variables
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/../create/preflight.sh" > /dev/null 2>&1

echo "=== WORKSPACES ==="
for dir in "${CLAUDE_WORKSPACES_ROOT}"/*/; do
    [ -d "$dir" ] || continue
    name=$(basename "$dir")

    # Skip hidden directories and template
    [[ "$name" == .* ]] && continue
    [[ "$name" == ".template" ]] && continue

    echo "$name"
done
