#!/bin/bash
# Create directory structure for ai-docs/

set -e

REPO_PATH="${1:-.}"

echo "📁 Creating ai-docs/ directory structure in: $REPO_PATH"
echo ""

# Create main directory
mkdir -p "$REPO_PATH/ai-docs"

# Create subdirectories
mkdir -p "$REPO_PATH/ai-docs/platform/operator-patterns"
mkdir -p "$REPO_PATH/ai-docs/platform/openshift-specifics"
mkdir -p "$REPO_PATH/ai-docs/practices/testing"
mkdir -p "$REPO_PATH/ai-docs/practices/security"
mkdir -p "$REPO_PATH/ai-docs/practices/reliability"
mkdir -p "$REPO_PATH/ai-docs/practices/development"
mkdir -p "$REPO_PATH/ai-docs/domain/kubernetes"
mkdir -p "$REPO_PATH/ai-docs/domain/openshift"
mkdir -p "$REPO_PATH/ai-docs/decisions"
mkdir -p "$REPO_PATH/ai-docs/workflows"
mkdir -p "$REPO_PATH/ai-docs/workflows/exec-plans"
mkdir -p "$REPO_PATH/ai-docs/references"

echo "✅ Directory structure created:"
tree -d "$REPO_PATH/ai-docs" 2>/dev/null || find "$REPO_PATH/ai-docs" -type d | sed 's|^|  |'

echo ""
echo "Next: Run populate-templates.sh to copy base files"
