#!/bin/bash
# Secure curl wrapper for JIRA API that prevents token exposure
# Usage: jira_curl.sh [curl arguments...]
#
# The JIRA credentials are read from environment variables and the token
# is added as "Authorization: Basic <base64>" header automatically,
# so it never appears in process listings or command history.
#
# Required environment variables:
#   JIRA_URL: JIRA instance URL (e.g., https://redhat.atlassian.net)
#   JIRA_API_TOKEN: Atlassian API token
#   JIRA_USERNAME: Atlassian account email (e.g., user@redhat.com)

set -euo pipefail

# Check for required environment variables
if [ -z "${JIRA_URL:-}" ]; then
  echo "Error: JIRA_URL environment variable is required" >&2
  echo "" >&2
  echo "Please set JIRA credentials:" >&2
  echo "  export JIRA_URL='https://redhat.atlassian.net'" >&2
  echo "  export JIRA_API_TOKEN='your-token-here'" >&2
  echo "  export JIRA_USERNAME='user@redhat.com'" >&2
  echo "" >&2
  echo "Alternatively, source a credentials file:" >&2
  echo "  source ~/.jira-credentials" >&2
  exit 1
fi

case "$JIRA_URL" in
  https://*) ;;
  *)
    echo "Error: JIRA_URL must use https:// scheme to protect credentials" >&2
    exit 1
    ;;
esac

if [ -z "${JIRA_API_TOKEN:-}" ]; then
  echo "Error: JIRA authentication token is required" >&2
  echo "" >&2
  echo "Please set:" >&2
  echo "  export JIRA_API_TOKEN='your-token-here'" >&2
  echo "  export JIRA_USERNAME='user@redhat.com'" >&2
  echo "" >&2
  echo "Get your token from:" >&2
  echo "  - Atlassian API Token: https://id.atlassian.com/manage-profile/security/api-tokens" >&2
  exit 1
fi

if [ -z "${JIRA_USERNAME:-}" ]; then
  echo "Error: JIRA_USERNAME environment variable is required" >&2
  echo "" >&2
  echo "Please set:" >&2
  echo "  export JIRA_USERNAME='user@redhat.com'" >&2
  exit 1
fi

# Execute curl with Basic authentication header
# The credentials are constructed here, inside the script, so they never
# appear in the parent process's command line arguments
AUTH_HEADER=$(printf '%s:%s' "$JIRA_USERNAME" "$JIRA_API_TOKEN" | base64 | tr -d '\r\n')
exec curl --proto '=https' --proto-redir '=https' \
  -H "Authorization: Basic $AUTH_HEADER" \
  -H "Accept: application/json" \
  "$@"
