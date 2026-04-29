#!/bin/bash
# Discovery script - check what exists and learn conventions

set -e

REPO_PATH="${1:-.}"

echo "🔍 Discovering existing structure in: $REPO_PATH"
echo ""

# Check if ai-docs exists
if [ -d "$REPO_PATH/ai-docs" ]; then
    echo "✅ ai-docs/ exists"

    # Check index file naming
    if ls "$REPO_PATH"/ai-docs/*/index.md >/dev/null 2>&1; then
        echo "  ✅ Convention: Uses index.md (not README.md)"
    fi

    # Check ADR naming
    ADR_SAMPLE=$(ls "$REPO_PATH/ai-docs/decisions/"adr-*.md 2>/dev/null | head -1)
    if [ -n "$ADR_SAMPLE" ]; then
        echo "  ✅ Convention: $(basename "$ADR_SAMPLE" | grep -oE '^adr-[0-9]+-')"
    fi

    # Count existing files
    echo ""
    echo "📊 Existing files:"
    for dir in platform/operator-patterns practices/testing practices/security practices/reliability practices/development domain/kubernetes domain/openshift decisions workflows references; do
        if [ -d "$REPO_PATH/ai-docs/$dir" ]; then
            COUNT=$(find "$REPO_PATH/ai-docs/$dir" -name "*.md" -type f | wc -l)
            echo "  - $dir: $COUNT files"
        fi
    done
else
    echo "ℹ️  ai-docs/ does not exist - will create from scratch"
    echo ""
    echo "📋 Will create structure with conventions:"
    echo "  - index.md for navigation files"
    echo "  - adr-NNNN- for ADRs (4 digits)"
    echo "  - Short file names (pyramid.md not testing-pyramid.md)"
    echo "  - Target 150-300 lines per file"
fi

echo ""
echo "✅ Discovery complete"
