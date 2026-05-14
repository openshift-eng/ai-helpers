#!/bin/bash
set -euo pipefail

REPO_PATH="${1:-.}"

echo "📁 Creating component documentation structure in: $REPO_PATH"

# Create directory structure
mkdir -p "$REPO_PATH/ai-docs/domain"
mkdir -p "$REPO_PATH/ai-docs/architecture"
mkdir -p "$REPO_PATH/ai-docs/decisions"
mkdir -p "$REPO_PATH/ai-docs/exec-plans/active"
mkdir -p "$REPO_PATH/ai-docs/exec-plans/completed"
mkdir -p "$REPO_PATH/ai-docs/references"

echo "✅ Directory structure created:"
tree -L 3 "$REPO_PATH/ai-docs" 2>/dev/null || find "$REPO_PATH/ai-docs" -type d

echo ""
echo "Next: LLM creates documentation files based on SKILL.md"
