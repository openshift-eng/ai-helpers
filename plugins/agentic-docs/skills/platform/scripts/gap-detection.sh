#!/bin/bash
# Detect gaps in existing ai-docs/ structure

set -e

REPO_PATH="${1:-.}"
AI_DOCS="$REPO_PATH/ai-docs"

if [ ! -d "$AI_DOCS" ]; then
    echo "❌ ai-docs/ does not exist. Use /platform-docs first."
    exit 1
fi

echo "🔍 Scanning ai-docs/ for gaps..."
echo ""

# Track what's missing
MISSING_COUNT=0

# Function to check a category for missing files
check_category() {
    local category_name="$1"
    local base_path="$2"
    shift 2
    local expected_files=("$@")

    echo "## $category_name"

    local missing=()
    for file in "${expected_files[@]}"; do
        if [ ! -f "$AI_DOCS/$base_path/$file" ]; then
            missing+=("$file")
            MISSING_COUNT=$((MISSING_COUNT + 1))
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        echo "Missing:"
        for file in "${missing[@]}"; do
            echo "  - $base_path/$file"
        done
    else
        echo "✅ Complete"
    fi
    echo ""
}

# Platform Patterns
check_category "Platform Patterns" "platform/operator-patterns" \
    controller-runtime.md \
    status-conditions.md \
    webhooks.md \
    finalizers.md \
    rbac.md \
    must-gather.md

# Domain Concepts - Kubernetes
check_category "Domain Concepts - Kubernetes" "domain/kubernetes" \
    pod.md \
    service.md \
    crds.md

# Domain Concepts - OpenShift
check_category "Domain Concepts - OpenShift" "domain/openshift" \
    clusteroperator.md \
    clusterversion.md

# Practices
check_category "Practices" "practices" \
    testing/pyramid.md \
    testing/index.md \
    security/index.md \
    reliability/index.md \
    development/index.md

# Workflows
check_category "Workflows" "workflows" \
    enhancement-process.md \
    implementing-features.md \
    exec-plans/README.md \
    exec-plans/template.md \
    index.md

# Decisions (ADRs)
check_category "Decisions" "decisions" \
    adr-template.md \
    index.md

# References
check_category "References" "references" \
    repo-index.md \
    glossary.md \
    api-reference.md \
    index.md

# Core Files (in ai-docs/ root)
echo "## Core Files"
CORE_MISSING=()
for core in DESIGN_PHILOSOPHY.md KNOWLEDGE_GRAPH.md; do
    if [ ! -f "$AI_DOCS/$core" ]; then
        CORE_MISSING+=("$core")
        MISSING_COUNT=$((MISSING_COUNT + 1))
    fi
done

if [ ${#CORE_MISSING[@]} -gt 0 ]; then
    echo "Missing:"
    for core in "${CORE_MISSING[@]}"; do
        echo "  - $core"
    done
else
    echo "✅ Complete"
fi
echo ""

# AGENTS.md (in repo root)
echo "## Navigation"
if [ ! -f "$REPO_PATH/AGENTS.md" ]; then
    echo "Missing:"
    echo "  - AGENTS.md (at repo root)"
    MISSING_COUNT=$((MISSING_COUNT + 1))
else
    AGENTS_LINES=$(wc -l < "$REPO_PATH/AGENTS.md")
    if [ "$AGENTS_LINES" -gt 200 ]; then
        echo "⚠️  AGENTS.md exists but is too long: $AGENTS_LINES lines (target: ≤200)"
    else
        echo "✅ AGENTS.md exists ($AGENTS_LINES lines)"
    fi
fi
echo ""

# Summary
echo "========================================"
if [ $MISSING_COUNT -eq 0 ]; then
    echo "✅ No gaps detected. Documentation is complete!"
else
    echo "📊 Summary: $MISSING_COUNT missing files detected"
    echo ""
    echo "Run /update-platform-docs to add missing content."
fi

exit 0
