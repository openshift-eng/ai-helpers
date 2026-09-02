#!/bin/bash
set -euo pipefail

REPO_PATH="${1:-.}"

if [[ ! -d "$REPO_PATH" ]]; then
    echo "❌ Repository path does not exist: ${1:-.}" >&2
    exit 1
fi
REPO_PATH=$(cd "$REPO_PATH" && pwd -P)

BACKUP_DIR="$REPO_PATH/ai-docs/_sources"

if [[ -L "$REPO_PATH/ai-docs" ]]; then
    echo "❌ Refusing to use a symlinked ai-docs directory" >&2
    exit 1
fi

echo "📁 Creating component documentation structure in: $REPO_PATH"

mkdir -p "$REPO_PATH/ai-docs"
if [[ -L "$BACKUP_DIR" ]]; then
    echo "❌ Refusing to use a symlinked backup directory: $BACKUP_DIR" >&2
    exit 1
elif [[ -e "$BACKUP_DIR" && ! -d "$BACKUP_DIR" ]]; then
    echo "❌ Backup path is not a directory: $BACKUP_DIR" >&2
    exit 1
fi
mkdir -p -- "$BACKUP_DIR"

backup_doc() {
    local src_path=$1
    local dest_path=$2

    if [[ ! -e "$src_path" && ! -L "$src_path" ]]; then
        return 0
    fi

    local resolved_source
    if ! resolved_source=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$src_path"); then
        echo "❌ Cannot resolve existing documentation source: $src_path" >&2
        return 1
    fi

    case "$resolved_source" in
        "$REPO_PATH"/*) ;;
        *)
            echo "❌ Refusing to back up documentation outside repository: $src_path -> $resolved_source" >&2
            return 1
            ;;
    esac

    if [[ ! -f "$resolved_source" ]]; then
        echo "❌ Documentation source is not a regular file: $src_path" >&2
        return 1
    fi

    if [[ -L "$dest_path" ]]; then
        echo "❌ Refusing to overwrite a symlinked backup destination: $dest_path" >&2
        return 1
    elif [[ -e "$dest_path" && ! -f "$dest_path" ]]; then
        echo "❌ Backup destination is not a regular file: $dest_path" >&2
        return 1
    fi

    cp -- "$resolved_source" "$dest_path"
    echo "  📄 Preserved existing $(basename "$src_path") -> ${dest_path#$REPO_PATH/}"
}

backup_doc "$REPO_PATH/CLAUDE.md" "$BACKUP_DIR/CLAUDE.pre-agentic-docs.md"
backup_doc "$REPO_PATH/AGENTS.md" "$BACKUP_DIR/AGENTS.pre-agentic-docs.md"

echo "✅ Directory structure created:"
echo "  ai-docs/"
echo "    ARCHITECTURE.md, DEVELOPMENT.md, TESTING.md, ENHANCEMENTS.md (optional)"
echo "    _sources/ (prior CLAUDE.md / AGENTS.md backups)"
echo ""
echo "Note: CLAUDE.md → AGENTS.md symlink is created by the LLM after generating AGENTS.md"
echo ""
echo "Next: LLM creates documentation files based on SKILL.md"
