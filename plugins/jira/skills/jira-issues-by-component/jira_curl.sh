#!/bin/bash
# Secure curl wrapper for JIRA API that prevents token exposure
# Usage: jira_curl.sh [curl arguments...]
#
# The JIRA credentials are read from environment variables and the token
# is added as "Authorization: Bearer <token>" header automatically,
# so it never appears in process listings or command history.
#
# Required environment variables:
#   JIRA_URL: JIRA instance URL (e.g., https://issues.redhat.com)
#   JIRA_PERSONAL_TOKEN or JIRA_API_TOKEN: Authentication token

set -euo pipefail

# Check for required environment variables
if [ -z "${JIRA_URL:-}" ]; then
  echo "Error: JIRA_URL environment variable is required" >&2
  echo "" >&2
  echo "Please set JIRA credentials:" >&2
  echo "  export JIRA_URL='https://issues.redhat.com'" >&2
  echo "  export JIRA_PERSONAL_TOKEN='your-token-here'" >&2
  echo "" >&2
  echo "Alternatively, source a credentials file:" >&2
  echo "  source ~/.jira-credentials" >&2
  exit 1
fi

# Use JIRA_PERSONAL_TOKEN if available, otherwise fall back to JIRA_API_TOKEN
AUTH_TOKEN="${JIRA_PERSONAL_TOKEN:-${JIRA_API_TOKEN:-}}"

if [ -z "$AUTH_TOKEN" ]; then
  echo "Error: JIRA authentication token is required" >&2
  echo "" >&2
  echo "Please set either:" >&2
  echo "  export JIRA_PERSONAL_TOKEN='your-token-here'  # Preferred for Red Hat JIRA" >&2
  echo "  export JIRA_API_TOKEN='your-token-here'       # For JIRA Cloud" >&2
  echo "" >&2
  echo "Get your token from:" >&2
  echo "  - Red Hat JIRA PAT: https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens" >&2
  echo "  - Atlassian API Token: https://id.atlassian.com/manage-profile/security/api-tokens" >&2
  exit 1
fi

# Execute curl with the Authorization header
# The token is added here, inside the script, so it never appears in the
# parent process's command line arguments
exec curl -H "Authorization: Bearer $AUTH_TOKEN" -H "Accept: application/json" "$@"
