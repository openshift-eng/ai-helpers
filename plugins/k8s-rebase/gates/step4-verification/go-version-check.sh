#!/bin/bash
# Gate companion: go-version-check — verify Go version consistency.
# Usage: bash go-version-check.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

details=()

go_versions=()
while IFS= read -r gomod; do
  ver=$(awk '/^go /{print $2; exit}' "$gomod")
  [[ -n "$ver" ]] && go_versions+=("$gomod:$ver")
done < <(find . -name "go.mod" -not -path "*/vendor/*" | sort)

if [[ ${#go_versions[@]} -gt 1 ]]; then
  unique=$(printf '%s\n' "${go_versions[@]}" | cut -d: -f2 | sort -u | wc -l)
  if [[ "$unique" -gt 1 ]]; then
    # Dependency edits do not introduce an existing directive inconsistency.
    _is_new=1
    if [[ -n "$BASE" ]]; then
      _is_new=0
      for _entry in "${go_versions[@]}"; do
        _mod="${_entry%%:*}"; _mod="${_mod#./}"
        _base_go=$(git show "$BASE:$_mod" 2>/dev/null | awk '/^go /{print $2; exit}' || true)
        if [[ "${_entry#*:}" != "$_base_go" ]]; then
          _is_new=1; break
        fi
      done
    fi
    if [[ "$_is_new" -eq 1 ]]; then
      details+=("NEW MISMATCH: inconsistent go directives: $(printf '%s ' "${go_versions[@]}")")
      inc NEW_ISSUES
    else
      details+=("INFO PRE-EXISTING: inconsistent go directives unchanged: $(printf '%s ' "${go_versions[@]}")")
    fi
  fi
fi

expected_go=""
expected_gomod=go.mod
if [[ -f go.mod ]]; then
  expected_go=$(awk '/^go /{print $2; exit}' go.mod)
fi
if [[ -z "$expected_go" ]] && [[ ${#go_versions[@]} -gt 0 ]]; then
  expected_gomod="${go_versions[0]%%:*}"
  expected_go="${go_versions[0]#*:}"
fi

base_go=""
if [[ -n "$BASE" ]]; then
  base_go=$(git show "$BASE:${expected_gomod#./}" 2>/dev/null | awk '/^go /{print $2; exit}' || true)
fi
_reference_versions() {
  # Extract from the reference itself, not numbers in its path or line number.
  # Every inline workflow matrix entry must be checked, including duplicates.
  if [[ "$1" == workflow ]]; then
    grep -oE 'go-version:[^#]*' | grep -oE '[0-9]+\.[0-9]+' || true
    return 0
  fi
  case "$1" in
    make) grep -oE '\b(GO_VERSION|GOLANG_VERSION)\b[^#0-9]*[0-9]+\.[0-9]+' ;;
    docker) grep -oE 'golang:[0-9]+\.[0-9]+' ;;
  esac | grep -oE '[0-9]+\.[0-9]+' | head -1 || true
}

_reference_module() {
  local directory
  directory=$(dirname "${1#./}")
  while [[ "$directory" != . ]]; do
    if [[ -f "$directory/go.mod" ]]; then
      printf '%s/go.mod\n' "$directory"
      return 0
    fi
    directory=$(dirname "$directory")
  done
  printf '%s\n' "$expected_gomod"
}

_reference_mismatches() {
  local kind="$1" version="$2" expected="$3"
  [[ "$version" != "$expected" ]] || return 1
  # Workflow matrices may deliberately exercise newer Go versions.
  [[ "$kind" != workflow ]] || [[ "$(printf '%s\n%s\n' "$version" "$expected" | sort -V | head -1)" == "$version" ]]
}

declare -A base_ref_counts=() seen_ref_counts=()
_check_refs() {
  local kind="$1" match file line version key count base_line base_version seen
  local ref_gomod ref_go ref_base_go ref_short ref_base_short
  while IFS= read -r match; do
    [[ -z "$match" ]] && continue
    file="${match%%:*}"
    line="${match#*:}"; line="${line#*:}"
    ref_gomod=$(_reference_module "$file")
    ref_go=$(awk '/^go /{print $2; exit}' "$ref_gomod")
    ref_base_go=""
    if [[ -n "$BASE" ]]; then
      ref_base_go=$(git show "$BASE:${ref_gomod#./}" 2>/dev/null | awk '/^go /{print $2; exit}' || true)
    fi
    ref_short=$(cut -d. -f1,2 <<< "$ref_go")
    ref_base_short=$(cut -d. -f1,2 <<< "$ref_base_go")
    while IFS= read -r version; do
      [[ -n "$version" ]] || continue
      if ! _reference_mismatches "$kind" "$version" "$ref_short"; then
        echo "  CORRECT: $match (compatible with $ref_gomod go $ref_go)"
        continue
      fi
      # Preserve a baseline mismatch even if its file, line, or dependencies
      # changed for another reason. Count occurrences so adding another stale
      # reference cannot borrow the pre-existing status of the first one.
      key="$file|$kind|$version"
      seen="${seen_ref_counts[$key]:-0}"
      seen_ref_counts[$key]=$((seen + 1))
      if [[ -n "$ref_base_short" ]] && _reference_mismatches "$kind" "$version" "$ref_base_short"; then
        if [[ -z "${base_ref_counts[$key]+set}" ]]; then
          count=0
          while IFS= read -r base_line; do
            while IFS= read -r base_version; do
              [[ "$base_version" != "$version" ]] || count=$((count + 1))
            done < <(_reference_versions "$kind" <<< "$base_line")
          done < <(git show "$BASE:${file#./}" 2>/dev/null | grep -E '\b(GO_VERSION|GOLANG_VERSION)\b|golang:|go-version:' || true)
          base_ref_counts[$key]="$count"
        fi
        if (( seen < base_ref_counts[$key] )); then
          details+=("INFO PRE-EXISTING: $match (already mismatched $ref_gomod go $ref_base_go on base)")
          continue
        fi
      fi
      echo "  NEW MISMATCH: $match"
      details+=("NEW MISMATCH: $match (Go $version; $ref_gomod requires $ref_go)")
      inc NEW_ISSUES
    done < <(_reference_versions "$kind" <<< "$line")
  done
}

if [[ -n "$expected_go" ]]; then
  _check_refs make < <(grep -rn '\bGO_VERSION\b\|\bGOLANG_VERSION\b' --include='Makefile*' . 2>/dev/null | grep -v vendor | grep -v 'GINKGO_VERSION\|HUGO_VERSION\|CARGO_VERSION\|CARGO_GO\|PROTO_GO\|MOCKGEN_GO\|OPERATOR_GO' || true)
  _check_refs docker < <(grep -rn 'golang:' --include='Dockerfile*' . 2>/dev/null | grep -v vendor || true)
  if [[ -d .github/workflows ]]; then
    _check_refs workflow < <(grep -rn 'go-version:' .github/workflows/ 2>/dev/null || true)
  fi
fi

# Always record what was scanned so evidence is independently verifiable.
[[ -n "$expected_go" ]] && details+=("go.mod go directive: $expected_go")
[[ -n "$base_go" ]] && details+=("base go directive: $base_go")
df_count=$(find . -name 'Dockerfile*' -not -path '*/vendor/*' 2>/dev/null | wc -l | tr -d ' ')
details+=("Dockerfiles scanned: $df_count")

finish_evidence "$NEW_ISSUES Go version issues" "${details[@]}"
