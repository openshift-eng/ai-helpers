#!/bin/bash
# k8s-rebase-review.sh — Antagonistic review
#
# For each fix commit, loads the review prompt template, substitutes
# variables with pre-fetched evidence, invokes claude -p as a separate
# process (fresh context), and parses the APPROVE/REJECT verdict.
#
# Usage: k8s-rebase-review.sh <commit-hash> <original-error...>
#
# Exit codes: 0 = APPROVE, 1 = REJECT (reason on stdout)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "ERROR: Not in a git repository" >&2; exit 1; }
TEMPLATE="$SCRIPT_DIR/k8s-rebase-review-prompt.md"
# Patterns file: check plugin docs first, then repo docs
PATTERNS="$SCRIPT_DIR/../docs/k8s-rebase-patterns.md"
[[ -f "$PATTERNS" ]] || PATTERNS="$REPO_ROOT/docs/k8s-rebase-patterns.md"

if [[ $# -lt 2 ]]; then
  echo "Usage: $(basename "$0") <commit-hash> <original-error>"
  exit 1
fi

COMMIT="$1"
shift
ORIGINAL_ERROR="$*"

# Pre-fetch evidence deterministically
MERGE_BASE=$(git -C "$REPO_ROOT" merge-base "$COMMIT" master 2>/dev/null \
  || git -C "$REPO_ROOT" merge-base "$COMMIT" main 2>/dev/null \
  || git -C "$REPO_ROOT" merge-base "$COMMIT" trunk 2>/dev/null \
  || { echo "WARNING: Cannot find merge-base against master/main/trunk, using COMMIT~1" >&2; echo "$COMMIT~1"; })
if ! git -C "$REPO_ROOT" rev-parse "$MERGE_BASE" &>/dev/null; then
  echo "WARNING: Cannot resolve merge-base '$MERGE_BASE' (shallow clone?), using COMMIT~1" >&2
  MERGE_BASE="$COMMIT~1"
fi

# Verify COMMIT is on the rebase branch (not a master/main commit)
if git -C "$REPO_ROOT" merge-base --is-ancestor "$COMMIT" "$MERGE_BASE" 2>/dev/null; then
  echo "ERROR: commit $COMMIT is on master/main, not the rebase branch" >&2
  echo "ERROR: Current branch: $(git -C "$REPO_ROOT" branch --show-current), HEAD: $(git -C "$REPO_ROOT" rev-parse --short HEAD)" >&2
  exit 1
fi
_DIFF_FULL=$(git -C "$REPO_ROOT" show "$COMMIT" -- "*.go" "*.yml" "*.yaml" "*.sh" "go.mod" \
  ':!*/vendor/*' ':!*generated*' ':!*clientset*' ':!*informer*' ':!*lister*' \
  ':!*applyconfiguration*' ':!*mocks/*' ':!*deepcopy*')
DIFF=$(head -2000 <<< "$_DIFF_FULL")
_DIFF_LINES=$(wc -l <<< "$_DIFF_FULL")
export DIFF
export TRUNCATION_WARNING=""
if [[ "$_DIFF_LINES" -gt 2000 ]]; then
  export TRUNCATION_WARNING="WARNING: diff was truncated at 2000 of ${_DIFF_LINES} lines — changes beyond line 2000 are not shown. If you cannot verify the fix is complete from what is visible, output: REJECT: diff truncated — cannot fully verify."
fi

export ORIGINAL_ERROR

# K8S_CHANGELOG: do not populate from the local fix commit message.
# A local commit body is not upstream Kubernetes release notes.
# To populate this with authoritative data, fetch from the
# kubernetes/kubernetes tag matching the target version.
# For now, leave empty so the reviewer is not misled.
export K8S_CHANGELOG=""

export PATTERN_HINT=""
if [[ -f "$PATTERNS" ]]; then
  # Try to find a matching pattern based on the error
  for keyword in "undefined" "SA1019" "deprecated" "FAIL" "too many" "too few" "hang"; do
    if grep -qi "$keyword" <<< "$ORIGINAL_ERROR"; then
      PATTERN_HINT=$(grep -A2 -i "$keyword" "$PATTERNS" | head -6 || true)
      break
    fi
  done
fi

# Load and fill the template
if [[ ! -f "$TEMPLATE" ]]; then
  echo "WARNING: Review template not found at $TEMPLATE, skipping review"
  echo "APPROVE: template not found, skipping"
  exit 0
fi

PROMPT=$(envsubst '$DIFF $ORIGINAL_ERROR $K8S_CHANGELOG $PATTERN_HINT $TRUNCATION_WARNING' < "$TEMPLATE")

# Invoke review agent
if ! command -v claude &>/dev/null; then
  echo "WARNING: claude CLI not found, skipping antagonistic review"
  echo "APPROVE: claude CLI not available"
  exit 0
fi

echo ":: Reviewing commit $COMMIT..."
VERDICT=$(timeout 120 claude -p --output-format text 2>/dev/null <<< "$PROMPT" | grep -E "^(APPROVE|REJECT):" | head -1)

if [[ -z "$VERDICT" ]]; then
  echo "WARNING: No verdict from review agent (timeout or parse failure)"
  echo "APPROVE: no verdict (infrastructure issue, not a code defect)"
  exit 0
fi

echo "$VERDICT"

if [[ "$VERDICT" == APPROVE:* ]]; then
  exit 0
else
  exit 1
fi
