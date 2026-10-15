#!/usr/bin/env bash
# Audit pre-existing .grype.yaml entries for staleness.
# Checks whether permanent ignores are stale and whether fix-state entries now
# have grype-advertised fixes available.
# Usage: existing-entries.sh STATE_FILE [REPORT_DIR]
set -euo pipefail

STATE_FILE="${1:?Usage: existing-entries.sh STATE_FILE [REPORT_DIR]}"
REPORT_DIR="${2:-}"

# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)/lib.sh"
load_state "$STATE_FILE"

ISSUES=()

# Get pre-existing .grype.yaml content from the branch base
ORIGINAL=$(git show "origin/$BRANCH:.grype.yaml" 2>/dev/null || echo "")
if [[ -z "$ORIGINAL" ]]; then
  echo "NEW_ISSUES=0"
  echo "No pre-existing .grype.yaml on origin/$BRANCH"
  exit 0
fi

# Parse entries from pre-existing content
# Track: vulnerability ID, package name, fix-state, location. Entries for other
# ecosystems (rpm, apk, ...) govern image scans this source scan never sees, so
# only Go entries are audited.
ENTRIES=()
CURRENT_VULN=""
CURRENT_PKG=""
CURRENT_FIX_STATE=""
CURRENT_LOCATION=""
CURRENT_TYPE=""
_save_entry() {
  [[ -n "$CURRENT_VULN" && -n "$CURRENT_PKG" ]] || return 0
  [[ -z "$CURRENT_TYPE" || "$CURRENT_TYPE" == go-module ]] || return 0
  [[ "$CURRENT_PKG" == stdlib || ( "$CURRENT_PKG" == */* && "${CURRENT_PKG%%/*}" == *.* ) ]] || return 0
  ENTRIES+=("$CURRENT_VULN|$CURRENT_PKG|$CURRENT_FIX_STATE|$CURRENT_LOCATION")
}

while IFS= read -r line; do
  # Skip comment lines
  if [[ "$line" =~ ^[[:space:]]*# ]]; then
    continue
  fi

  if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*vulnerability: ]]; then
    _save_entry
    CURRENT_VULN=$(echo "$line" | sed 's/.*vulnerability:[[:space:]]*//' | xargs)
    CURRENT_PKG=""
    CURRENT_FIX_STATE=""
    CURRENT_LOCATION=""
    CURRENT_TYPE=""
  fi

  if [[ "$line" =~ ^[[:space:]]*type: ]]; then
    CURRENT_TYPE=$(echo "$line" | sed 's/.*type:[[:space:]]*//' | xargs)
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
done <<< "$ORIGINAL"

_save_entry

SCAN_FILE=""
if (( ${#ENTRIES[@]} > 0 )); then
  if ! SCAN_FILE=$(review_scan_file "$REPORT_DIR"); then
    echo "NEW_ISSUES=0"
    echo "SCAN_FAILED=1"
    echo "SKIP: Current Grype scan evidence unavailable or invalid"
    exit 1
  fi
fi

# Check each entry
for entry in "${ENTRIES[@]}"; do
  IFS='|' read -r VULN PKG FIX_STATE LOCATION <<< "$entry"

  # Skip packages already classified by fix functions (fix-package.sh exit 2/3):
  # fix-availability already skips them, but existing-entries reads the branch-base
  # .grype.yaml independently and would re-report the same package as stale.
  pkg_is_exempt "$PKG" "$REPORT_DIR" "$LOCATION" && continue

  # Use grype's authoritative fix.versions from the selected scan's ignoredMatches.
  # If grype has no fix version for this CVE, there is no actionable fix — skip.
  # This prevents false positives where a newer package version exists but grype
  # still reports the CVE as not-fixed (e.g. containerd: 1.7.34 still vulnerable).
  GRYPE_FIX_VER=""
  IN_SCAN="unknown"
  if [[ -n "$SCAN_FILE" ]]; then
    GRYPE_FIX_VER=$(grype_ignored_fix_version "$VULN" "$PKG" "$SCAN_FILE" "$LOCATION")
    # Check whether grype still reports this CVE for this package at all.
    # If it appears in neither matches nor ignoredMatches, grype has dropped it
    # (e.g. a false-positive was corrected in the DB) and the ignore is stale.
    IN_SCAN=$(jq -r --arg vid "$VULN" --arg pkg "$PKG" --arg location "$(normalize_scan_location "$LOCATION")" \
      'def normloc: sub("^/src/"; "/") | if startswith("/") then . else "/" + . end;
       if (([.matches // [], .ignoredMatches // []] | add // []) |
         map(select(.vulnerability.id == $vid and .artifact.name == $pkg) |
           select($location == "" or any(.artifact.locations[]?; (.path | normloc) == $location))) |
         length) > 0 then "yes" else "no" end' \
      "$SCAN_FILE" 2>/dev/null || echo "unknown")
  fi
  # CVE no longer reported by grype → the ignore entry is stale, flag for removal.
  # But only if the entry still exists in the current .grype.yaml — a prior commit on
  # this branch may have already removed it, in which case there is nothing to do and
  # re-reporting it would cause the verification loop to cycle forever.
  # Only auto-expiring (fix-state) entries are this tool's to prune; a
  # permanent ignore is maintainer policy, and another Grype version or
  # database may still report it.
  if [[ "$IN_SCAN" == "no" && -z "$FIX_STATE" ]]; then
    continue
  fi
  if [[ "$IN_SCAN" == "no" ]]; then
    if grype_ignore_entry_exists .grype.yaml "$VULN" "$PKG" "$LOCATION"; then
      _scope_field=""
      [[ -n "$LOCATION" ]] && _scope_field=" location:$(normalize_scan_location "$LOCATION")"
      ISSUES+=("STALE: $VULN ($PKG)${_scope_field} no longer reported by grype — ignore entry can be removed")
    fi
    continue
  fi
  # No fix version from grype → nothing actionable, skip
  if [[ -z "$GRYPE_FIX_VER" ]]; then
    # A pre-existing broad auto-expiring ignore can hide a finding in
    # ignoredMatches before the normal no-fix dispatch sees it. If Grype
    # reports exactly one go.mod location for the finding, narrow the policy
    # instead of leaving a repository-wide mask in place. The scanner tuple is
    # authoritative: dependency-graph presence in another module must not
    # invent another affected scan location. Permanent ignores and
    # ambiguous/multi-location findings remain human policy.
    if [[ -z "$LOCATION" && "$FIX_STATE" =~ ^(not-fixed|unknown)$ &&
          -n "$SCAN_FILE" ]]; then
      SCOPE_LOCATION_STATE=$(jq -r --arg vid "$VULN" --arg pkg "$PKG" '
        def normloc: sub("^/src/"; "/") | if startswith("/") then . else "/" + . end;
        [((.matches // []) + (.ignoredMatches // []))[] |
          select(.vulnerability.id == $vid and .artifact.name == $pkg)] as $findings |
        [$findings[] | .artifact.locations[]?.path | normloc] | unique as $locations |
        [$findings[] | (.vulnerability.fix.state // "unknown") |
          if . == "" then "unknown" else . end] | unique as $states |
        if ($locations | length) == 1 and
           ($locations[0] | endswith("/go.mod")) and ($states | length) == 1 and
           ($states[0] | IN("not-fixed", "unknown", "wont-fix"))
        then "\($locations[0])|\($states[0])" else "" end
      ' "$SCAN_FILE" 2>/dev/null || true)
      if [[ "$SCOPE_LOCATION_STATE" == *'|'* ]]; then
        SCOPE_LOCATION="${SCOPE_LOCATION_STATE%%|*}"
        SCOPE_STATE="${SCOPE_LOCATION_STATE#*|}"
        # The main no-fix phase may already have migrated this entry before
        # the existing-entry companion runs. Treat the exact scoped rule as
        # handled; do not report the same migration a second time.
        if ! grype_ignore_entry_exists .grype.yaml "$VULN" "$PKG" "$SCOPE_LOCATION"; then
          ISSUES+=("SCOPE-AVAILABLE: $VULN ($PKG) -> $SCOPE_LOCATION fix-state: $SCOPE_STATE")
        fi
      fi
    fi
    continue
  fi

  # Find a vulnerable installed occurrence, scoped to the entry's location when
  # set. An unscoped ignore applies repository-wide, so checking only the first
  # module is unsafe: a safe version in one module must not hide an older version
  # in another (for example coredns/go.mod masking root/tools go.mod).
  CURRENT_VER=""
  NORMALIZED_LOCATION=$(normalize_scan_location "$LOCATION")
  while IFS= read -r GOMOD; do
    [[ -n "$NORMALIZED_LOCATION" ]] && \
      [[ "$(normalize_scan_location "$GOMOD")" != "$NORMALIZED_LOCATION" ]] && continue
    MODDIR=$(dirname "$GOMOD")
    _candidate=$(get_installed_version "$MODDIR" "$PKG" 2>/dev/null || echo "")
    [[ -z "$_candidate" ]] && continue
    if ! version_gte "$_candidate" "${GRYPE_FIX_VER#v}"; then
      CURRENT_VER="$_candidate"
      break
    fi
  done < <(find_gomods)
  GRYPE_FIX_VER="${GRYPE_FIX_VER#v}"

  # No vulnerable module occurrence remains.
  [[ -z "$CURRENT_VER" ]] && continue

  if [[ -z "$FIX_STATE" ]]; then
    # Permanent ignore where grype now knows a fix version: the entry's rationale
    # is wrong (a real fix exists). Emit FIX-AVAILABLE so the deterministic fix
    # handler can bump the package and remove the stale ignore entry.
    _scope_field=""
    [[ -n "$LOCATION" ]] && _scope_field=" location:$(normalize_scan_location "$LOCATION")"
    ISSUES+=("FIX-AVAILABLE: $PKG $CURRENT_VER -> $GRYPE_FIX_VER${_scope_field} CVEs:$VULN")
  else
    _scope_field=""
    [[ -n "$LOCATION" ]] && _scope_field=" location:$(normalize_scan_location "$LOCATION")"
    ISSUES+=("FIX-NOW-AVAILABLE: $VULN ($PKG)${_scope_field} marked not-fixed but grype has fix $GRYPE_FIX_VER")
  fi
done

# Output structured results
echo "NEW_ISSUES=${#ISSUES[@]}"
for issue in "${ISSUES[@]}"; do
  echo "$issue"
done
