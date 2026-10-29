#!/usr/bin/env bash
# Validate .grype.yaml entries added in this run.
# Checks format, required fields, no blank lines/trailing whitespace.
# Usage: yaml-integrity.sh STATE_FILE
set -euo pipefail

STATE_FILE="${1:?Usage: yaml-integrity.sh STATE_FILE}"

# shellcheck source=/dev/null
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
source "$SCRIPT_DIR/lib.sh"
load_state "$STATE_FILE"

ISSUES=()

# Get diff of .grype.yaml against the branch base
if ! DIFF=$(git diff "origin/$BRANCH" -- .grype.yaml 2>/dev/null); then
  ISSUES+=("GIT_POLICY_DIFF_ERROR: cannot compare ignore policy with the branch base")
fi

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

# One structural reader handles aliases, merges and field ordering. Semantic
# added-rule checks preserve inherited and non-Go policy rather than grading layout.
if [[ -e .grype.yaml || -L .grype.yaml ]]; then
  STRUCTURAL_ISSUES=""
  STRUCTURAL_ISSUES=$(python3 "$SCRIPT_DIR/check-grype-ignores.py" --audit .grype.yaml "origin/$BRANCH" 2>&1) || {
    [[ -n "$STRUCTURAL_ISSUES" ]] || STRUCTURAL_ISSUES="YAML_PARSE_ERROR: structural check failed without diagnostics"
  }
  while IFS= read -r issue; do
    [[ -n "$issue" ]] && ISSUES+=("$issue")
  done <<< "$STRUCTURAL_ISSUES"
  if POLICY=$(grype_policy_entries .grype.yaml 2>/dev/null); then
    while IFS= read -r issue; do
      [[ -n "$issue" ]] && ISSUES+=("$issue")
    done < <(grype_ignore_scope_conflicts .grype.yaml)
  fi
fi

# Output structured results
echo "NEW_ISSUES=${#ISSUES[@]}"
for issue in "${ISSUES[@]}"; do
  echo "$issue"
done
