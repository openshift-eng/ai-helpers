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
if ! PR_DATA=$(gh pr view ${PR_NUMBER} --repo ${REPO} --json state,comments 2>/dev/null); then
  echo '{"error": "Failed to fetch PR data from GitHub"}' >&2
  exit 1
fi

PR_STATE=$(echo "$PR_DATA" | jq -r '.state')

if [ "$PR_STATE" != "OPEN" ]; then
  echo '{"repo": "'"$REPO"'", "pr_number": '$PR_NUMBER', "state": "'"$PR_STATE"'", "error": "PR is not open", "payload_runs": 0, "failed_jobs": [], "running_jobs": []}'
  exit 0
fi

# Get payload URLs from PR comments (already fetched in PR_DATA)
PAYLOAD_URLS=$(echo "$PR_DATA" | \
  jq -r '.comments[].body' | \
  grep -oE 'https://pr-payload-tests[^ )]+' | \
  sort -u || true)

if [ -z "$PAYLOAD_URLS" ]; then
  echo '{"repo": "'"$REPO"'", "pr_number": '$PR_NUMBER', "payload_runs": 0, "failed_jobs": [], "running_jobs": []}'
  exit 0
fi

NUM_URLS=$(echo "$PAYLOAD_URLS" | wc -l)

# Create unique temp directory and setup cleanup
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Fetch all payload pages in parallel
i=1
while read -r url; do
  {
    curl -sL "$url" > "$TMPDIR/payload_$i.html" 2>/dev/null
  } &
  i=$((i+1))
done <<< "$PAYLOAD_URLS"
wait

# Parse each payload run and build data structure

i=1
while read -r url; do
  html_file="$TMPDIR/payload_$i.html"

  timestamp=$(grep -E 'Created:' "$html_file" 2>/dev/null | \
    sed -E 's/.*Created: ([^<]+).*/\1/' | head -1 || echo "")

  if [ -z "$timestamp" ]; then
    i=$((i+1))
    continue
  fi

  # Parse all jobs with their status
  # NOTE: This relies on specific HTML structure from pr-payload-tests dashboard:
  #   - Failed jobs: <span class="text-danger">job-name</span>
  #   - Success jobs: <span class="text-success">job-name</span>
  #   - Running jobs: <span class="">job-name</span>
  #   - Job names start with: periodic-ci-
  # If HTML structure changes, parsing may fail silently.

  # Write to per-iteration file to avoid concurrent append issues
  jobs_file="$TMPDIR/jobs_$i.txt"

  # Get failed jobs
  grep -oE '<span class="text-danger">[^<]+</span>' "$html_file" 2>/dev/null | \
    sed -E 's/<span class="text-danger">([^<]+)<\/span>/\1/' | \
    grep '^periodic-ci-' | \
    while read -r job; do
      echo "$job|$timestamp|failed" >> "$jobs_file"
    done || true

  # Get successful jobs
  grep -oE '<span class="text-success">[^<]+</span>' "$html_file" 2>/dev/null | \
    sed -E 's/<span class="text-success">([^<]+)<\/span>/\1/' | \
    grep '^periodic-ci-' | \
    while read -r job; do
      echo "$job|$timestamp|success" >> "$jobs_file"
    done || true

  # Get running jobs
  grep -oE '<span class="">[^<]+</span>' "$html_file" 2>/dev/null | \
    sed -E 's/<span class="">([^<]+)<\/span>/\1/' | \
    grep '^periodic-ci-' | \
    while read -r job; do
      echo "$job|$timestamp|running" >> "$jobs_file"
    done || true

  i=$((i+1))
done <<< "$PAYLOAD_URLS"

# Concatenate all per-iteration job files
cat "$TMPDIR"/jobs_*.txt > "$TMPDIR/payload_jobs.txt" 2>/dev/null || true

if [ ! -f "$TMPDIR/payload_jobs.txt" ] || [ ! -s "$TMPDIR/payload_jobs.txt" ]; then
  echo "NOTE: No payload jobs found. If payload runs exist, HTML structure may have changed." >&2
  echo '{"repo": "'"$REPO"'", "pr_number": '$PR_NUMBER', "payload_runs": '$NUM_URLS', "failed_jobs": [], "running_jobs": []}'
  exit 0
fi

# Sort all job entries by timestamp (newest first) and job name
sort -t'|' -k2,2r -k1,1 "$TMPDIR/payload_jobs.txt" > "$TMPDIR/payload_jobs_sorted.txt"

# Build consecutive failure counts
declare -A job_most_recent_status
declare -A job_consecutive_failures
declare -A job_is_running

unique_jobs=$(cut -d'|' -f1 "$TMPDIR/payload_jobs_sorted.txt" | sort -u)

while read -r job; do
  [ -z "$job" ] && continue

  job_entries=$(awk -F'|' -v j="$job" '$1==j' "$TMPDIR/payload_jobs_sorted.txt")
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

# Build JSON output using jq for safe escaping
jq -n \
  --arg repo "$REPO" \
  --argjson pr_number "$PR_NUMBER" \
  --argjson payload_runs "$NUM_URLS" \
  '{repo: $repo, pr_number: $pr_number, payload_runs: $payload_runs, failed_jobs: [], running_jobs: []}' \
  > $TMPDIR/payload_output.json

# Add failed jobs
for job in "${!job_most_recent_status[@]}"; do
  if [ "${job_most_recent_status[$job]}" = "failed" ]; then
    consecutive=${job_consecutive_failures[$job]:-0}

    jq \
      --arg job "$job" \
      --argjson cons "$consecutive" \
      '.failed_jobs += [{name: $job, consecutive: $cons}]' \
      $TMPDIR/payload_output.json > $TMPDIR/payload_output.json.tmp
    mv $TMPDIR/payload_output.json.tmp $TMPDIR/payload_output.json
  fi
done

# Add running jobs
for job in "${!job_is_running[@]}"; do
  jq \
    --arg job "$job" \
    '.running_jobs += [$job]' \
    $TMPDIR/payload_output.json > $TMPDIR/payload_output.json.tmp
  mv $TMPDIR/payload_output.json.tmp $TMPDIR/payload_output.json
done

# Output final JSON
cat $TMPDIR/payload_output.json

# Cleanup handled by trap
