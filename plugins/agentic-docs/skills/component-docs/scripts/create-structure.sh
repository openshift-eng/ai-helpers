#!/bin/bash
set -euo pipefail

REPO_PATH="${1:-.}"

echo "📁 Creating component documentation structure in: $REPO_PATH"

mkdir -p "$REPO_PATH/ai-docs"
mkdir -p "$REPO_PATH/ai-docs/_sources"

backup_doc() {
    local src_path=$1
    local dest_path=$2

    if [ -e "$src_path" ] || [ -L "$src_path" ]; then
        cp -L "$src_path" "$dest_path" 2>/dev/null || cp "$src_path" "$dest_path"
        echo "  📄 Preserved existing $(basename "$src_path") -> ${dest_path#$REPO_PATH/}"
    fi
}

backup_doc "$REPO_PATH/CLAUDE.md" "$REPO_PATH/ai-docs/_sources/CLAUDE.pre-agentic-docs.md"
backup_doc "$REPO_PATH/AGENTS.md" "$REPO_PATH/ai-docs/_sources/AGENTS.pre-agentic-docs.md"

echo "✅ Directory structure created:"
echo "  ai-docs/"
echo "    ARCHITECTURE.md, DEVELOPMENT.md, TESTING.md, ENHANCEMENTS.md (optional)"
echo "    _sources/ (prior CLAUDE.md / AGENTS.md backups)"
echo ""
echo "Note: CLAUDE.md → AGENTS.md symlink is created by the LLM after generating AGENTS.md"
echo ""
echo "Next: LLM creates documentation files based on SKILL.md"
