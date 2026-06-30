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
VERBOSE="${VERBOSE:-false}"   # Set VERBOSE=true to see all successful links

echo "✅ Validating component documentation in: $REPO_PATH"
echo ""

# Function to validate internal/relative links
validate_internal_links() {
    local file_path=$1
    local file_dir=$(dirname "$file_path")
    local links_found=false
    local broken_links=false
    local total_links=0
    local valid_links=0
    local invalid_links=0

    # Extract markdown links: [text](url)
    # Match relative paths (not starting with http:// or https://)
    while IFS= read -r link; do
        links_found=true
        ((total_links++))

        # Skip anchors (links starting with #)
        if [[ "$link" =~ ^# ]]; then
            ((valid_links++))
            continue
        fi

        # Resolve relative path
        local resolved_path
        if [[ "$link" =~ ^/ ]]; then
            # Absolute path from repo root
            resolved_path="$REPO_PATH$link"
        else
            # Relative path from current file
            resolved_path="$file_dir/$link"
        fi

        # Remove anchor if present (e.g., file.md#section)
        resolved_path="${resolved_path%%#*}"

        # Check if file exists
        if [ -f "$resolved_path" ] || [ -d "$resolved_path" ]; then
            ((valid_links++))
            if [ "${VERBOSE:-false}" = "true" ]; then
                echo "  ✅ OK: $link"
            fi
        else
            ((invalid_links++))
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

# Function to remove broken link from file
remove_broken_link() {
    local file_path=$1
    local broken_url=$2

    # Escape special characters in URL for sed/grep
    local escaped_url=$(printf '%s\n' "$broken_url" | sed 's/[[\.*^$/]/\\&/g')

    # Remove entire line containing the broken link
    sed -i "\|$escaped_url|d" "$file_path"

    echo "  🔧 REMOVED line containing broken link: $broken_url"
}

# Function to clean up empty sections after link removal
cleanup_empty_sections() {
    local file_path=$1
    local cleaned=false

    # Remove empty markdown tables (header + separator with no data rows)
    # Matches: | Header | ... |\n|--------|-----|  followed by blank line or new section
    python3 -c "
import re
with open('$file_path', 'r') as f:
    content = f.read()
# Match table header + separator with optional blank lines but no data rows
# Pattern: table header, separator, then either EOF, blank line + header, or just header
content = re.sub(r'\|[^\n]+\|\n\|[-:| ]+\|\n+(?=##|\Z)', '', content)
with open('$file_path', 'w') as f:
    f.write(content)
" && cleaned=true

    # Remove multiple consecutive blank lines (reduce to max 2)
    perl -i -0pe 's/\n{3,}/\n\n/g' "$file_path"

    # Remove section headers that have no content before next header
    # Pattern: ## Header\n\n## Another Header -> ## Another Header
    sed -i '/^##[^#]/ { N; s/^##[^#][^\n]*\n\n##/##/; }' "$file_path"

    if [ "$cleaned" = true ]; then
        echo "  🧹 Cleaned up empty sections"
    fi
}

# Function to validate HTTP/HTTPS links
validate_links() {
    local file_path=$1
    local links_found=false
    local broken_links=false
    local total_links=0
    local valid_links=0
    local invalid_links=0
    local links_to_remove=()

    # Extract markdown links: [text](url)
    # Match http:// and https:// URLs only
    while IFS= read -r link; do
        links_found=true
        ((total_links++))

        # Mark known sites that block curl but are valid
        local is_curl_blocked=false
        if [[ "$link" =~ "docs.openshift.com" ]]; then
            is_curl_blocked=true
        fi

        # Check if URL is accessible (with timeout and follow redirects)
        # Add user agent to avoid some sites blocking curl
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -L \
            -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
            "$link" 2>/dev/null || echo "000")

        # Small delay to avoid rate limiting
        sleep 0.1

        if [[ "$http_code" == "200" ]]; then
            ((valid_links++))
            if [ "${VERBOSE:-false}" = "true" ]; then
                echo "  ✅ OK ($http_code): $link"
            fi
        elif [[ "$http_code" =~ ^0+$ ]]; then
            ((invalid_links++))
            echo "  ❌ TIMEOUT/ERROR: $link"
            links_to_remove+=("$link")
            broken_links=true
        elif [[ "$http_code" == "404" ]]; then
            ((invalid_links++))
            echo "  ❌ NOT FOUND ($http_code): $link"
            links_to_remove+=("$link")
            broken_links=true
        elif [[ "$http_code" == "403" ]]; then
            if [ "$is_curl_blocked" = true ]; then
                ((valid_links++))
                if [ "${VERBOSE:-false}" = "true" ]; then
                    echo "  ⚠️  OK (site blocks curl, assume valid): $link"
                fi
            else
                ((invalid_links++))
                echo "  ❌ FORBIDDEN ($http_code): $link"
                links_to_remove+=("$link")
                broken_links=true
            fi
        else
            ((invalid_links++))
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

    # Remove broken links from the file
    if [ ${#links_to_remove[@]} -gt 0 ]; then
        echo "  🔧 Removing ${#links_to_remove[@]} broken link(s) from file..."
        for broken_link in "${links_to_remove[@]}"; do
            remove_broken_link "$file_path" "$broken_link"
        done
        # Clean up empty sections after removing links
        cleanup_empty_sections "$file_path"
    fi

    if [ "$broken_links" = true ]; then
        return 1
    fi
    return 0
}

# Check AGENTS.md at root
if [ ! -f "$REPO_PATH/AGENTS.md" ]; then
    echo "❌ AGENTS.md not found at repository root"
    exit 1
fi

LINE_COUNT=$(wc -l < "$REPO_PATH/AGENTS.md")
echo "  ✅ AGENTS.md exists"
if [ "$LINE_COUNT" -lt 80 ] || [ "$LINE_COUNT" -gt 100 ]; then
    echo "  ⚠️  AGENTS.md is $LINE_COUNT lines (target: 80-100)"
else
    echo "     $LINE_COUNT lines (target: 80-100) ✅"
fi

# Check for Platform references
if grep -q "Platform" "$REPO_PATH/AGENTS.md" || grep -q "openshift/enhancements" "$REPO_PATH/AGENTS.md"; then
    echo "  ✅ Platform ecosystem references found"
else
    echo "  ⚠️  No Platform ecosystem references found"
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
    if grep -q "Platform" "$REPO_PATH/ai-docs/references/ecosystem.md"; then
        echo "     Contains Platform links ✅"
    else
        echo "     ⚠️  No Platform links found"
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
        echo "  ⚠️  Found generic pattern: '$pattern' (should link to Platform)"
        FOUND_DUPLICATION=true
    fi
done

if [ "$FOUND_DUPLICATION" = false ]; then
    echo "  ✅ No generic duplication detected"
fi

echo ""

# Validate links
echo "Validating links..."
echo ""

LINK_VALIDATION_FAILED=false

# Check links in AGENTS.md
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

# Check links in all ai-docs markdown files
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
    done < <(find "$REPO_PATH/ai-docs" -name "*.md" -type f -print0)
fi

if [ "$LINK_VALIDATION_FAILED" = true ]; then
    echo "⚠️  Some links are broken or inaccessible"
else
    echo "✅ All links validated successfully"
fi

echo ""
echo "==================================="
echo "✅ Validation complete"
