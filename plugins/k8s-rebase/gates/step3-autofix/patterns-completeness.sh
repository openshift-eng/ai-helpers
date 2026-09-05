#!/bin/bash
# Gate companion: patterns-completeness — build check + k8s import change summary.
# Usage: bash patterns-completeness.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

details=()
# NEW_ISSUES initialized to 0 by init_gate

# Build check — runs regardless of BASE availability
for mod_dir in $(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.claude/*" \
    -exec dirname {} \; | sort); do
  if [[ -d "$mod_dir/vendor" ]] && git check-ignore -q "$mod_dir/vendor" 2>/dev/null; then
    details+=("SKIP $mod_dir (vendor is gitignored)")
    continue
  fi
  build_rc=0
  result=$(cd "$mod_dir" && go build ./... 2>&1) || build_rc=$?
  errors=$(grep -c '^.*\.go:' <<< "$result" || true)
  if [[ "$errors" -gt 0 ]]; then
    details+=("BUILD-FAIL $mod_dir: $errors errors")
    NEW_ISSUES=$(( NEW_ISSUES + errors ))
  elif [[ "$build_rc" -ne 0 ]]; then
    # Non-zero exit with no file:line lines = linker error, permission, or toolchain issue
    details+=("BUILD-FAIL $mod_dir: non-file-line error (exit $build_rc)")
    inc NEW_ISSUES
  else
    details+=("BUILD-OK $mod_dir")
  fi
done

# Comparison checks — require BASE
if [[ -n "$BASE" ]]; then
  changed_imports=$(git diff "$BASE"..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' 2>/dev/null \
    | grep '^[+-].*"' | grep -vE '^\+\+\+|^---' \
    | grep -cE 'k8s\.io/|sigs\.k8s\.io/' || true)
  details+=("Changed k8s imports: $changed_imports")

  # Check 2: newly-added k8s imports using a non-versioned path when a v2+ sibling exists in vendor/
  while IFS= read -r import_path; do
    module_path=$(printf '%s' "$import_path" | cut -d/ -f1,2)
    printf '%s' "$import_path" | grep -qE '/v[2-9][0-9]*(/|$)' && continue
    for vN in v2 v3 v4 v5; do
      if [[ -d "vendor/${module_path}/${vN}" ]]; then
        details+=("IMPORT-VERSION-MISMATCH: $import_path uses non-versioned path but vendor/${module_path}/${vN} exists")
        inc NEW_ISSUES
        break
      fi
    done
  done < <(git diff "$BASE"..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' 2>/dev/null \
    | grep '^+' | grep -v '^+++' \
    | grep -oE '(k8s\.io|sigs\.k8s\.io)/[^"]+' | sort -u)

  changed_go=$(git diff --name-only "$BASE"..HEAD \
    -- '*.go' ':(exclude,glob)**/vendor/**' 2>/dev/null | wc -l)
  details+=("Go files changed (non-vendor): $changed_go")
  [[ "$changed_go" -eq 0 ]] && details+=("No Go source changes — build-only rebase")
fi

details+=("NEW_ISSUES=$NEW_ISSUES")
finish_evidence "$NEW_ISSUES build/pattern issues" "${details[@]}"
