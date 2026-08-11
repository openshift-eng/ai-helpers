#!/bin/bash
# Gate companion: crd-validation — pre-existing CRD validation filter.
# Identifies which CRD schema issues are pre-existing vs introduced by the rebase.
# Usage: bash crd-validation.sh <repo-path>

source "$(dirname "$0")/../../scripts/gate-script-lib.sh"
init_gate "$@"

details=()
new=0

crds=$(git ls-files -- '*.yaml' ':(exclude,glob)**/vendor/**' ':!.claude/' 2>/dev/null \
  | xargs grep -l 'kind: CustomResourceDefinition' 2>/dev/null || true)
if [[ -z "$crds" ]]; then
  finish_evidence "SKIP: no CRDs in repository" "SKIP: no CRD files found"
fi

if [[ -z "$BASE" ]]; then
  finish_evidence "no base branch — CRD comparison impossible" \
    "NO_BASE: cannot compare CRDs against base branch" \
    "NEW_ISSUES=0"
fi

for crd in $crds; do
  base_crd=$(git show "$BASE:$crd" 2>/dev/null) || true
  if [[ -z "$base_crd" ]]; then
    details+=("$crd ALL-NEW (file not on base branch)")
    inc new
    continue
  fi

  crd_diff=$(diff <(echo "$base_crd") "$crd" 2>/dev/null) || true
  if [[ -z "$crd_diff" ]]; then
    details+=("$crd IDENTICAL (no changes vs base)")
    continue
  fi

  changed=$(grep '^<' <<< "$crd_diff" \
    | grep -cE 'pattern:|format:|minimum:|maximum:|minLength:|maxLength:|minItems:|maxItems:|uniqueItems:|enum:|required:|additionalProperties:|x-kubernetes-' || true)
  if [[ "$changed" -eq 0 ]]; then
    details+=("$crd NO-VALIDATION-CHANGES")
  else
    details+=("$crd CHANGED-VALIDATION: $changed validation-related lines differ from base")
    new=$(( new + changed ))
  fi
done

details+=("NEW_ISSUES=$new")
finish_evidence "$new CRD validation changes" "${details[@]}"
