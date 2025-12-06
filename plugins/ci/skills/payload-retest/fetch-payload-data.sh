#!/bin/bash

set -euo pipefail

# fetch-payload-data.sh - Fetch and parse payload job data (NO INTERACTION)
# Usage: ./fetch-payload-data.sh [repo] <pr-number>
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

if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  echo '{"error": "PR number must be numeric"}' >&2
  exit 1
fi

# Check PR state before doing expensive fetching
PR_STATE=$(gh pr view ${PR_NUMBER} --repo ${REPO} --json state 2>/dev/null | jq -r '.state')

if [ "$PR_STATE" != "OPEN" ]; then
  echo '{"repo": "'"$REPO"'", "pr_number": '$PR_NUMBER', "state": "'"$PR_STATE"'", "error": "PR is not open", "payload_runs": 0, "failed_jobs": [], "running_jobs": []}'
  exit 0
fi

# Get payload URLs from PR comments
PAYLOAD_URLS=$(gh pr view ${PR_NUMBER} --repo ${REPO} --json comments 2>/dev/null | \
  jq -r '.comments[].body' | \
  grep -oE 'https://pr-payload-tests[^ )]+' | \
  sort -u || true)

if [ -z "$PAYLOAD_URLS" ]; then
  echo '{"repo": "'"$REPO"'", "pr_number": '$PR_NUMBER', "payload_runs": 0, "failed_jobs": [], "running_jobs": []}'
  exit 0
fi

NUM_URLS=$(echo "$PAYLOAD_URLS" | wc -l)

# Fetch all payload pages in parallel
i=1
while read -r url; do
  {
    curl -sL "$url" > "/tmp/payload_${PR_NUMBER}_$i.html" 2>/dev/null
  } &
  i=$((i+1))
done <<< "$PAYLOAD_URLS"
wait

# Parse each payload run and build data structure
rm -f "/tmp/payload_${PR_NUMBER}_jobs.txt"

i=1
while read -r url; do
  html_file="/tmp/payload_${PR_NUMBER}_$i.html"

  timestamp=$(grep -E 'Created:' "$html_file" 2>/dev/null | \
    sed -E 's/.*Created: ([^<]+).*/\1/' | head -1 || echo "")

  if [ -z "$timestamp" ]; then
    i=$((i+1))
    continue
  fi

  # Get failed jobs
  grep -oE '<span class="text-danger">[^<]+</span>' "$html_file" 2>/dev/null | \
    sed -E 's/<span class="text-danger">([^<]+)<\/span>/\1/' | \
    grep '^periodic-ci-' | \
    while read -r job; do
      echo "$job|$timestamp|failed" >> "/tmp/payload_${PR_NUMBER}_jobs.txt"
    done || true

  # Get successful jobs
  grep -oE '<span class="text-success">[^<]+</span>' "$html_file" 2>/dev/null | \
    sed -E 's/<span class="text-success">([^<]+)<\/span>/\1/' | \
    grep '^periodic-ci-' | \
    while read -r job; do
      echo "$job|$timestamp|success" >> "/tmp/payload_${PR_NUMBER}_jobs.txt"
    done || true

  # Get running jobs
  grep -oE '<span class="">[^<]+</span>' "$html_file" 2>/dev/null | \
    sed -E 's/<span class="">([^<]+)<\/span>/\1/' | \
    grep '^periodic-ci-' | \
    while read -r job; do
      echo "$job|$timestamp|running" >> "/tmp/payload_${PR_NUMBER}_jobs.txt"
    done || true

  i=$((i+1))
done <<< "$PAYLOAD_URLS"

if [ ! -f "/tmp/payload_${PR_NUMBER}_jobs.txt" ] || [ ! -s "/tmp/payload_${PR_NUMBER}_jobs.txt" ]; then
  echo '{"repo": "'"$REPO"'", "pr_number": '$PR_NUMBER', "payload_runs": '$NUM_URLS', "failed_jobs": [], "running_jobs": []}'
  rm -f /tmp/payload_${PR_NUMBER}_*.html /tmp/payload_${PR_NUMBER}_jobs.txt
  exit 0
fi

# Sort all job entries by timestamp (newest first) and job name
sort -t'|' -k2,2r -k1,1 "/tmp/payload_${PR_NUMBER}_jobs.txt" > "/tmp/payload_${PR_NUMBER}_jobs_sorted.txt"

# Build consecutive failure counts
declare -A job_most_recent_status
declare -A job_consecutive_failures
declare -A job_is_running

unique_jobs=$(cut -d'|' -f1 "/tmp/payload_${PR_NUMBER}_jobs_sorted.txt" | sort -u)

while read -r job; do
  [ -z "$job" ] && continue

  job_entries=$(grep "^${job}|" "/tmp/payload_${PR_NUMBER}_jobs_sorted.txt")
  most_recent_status=$(echo "$job_entries" | head -1 | cut -d'|' -f3)
  job_most_recent_status["$job"]="$most_recent_status"

  if [ "$most_recent_status" = "running" ]; then
    job_is_running["$job"]=1
  fi

  if [ "$most_recent_status" = "failed" ]; then
    consecutive=0
    while IFS='|' read -r j ts status; do
      if [ "$status" = "failed" ]; then
        consecutive=$((consecutive + 1))
      else
        break
      fi
    done <<< "$job_entries"
    job_consecutive_failures["$job"]=$consecutive
  fi
done <<< "$unique_jobs"

# Build JSON output
echo "{"
echo "  \"repo\": \"$REPO\","
echo "  \"pr_number\": $PR_NUMBER,"
echo "  \"payload_runs\": $NUM_URLS,"
echo "  \"failed_jobs\": ["

first=true
for job in "${!job_most_recent_status[@]}"; do
  if [ "${job_most_recent_status[$job]}" = "failed" ]; then
    consecutive=${job_consecutive_failures[$job]:-0}

    if [ "$first" = false ]; then
      echo ","
    fi
    first=false

    echo -n "    {\"name\": \"$job\", \"consecutive\": $consecutive}"
  fi
done

echo ""
echo "  ],"
echo "  \"running_jobs\": ["

first=true
for job in "${!job_is_running[@]}"; do
  if [ "$first" = false ]; then
    echo ","
  fi
  first=false
  echo -n "    \"$job\""
done

echo ""
echo "  ]"
echo "}"

# Cleanup
rm -f /tmp/payload_${PR_NUMBER}_*.html /tmp/payload_${PR_NUMBER}_*.txt
