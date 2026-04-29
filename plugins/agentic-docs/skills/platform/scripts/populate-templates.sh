#!/bin/bash
# Copy core template files to ai-docs/

set -e

REPO_PATH="${1:-.}"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "📄 Copying core template files to: $REPO_PATH/ai-docs"
echo ""

# Copy the two core files that are generic across all repositories
if [ ! -d "$REPO_PATH/ai-docs" ]; then
    echo "❌ Error: ai-docs/ directory does not exist"
    echo "   Run create-structure.sh first"
    exit 1
fi

cp "$SKILL_DIR/templates/DESIGN_PHILOSOPHY.md" "$REPO_PATH/ai-docs/"
echo "  ✅ Copied DESIGN_PHILOSOPHY.md"

cp "$SKILL_DIR/templates/KNOWLEDGE_GRAPH.md" "$REPO_PATH/ai-docs/"
echo "  ✅ Copied KNOWLEDGE_GRAPH.md"

echo ""
echo "✅ Core template files copied successfully"
echo ""
echo "Next: LLM creates remaining documentation files following template patterns"
