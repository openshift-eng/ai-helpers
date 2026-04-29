#!/bin/bash
# Identify missing recommended files

set -e

REPO_PATH="${1:-.}"
AI_DOCS="$REPO_PATH/ai-docs"

if [ ! -d "$AI_DOCS" ]; then
    echo "❌ ai-docs/ does not exist. Use /platform-docs first."
    exit 1
fi

echo "🔍 Identifying gaps in: $AI_DOCS"
echo ""

GAPS_FOUND=0

# Function to check file existence
check_file() {
    local file="$1"
    local label="${2:-$file}"

    if [ ! -f "$AI_DOCS/$file" ]; then
        echo "  ❌ Missing: $label"
        GAPS_FOUND=1
    else
        echo "  ✅ $label"
    fi
}

# Function to check directory file count
check_file_count() {
    local dir="$1"
    local label="$2"
    local min_count="$3"
    local pattern="${4:-*.md}"

    local count=0
    if [ -d "$AI_DOCS/$dir" ]; then
        count=$(find "$AI_DOCS/$dir" -name "$pattern" -type f 2>/dev/null | grep -v index.md | wc -l)
    fi

    echo "  $label: $count files (need $min_count minimum)"
    if [ "$count" -lt "$min_count" ]; then
        GAPS_FOUND=1
    fi
}

# Check critical files
echo "Checking critical files:"
check_file "DESIGN_PHILOSOPHY.md"
check_file "KNOWLEDGE_GRAPH.md"
echo ""

# Check AGENTS.md at repo root (not in ai-docs/)
if [ ! -f "$REPO_PATH/AGENTS.md" ]; then
    echo "  ❌ Missing: AGENTS.md (at repo root)"
    GAPS_FOUND=1
else
    echo "  ✅ AGENTS.md"
fi
echo ""

# Operator patterns (8 required)
echo "Checking operator patterns (need 8 minimum):"
check_file_count "platform/operator-patterns" "Operator patterns" 8
echo ""

# Practices
echo "Checking practices:"
check_file_count "practices/testing" "Testing" 4
check_file_count "practices/security" "Security" 2
check_file_count "practices/reliability" "Reliability" 2
check_file_count "practices/development" "Development" 2
echo ""

# Domain concepts
echo "Checking domain concepts:"
check_file_count "domain/kubernetes" "Kubernetes" 3
check_file_count "domain/openshift" "OpenShift" 4
echo ""

# ADRs
echo "Checking ADRs:"
check_file_count "decisions" "ADRs" 3 "adr-*.md"
echo ""

# Summary
if [ "$GAPS_FOUND" -eq 0 ]; then
    echo "✅ No gaps found - documentation is complete"
else
    echo "⚠️  Gaps found - create missing files"
fi

exit $GAPS_FOUND
