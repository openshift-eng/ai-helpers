#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --repo <owner/repo> --pr <number> [--previous-failures <\"name1 name2\">]" >&2
  echo "" >&2
  echo "Check CI status on a GitHub PR and detect new failures." >&2
  echo "" >&2
  echo "Options:" >&2
  echo "  --repo                GitHub repository in owner/repo format (required)" >&2
  echo "  --pr                  Pull request number (required)" >&2
  echo "  --previous-failures   Space-separated check names from last check (optional)" >&2
  exit 1
}

REPO=""
PR=""
PREVIOUS_FAILURES=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)               REPO="$2"; shift 2 ;;
    --pr)                 PR="$2"; shift 2 ;;
    --previous-failures)  PREVIOUS_FAILURES="$2"; shift 2 ;;
    -h|--help)            usage ;;
    *)                    echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [[ -z "$REPO" || -z "$PR" ]]; then
  echo '{"error": "Missing required arguments. Use --repo and --pr."}' >&2
  exit 1
fi

# --- Fetch CI checks ---
checks_json=$(gh pr checks "${PR}" --repo "${REPO}" --json name,state 2>/dev/null || echo "[]")

failing_checks=$(echo "${checks_json}" | jq '[.[] | select(.state == "FAIL" or .state == "FAILURE" or .state == "fail" or .state == "failure")]')
failing_count=$(echo "${failing_checks}" | jq 'length')
current_failing_names=$(echo "${failing_checks}" | jq -r '.[].name' 2>/dev/null | sort | tr '\n' ' ' | xargs)

# --- Detect new failures ---
has_new_failures=false
if [[ "${failing_count}" -gt 0 && "${current_failing_names}" != "${PREVIOUS_FAILURES}" ]]; then
  has_new_failures=true
fi

# --- Formatted output ---
formatted=$(echo "${failing_checks}" | jq -r '.[] | "- \(.name) (\(.state))"' 2>/dev/null || echo "")

# --- Output ---
jq -n \
  --argjson failing_checks "${failing_checks}" \
  --arg failing_count "${failing_count}" \
  --arg failing_names "${current_failing_names}" \
  --arg has_new_failures "${has_new_failures}" \
  --arg formatted "${formatted}" \
  '{
    failing_checks: $failing_checks,
    failing_count: ($failing_count | tonumber),
    failing_names: $failing_names,
    has_new_failures: ($has_new_failures == "true"),
    formatted: $formatted
  }'
