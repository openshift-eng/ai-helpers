#!/bin/bash
# create-jira-ticket.sh
#
# Create a linked JIRA documentation ticket from a planning output file.
#
# Usage: create-jira-ticket.sh <TICKET> <PROJECT> <PLAN_FILE>
# Requires: curl, jq, python3
# Environment: JIRA_API_TOKEN, JIRA_EMAIL

set -euo pipefail

TICKET="${1:?Usage: create-jira-ticket.sh <TICKET> <PROJECT> <PLAN_FILE>}"
PROJECT="${2:?Missing PROJECT argument}"
PLAN_FILE="${3:?Missing PLAN_FILE argument}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load local overrides first, then global defaults (resolve .env from project root)
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
_project_root="$(cd "$(dirname "$PLAN_FILE")" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$_project_root" ]]; then
    _safe_load_env "$_project_root/.env"
fi
_safe_load_env ~/.env
# Fallback: accept JIRA_AUTH_TOKEN for backward compatibility
: "${JIRA_API_TOKEN:=${JIRA_AUTH_TOKEN:-}}"
JIRA_URL="${JIRA_URL:-https://redhat.atlassian.net}"

if [[ -z "${JIRA_API_TOKEN:-}" || -z "${JIRA_EMAIL:-}" ]]; then
    echo "Error: JIRA_API_TOKEN and JIRA_EMAIL must be set" >&2
    exit 1
fi

if [[ ! -f "$PLAN_FILE" ]]; then
    echo "Error: Plan file not found: $PLAN_FILE" >&2
    exit 1
fi

# --- Check for existing Document link ---
LINKS_JSON=$(curl -s \
  -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${JIRA_URL}/rest/api/2/issue/${TICKET}?fields=issuelinks")

HAS_DOC_LINK=$(echo "$LINKS_JSON" | jq -r '
  .fields.issuelinks[]? |
  select(.type.name == "Document" and .inwardIssue != null) |
  .type.name' | head -1)

if [[ -n "$HAS_DOC_LINK" ]]; then
    LINKED_KEY=$(echo "$LINKS_JSON" | jq -r '
      .fields.issuelinks[] |
      select(.type.name == "Document" and .inwardIssue != null) |
      .inwardIssue.key' | head -1)
    echo "A documentation ticket (${LINKED_KEY}) already exists for ${TICKET}."
    echo "Skipping JIRA creation."
    exit 0
fi

# --- Check if project is public or private ---
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Content-Type: application/json" \
  "${JIRA_URL}/rest/api/2/project/${PROJECT}")

if [[ "$HTTP_STATUS" == "200" ]]; then
    PROJECT_IS_PUBLIC=true
else
    PROJECT_IS_PUBLIC=false
fi

# --- Extract description from plan ---
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

VISIBILITY="private"
if [[ "$PROJECT_IS_PUBLIC" == "true" ]]; then
    VISIBILITY="public"
fi

python3 "${SCRIPT_DIR}/extract-description.py" \
  "$PLAN_FILE" \
  "$TMPDIR/jira_description_raw.txt" \
  "$VISIBILITY"

# --- Convert markdown to JIRA wiki markup ---
python3 "${SCRIPT_DIR}/md2wiki.py" \
  "$TMPDIR/jira_description_raw.txt" \
  "$TMPDIR/jira_description_wiki.txt"

# --- Create the JIRA ticket ---
PARENT_SUMMARY=$(curl -s \
  -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  "${JIRA_URL}/rest/api/2/issue/${TICKET}?fields=summary" | jq -r '.fields.summary')

python3 "${SCRIPT_DIR}/build-payload.py" \
  "$TMPDIR/jira_description_wiki.txt" \
  "$TMPDIR/jira_create_payload.json" \
  "$PROJECT" \
  "$PARENT_SUMMARY"

RESPONSE=$(curl -s -X POST \
  -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data @"${TMPDIR}/jira_create_payload.json" \
  "${JIRA_URL}/rest/api/2/issue")

NEW_ISSUE_KEY=$(echo "$RESPONSE" | jq -r '.key')

if [[ -z "$NEW_ISSUE_KEY" || "$NEW_ISSUE_KEY" == "null" ]]; then
    echo "Error: Failed to create JIRA ticket" >&2
    echo "$RESPONSE" >&2
    exit 1
fi

# --- Link new ticket to parent (link type is "Document", not "Documents") ---
LINK_PAYLOAD=$(jq -n \
  --arg ticket "$TICKET" \
  --arg new_key "$NEW_ISSUE_KEY" \
  '{ type: {name: "Document"}, outwardIssue: {key: $ticket}, inwardIssue: {key: $new_key} }')
LINK_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data "$LINK_PAYLOAD" \
  "${JIRA_URL}/rest/api/2/issueLink")

if [[ "$LINK_HTTP_CODE" -lt 200 || "$LINK_HTTP_CODE" -ge 300 ]]; then
    echo "Warning: Failed to link ${NEW_ISSUE_KEY} to ${TICKET} (HTTP ${LINK_HTTP_CODE})" >&2
fi

# --- Attach plan file (private projects only) ---
if [[ "$PROJECT_IS_PUBLIC" != "true" ]]; then
    ATTACH_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
      -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
      -H "X-Atlassian-Token: no-check" \
      -F "file=@${PLAN_FILE}" \
      "${JIRA_URL}/rest/api/2/issue/${NEW_ISSUE_KEY}/attachments")

    if [[ "$ATTACH_HTTP_CODE" -lt 200 || "$ATTACH_HTTP_CODE" -ge 300 ]]; then
        echo "Warning: Failed to attach plan to ${NEW_ISSUE_KEY} (HTTP ${ATTACH_HTTP_CODE})" >&2
    fi
fi

# --- Print the new ticket URL ---
echo "${JIRA_URL}/browse/${NEW_ISSUE_KEY}"
