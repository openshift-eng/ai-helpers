#!/bin/bash

# common.sh - Shared utility functions for e2e-retest

# Count consecutive failures from prow history
# Args: job_name, html_file
# Output: consecutive|total_fail|total_pass|total_abort
count_consecutive_failures() {
  local job_name="$1"
  local html_file="$2"

  # Escape regex special characters in job name for safe grep pattern matching
  local escaped_job_name=$(printf '%s\n' "$job_name" | sed 's/[[\.*^$/]/\\&/g')

  local runs=$(grep -A 10 ">${escaped_job_name}<" "$html_file" | \
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
