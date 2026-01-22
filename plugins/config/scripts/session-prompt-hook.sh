#!/bin/bash
# Hook script to capture user prompts per session
# Triggered on UserPromptSubmit event

# Read JSON input from stdin
input=$(cat)

# Variables
TARGET_DIR="${TMPDIR:-/tmp}/claude-sessions"

# Extract session_id and prompt
SESSION_ID=$(echo "$input" | jq -r '.session_id // empty')
PROMPT=$(echo "$input" | jq -r '.prompt // empty')

# Exit if we couldn't extract required data
if [ -z "$SESSION_ID" ] || [ -z "$PROMPT" ]; then
    exit 0
fi

# Convert multiline prompt to single line
PROMPT_SINGLE_LINE=$(echo "$PROMPT" | tr '\n' ' ' | sed 's/  */ /g')

# Verify target folder exists
mkdir -p "$TARGET_DIR"

# Append to session-specific file
echo "$PROMPT_SINGLE_LINE" >> "$TARGET_DIR/prompts-${SESSION_ID}.txt"
