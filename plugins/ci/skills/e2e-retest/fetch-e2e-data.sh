#!/bin/bash

set -euo pipefail

# fetch-e2e-data.sh - Fetch and parse e2e job data (NO INTERACTION)
# Usage: ./fetch-e2e-data.sh [repo] <pr-number>
# Output: JSON structure with failed and running jobs

# Parse arguments
if [ $# -eq 1 ]; then
  PR_NUMBER="$1"
  REPO=$(git remote -v | head -1 | grep -oP '(?<=github.com[:/])[^/]+/[^.\s]+' | sed 's/\.git$//' || true)
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
PR_DATA=$(gh pr view ${PR_NUMBER} --repo ${REPO} --json state,baseRefName 2>/dev/null)
PR_STATE=$(echo "$PR_DATA" | jq -r '.state')
BASE_REF=$(echo "$PR_DATA" | jq -r '.baseRefName')

if [ "$PR_STATE" != "OPEN" ]; then
  echo '{"repo": "'"$REPO"'", "pr_number": '$PR_NUMBER', "state": "'"$PR_STATE"'", "error": "PR is not open", "failed_jobs": [], "running_jobs": []}'
  exit 0
fi

# Fetch in parallel
{
  gh pr view ${PR_NUMBER} --repo ${REPO} --json statusCheckRollup > /tmp/e2e_pr_status_${PR_NUMBER}.json 2>/dev/null
} &
{
  curl -sL "https://prow.ci.openshift.org/pr-history?org=${ORG}&repo=${REPO_NAME}&pr=${PR_NUMBER}" > /tmp/e2e_prow_history_${PR_NUMBER}.html 2>/dev/null
} &
wait

# Parse failed and running jobs
FAILED_E2E=$(cat /tmp/e2e_pr_status_${PR_NUMBER}.json | jq -r '.statusCheckRollup[] |
  select(.state == "FAILURE" or .state == "ERROR") |
  select(.context | test("ci/prow/.*e2e")) |
  .context | sub("ci/prow/"; "")')

RUNNING_E2E=$(cat /tmp/e2e_pr_status_${PR_NUMBER}.json | jq -r '.statusCheckRollup[] |
  select(.state == "PENDING") |
  select(.context | test("ci/prow/.*e2e")) |
  .context | sub("ci/prow/"; "")')

# Function to count consecutive failures
count_consecutive_failures() {
  local job_name="$1"
  local html_file="$2"

  local runs=$(grep -A 10 ">${job_name}<" "$html_file" | \
    grep -oE "run-(success|failure|aborted|pending)" | \
    head -10)

  local consecutive=0
  local total_fail=0
  local total_pass=0
  local total_abort=0
  local found_non_failure=0

  while IFS= read -r run; do
    [ -z "$run" ] && continue
    case "$run" in
      run-failure)
        total_fail=$((total_fail + 1))
        if [ "$found_non_failure" -eq 0 ]; then
          consecutive=$((consecutive + 1))
        fi
        ;;
      run-success)
        total_pass=$((total_pass + 1))
        found_non_failure=1
        ;;
      run-aborted)
        total_abort=$((total_abort + 1))
        found_non_failure=1
        ;;
      run-pending)
        ;;
    esac
  done <<< "$runs"

  echo "${consecutive}|${total_fail}|${total_pass}|${total_abort}"
}

# Build JSON output
echo "{"
echo "  \"repo\": \"$REPO\","
echo "  \"pr_number\": $PR_NUMBER,"
echo "  \"failed_jobs\": ["

first=true
while IFS= read -r job; do
  [ -z "$job" ] && continue

  FULL_JOB="pull-ci-${ORG}-${REPO_NAME}-${BASE_REF}-${job}"
  STATS=$(count_consecutive_failures "$FULL_JOB" /tmp/e2e_prow_history_${PR_NUMBER}.html)
  CONSEC=$(echo "$STATS" | cut -d'|' -f1)
  FAIL=$(echo "$STATS" | cut -d'|' -f2)
  PASS=$(echo "$STATS" | cut -d'|' -f3)
  ABORT=$(echo "$STATS" | cut -d'|' -f4)

  if [ "$first" = false ]; then
    echo ","
  fi
  first=false

  echo -n "    {\"name\": \"$job\", \"consecutive\": $CONSEC, \"fail\": $FAIL, \"pass\": $PASS, \"abort\": $ABORT}"
done <<< "$FAILED_E2E"

echo ""
echo "  ],"
echo "  \"running_jobs\": ["

first=true
while IFS= read -r job; do
  [ -z "$job" ] && continue
  if [ "$first" = false ]; then
    echo ","
  fi
  first=false
  echo -n "    \"$job\""
done <<< "$RUNNING_E2E"

echo ""
echo "  ]"
echo "}"

# Cleanup
rm -f /tmp/e2e_pr_status_${PR_NUMBER}.json /tmp/e2e_prow_history_${PR_NUMBER}.html
