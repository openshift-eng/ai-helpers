#!/usr/bin/env bash
# Validate .grype.yaml entries added in this run.
# Checks format, required fields, no blank lines/trailing whitespace.
# Usage: yaml-integrity.sh STATE_FILE
set -euo pipefail

STATE_FILE="${1:?Usage: yaml-integrity.sh STATE_FILE}"

# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)/lib.sh"
load_state "$STATE_FILE"

ISSUES=()

# Get diff of .grype.yaml against the branch base
DIFF=$(git diff "origin/$BRANCH" -- .grype.yaml 2>/dev/null || echo "")

# Extract added lines with context (line numbers in new file)
# Process added blocks: look for entries starting with "- vulnerability:"
# A deletion-only diff has no added lines, so grep '^+' (after dropping the +++
# header) matches nothing and exits 1 — || true keeps set -e from aborting before
# this companion emits its NEW_ISSUES= marker.
ADDED_LINES=$(echo "$DIFF" | grep '^+' | grep -v '^+++' | sed 's/^+//' || true)

# Check for blank lines with trailing whitespace
# grep -c prints zero even though a zero-match search exits 1.
TRAILING_WS=$(grep -c '^[[:space:]]\+$' <<< "$ADDED_LINES" || true)
if [[ "$TRAILING_WS" -gt 0 ]]; then
  ISSUES+=("TRAILING_WHITESPACE: $TRAILING_WS blank line(s) with trailing whitespace in added content")
fi

# Check each vulnerability entry in added lines
VULN_IDS=$(echo "$ADDED_LINES" | grep 'vulnerability:' | sed 's/.*vulnerability:[[:space:]]*//' || true)

while IFS= read -r vuln_id; do
  [[ -z "$vuln_id" ]] && continue

  # Check vulnerability ID format
  if ! [[ "$vuln_id" =~ ^(CVE-|GHSA-|GO-) ]]; then
    ISSUES+=("BAD_VULN_FORMAT: '$vuln_id' does not match CVE-/GHSA-/GO- pattern")
  fi
done <<< "$VULN_IDS"

# Check fix-state values
FIX_STATES=$(printf '%s\n' "$ADDED_LINES" | grype_fix_states)

while IFS= read -r fix_state; do
  [[ -z "$fix_state" ]] && continue
  if [[ "$fix_state" != "not-fixed" && "$fix_state" != "unknown" && "$fix_state" != "wont-fix" ]]; then
    ISSUES+=("BAD_FIX_STATE: fix-state '$fix_state' is not 'not-fixed', 'unknown', or 'wont-fix'")
  fi
done <<< "$FIX_STATES"

# Check that each vulnerability entry has a preceding comment
# Parse the full new-file content of .grype.yaml to check context
# The working-tree file is authoritative. Reading HEAD first hides an unsafe
# uncommitted/staged edit and can let verification report a false PASS.
FULL_GRYPE=""
if [[ -e .grype.yaml || -L .grype.yaml ]]; then
  FULL_GRYPE=$(cat .grype.yaml)
fi

# Audit the complete current ignore list, not only additions. A pre-existing
# vulnerability-only entry suppresses that CVE for every package and must never
# be grandfathered in merely because this branch did not add it.
if [[ -n "$FULL_GRYPE" ]]; then
  while IFS= read -r structural_issue; do
    [[ -n "$structural_issue" ]] && ISSUES+=("$structural_issue")
  done < <(awk '
    function trim(s) { sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s }
    function flush() {
      if (!entry) return
      if (vuln == "") print "MISSING_VULNERABILITY_FIELD: ignore entry for \047" (pkg==""?"unknown":pkg) "\047 has no vulnerability: field"
      if (pkg == "") print "MISSING_PACKAGE_FIELD: ignore entry for \047" (vuln==""?"unknown":vuln) "\047 has no package name — broad ignores are forbidden"
      entry=0; vuln=pkg=""
    }
    /^ignore:[[:space:]]*(#.*)?$/ { in_ignore=1; next }
    /^[^[:space:]#]/ && !/^-([[:space:]]|$)/ { if (in_ignore) flush(); in_ignore=0 }
    in_ignore && /^[[:space:]]*-([[:space:]]|$)/ {
      flush(); entry=1
    }
    in_ignore && entry && /vulnerability:/ { x=$0; sub(/.*vulnerability:[[:space:]]*/, "", x); vuln=trim(x) }
    in_ignore && entry {
      t = $0; sub(/(^|[[:space:]])#.*/, "", t)
      if (t ~ /^[[:space:]]*name:/ || t ~ /package:[[:space:]]*\{[^}]*name:/) {
        x = t; sub(/.*(^|[{,[:space:]])name:[[:space:]]*/, "", x); sub(/[,}].*/, "", x); pkg = trim(x)
      }
    }
    END { if (in_ignore) flush() }
  ' <<< "$FULL_GRYPE")

  # A repository-wide ignore must not shadow a module-scoped ignore for the
  # same CVE/package. Grype may still report the desired clean scan, but the
  # policy is misleading and unsafe to ship.
  while IFS= read -r scope_issue; do
    [[ -n "$scope_issue" ]] && ISSUES+=("$scope_issue")
  done < <(grype_ignore_scope_conflicts .grype.yaml)
fi
PREV_LINE=""
while IFS= read -r line; do
  if echo "$line" | grep -q '^[[:space:]]*- vulnerability:'; then
    # Check if the previous line is a comment
    if ! echo "$PREV_LINE" | grep -q '^[[:space:]]*#'; then
      VULN="${line##*vulnerability:}"
      VULN="${VULN#"${VULN%%[![:space:]]*}"}"
      # Only flag if this is a newly added entry
      if echo "$ADDED_LINES" | grep -qF "vulnerability: $VULN"; then
        ISSUES+=("MISSING_COMMENT: no comment line before entry for $VULN")
      fi
    fi
  fi
  PREV_LINE="$line"
done <<< "$FULL_GRYPE"

# Output structured results
echo "NEW_ISSUES=${#ISSUES[@]}"
for issue in "${ISSUES[@]}"; do
  echo "$issue"
done
