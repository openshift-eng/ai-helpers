#!/bin/bash
# Curl wrapper that automatically adds OAuth token from specified cluster
# Usage: curl_with_token.sh <cluster_id> [curl arguments...]
# cluster_id: Either "app.ci" or "dpcr"
# 
# The token is retrieved and added as "Authorization: Bearer <token>" header
# automatically, so it never appears in output or command history.

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <cluster_id> [curl arguments...]" >&2
  echo "cluster_id: app.ci or dpcr" >&2
  echo "Example: $0 app.ci -X GET https://api.example.com/endpoint" >&2
  exit 1
fi

CLUSTER_ID="$1"
shift  # Remove cluster_id from arguments

# Define cluster patterns and console URLs
case "$CLUSTER_ID" in
  "app.ci")
    PATTERN="ci-l2s4-p1"
    CONSOLE_URL="https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/"
    ;;
  "dpcr")
    PATTERN="cr-j7t7-p1"
    CONSOLE_URL="https://console-openshift-console.apps.cr.j7t7.p1.openshiftapps.com/"
    ;;
  *)
    echo "Error: Unknown cluster_id: $CLUSTER_ID" >&2
    echo "Valid options: app.ci, dpcr" >&2
    exit 1
    ;;
esac

# Find the context for the specified cluster
CONTEXT=$(oc config get-contexts -o name 2>/dev/null | while read -r ctx; do
  cluster=$(oc config view -o jsonpath="{.contexts[?(@.name=='$ctx')].context.cluster}" 2>/dev/null || echo "")
  if echo "$cluster" | grep -q "$PATTERN"; then
    echo "$ctx"
    break
  fi
done)

if [ -z "$CONTEXT" ]; then
  echo "Error: No oc context found for $CLUSTER_ID cluster (pattern: $PATTERN)" >&2
  echo "" >&2
  echo "Please authenticate first:" >&2
  echo "1. Visit $CONSOLE_URL" >&2
  echo "2. Log in through the browser with SSO credentials" >&2
  echo "3. Click on username → 'Copy login command'" >&2
  echo "4. Paste and execute the 'oc login' command in terminal" >&2
  echo "" >&2
  echo "Verify authentication with:" >&2
  echo "  oc config get-contexts" >&2
  echo "Look for a context with cluster name containing '$PATTERN'." >&2
  exit 2
fi

# Get token from the context
TOKEN=$(oc whoami -t --context="$CONTEXT" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
  echo "Error: Failed to retrieve token from context $CONTEXT" >&2
  echo "Please re-authenticate to the $CLUSTER_ID cluster" >&2
  exit 3
fi

# Execute curl with the Authorization header and all provided arguments
exec curl -H "Authorization: Bearer $TOKEN" "$@"

