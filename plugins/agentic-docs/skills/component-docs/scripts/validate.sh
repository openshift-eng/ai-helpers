#!/bin/bash
#
# Component Documentation Validator
#
# Validates component-level documentation structure and links.
#
# Usage:
#   ./validate.sh [REPO_PATH]
#
# Arguments:
#   REPO_PATH        Path to repository (default: current directory)
#
# Environment:
#   VERBOSE=true     Show all successful links (default: false, only shows broken links)
#
# Examples:
#   ./validate.sh                          # Validate current directory with link checking
#   ./validate.sh /path/to/repo            # Validate specific repo
#   VERBOSE=true ./validate.sh             # Show all links, including successful ones
#
set -euo pipefail

REPO_PATH="${1:-.}"
VERBOSE="${VERBOSE:-false}"
CHECK_EXTERNAL_LINKS="${CHECK_EXTERNAL_LINKS:-true}"
VALIDATION_FAILED=false

if [[ ! -d "$REPO_PATH" ]]; then
    echo "❌ Repository path does not exist: $REPO_PATH" >&2
    exit 1
fi
REPO_PATH=$(cd "$REPO_PATH" && pwd -P)

if [[ -L "$REPO_PATH/ai-docs" ]]; then
    echo "❌ Refusing to validate a symlinked ai-docs directory" >&2
    exit 1
fi

echo "✅ Validating component documentation in: $REPO_PATH"
echo ""

validate_internal_links() {
    local file_path=$1
    local file_dir=$(dirname "$file_path")
    local links_found=false
    local broken_links=false
    local total_links=0
    local valid_links=0
    local invalid_links=0

    while IFS= read -r link; do
        links_found=true
        ((++total_links))

        if [[ "$link" =~ ^# ]]; then
            ((++valid_links))
            continue
        fi

        local resolved_path
        if [[ "$link" =~ ^/ ]]; then
            resolved_path="$REPO_PATH$link"
        else
            resolved_path="$file_dir/$link"
        fi

        resolved_path="${resolved_path%%#*}"

        if [ -f "$resolved_path" ] || [ -d "$resolved_path" ]; then
            ((++valid_links))
            if [ "${VERBOSE:-false}" = "true" ]; then
                echo "  ✅ OK: $link"
            fi
        else
            ((++invalid_links))
            echo "  ❌ NOT FOUND: $link (resolved to: $resolved_path)"
            broken_links=true
        fi
    done < <(grep -oP '\[([^\]]+)\]\(\K([^)]+)(?=\))' "$file_path" 2>/dev/null | grep -v '^https\?://' || true)

    if [ "$links_found" = false ]; then
        echo "  ℹ️  No internal links found"
    else
        echo "  📊 Internal links: $total_links total, $valid_links valid, $invalid_links invalid"
    fi

    if [ "$broken_links" = true ]; then
        return 1
    fi
    return 0
}

remove_broken_link() {
    local file_path=$1
    local broken_url=$2

    # Keep the untrusted URL out of the command/program text; pass it as data.
    python3 - "$file_path" "$broken_url" <<'PY'
from pathlib import Path
import sys

file_path, broken_url = sys.argv[1:]
path = Path(file_path)
lines = path.read_text().splitlines(keepends=True)
path.write_text("".join(line for line in lines if broken_url not in line))
PY
    echo "  🔧 REMOVED line containing broken link: $broken_url"
}

cleanup_empty_sections() {
    local file_path=$1
    local cleaned=false

    python3 -c "
import re
with open('$file_path', 'r') as f:
    content = f.read()
content = re.sub(r'\|[^\n]+\|\n\|[-:| ]+\|\n+(?=##|\Z)', '', content)
with open('$file_path', 'w') as f:
    f.write(content)
" && cleaned=true

    perl -i -0pe 's/\n{3,}/\n\n/g' "$file_path"
    sed -i '/^##[^#]/ { N; s/^##[^#][^\n]*\n\n##/##/; }' "$file_path"

    if [ "$cleaned" = true ]; then
        echo "  🧹 Cleaned up empty sections"
    fi
}

validate_links() {
    local file_path=$1
    local links_found=false
    local broken_links=false
    local total_links=0
    local valid_links=0
    local invalid_links=0
    local links_to_remove=()

    if [[ "$CHECK_EXTERNAL_LINKS" != "true" ]]; then
        echo "  ⚠️  External link checks disabled; links are unverified"
        return 0
    fi

    if ! command -v curl >/dev/null 2>&1; then
        echo "  ⚠️  curl is unavailable; external links are unverified"
        return 0
    fi

    while IFS= read -r link; do
        links_found=true
        ((++total_links))

        local http_code
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -L \
            -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
            "$link" 2>/dev/null || echo "000")

        sleep 0.1

        if [[ "$http_code" == "200" ]]; then
            ((++valid_links))
            if [ "${VERBOSE:-false}" = "true" ]; then
                echo "  ✅ OK ($http_code): $link"
            fi
        elif [[ "$http_code" =~ ^0+$ ]]; then
            ((++invalid_links))
            echo "  ❌ TIMEOUT/ERROR: $link"
            links_to_remove+=("$link")
            broken_links=true
        elif [[ "$http_code" == "404" ]]; then
            ((++invalid_links))
            echo "  ❌ NOT FOUND ($http_code): $link"
            links_to_remove+=("$link")
            broken_links=true
        elif [[ "$http_code" == "403" || "$http_code" == "429" ]]; then
            ((++valid_links))
            echo "  ⚠️  MANUAL CHECK ($http_code): $link"
        else
            ((++invalid_links))
            echo "  ❌ BROKEN ($http_code): $link"
            links_to_remove+=("$link")
            broken_links=true
        fi
    done < <(grep -oP '\[([^\]]+)\]\(\K(https?://[^)]+)' "$file_path" 2>/dev/null || true)

    if [ "$links_found" = false ]; then
        echo "  ℹ️  No HTTP/HTTPS links found"
    else
        echo "  📊 Links: $total_links total, $valid_links valid, $invalid_links invalid"
    fi

    if [ ${#links_to_remove[@]} -gt 0 ]; then
        echo "  🔧 Removing ${#links_to_remove[@]} broken link(s) from file..."
        for broken_link in "${links_to_remove[@]}"; do
            remove_broken_link "$file_path" "$broken_link"
        done
        cleanup_empty_sections "$file_path"
    fi

    if [ "$broken_links" = true ]; then
        return 1
    fi
    return 0
}

# === AGENTS.md ===

if [ ! -f "$REPO_PATH/AGENTS.md" ]; then
    echo "❌ AGENTS.md not found at repository root"
    exit 1
fi

LINE_COUNT=$(wc -l < "$REPO_PATH/AGENTS.md")
echo "  ✅ AGENTS.md exists"
if [ "$LINE_COUNT" -lt 40 ] || [ "$LINE_COUNT" -gt 60 ]; then
    echo "  ⚠️  AGENTS.md is $LINE_COUNT lines (target: 40-60)"
else
    echo "     $LINE_COUNT lines (target: 40-60) ✅"
fi

if grep -q "Platform\|openshift/enhancements" "$REPO_PATH/AGENTS.md"; then
    echo "  ✅ Platform documentation reference found"
else
    echo "  ⚠️  No Platform documentation reference found"
fi

echo ""

# === CLAUDE.md symlink ===

if [ -L "$REPO_PATH/CLAUDE.md" ]; then
    target=$(readlink "$REPO_PATH/CLAUDE.md")
    if [ "$target" = "AGENTS.md" ]; then
        echo "  ✅ CLAUDE.md → AGENTS.md symlink correct"
    else
        echo "  ❌ CLAUDE.md symlink points to $target (expected AGENTS.md)"
        VALIDATION_FAILED=true
    fi
else
    echo "  ❌ CLAUDE.md symlink missing (run: ln -sf AGENTS.md CLAUDE.md)"
    VALIDATION_FAILED=true
fi

echo ""

# === ai-docs/ directory ===

if [ ! -d "$REPO_PATH/ai-docs" ]; then
    echo "❌ ai-docs/ directory missing"
    exit 1
fi
echo "  ✅ ai-docs/ exists"

EXPECT_SOURCE_BACKUP=false
if [ -d "$REPO_PATH/ai-docs/_sources" ]; then
    EXPECT_SOURCE_BACKUP=true
fi

# Required files
for f in ARCHITECTURE.md DEVELOPMENT.md TESTING.md; do
    if [ -f "$REPO_PATH/ai-docs/$f" ]; then
        echo "  ✅ ai-docs/$f exists"
    else
        echo "  ❌ ai-docs/$f missing"
        VALIDATION_FAILED=true
    fi
done

# Optional file
if [ -f "$REPO_PATH/ai-docs/ENHANCEMENTS.md" ]; then
    echo "  ✅ ai-docs/ENHANCEMENTS.md exists (optional)"
fi

echo ""

# === Source preservation ===

if [ "$EXPECT_SOURCE_BACKUP" = true ]; then
    if [ -d "$REPO_PATH/ai-docs/_sources" ]; then
        echo "  ✅ ai-docs/_sources/ exists"
    else
        echo "  ⚠️  ai-docs/_sources/ missing"
    fi

    if [ -f "$REPO_PATH/ai-docs/_sources/CLAUDE.pre-agentic-docs.md" ]; then
        echo "  ✅ Prior CLAUDE.md preserved"
    else
        echo "  ⚠️  Prior CLAUDE.md backup missing"
    fi

    if [ -f "$REPO_PATH/ai-docs/_sources/AGENTS.pre-agentic-docs.md" ]; then
        echo "  ✅ Prior AGENTS.md preserved"
    else
        echo "  ℹ️  Prior AGENTS.md backup not found"
    fi
fi

echo ""

# === ARCHITECTURE.md content checks ===

if [ -f "$REPO_PATH/ai-docs/ARCHITECTURE.md" ]; then
    ARCH_LINES=$(wc -l < "$REPO_PATH/ai-docs/ARCHITECTURE.md")
    if [ "$ARCH_LINES" -lt 200 ] || [ "$ARCH_LINES" -gt 400 ]; then
        echo "  ⚠️  ARCHITECTURE.md is $ARCH_LINES lines (target: 200-400)"
    else
        echo "  ✅ ARCHITECTURE.md: $ARCH_LINES lines (target: 200-400)"
    fi

    if grep -qi "Platform Documentation\|openshift/enhancements" "$REPO_PATH/ai-docs/ARCHITECTURE.md" 2>/dev/null; then
        echo "  ✅ ARCHITECTURE.md contains Platform documentation links"
    else
        echo "  ⚠️  ARCHITECTURE.md missing Platform Documentation section"
    fi
fi

echo ""

# === REVIEW.md ===

if [ -f "$REPO_PATH/REVIEW.md" ]; then
    echo "  ✅ REVIEW.md exists"
    REVIEW_LINES=$(wc -l < "$REPO_PATH/REVIEW.md")
    if [ "$REVIEW_LINES" -gt 100 ]; then
        echo "  ⚠️  REVIEW.md is $REVIEW_LINES lines (soft cap: 100)"
    else
        echo "     $REVIEW_LINES lines (target: 60-80, cap: 100) ✅"
    fi
    if grep -qi "dev-guide\|CONVENTIONS\|enhancements" "$REPO_PATH/REVIEW.md"; then
        echo "  ✅ Platform rule citations found"
    else
        echo "  ⚠️  No platform rule citations found"
    fi
    while IFS= read -r skip_path; do
        clean_path=$(echo "$skip_path" | sed 's/[`*]//g' | xargs)
        if [ -n "$clean_path" ] && [[ "$clean_path" != vendor* ]] && [[ "$clean_path" != go.* ]]; then
            base_dir=$(echo "$clean_path" | cut -d'/' -f1)
            if [ -d "$REPO_PATH/$base_dir" ] || [ -f "$REPO_PATH/$base_dir" ]; then
                if [ "${VERBOSE:-false}" = "true" ]; then
                    echo "  ✅ Skip path base exists: $base_dir"
                fi
            else
                echo "  ⚠️  Skip path base not found: $base_dir (from $skip_path)"
            fi
        fi
    done < <(grep -oP '`[^`]+\*\*[^`]*`' "$REPO_PATH/REVIEW.md" 2>/dev/null || true)
    if [ -f "$REPO_PATH/AGENTS.md" ]; then
        overlap=$(comm -12 \
            <(grep -v '^$\|^#\|^-' "$REPO_PATH/REVIEW.md" 2>/dev/null | sort -u) \
            <(grep -v '^$\|^#\|^-' "$REPO_PATH/AGENTS.md" 2>/dev/null | sort -u) \
            | wc -l)
        if [ "$overlap" -gt 3 ]; then
            echo "  ⚠️  REVIEW.md has $overlap lines overlapping with AGENTS.md"
        else
            echo "  ✅ No significant AGENTS.md overlap"
        fi
    fi
else
    echo "  ❌ REVIEW.md not found (required — run Phase 6 to generate)"
    VALIDATION_FAILED=true
fi

echo ""

# === .coderabbit.yaml ===

if [ -f "$REPO_PATH/.coderabbit.yaml" ]; then
    echo "  ✅ .coderabbit.yaml exists"
    if python3 -c 'import sys, yaml; yaml.safe_load(open(sys.argv[1]))' "$REPO_PATH/.coderabbit.yaml" 2>/dev/null; then
        echo "  ✅ Valid YAML syntax"
    else
        echo "  ❌ Invalid YAML syntax"
        VALIDATION_FAILED=true
    fi
    if grep -q "REVIEW.md" "$REPO_PATH/.coderabbit.yaml"; then
        echo "  ✅ filePatterns includes REVIEW.md"
    else
        echo "  ⚠️  filePatterns missing REVIEW.md"
    fi
    if grep -q "CLAUDE.md" "$REPO_PATH/.coderabbit.yaml" 2>/dev/null; then
        echo "  ⚠️  filePatterns includes CLAUDE.md (auto-detected, remove)"
    fi
else
    echo "  ❌ .coderabbit.yaml not found (required — run Phase 6 to generate)"
    VALIDATION_FAILED=true
fi

echo ""

# === Generic duplication check ===

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
        echo "  ⚠️  Found generic pattern: '$pattern' (should link to Platform)"
        FOUND_DUPLICATION=true
    fi
done

if [ "$FOUND_DUPLICATION" = false ]; then
    echo "  ✅ No generic duplication detected"
fi

echo ""

# === Link validation ===

echo "Validating links..."
echo ""

LINK_VALIDATION_FAILED=false

if [ -f "$REPO_PATH/AGENTS.md" ]; then
    echo "📄 Checking AGENTS.md:"
    echo "  🔗 External links:"
    if ! validate_links "$REPO_PATH/AGENTS.md"; then
        LINK_VALIDATION_FAILED=true
    fi
    echo "  🔗 Internal links:"
    if ! validate_internal_links "$REPO_PATH/AGENTS.md"; then
        LINK_VALIDATION_FAILED=true
    fi
    echo ""
fi

if [ -f "$REPO_PATH/REVIEW.md" ]; then
    echo "📄 Checking REVIEW.md:"
    echo "  🔗 External links:"
    if ! validate_links "$REPO_PATH/REVIEW.md"; then
        LINK_VALIDATION_FAILED=true
    fi
    echo "  🔗 Internal links:"
    if ! validate_internal_links "$REPO_PATH/REVIEW.md"; then
        LINK_VALIDATION_FAILED=true
    fi
    echo ""
fi

if [ -d "$REPO_PATH/ai-docs" ]; then
    while IFS= read -r -d '' file; do
        echo "📄 Checking $(basename "$file"):"
        echo "  🔗 External links:"
        if ! validate_links "$file"; then
            LINK_VALIDATION_FAILED=true
        fi
        echo "  🔗 Internal links:"
        if ! validate_internal_links "$file"; then
            LINK_VALIDATION_FAILED=true
        fi
        echo ""
    done < <(find "$REPO_PATH/ai-docs" -path "$REPO_PATH/ai-docs/_sources" -prune -o -name "*.md" -type f -print0)
fi

if [ "$LINK_VALIDATION_FAILED" = true ]; then
    echo "❌ Some links are broken or inaccessible"
    VALIDATION_FAILED=true
else
    echo "✅ All links validated successfully"
fi

echo ""
echo "==================================="
if [[ "$VALIDATION_FAILED" = true ]]; then
    echo "❌ Validation failed"
    exit 1
fi

echo "✅ Validation complete"
