#!/bin/bash
# Gather info: run preflight check, verify template, and list available repos

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run preflight check and capture output
if ! PREFLIGHT_OUTPUT=$("${SCRIPT_DIR}/preflight.sh" "$@" 2>&1); then
    echo "$PREFLIGHT_OUTPUT"
    exit 1
fi
echo "$PREFLIGHT_OUTPUT"

# Source preflight to get environment variables
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/preflight.sh" > /dev/null 2>&1

# Define CONFIG_DIR and CUSTOM_PROMPT_FILE
CONFIG_DIR="${HOME}/.claude/plugins/config/workspaces"
CUSTOM_PROMPT_FILE="${CONFIG_DIR}/custom-prompt.md"

# Check template exists (silently)
if [ ! -d "${CLAUDE_WORKSPACES_ROOT}/.template" ]; then
    echo "ERROR: Template directory missing"
    exit 1
fi

echo ""
echo "=== REPOS ==="
# Use portable find syntax (GNU -printf not available on macOS/BSD)
find "${CLAUDE_GIT_REPOS_ROOT}/" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | tr '\n' ' ' | sed 's/ $/\n/'

# Output custom prompt contents only if it has been customized by the user
# Check if the file still contains the DISABLED marker
if [ -f "${CUSTOM_PROMPT_FILE}" ]; then
    if ! grep -q "^# DISABLED" "${CUSTOM_PROMPT_FILE}"; then
        # File has been customized (marker removed)
        echo ""
        echo "=== CUSTOM_PROMPT ==="
        cat "${CUSTOM_PROMPT_FILE}"
    fi
fi
