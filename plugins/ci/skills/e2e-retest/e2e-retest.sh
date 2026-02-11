#!/bin/bash

set -euo pipefail

# ci:e2e-retest - Find and retest failed e2e CI jobs on a PR
# Usage: ./e2e-retest.sh [repo] <pr-number>

# Source shared utilities
source "$(dirname "$0")/common.sh"

# Parse arguments
if [ $# -eq 1 ]; then
  PR_NUMBER="$1"
  # Auto-detect from git remote
  REPO=$(git remote -v | head -1 | sed -E 's/.*github\.com[:/]([^/]+\/[^ .]+).*/\1/' | sed 's/\.git$//' || true)
  if [ -z "$REPO" ]; then
    echo "❌ Error: Could not detect repository from git remote."
    echo "Please specify repo: $0 <repo> <pr-number>"
    exit 1
  fi
  echo "Repository: $REPO"

elif [ $# -eq 2 ]; then
  REPO_ARG="$1"
  PR_NUMBER="$2"

  # Check if contains slash (org/repo format)
  if [[ "$REPO_ARG" == *"/"* ]]; then
    REPO="$REPO_ARG"
  else
    # Assume openshift org
    REPO="openshift/$REPO_ARG"
  fi
  echo "Repository: $REPO"

else
  echo "❌ Error: Invalid arguments"
  echo "Usage: $0 [repo] <pr-number>"
  exit 1
fi

# Extract org and repo name
ORG=$(echo "$REPO" | cut -d'/' -f1)
REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)

# Validate PR number
if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  echo "❌ Error: PR number must be numeric"
  exit 1
fi

echo ""

# Create unique temp directory and setup cleanup
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Fetch data in parallel
{
  gh pr view ${PR_NUMBER} --repo ${REPO} --json statusCheckRollup,baseRefName > "$TMPDIR/e2e_pr_status.json" 2>/dev/null
} &
{
  curl -sL "https://prow.ci.openshift.org/pr-history?org=${ORG}&repo=${REPO_NAME}&pr=${PR_NUMBER}" > "$TMPDIR/e2e_prow_history.html" 2>/dev/null
} &
wait

# Validate fetched data exists and is non-empty
if [ ! -s "$TMPDIR/e2e_pr_status.json" ]; then
  echo "Error: Failed to fetch PR status checks from GitHub" >&2
  exit 1
fi

if [ ! -s "$TMPDIR/e2e_prow_history.html" ]; then
  echo "Error: Failed to fetch prow history" >&2
  exit 1
fi

# Get base ref from PR data
BASE_REF=$(jq -r '.baseRefName' "$TMPDIR/e2e_pr_status.json")

# Parse failed and running jobs
FAILED_E2E=$(cat "$TMPDIR/e2e_pr_status.json" | jq -r '.statusCheckRollup[] |
  select(.state == "FAILURE" or .state == "ERROR") |
  select(.context | test("ci/prow/.*e2e")) |
  .context | sub("ci/prow/"; "")')

RUNNING_E2E=$(cat "$TMPDIR/e2e_pr_status.json" | jq -r '.statusCheckRollup[] |
  select(.state == "PENDING") |
  select(.context | test("ci/prow/.*e2e")) |
  .context | sub("ci/prow/"; "")')

# Count them
if [ -n "$FAILED_E2E" ]; then
  NUM_FAILED=$(echo "$FAILED_E2E" | grep -c "^")
else
  NUM_FAILED=0
fi

if [ -n "$RUNNING_E2E" ]; then
  NUM_RUNNING=$(echo "$RUNNING_E2E" | grep -c "^")
else
  NUM_RUNNING=0
fi

# Display failed jobs with statistics
if [ "$NUM_FAILED" -gt 0 ]; then
  echo "Failed e2e jobs:"
  while IFS= read -r job; do
    [ -z "$job" ] && continue

    FULL_JOB="pull-ci-${ORG}-${REPO_NAME}-${BASE_REF}-${job}"

    STATS=$(count_consecutive_failures "$FULL_JOB" "$TMPDIR/e2e_prow_history.html")
    CONSEC=$(echo "$STATS" | cut -d'|' -f1)
    FAIL=$(echo "$STATS" | cut -d'|' -f2)
    PASS=$(echo "$STATS" | cut -d'|' -f3)
    ABORT=$(echo "$STATS" | cut -d'|' -f4)

    echo "  ❌ $job"
    if [ "$CONSEC" -gt 0 ]; then
      echo "     Consecutive failures: $CONSEC"
    fi
    if [ "$FAIL" -gt 0 ] || [ "$PASS" -gt 0 ] || [ "$ABORT" -gt 0 ]; then
      echo "     Recent history: $FAIL fail / $PASS pass / $ABORT abort"
    fi
  done <<< "$FAILED_E2E"
  echo ""
fi

# Display running jobs
if [ "$NUM_RUNNING" -gt 0 ]; then
  echo "⏳ Currently running ($NUM_RUNNING jobs):"
  while IFS= read -r job; do
    [ -z "$job" ] && continue
    echo "  • $job"
  done <<< "$RUNNING_E2E"
  echo ""
fi

# Exit if no failed jobs
if [ "$NUM_FAILED" -eq 0 ]; then
  echo "✅ No failed e2e jobs!"
  exit 0
fi

# Present retest options
echo "What would you like to do?"
echo "  1) Retest selected jobs"
echo "  2) Retest all failed ($NUM_FAILED jobs)"
echo "  3) Use /retest (single command)"
echo "  4) Just show list (done)"
echo ""
read -p "Choose [1-4]: " choice

case "$choice" in
  1)
    echo ""
    echo "Available jobs:"
    echo "$FAILED_E2E" | nl
    echo ""
    read -p "Enter job numbers to retest (space-separated, e.g., '1 3 5'): " job_nums

    # Build comment with selected jobs
    COMMENT=""
    for num in $job_nums; do
      job=$(echo "$FAILED_E2E" | sed -n "${num}p")
      if [ -n "$job" ]; then
        COMMENT="${COMMENT}/test ${job}"$'\n'
      fi
    done

    if [ -n "$COMMENT" ]; then
      echo ""
      echo "Posting comment:"
      echo "$COMMENT"
      gh pr comment ${PR_NUMBER} --repo ${REPO} --body "$COMMENT"
      echo "✅ Done!"
    else
      echo "No valid jobs selected"
    fi
    ;;

  2)
    # Retest all failed jobs
    COMMENT=""
    while IFS= read -r job; do
      [ -z "$job" ] && continue
      COMMENT="${COMMENT}/test ${job}"$'\n'
    done <<< "$FAILED_E2E"

    echo ""
    echo "Posting comment to retest all $NUM_FAILED jobs:"
    echo "$COMMENT"
    gh pr comment ${PR_NUMBER} --repo ${REPO} --body "$COMMENT"
    echo "✅ Done!"
    ;;

  3)
    # Use /retest
    echo ""
    echo "Posting /retest comment..."
    gh pr comment ${PR_NUMBER} --repo ${REPO} --body "/retest"
    echo "✅ Done!"
    ;;

  4)
    # Just show list
    echo "Done."
    ;;

  *)
    echo "Invalid choice"
    exit 1
    ;;
esac

# Cleanup handled by trap
