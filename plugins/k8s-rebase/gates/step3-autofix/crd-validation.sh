#!/bin/bash
# Gate script: crd-validation pre-existing filter
# Run BEFORE the gate subagent. Identifies which CRD issues
# are pre-existing vs introduced by the rebase.
# Usage: bash crd-validation.sh <repo-path>
#
# Output: for each CRD, lists findings as NEW or PRE-EXISTING.
# The subagent reads this output to set its verdict correctly.

set -uo pipefail
repo="${1:-.}"
cd "$repo" || exit 1

BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main 2>/dev/null)
if [[ -z "$BASE" ]]; then
  echo "NO_BASE: cannot determine pre-existing issues"
  exit 0
fi

crds=$(git ls-files -- '*.yaml' ':(exclude,glob)**/vendor/**' ':!.claude/' 2>/dev/null \
  | xargs grep -l 'kind: CustomResourceDefinition' 2>/dev/null || true)
if [[ -z "$crds" ]]; then
  echo "SKIP: no CRDs found"
  exit 0
fi

new=0 pre=0

for crd in $crds; do
  # Check if CRD exists on base branch
  base_crd=$(git show "$BASE:$crd" 2>/dev/null)
  if [[ -z "$base_crd" ]]; then
    echo "$crd ALL-NEW (file not on base branch)"
    new=$((new + 1))
    continue
  fi

  # Diff the CRD against base — any validation change is a finding
  crd_diff=$(diff <(echo "$base_crd") "$crd" 2>/dev/null)
  if [[ -z "$crd_diff" ]]; then
    echo "$crd IDENTICAL (no changes vs base)"
    continue
  fi

  # Count changed lines that affect validation
  changed=$(echo "$crd_diff" | grep '^[<>]' | grep -cE 'pattern:|format:|minimum:|maximum:|enum:|required:' || true)
  if [[ "$changed" -eq 0 ]]; then
    echo "$crd NO-VALIDATION-CHANGES"
  else
    echo "$crd CHANGED-VALIDATION: $changed validation-related lines differ from base"
    new=$((new + changed))
  fi
done

echo ""
echo "NEW_ISSUES=$new"
echo "PRE_EXISTING=$pre"
echo "NOTE: Issues that exist identically on base branch are pre-existing and should not trigger FAIL"
