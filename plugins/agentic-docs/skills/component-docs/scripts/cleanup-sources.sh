#!/bin/bash
set -euo pipefail

REPO_PATH="${1:-.}"
SOURCES_DIR="$REPO_PATH/ai-docs/_sources"

if [[ -d "$SOURCES_DIR" ]]; then
    rm -rf "$SOURCES_DIR"
    echo "🧹 Removed temporary ai-docs/_sources/"
fi
