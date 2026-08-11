#!/bin/bash
# Gate companion: major-version-imports — check for stale v1 imports.
# Usage: bash major-version-imports.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

NEW_ISSUES=0
details=()

check_import() {
  local bare="$1" versioned="$2"
  local hits
  hits=$(grep -rn "\"$bare\"" --include='*.go' . 2>/dev/null \
    | grep -v vendor/ | grep -v '.cache/' | grep -v "/$versioned" || true)

  if [[ -z "$hits" ]]; then
    echo "CLEAN: no bare $bare imports"
    return
  fi

  while IFS= read -r match; do
    [[ -z "$match" ]] && continue
    file=$(echo "$match" | cut -d: -f1)
    if [[ -n "$BASE" ]] && base_file_has "$file" "\"$bare\""; then
      echo "  PRE-EXISTING: $match"
    else
      echo "  NEW: $match"
      details+=("$match (should be $bare/$versioned)")
      ((NEW_ISSUES++)) || true
    fi
  done <<< "$hits"
}

check_import "k8s.io/klog" "v2"

if grep -q 'sigs.k8s.io/controller-runtime/v2' go.mod 2>/dev/null; then
  check_import "sigs.k8s.io/controller-runtime" "v2"
fi

versioned_mods=$(grep -E '/v[0-9]+' go.mod 2>/dev/null | grep -v '^\s*//' | \
  sed -n 's|.*[[:space:]]\([a-z][a-z0-9._/-]*/v[0-9]\+\)[[:space:]].*|\1|p' | sort -u || true)
for vmod in $versioned_mods; do
  bare="${vmod%/v[0-9]*}"
  [[ "$bare" == "k8s.io/klog" ]] && continue
  hits=$(grep -rn "\"$bare\"" --include='*.go' . 2>/dev/null \
    | grep -v vendor/ | grep -v '.cache/' | grep -v "/$vmod" | head -5 || true)
  if [[ -n "$hits" ]]; then
    while IFS= read -r match; do
      file=$(echo "$match" | cut -d: -f1)
      if [[ -n "$BASE" ]] && base_file_has "$file" "\"$bare\""; then
        echo "  PRE-EXISTING: $match"
      else
        echo "  NEW: $match"
        details+=("$match (should use $vmod)")
        ((NEW_ISSUES++)) || true
      fi
    done <<< "$hits"
  fi
done

finish_gate "$NEW_ISSUES" "$NEW_ISSUES stale major-version imports" "${details[@]}"
