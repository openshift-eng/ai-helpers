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

if ! POLICY=$(grype_policy_entries "$GRYPE_FILE"); then
  echo "NEW_ISSUES=0"
  echo "SKIP: Grype ignore policy could not be decoded"
  exit 1
fi
mapfile -t NOT_FIXED_ENTRIES < <(jq -r '
  .[] | select(.type == "go-module" or (.type == "" and
    (.package == "stdlib" or (.package | test("^[^/]*[.][^/]*/"))))) |
  select(.fix_state | IN("not-fixed", "unknown")) |
  [.vulnerability,.package,.location] | join("|")' <<< "$POLICY")

if [[ ${#NOT_FIXED_ENTRIES[@]} -eq 0 ]]; then
  echo "NEW_ISSUES=0"
  echo "No not-fixed entries in .grype.yaml"
  exit 0
fi

SCAN_FILE=""
if ! SCAN_FILE=$(review_scan_file "$REPORT_DIR") || [[ -z "$SCAN_FILE" ]]; then
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
