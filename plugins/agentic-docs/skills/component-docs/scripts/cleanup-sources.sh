#!/bin/bash
set -euo pipefail

REPO_PATH="${1:-.}"

if [[ ! -d "$REPO_PATH" ]]; then
    echo "❌ Repository path does not exist: ${1:-.}" >&2
    exit 1
fi
REPO_PATH=$(cd "$REPO_PATH" && pwd -P)

SOURCES_DIR="$REPO_PATH/ai-docs/_sources"

if [[ -L "$REPO_PATH/ai-docs" ]]; then
    echo "❌ Refusing to clean a symlinked ai-docs directory" >&2
    exit 1
fi

if [[ -d "$SOURCES_DIR" ]]; then
    rm -rf -- "$SOURCES_DIR"
    echo "🧹 Removed temporary ai-docs/_sources/"
fi
