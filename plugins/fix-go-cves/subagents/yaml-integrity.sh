#!/usr/bin/env bash
# Validate .grype.yaml entries added in this run.
# Checks structural selectors, added-rule rationale and branch-base policy.
# Usage: yaml-integrity.sh STATE_FILE
set -euo pipefail

STATE_FILE="${1:?Usage: yaml-integrity.sh STATE_FILE}"

# shellcheck source=/dev/null
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
source "$SCRIPT_DIR/lib.sh"
load_state "$STATE_FILE"

ISSUES=()

# One structural reader handles aliases, merges and field ordering. Semantic
# added-rule checks preserve inherited and non-Go policy rather than grading layout.
if [[ -e .grype.yaml || -L .grype.yaml ]]; then
  STRUCTURAL_ISSUES=""
  STRUCTURAL_ISSUES=$(python3 "$SCRIPT_DIR/check-grype-ignores.py" --audit .grype.yaml "${UPSTREAM_REF:-}" 2>&1) || {
    [[ -n "$STRUCTURAL_ISSUES" ]] || STRUCTURAL_ISSUES="YAML_PARSE_ERROR: structural check failed without diagnostics"
  }
  while IFS= read -r issue; do
    [[ -n "$issue" ]] && ISSUES+=("$issue")
  done <<< "$STRUCTURAL_ISSUES"
  while IFS= read -r issue; do
    [[ -n "$issue" ]] && ISSUES+=("$issue")
  done < <(grype_ignore_scope_conflicts .grype.yaml 2>/dev/null)
else
  POLICY_DIFF_EXIT=0
  git diff --quiet "${UPSTREAM_REF:-}" -- .grype.yaml >/dev/null 2>&1 || POLICY_DIFF_EXIT=$?
  case "$POLICY_DIFF_EXIT" in
    0) ;;
    1) ISSUES+=("POLICY_REMOVED: inherited .grype.yaml is missing; review the policy removal") ;;
    *) ISSUES+=("GIT_POLICY_DIFF_ERROR: cannot compare ignore policy with the branch base") ;;
  esac
fi

# Output structured results
echo "NEW_ISSUES=${#ISSUES[@]}"
for issue in "${ISSUES[@]}"; do
  echo "$issue"
done
