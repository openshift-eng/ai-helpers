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
export DIFF
MERGE_BASE=$(git -C "$REPO_ROOT" merge-base "$COMMIT" master 2>/dev/null || git -C "$REPO_ROOT" merge-base "$COMMIT" main 2>/dev/null || echo "$COMMIT~10")

# Verify COMMIT is on the rebase branch (not a master/main commit)
if git -C "$REPO_ROOT" merge-base --is-ancestor "$COMMIT" "$MERGE_BASE" 2>/dev/null; then
  echo "ERROR: commit $COMMIT is on master/main, not the rebase branch" >&2
  echo "ERROR: Current branch: $(git -C "$REPO_ROOT" branch --show-current), HEAD: $(git -C "$REPO_ROOT" rev-parse --short HEAD)" >&2
  exit 1
fi
DIFF=$(git -C "$REPO_ROOT" diff "$MERGE_BASE".."$COMMIT" -- "*.go" "*.yml" "*.yaml" "*.sh" \
  ':!*/vendor/*' ':!*generated*' ':!*clientset*' ':!*informer*' ':!*lister*' \
  ':!*applyconfiguration*' ':!*mocks/*' ':!*deepcopy*' | head -2000)

export ORIGINAL_ERROR

export K8S_CHANGELOG=""
# Try to extract relevant changelog from the commit message
K8S_CHANGELOG=$(git -C "$REPO_ROOT" log "$COMMIT" -1 --format="%B" | tail -n +2 || true)

export PATTERN_HINT=""
if [[ -f "$PATTERNS" ]]; then
  # Try to find a matching pattern based on the error
  for keyword in "undefined" "SA1019" "deprecated" "FAIL" "too many" "too few" "hang"; do
    if echo "$ORIGINAL_ERROR" | grep -qi "$keyword"; then
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

PROMPT=$(envsubst '$DIFF $ORIGINAL_ERROR $K8S_CHANGELOG $PATTERN_HINT' < "$TEMPLATE")

# Invoke review agent
if ! command -v claude &>/dev/null; then
  echo "WARNING: claude CLI not found, skipping antagonistic review"
  echo "APPROVE: claude CLI not available"
  exit 0
fi

echo ":: Reviewing commit $COMMIT..."
VERDICT=$(echo "$PROMPT" | claude -p --output-format text 2>/dev/null | grep -E "^(APPROVE|REJECT):" | head -1)

if [[ -z "$VERDICT" ]]; then
  echo "WARNING: No clear verdict from review agent"
  echo "REJECT: no verdict (defaulting to reject for safety)"
  exit 1
fi

echo "$VERDICT"

if echo "$VERDICT" | grep -q "^APPROVE:"; then
  exit 0
else
  exit 1
fi
