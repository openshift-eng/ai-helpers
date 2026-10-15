#!/usr/bin/env bash
# Check grype not-fixed entries against grype's own fix.versions from the current scan.
# Checks if newer versions are available for packages marked as not-fixed.
# Usage: fix-availability.sh STATE_FILE [REPORT_DIR]
set -euo pipefail

STATE_FILE="${1:?Usage: fix-availability.sh STATE_FILE [REPORT_DIR]}"
REPORT_DIR="${2:-}"

# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)/lib.sh"
load_state "$STATE_FILE"

ISSUES=()

# Parse .grype.yaml for entries with fix-state: not-fixed
GRYPE_FILE=".grype.yaml"
if [[ ! -f "$GRYPE_FILE" ]]; then
  echo "NEW_ISSUES=0"
  echo "No .grype.yaml file found"
  exit 0
fi

# Extract exact CVE/package/location entries with fix-state: not-fixed.
# YAML structure:
#   - vulnerability: GHSA-xxxx
#     fix-state: not-fixed
#     package:
#       name: package.name/path
NOT_FIXED_ENTRIES=()
CURRENT_FIX_STATE=""
CURRENT_PKG=""
CURRENT_VULN=""
CURRENT_LOCATION=""
while IFS= read -r line; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*vulnerability: ]]; then
    # Save previous entry if it was not-fixed
    if [[ "$CURRENT_FIX_STATE" =~ ^(not-fixed|unknown)$ ]] && [[ -n "$CURRENT_PKG" ]]; then
      NOT_FIXED_ENTRIES+=("$CURRENT_VULN|$CURRENT_PKG|$CURRENT_LOCATION")
    fi
    CURRENT_VULN=$(echo "$line" | sed 's/.*vulnerability:[[:space:]]*//' | xargs)
    CURRENT_FIX_STATE=""
    CURRENT_PKG=""
    CURRENT_LOCATION=""
  fi
  if [[ "$line" =~ ^[[:space:]]*fix-state: ]]; then
    CURRENT_FIX_STATE=$(grype_fix_states <<< "$line")
  fi
  if [[ "$line" =~ ^[[:space:]]*name: ]]; then
    CURRENT_PKG=$(echo "$line" | sed 's/.*name:[[:space:]]*//; s/[[:space:]]#.*//' | xargs)
  fi
  if [[ "$line" =~ ^[[:space:]]*location: ]]; then
    CURRENT_LOCATION=$(echo "$line" | sed 's/.*location:[[:space:]]*//' | xargs)
  fi
done < "$GRYPE_FILE"
# Save last entry
if [[ "$CURRENT_FIX_STATE" =~ ^(not-fixed|unknown)$ ]] && [[ -n "$CURRENT_PKG" ]]; then
  NOT_FIXED_ENTRIES+=("$CURRENT_VULN|$CURRENT_PKG|$CURRENT_LOCATION")
fi

if [[ ${#NOT_FIXED_ENTRIES[@]} -eq 0 ]]; then
  echo "NEW_ISSUES=0"
  echo "No not-fixed entries in .grype.yaml"
  exit 0
fi

SCAN_FILE=""
if ! SCAN_FILE=$(review_scan_file "$REPORT_DIR"); then
  echo "NEW_ISSUES=0"
  echo "SCAN_FAILED=1"
  echo "SKIP: Current Grype scan evidence unavailable or invalid"
  exit 1
fi

# Check each independently-scoped entry for a fix.
while IFS='|' read -r VULN PKG LOCATION; do
  # Skip packages already classified by fix functions (fix-package.sh exit 2/3):
  # their fix-state: not-fixed entry will be left in place, but we know a newer
  # version either reached a deterministic policy boundary (exit 2) or still has
  # the CVE (exit 3).
  pkg_is_exempt "$PKG" "$REPORT_DIR" "$LOCATION" && continue

  # Use grype's authoritative fix.versions from the current scan's ignoredMatches.
  # Auto-expiry (fix-state:not-fixed rule) already moves truly-fixable CVEs to
  # .matches where the deterministic phase handles them. This subagent catches the
  # rare case where grype knows a fix version for an 'unknown'-state ignore entry.
  # If grype has no fix version → upgrading to latest won't help → skip.
  FIX_TARGET=""
  if [[ -n "$SCAN_FILE" ]]; then
    FIX_TARGET=$(grype_ignored_fix_version "$VULN" "$PKG" "$SCAN_FILE" "$LOCATION")
    FIX_TARGET="${FIX_TARGET#v}"
  fi
  [[ -z "$FIX_TARGET" ]] && continue

  # Find which go.mod(s) have this package below grype's fix version
  while IFS= read -r GOMOD; do
    [[ -n "$LOCATION" ]] && \
      [[ "$(normalize_scan_location "$GOMOD")" != "$(normalize_scan_location "$LOCATION")" ]] && continue
    MODDIR=$(dirname "$GOMOD")
    RESOLVE_RC=0
    resolve_module_dependency "$MODDIR" "$PKG" || RESOLVE_RC=$?
    if [[ "$RESOLVE_RC" -eq 2 ]]; then
      ISSUES+=("RESOLUTION_FAILED: $PKG in $GOMOD: ${RESOLVE_ERROR:-unknown graph error}")
      continue
    fi
    [[ "$RESOLVE_RC" -ne 0 ]] && continue
    CURRENT="$RESOLVED_VERSION"
    if ! version_gte "$CURRENT" "$FIX_TARGET"; then
      _scope_field=""
      [[ -n "$LOCATION" ]] && _scope_field=" location:$(normalize_scan_location "$LOCATION")"
      ISSUES+=("FIX-AVAILABLE: $PKG $CURRENT -> $FIX_TARGET${_scope_field} CVEs:$VULN")
      # An unscoped ignore is repaired atomically across all modules by an
      # unscoped fix-package call; emit only one dispatch line.
      [[ -z "$LOCATION" ]] && break
    fi
  done < <(find_gomods 2>/dev/null)
done < <(printf '%s\n' "${NOT_FIXED_ENTRIES[@]}" | sort -u)

# Output structured results
echo "NEW_ISSUES=${#ISSUES[@]}"
for issue in "${ISSUES[@]}"; do
  echo "$issue"
done
