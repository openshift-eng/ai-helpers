#!/bin/bash
# Comprehensive validation script

set -e

REPO_PATH="${1:-.}"

echo "✅ Validating ai-docs/ in: $REPO_PATH"
echo ""

ERRORS=0

# Phase 1: Entry Points (Required)
echo "=== Phase 1: Entry Points (Required) ==="
echo ""

# AGENTS.md in repo root
if [ ! -f "$REPO_PATH/AGENTS.md" ]; then
    echo "  ❌ Missing: AGENTS.md (must be in repo root)"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✅ AGENTS.md"
    LINE_COUNT=$(wc -l < "$REPO_PATH/AGENTS.md")
    echo "     $LINE_COUNT lines"
    if [ "$LINE_COUNT" -lt 80 ] || [ "$LINE_COUNT" -gt 220 ]; then
        echo "     ⚠️  WARNING: Should be 100-200 lines (current: $LINE_COUNT)"
    fi
fi

# ai-docs/ core files
for file in DESIGN_PHILOSOPHY.md KNOWLEDGE_GRAPH.md; do
    if [ ! -f "$REPO_PATH/ai-docs/$file" ]; then
        echo "  ❌ Missing: ai-docs/$file"
        ERRORS=$((ERRORS + 1))
    else
        echo "  ✅ ai-docs/$file"
    fi
done

# Phase 2: Required Workflow Files (Explicit Checkboxes)
echo ""
echo "=== Phase 2: Required Workflow Files ==="
echo ""

# These two files have explicit checkboxes in the workflow - must exist
for file in "workflows/enhancement-process.md" "workflows/implementing-features.md"; do
    if [ ! -f "$REPO_PATH/ai-docs/$file" ]; then
        echo "  ❌ Missing required: ai-docs/$file (explicit checkbox in workflow)"
        ERRORS=$((ERRORS + 1))
    else
        echo "  ✅ ai-docs/$file"
    fi
done

# Phase 3: Design Philosophy Coverage (Non-Prescriptive)
echo ""
echo "=== Phase 3: Design Philosophy Coverage ==="
echo ""

echo "Checking for pattern documentation:"
PATTERN_COUNT=$(find "$REPO_PATH/ai-docs/platform" -name "*.md" -type f 2>/dev/null | wc -l)
if [ "$PATTERN_COUNT" -gt 0 ]; then
    echo "  ✅ Found $PATTERN_COUNT platform pattern files"
else
    echo "  ⚠️  No platform pattern files found (consider documenting key operator patterns)"
fi

echo ""
echo "Checking for domain documentation:"
DOMAIN_COUNT=$(find "$REPO_PATH/ai-docs/domain" -name "*.md" -type f 2>/dev/null | wc -l)
if [ "$DOMAIN_COUNT" -gt 0 ]; then
    echo "  ✅ Found $DOMAIN_COUNT domain concept files"
else
    echo "  ⚠️  No domain concept files found (consider documenting core APIs)"
fi

echo ""
echo "Checking for practices documentation:"
PRACTICE_COUNT=$(find "$REPO_PATH/ai-docs/practices" -name "*.md" -type f 2>/dev/null | wc -l)
if [ "$PRACTICE_COUNT" -gt 0 ]; then
    echo "  ✅ Found $PRACTICE_COUNT practice files"
else
    echo "  ⚠️  No practice files found (ensure cross-cutting concerns are covered)"
fi

# Phase 4: Avoid Duplication
echo ""
echo "=== Phase 4: Duplication Check ==="
echo ""

echo "Checking for pointer-based references:"
if [ -f "$REPO_PATH/ai-docs/references/repo-index.md" ]; then
    if grep -q "github.com/orgs/openshift" "$REPO_PATH/ai-docs/references/repo-index.md" 2>/dev/null; then
        echo "  ✅ repo-index.md uses GitHub org links (good)"
    else
        echo "  ⚠️  repo-index.md should use GitHub org search links, not exhaustive lists"
    fi
fi

if [ -f "$REPO_PATH/ai-docs/references/api-reference.md" ]; then
    if grep -q "oc api-resources" "$REPO_PATH/ai-docs/references/api-reference.md" 2>/dev/null; then
        echo "  ✅ api-reference.md points to oc command (good)"
    else
        echo "  ⚠️  api-reference.md should reference 'oc api-resources', not list all APIs"
    fi
fi

# Phase 5: Structural Quality
echo ""
echo "=== Phase 5: Structural Quality ==="
echo ""

# Check for index files in directories with content
echo "Checking for index files in populated directories:"
for dir in platform practices domain decisions workflows references; do
    if [ -d "$REPO_PATH/ai-docs/$dir" ]; then
        FILE_COUNT=$(find "$REPO_PATH/ai-docs/$dir" -maxdepth 2 -name "*.md" -type f 2>/dev/null | wc -l)
        if [ "$FILE_COUNT" -gt 1 ]; then
            # Directory has content, should have navigation
            INDEX_COUNT=$(find "$REPO_PATH/ai-docs/$dir" -maxdepth 2 -name "index.md" -type f 2>/dev/null | wc -l)
            if [ "$INDEX_COUNT" -gt 0 ]; then
                echo "  ✅ $dir/ has index files for navigation"
            else
                echo "  ⚠️  $dir/ has $FILE_COUNT files but no index.md for navigation"
            fi
        fi
    fi
done

# Check ADR naming format (if ADRs exist)
echo ""
echo "Checking ADR naming format:"
ADR_COUNT=$(find "$REPO_PATH/ai-docs/decisions" -name "adr-*.md" -type f 2>/dev/null | wc -l)
if [ "$ADR_COUNT" -gt 0 ]; then
    INVALID_ADRS=$(find "$REPO_PATH/ai-docs/decisions" -name "adr-*.md" -type f 2>/dev/null | grep -v -E 'adr-[0-9]{4}-' | wc -l)
    if [ "$INVALID_ADRS" -eq 0 ]; then
        echo "  ✅ All ADRs use adr-NNNN- format"
    else
        echo "  ⚠️  Some ADRs don't use adr-NNNN- format"
    fi
fi

# Summary
echo ""
echo "==================================="
if [ "$ERRORS" -eq 0 ]; then
    echo "✅ Validation PASSED - All checks successful"
    exit 0
else
    echo "❌ Validation FAILED - Found $ERRORS errors"
    exit 1
fi
