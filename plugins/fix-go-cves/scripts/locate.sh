#!/usr/bin/env bash
# Find a Go package in go.mod files, check for replace directives and dependencies.
# Usage: locate.sh STATE_FILE PACKAGE
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

STATE_FILE="${1:?Usage: locate.sh STATE_FILE PACKAGE}"
PACKAGE="${2:?Usage: locate.sh STATE_FILE PACKAGE}"
load_state "$STATE_FILE"

echo "=== Locating: $PACKAGE ==="

# Resolve the effective dependency graph in every module; also collect replace
# directives in one pass. A package need not be textually present in go.mod.
FOUND_IN=()
RESOLUTION_ERRORS=()
REPLACE_HITS=""
while IFS= read -r GOMOD; do
  MODDIR=$(dirname "$GOMOD")
  RESOLVE_RC=0
  resolve_module_dependency "$MODDIR" "$PACKAGE" || RESOLVE_RC=$?
  if [[ "$RESOLVE_RC" -eq 0 || "$RESOLVE_RC" -eq 3 ]]; then
    FOUND_IN+=("$GOMOD")
  elif [[ "$RESOLVE_RC" -eq 2 ]]; then
    RESOLUTION_ERRORS+=("$GOMOD: ${RESOLVE_ERROR:-unknown graph error}")
  fi
  # Keep locate useful in offline/fixture environments and for malformed
  # module graphs. Mutation and verification remain fail-closed in fix-package.
  if [[ "$RESOLVE_RC" -ne 0 && "$RESOLVE_RC" -ne 3 ]] && \
     gomod_has_module_reference "$GOMOD" "$PACKAGE"; then
    FOUND_IN+=("$GOMOD")
  fi
  if MOD_JSON=$(GOTOOLCHAIN=local go -C "$(dirname "$GOMOD")" mod edit -json 2>/dev/null) &&
     jq -e 'type == "object"' >/dev/null 2>&1 <<< "$MOD_JSON"; then
    HITS=$(jq -r --arg pkg "$PACKAGE" '.Replace[]? | select(.Old.Path == $pkg or .New.Path == $pkg) |
      "replace \(.Old.Path) => \(.New.Path) \(.New.Version // "")"' <<< "$MOD_JSON")
  else
    HITS=$(grep -F "$PACKAGE" "$GOMOD" | grep -E '^[[:space:]]*(replace[[:space:]]+)?[^[:space:]]+([[:space:]]+[^[:space:]]+)?[[:space:]]+=>' || true)
  fi
  [[ -n "$HITS" ]] && REPLACE_HITS+="$GOMOD: $HITS"$'\n'
done < <(find_gomods)

if [[ ${#FOUND_IN[@]} -eq 0 ]]; then
  if [[ ${#RESOLUTION_ERRORS[@]} -gt 0 ]]; then
    printf '%s\n' "${RESOLUTION_ERRORS[@]}" >&2
    die "could not resolve $PACKAGE in the module graph"
  fi
  die "$PACKAGE not found in any go.mod"
fi
echo "Found in: ${FOUND_IN[*]}"

if [[ -n "$REPLACE_HITS" ]]; then
  echo ""
  echo "REPLACE DIRECTIVES:"
  printf '%s' "$REPLACE_HITS"
fi

# Show dependency graph excerpt for each module containing the package
echo ""
echo "Dependency graph (may download module metadata)..."
for GOMOD in "${FOUND_IN[@]}"; do
  MODDIR=$(dirname "$GOMOD")
  [[ "$MODDIR" != "." ]] && echo "($MODDIR)"
  timeout 30 go -C "$MODDIR" mod graph 2>/dev/null | grep -F "$PACKAGE" | head -10 || true
done
