#!/bin/bash
# jira-ready-check.sh
#
# Gate script for automated docs-orchestrator runs.
# Queries JIRA for tickets matching a JQL query, filters out tickets
# that already have a workflow progress file on disk, and outputs
# a JSON list of actionable ticket IDs.
#
# Usage:
#   bash jira-ready-check.sh \
#     --jql "project=PROJ AND labels=docs-needed" \
#     [--base-path artifacts] \
#     [--label docs-workflow-started] \
#     [--add-label]
#
# Requires: jq, python3, jira_reader.py, JIRA_API_TOKEN, JIRA_EMAIL

set -euo pipefail

# --- Defaults ---
JQL=""
BASE_PATH="artifacts"
LABEL="docs-workflow-started"
ADD_LABEL=false
MAX_RESULTS=5
JIRA_URL="${JIRA_URL:-https://redhat.atlassian.net}"

# Resolve jira_reader.py relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JIRA_READER="${SCRIPT_DIR}/../../jira-reader/scripts/jira_reader.py"

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --jql)
      [[ -n "${2:-}" ]] || { echo '{"error": "--jql requires a query string"}'; exit 1; }
      JQL="$2"; shift 2 ;;
    --base-path)
      [[ -n "${2:-}" ]] || { echo '{"error": "--base-path requires a path"}'; exit 1; }
      BASE_PATH="$2"; shift 2 ;;
    --label)
      [[ -n "${2:-}" ]] || { echo '{"error": "--label requires a label name"}'; exit 1; }
      LABEL="$2"; shift 2 ;;
    --max-results)
      [[ -n "${2:-}" ]] || { echo '{"error": "--max-results requires a number"}'; exit 1; }
      MAX_RESULTS="$2"; shift 2 ;;
    --add-label)
      ADD_LABEL=true; shift ;;
    --dry-run)
      shift ;;  # dry-run is the default; accepted for explicitness
    *)
      echo "{\"error\": \"Unknown argument: $1\"}"; exit 1 ;;
  esac
done

if [[ -z "$JQL" ]]; then
  echo '{"error": "--jql is required"}'
  exit 1
fi

# --- Load environment ---
# Safe key/value parser: only reads KEY=VALUE lines, skips shell commands
_safe_load_env() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" =~ ^[[:space:]]*([a-zA-Z_][a-zA-Z0-9_]*)[[:space:]]*=(.*) ]] || continue
    local key="${BASH_REMATCH[1]}"
    local value="${BASH_REMATCH[2]}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ "$value" =~ ^\"(.*)\"$ ]] || [[ "$value" =~ ^\'(.*)\'$ ]]; then
      value="${BASH_REMATCH[1]}"
    fi
    if [[ -z "${!key+x}" ]]; then
      export "$key=$value"
    fi
  done < "$file"
}
_project_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$_project_root" ]]; then
  _project_root="$(cd "$SCRIPT_DIR" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null || true)"
fi
if [[ -n "$_project_root" ]]; then
  _safe_load_env "$_project_root/.env"
fi
_safe_load_env ~/.env
# Fallback: accept JIRA_AUTH_TOKEN for backward compatibility
: "${JIRA_API_TOKEN:=${JIRA_AUTH_TOKEN:-}}"

if [[ -z "${JIRA_API_TOKEN:-}" ]]; then
  echo '{"error": "JIRA_API_TOKEN is not set. Add it to .env or ~/.env."}'
  exit 1
fi

if [[ -z "${JIRA_EMAIL:-}" ]]; then
  echo '{"error": "JIRA_EMAIL is not set. Add it to .env or ~/.env."}'
  exit 1
fi

if [[ ! -f "$JIRA_READER" ]]; then
  echo "{\"error\": \"jira_reader.py not found at $JIRA_READER\"}"
  exit 1
fi

# --- Query JIRA ---
JIRA_OUTPUT=$(python3 "$JIRA_READER" --jql "$JQL" --max-results "$MAX_RESULTS" 2>&1) || {
  echo "{\"error\": \"jira_reader.py failed\", \"detail\": $(echo "$JIRA_OUTPUT" | jq -Rs .)}"
  exit 1
}

# Extract ticket keys from summary output
# jira_reader.py returns a bare object (not array) when exactly 1 result is found
ALL_TICKETS=$(echo "$JIRA_OUTPUT" | jq -r '(if type == "array" then .[].issue_key else .issue_key end) // empty' 2>/dev/null)

if [[ -z "$ALL_TICKETS" ]]; then
  # Output empty result
  cat <<EOF
{
  "query": $(echo "$JQL" | jq -Rs .),
  "total_matched": 0,
  "filtered_out": 0,
  "ready": [],
  "filtered": {}
}
EOF
  exit 0
fi

TOTAL=$(echo "$ALL_TICKETS" | wc -l | tr -d ' ')

# --- Filter out already-processed tickets ---
READY=()
declare -A FILTERED
FILTERED_COUNT=0

while IFS= read -r TICKET; do
  [[ -n "$TICKET" ]] || continue
  TICKET_LOWER=$(echo "$TICKET" | tr '[:upper:]' '[:lower:]')

  # Check for existing progress file
  if compgen -G "${BASE_PATH}/${TICKET_LOWER}/workflow/*.json" >/dev/null 2>&1; then
    FILTERED["$TICKET"]="progress_file_exists"
    FILTERED_COUNT=$((FILTERED_COUNT + 1))
    continue
  fi

  READY+=("$TICKET")
done <<< "$ALL_TICKETS"

# --- Build JSON output ---
if [[ ${#READY[@]} -eq 0 ]]; then
  READY_JSON="[]"
else
  READY_JSON=$(printf '%s\n' "${READY[@]}" | jq -R . | jq -s .)
fi

FILTERED_JSON="{"
FIRST=true
if [[ $FILTERED_COUNT -gt 0 ]]; then
  for KEY in "${!FILTERED[@]}"; do
    if [[ "$FIRST" == "true" ]]; then
      FIRST=false
    else
      FILTERED_JSON+=","
    fi
    FILTERED_JSON+="$(printf '%s' "$KEY" | jq -Rs .):$(printf '%s' "${FILTERED[$KEY]}" | jq -Rs .)"
  done
fi
FILTERED_JSON+="}"

RESULT=$(jq -n \
  --argjson ready "$READY_JSON" \
  --argjson filtered "$FILTERED_JSON" \
  --arg query "$JQL" \
  --argjson total "$TOTAL" \
  --argjson filtered_count "$FILTERED_COUNT" \
  '{
    query: $query,
    total_matched: $total,
    filtered_out: $filtered_count,
    ready: $ready,
    filtered: $filtered
  }')

echo "$RESULT"

# --- Optionally add label to ready tickets ---
if [[ "$ADD_LABEL" == "true" && ${#READY[@]} -gt 0 ]]; then
  for TICKET in "${READY[@]}"; do
    # Validate ticket key format
    if [[ ! "$TICKET" =~ ^[A-Z][A-Z0-9]+-[0-9]+$ ]]; then
      echo "{\"warning\": \"Skipping invalid ticket key: $(echo "$TICKET" | jq -Rs .)\"}" >&2
      continue
    fi

    PAYLOAD=$(jq -n --arg label "$LABEL" '{"update":{"labels":[{"add": $label}]}}')
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT \
      -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
      -H "Content-Type: application/json" \
      --data "$PAYLOAD" \
      "${JIRA_URL}/rest/api/2/issue/${TICKET}")

    if [[ "$HTTP_CODE" != "204" && "$HTTP_CODE" != "200" ]]; then
      echo "{\"warning\": \"Failed to add label '${LABEL}' to ${TICKET} (HTTP ${HTTP_CODE})\"}" >&2
    fi
  done
fi
