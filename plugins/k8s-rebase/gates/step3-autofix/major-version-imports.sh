#!/bin/bash
# Gate companion: major-version-imports — check for stale v1 imports.
# Usage: bash major-version-imports.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

# PRIMARY_GOMOD discovery: sub-module repos (e.g. ovn-org/ovn-kubernetes) keep
# go.mod and vendor/ under a subdirectory (go-controller/), not the repo root.
# Find the go.mod that depends on k8s.io/client-go; scope versioned-mod checks there.
PRIMARY_GOMOD_DIR="$REPO"
if ! grep -q 'k8s.io/client-go' "$REPO/go.mod" 2>/dev/null; then
  found_mod=""
  while IFS= read -r gomod; do
    if grep -q 'k8s.io/client-go' "$gomod" 2>/dev/null; then
      found_mod="$gomod"
      break
    fi
  done < <(find . -maxdepth 3 -name 'go.mod' \
    -not -path '*/vendor/*' -not -path '*/.claude/*' 2>/dev/null | LC_ALL=C sort)
  [[ -n "$found_mod" ]] && PRIMARY_GOMOD_DIR=$(dirname "$found_mod")
fi

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

  # Per-file count-delta: track how many base occurrences remain to absorb as PRE-EXISTING.
  # Avoids the binary base_file_has test that marked all current hits PRE-EXISTING if even
  # one existed before the rebase.
  declare -A _bc
  while IFS= read -r match; do
    file="${match%%:*}"
    if [[ -n "$BASE" ]] && [[ -z "${_bc[$file]+set}" ]]; then
      _bc[$file]=$(git show "$BASE:$file" 2>/dev/null | grep -cF "\"$bare\"" || true)
    fi
    local bc=${_bc[$file]:-0}
    if [[ $bc -gt 0 ]]; then
      echo "  PRE-EXISTING: $match"
      _bc[$file]=$(( bc - 1 ))
    else
      echo "  NEW: $match"
      details+=("$match (should be $bare/$versioned)")
      inc NEW_ISSUES
    fi
  done <<< "$hits"
}

check_import "k8s.io/klog" "v2"

versioned_mods=$(grep -E '/v[0-9]+' "$PRIMARY_GOMOD_DIR/go.mod" 2>/dev/null | grep -v '^\s*//' | \
  sed -n 's|.*[[:space:]]\([a-z][a-z0-9._/-]*/v[0-9]\+\)[[:space:]].*|\1|p' | sort -u || true)
for vmod in $versioned_mods; do
  bare="${vmod%/v[0-9]*}"
  [[ "$bare" == "k8s.io/klog" ]] && continue
  hits=$(grep -rn "\"$bare\"" --include='*.go' . 2>/dev/null \
    | grep -v vendor/ | grep -v '.cache/' | grep -v "/$vmod" || true)
  if [[ -n "$hits" ]]; then
    unset _bc; declare -A _bc
    while IFS= read -r match; do
      file="${match%%:*}"
      if [[ -n "$BASE" ]] && [[ -z "${_bc[$file]+set}" ]]; then
        _bc[$file]=$(git show "$BASE:$file" 2>/dev/null | grep -cF "\"$bare\"" || true)
      fi
      bc=${_bc[$file]:-0}
      if [[ $bc -gt 0 ]]; then
        echo "  PRE-EXISTING: $match"
        _bc[$file]=$(( bc - 1 ))
      else
        echo "  NEW: $match"
        details+=("$match (should use $vmod)")
        inc NEW_ISSUES
      fi
    done <<< "$hits"
  fi
done

checked_mods=$(grep -E '/v[0-9]+' "$PRIMARY_GOMOD_DIR/go.mod" 2>/dev/null | grep -v '^\s*//' | wc -l || echo 0)
details+=("CHECKED: $checked_mods versioned module(s) in $PRIMARY_GOMOD_DIR/go.mod")

finish_evidence "$NEW_ISSUES stale major-version imports" "${details[@]}"
