#!/bin/bash
# AI Helpers Metrics Tracking Script
# Sends anonymous usage metrics in the background and logs locally
#
# Usage:
#   track-metrics --name <command-name> [--version <version>] [--engine <engine>]
#
# Arguments:
#   --name: Name of the command/skill being executed (required)
#   --version: Version of the command/skill from its MD file (optional, default: 1.0)
#   --engine: AI engine executing the command (optional, default: claude)

# Default values
COMMAND_NAME=""
VERSION="1.0"  # Version of the command/skill, not this script
ENGINE="claude"
LOG_FILE="$HOME/.ai-helpers/metrics.log"

# Parse named arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --name)
      COMMAND_NAME="$2"
      shift 2
      ;;
    --version)
      VERSION="$2"
      shift 2
      ;;
    --engine)
      ENGINE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 --name <command-name> [--version <version>] [--engine <engine>]"
      exit 1
      ;;
  esac
done

# Validate required arguments
if [ -z "$COMMAND_NAME" ]; then
  echo "Error: --name is required"
  echo "Usage: $0 --name <command-name> [--version <version>] [--engine <engine>]"
  exit 1
fi

# Ensure log directory exists
mkdir -p "$HOME/.ai-helpers"

# Opt-out: If the opt-out file exists, exit silently
if [ -f "$HOME/.ai-helpers/metrics-opt-out" ]; then
  exit 0
fi

# Session management (reuse session ID within 24 hour windows)
SESSION_FILE="$HOME/.ai-helpers/session"
if [ ! -f "$SESSION_FILE" ] || [ -n "$(find "$SESSION_FILE" -mmin +1440 2>/dev/null)" ]; then
  uuidgen > "$SESSION_FILE" 2>/dev/null || echo "session-$(date +%s)-$$" > "$SESSION_FILE"
fi
SESSION_ID=$(cat "$SESSION_FILE" 2>/dev/null || echo "session-unknown")

# Build JSON payload
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')

# Split command into type and name (e.g., "command" and "hello-world")
# For skills/commands, the type is "command"
TYPE="command"
NAME="$COMMAND_NAME"

# Compute MAC (Message Authentication Code) to dissuade unauthorized usage
# Simple hash of session_id + timestamp using SHA256
MAC_INPUT="${SESSION_ID}${TIMESTAMP}"
MAC=$(echo -n "$MAC_INPUT" | shasum -a 256 | cut -d' ' -f1)

PAYLOAD="{\"type\":\"$TYPE\",\"name\":\"$NAME\",\"engine\":\"$ENGINE\",\"version\":\"$VERSION\",\"timestamp\":\"$TIMESTAMP\",\"session_id\":\"$SESSION_ID\",\"os\":\"$OS\",\"mac\":\"$MAC\"}"

# Log locally (synchronous)
echo "[$TIMESTAMP] Sending metrics: $PAYLOAD" >> "$LOG_FILE"

# Send metrics (non-blocking)
# Note: Authentication is handled via the MAC in the payload
(
  RESPONSE=$(curl -s -m 2 -w "\nHTTP_CODE:%{http_code}" -X POST https://ai-helpers.dptools.openshift.org/api/v1/metrics \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" 2>&1)
  
  HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
  BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE:")
  
  if [ -n "$HTTP_CODE" ]; then
    echo "[$TIMESTAMP] Response: HTTP $HTTP_CODE - $BODY" >> "$LOG_FILE"
  else
    echo "[$TIMESTAMP] Response: Failed to send (network error or timeout)" >> "$LOG_FILE"
  fi
) &

