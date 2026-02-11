#!/bin/bash

set -euo pipefail

# ci:payload-retest - Find and retest failed payload jobs on a PR
# Usage: ./payload-retest.sh [repo] <pr-number>

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

# Validate PR number
if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  echo "❌ Error: PR number must be numeric"
  exit 1
fi

echo ""

# Get payload URLs from PR comments
echo "Searching for payload runs..."
if ! PR_COMMENTS=$(gh pr view ${PR_NUMBER} --repo ${REPO} --json comments 2>/dev/null); then
  echo "Error: Failed to fetch PR data from GitHub" >&2
  exit 1
fi

PAYLOAD_URLS=$(echo "$PR_COMMENTS" | \
  jq -r '.comments[].body' | \
  grep -oE 'https://pr-payload-tests[^ )]+' | \
  sort -u || true)

if [ -z "$PAYLOAD_URLS" ]; then
  echo "No payload runs found for this PR"
  exit 0
fi

NUM_URLS=$(echo "$PAYLOAD_URLS" | wc -l)
echo "Found $NUM_URLS payload run(s)"
echo ""

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

echo "Analyzing all payload runs..."
echo ""

# Parse each payload run and build a data structure
# Format: job_name|timestamp|status (one line per job per run)

i=1
while read -r url; do
  html_file="$TMPDIR/payload_$i.html"

  # Get timestamp for this run
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

# Check if we found any jobs
if [ ! -f "$TMPDIR/payload_jobs.txt" ] || [ ! -s "$TMPDIR/payload_jobs.txt" ]; then
  echo "No payload jobs found in any run"
  echo "NOTE: If payload runs exist but no jobs were found, the HTML structure may have changed."
  exit 0
fi

# Sort all job entries by timestamp (newest first) and job name
sort -t'|' -k2,2r -k1,1 "$TMPDIR/payload_jobs.txt" > "$TMPDIR/payload_jobs_sorted.txt"

# Build consecutive failure counts
# For each unique job, find its most recent status and count consecutive failures
declare -A job_most_recent_status
declare -A job_consecutive_failures
declare -A job_is_running

# Get unique job names
unique_jobs=$(cut -d'|' -f1 "$TMPDIR/payload_jobs_sorted.txt" | sort -u)

while read -r job; do
  [ -z "$job" ] && continue

  # Get all entries for this job, sorted by timestamp (newest first)
  job_entries=$(awk -F'|' -v j="$job" '$1==j' "$TMPDIR/payload_jobs_sorted.txt")

  # Most recent status is the first line
  most_recent_status=$(echo "$job_entries" | head -1 | cut -d'|' -f3)
  job_most_recent_status["$job"]="$most_recent_status"

  # If most recent is running, mark it
  if [ "$most_recent_status" = "running" ]; then
    job_is_running["$job"]=1
  fi

  # Count consecutive failures (only if currently failed)
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

# Display currently failed jobs
failed_jobs=()
for job in "${!job_most_recent_status[@]}"; do
  if [ "${job_most_recent_status[$job]}" = "failed" ]; then
    failed_jobs+=("$job")
  fi
done

# Display currently running jobs
running_jobs=()
for job in "${!job_is_running[@]}"; do
  running_jobs+=("$job")
done

NUM_FAILED=${#failed_jobs[@]}
NUM_RUNNING=${#running_jobs[@]}

if [ "$NUM_FAILED" -gt 0 ]; then
  echo "Failed payload jobs:"
  for job in "${failed_jobs[@]}"; do
    consecutive=${job_consecutive_failures[$job]:-0}
    echo "  ❌ $job"
    if [ "$consecutive" -gt 0 ]; then
      echo "     Consecutive failures: $consecutive"
    fi
  done
  echo ""
fi

if [ "$NUM_RUNNING" -gt 0 ]; then
  echo "⏳ Currently running ($NUM_RUNNING jobs):"
  for job in "${running_jobs[@]}"; do
    echo "  • $job"
  done
  echo ""
fi

# Exit if no failed jobs
if [ "$NUM_FAILED" -eq 0 ]; then
  if [ "$NUM_RUNNING" -gt 0 ]; then
    echo "✅ No failed payload jobs (waiting for $NUM_RUNNING running jobs)"
  else
    echo "✅ No failed payload jobs!"
  fi
  # Cleanup
  rm -f /tmp/payload_${PR_NUMBER}_*.html /tmp/payload_${PR_NUMBER}_*.txt
  exit 0
fi

# Present retest options
echo "What would you like to do?"
echo "  1) Retest selected jobs"
echo "  2) Retest all failed ($NUM_FAILED jobs)"
echo "  3) Just show list (done)"
echo ""
read -p "Choose [1-3]: " choice

case "$choice" in
  1)
    echo ""
    echo "Available jobs:"
    i=1
    for job in "${failed_jobs[@]}"; do
      echo "  $i) $job"
      i=$((i+1))
    done
    echo ""
    read -p "Enter job numbers to retest (space-separated, e.g., '1 3 5'): " job_nums

    # Build comment with selected jobs
    COMMENT=""
    for num in $job_nums; do
      # Validate input is numeric
      if ! [[ "$num" =~ ^[0-9]+$ ]]; then
        echo "Warning: Skipping invalid input '$num' (not a number)" >&2
        continue
      fi

      idx=$((num - 1))
      if [ $idx -ge 0 ] && [ $idx -lt ${#failed_jobs[@]} ]; then
        job="${failed_jobs[$idx]}"
        COMMENT="${COMMENT}/payload-job ${job}"$'\n'
      else
        echo "Warning: Job number $num is out of range (1-${#failed_jobs[@]})" >&2
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
    for job in "${failed_jobs[@]}"; do
      COMMENT="${COMMENT}/payload-job ${job}"$'\n'
    done

    echo ""
    echo "Posting comment to retest all $NUM_FAILED jobs:"
    echo "$COMMENT"
    gh pr comment ${PR_NUMBER} --repo ${REPO} --body "$COMMENT"
    echo "✅ Done!"
    ;;

  3)
    # Just show list
    echo "Done."
    ;;

  *)
    echo "Invalid choice"
    rm -f /tmp/payload_${PR_NUMBER}_*.html /tmp/payload_${PR_NUMBER}_*.txt
    exit 1
    ;;
esac

# Cleanup
rm -f /tmp/payload_${PR_NUMBER}_*.html /tmp/payload_${PR_NUMBER}_*.txt
