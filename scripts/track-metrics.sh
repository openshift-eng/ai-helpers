#!/bin/bash
# AI Helpers Metrics Tracking Script
# Sends anonymous usage metrics in the background and logs locally

COMMAND_NAME="$1"
LOG_FILE="$HOME/.ai-helpers/metrics.log"

# Ensure log directory exists
mkdir -p "$HOME/.ai-helpers"

# Session management (reuse session ID within 24 hour windows)
SESSION_FILE="$HOME/.ai-helpers-session"
if [ ! -f "$SESSION_FILE" ] || [ -n "$(find "$SESSION_FILE" -mmin +1440 2>/dev/null)" ]; then
  uuidgen 2>/dev/null || echo "session-$(date +%s)-$$" > "$SESSION_FILE"
fi
SESSION_ID=$(cat "$SESSION_FILE" 2>/dev/null || echo "session-unknown")

# Build JSON payload
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
PAYLOAD="{\"command\":\"$COMMAND_NAME\",\"timestamp\":\"$TIMESTAMP\",\"session_id\":\"$SESSION_ID\",\"os\":\"$OS\"}"

# Log locally (synchronous)
echo "[$TIMESTAMP] Sending metrics: $PAYLOAD" >> "$LOG_FILE"

# Send metrics (non-blocking)
# Note: The metrics token is not secretive - it's just to prevent random API discovery
(
  RESPONSE=$(curl -s -m 2 -w "\nHTTP_CODE:%{http_code}" -X POST https://ai-helpers.dptools.openshift.org/api/v1/metrics \
    -H "Content-Type: application/json" \
    -H "X-Metrics-Token: 7f8e9d2c-4b3a-4e1f-9c5d-6a7b8c9d0e1f" \
    -d "$PAYLOAD" 2>&1)
  
  HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
  BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE:")
  
  if [ -n "$HTTP_CODE" ]; then
    echo "[$TIMESTAMP] Response: HTTP $HTTP_CODE - $BODY" >> "$LOG_FILE"
  else
    echo "[$TIMESTAMP] Response: Failed to send (network error or timeout)" >> "$LOG_FILE"
  fi
) &

