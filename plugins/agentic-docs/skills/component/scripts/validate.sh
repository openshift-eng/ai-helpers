#!/bin/bash
set -euo pipefail

REPO_PATH="${1:-.}"

echo "✅ Validating component documentation in: $REPO_PATH"
echo ""

# Check AGENTS.md at root
if [ ! -f "$REPO_PATH/AGENTS.md" ]; then
    echo "❌ AGENTS.md not found at repository root"
    exit 1
fi

LINE_COUNT=$(wc -l < "$REPO_PATH/AGENTS.md")
echo "  ✅ AGENTS.md exists"
if [ "$LINE_COUNT" -gt 100 ]; then
    echo "  ⚠️  AGENTS.md is $LINE_COUNT lines (target: 80-100)"
else
    echo "     $LINE_COUNT lines (target: 80-100) ✅"
fi

# Check for Tier 1 references
if grep -q "Tier 1" "$REPO_PATH/AGENTS.md" || grep -q "openshift/enhancements" "$REPO_PATH/AGENTS.md"; then
    echo "  ✅ Tier 1 ecosystem references found"
else
    echo "  ⚠️  No Tier 1 ecosystem references found"
fi

# Check for retrieval-first instruction
if grep -q -i "retrieval" "$REPO_PATH/AGENTS.md"; then
    echo "  ✅ Retrieval-first instruction found"
else
    echo "  ⚠️  No retrieval-first instruction"
fi

echo ""

# Check required directories
for dir in domain architecture decisions exec-plans references; do
    if [ -d "$REPO_PATH/ai-docs/$dir" ]; then
        echo "  ✅ ai-docs/$dir/ exists"
    else
        echo "  ❌ ai-docs/$dir/ missing"
    fi
done

echo ""

# Check ecosystem.md
if [ -f "$REPO_PATH/ai-docs/references/ecosystem.md" ]; then
    echo "  ✅ references/ecosystem.md exists"
    if grep -q "Tier 1" "$REPO_PATH/ai-docs/references/ecosystem.md"; then
        echo "     Contains Tier 1 links ✅"
    else
        echo "     ⚠️  No Tier 1 links found"
    fi
else
    echo "  ⚠️  references/ecosystem.md missing"
fi

echo ""

# Check for forbidden patterns (generic content duplication)
echo "Checking for generic duplication..."

FORBIDDEN_PATTERNS=(
    "testing pyramid"
    "controller-runtime reconciliation"
    "Available/Progressing/Degraded conditions"
    "STRIDE threat model"
    "SLO error budget"
)

FOUND_DUPLICATION=false
for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    if grep -riq "$pattern" "$REPO_PATH/ai-docs/" 2>/dev/null; then
        echo "  ⚠️  Found generic pattern: '$pattern' (should link to Tier 1)"
        FOUND_DUPLICATION=true
    fi
done

if [ "$FOUND_DUPLICATION" = false ]; then
    echo "  ✅ No generic duplication detected"
fi

echo ""
echo "==================================="
echo "✅ Validation complete"
