#!/bin/bash
# Curl wrapper that automatically adds OAuth token from specified cluster
# Usage: curl_with_token.sh <cluster_api_url> [curl arguments...]
# cluster_api_url: Full API server URL (e.g., https://api.ci.l2s4.p1.openshiftapps.com:6443)
# 
# The token is retrieved and added as "Authorization: Bearer <token>" header
# automatically, so it never appears in output or command history.

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <cluster_api_url> [curl arguments...]" >&2
  echo "cluster_api_url: Full API server URL" >&2
  echo "Example: $0 https://api.ci.l2s4.p1.openshiftapps.com:6443 -X GET https://api.example.com/endpoint" >&2
  exit 1
fi

CLUSTER_API_URL="$1"
shift  # Remove cluster_api_url from arguments

# Extract the cluster API server without protocol for matching
CLUSTER_SERVER=$(echo "$CLUSTER_API_URL" | sed -E 's|^https?://||')

# Find the context for the specified cluster by matching the server URL
CONTEXT=$(oc config get-contexts -o name 2>/dev/null | while read -r ctx; do
  server=$(oc config view -o jsonpath="{.clusters[?(@.name=='$(oc config view -o jsonpath="{.contexts[?(@.name=='$ctx')].context.cluster}" 2>/dev/null)')].cluster.server}" 2>/dev/null || echo "")
  # Extract server without protocol for comparison
  server_clean=$(echo "$server" | sed -E 's|^https?://||')
  if [ "$server_clean" = "$CLUSTER_SERVER" ]; then
    echo "$ctx"
    break
  fi
done)

if [ -z "$CONTEXT" ]; then
  echo "Error: No oc context found for cluster with API server: $CLUSTER_API_URL" >&2
  echo "" >&2
  echo "Please authenticate first:" >&2
  echo "1. Visit the cluster's console URL in your browser" >&2
  echo "2. Log in through the browser with your credentials" >&2
  echo "3. Click on username → 'Copy login command'" >&2
  echo "4. Paste and execute the 'oc login' command in terminal" >&2
  echo "" >&2
  echo "Verify authentication with:" >&2
  echo "  oc config get-contexts" >&2
  echo "  oc cluster-info" >&2
  echo "" >&2
  echo "The oc login command should connect to: $CLUSTER_API_URL" >&2
  exit 2
fi

# Get token from the context
TOKEN=$(oc whoami -t --context="$CONTEXT" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
  echo "Error: Failed to retrieve token from context $CONTEXT" >&2
  echo "Please re-authenticate to the cluster: $CLUSTER_API_URL" >&2
  exit 3
fi

# Execute curl with the Authorization header and all provided arguments
exec curl -H "Authorization: Bearer $TOKEN" "$@"

