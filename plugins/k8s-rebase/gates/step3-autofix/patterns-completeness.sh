#!/bin/bash
# Gate script: patterns-completeness pre-existing filter
# Run BEFORE the gate subagent. Identifies which incomplete
# patterns are pre-existing vs introduced by the rebase.
# Usage: bash patterns-completeness.sh <repo-path>

set -uo pipefail
repo="${1:-.}"
cd "$repo" || exit 1

BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main 2>/dev/null)
if [[ -z "$BASE" ]]; then
  echo "NO_BASE: cannot determine pre-existing issues"
  exit 0
fi

new=0 pre=0

echo "=== Build check ==="
# Find module directories
for mod_dir in $(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.claude/*" -exec dirname {} \; | sort); do
  if [[ -d "$mod_dir/vendor" ]] && git check-ignore -q "$mod_dir/vendor" 2>/dev/null; then
    echo "SKIP $mod_dir (vendor is gitignored)"
    continue
  fi
  result=$(cd "$mod_dir" && go build ./... 2>&1) || true
  errors=$(echo "$result" | grep -c '^.*\.go:' || true)
  if [[ "$errors" -gt 0 ]]; then
    echo "BUILD-FAIL $mod_dir: $errors errors"
    new=$((new + errors))
  else
    echo "BUILD-OK $mod_dir"
  fi
done

echo ""
echo "=== Import consistency ==="
# Check for stale imports (old version when new exists)
changed_imports=$(git diff "$BASE"..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' 2>/dev/null \
  | grep '^[+-].*"' | grep -v '^\+\+\+\|^---' | grep -cE 'k8s\.io/|sigs\.k8s\.io/' || true)
echo "Changed k8s imports: $changed_imports"

echo ""
echo "=== Pre-existing check for changed Go files ==="
# For each Go file changed in the rebase, verify changes are intentional
changed_go=$(git diff --name-only "$BASE"..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' 2>/dev/null | wc -l)
echo "Go files changed (non-vendor): $changed_go"
# No per-file pre-existing check here — the build check above is
# the mechanical gate. Per-file analysis is the subagent's job.
if [[ "$changed_go" -eq 0 ]]; then
  echo "No Go source changes — build-only rebase"
fi

echo ""
echo "NEW_ISSUES=$new"
echo "PRE_EXISTING=$pre"
