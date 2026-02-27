#!/bin/bash

set -euo pipefail

# fetch-e2e-data.sh - Fetch and parse e2e job data (NO INTERACTION)
# Usage: ./fetch-e2e-data.sh [repo] <pr-number>
# Output: JSON structure with failed and running jobs

# Source shared utilities
source "$(dirname "$0")/common.sh"

# Parse arguments
if [ $# -eq 1 ]; then
  PR_NUMBER="$1"
  REPO=$(git remote -v | head -1 | sed -E 's/.*github\.com[:/]([^/]+\/[^ .]+).*/\1/' | sed 's/\.git$//' || true)
  if [ -z "$REPO" ]; then
    echo '{"error": "Could not detect repository from git remote"}' >&2
    exit 1
  fi
elif [ $# -eq 2 ]; then
  REPO_ARG="$1"
  PR_NUMBER="$2"
  if [[ "$REPO_ARG" == *"/"* ]]; then
    REPO="$REPO_ARG"
  else
    REPO="openshift/$REPO_ARG"
  fi
else
  echo '{"error": "Invalid arguments"}' >&2
  exit 1
fi

ORG=$(echo "$REPO" | cut -d'/' -f1)
REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)

if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  echo '{"error": "PR number must be numeric"}' >&2
  exit 1
fi

# Check PR state and get base ref before doing expensive fetching
if ! PR_DATA=$(gh pr view ${PR_NUMBER} --repo ${REPO} --json state,baseRefName 2>/dev/null); then
  echo '{"error": "Failed to fetch PR data from GitHub"}' >&2
  exit 1
fi
PR_STATE=$(echo "$PR_DATA" | jq -r '.state')
BASE_REF=$(echo "$PR_DATA" | jq -r '.baseRefName')

if [ "$PR_STATE" != "OPEN" ]; then
  echo '{"repo": "'"$REPO"'", "pr_number": '$PR_NUMBER', "state": "'"$PR_STATE"'", "error": "PR is not open", "failed_jobs": [], "running_jobs": []}'
  exit 0
fi

# Create unique temp directory and setup cleanup
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Fetch in parallel
{
  gh pr view ${PR_NUMBER} --repo ${REPO} --json statusCheckRollup > "$TMPDIR/e2e_pr_status.json" 2>/dev/null
} &
{
  curl -sL "https://prow.ci.openshift.org/pr-history?org=${ORG}&repo=${REPO_NAME}&pr=${PR_NUMBER}" > "$TMPDIR/e2e_prow_history.html" 2>/dev/null
} &
wait

# Parse failed and running jobs
FAILED_E2E=$(cat "$TMPDIR/e2e_pr_status.json" | jq -r '.statusCheckRollup[] |
  select(.state == "FAILURE" or .state == "ERROR") |
  select(.context | test("ci/prow/.*e2e")) |
  .context | sub("ci/prow/"; "")')

RUNNING_E2E=$(cat "$TMPDIR/e2e_pr_status.json" | jq -r '.statusCheckRollup[] |
  select(.state == "PENDING") |
  select(.context | test("ci/prow/.*e2e")) |
  .context | sub("ci/prow/"; "")')

# Build JSON output using jq for safe escaping
# Start with base structure
jq -n \
  --arg repo "$REPO" \
  --argjson pr_number "$PR_NUMBER" \
  '{repo: $repo, pr_number: $pr_number, failed_jobs: [], running_jobs: []}' \
  > "$TMPDIR/e2e_output.json"

# Add failed jobs
while IFS= read -r job; do
  [ -z "$job" ] && continue

  FULL_JOB="pull-ci-${ORG}-${REPO_NAME}-${BASE_REF}-${job}"
  STATS=$(count_consecutive_failures "$FULL_JOB" "$TMPDIR/e2e_prow_history.html")
  CONSEC=$(echo "$STATS" | cut -d'|' -f1)
  FAIL=$(echo "$STATS" | cut -d'|' -f2)
  PASS=$(echo "$STATS" | cut -d'|' -f3)
  ABORT=$(echo "$STATS" | cut -d'|' -f4)

  jq \
    --arg job "$job" \
    --argjson cons "$CONSEC" \
    --argjson fail "$FAIL" \
    --argjson pass "$PASS" \
    --argjson abort "$ABORT" \
    '.failed_jobs += [{name: $job, consecutive: $cons, fail: $fail, pass: $pass, abort: $abort}]' \
    $TMPDIR/e2e_output.json > $TMPDIR/e2e_output.json.tmp
  mv $TMPDIR/e2e_output.json.tmp $TMPDIR/e2e_output.json
done <<< "$FAILED_E2E"

# Add running jobs
while IFS= read -r job; do
  [ -z "$job" ] && continue
  jq \
    --arg job "$job" \
    '.running_jobs += [$job]' \
    $TMPDIR/e2e_output.json > $TMPDIR/e2e_output.json.tmp
  mv $TMPDIR/e2e_output.json.tmp $TMPDIR/e2e_output.json
done <<< "$RUNNING_E2E"

# Output final JSON
cat $TMPDIR/e2e_output.json

# Cleanup handled by trap
