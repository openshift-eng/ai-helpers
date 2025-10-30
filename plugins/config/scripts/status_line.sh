#!/usr/bin/env bash

# Read JSON input from stdin
input=$(cat)

# Extract values using jq
VERSION=$(echo "$input" | jq -r '.version')
MODEL_DISPLAY=$(echo "$input" | jq -r '.model.display_name')
CURRENT_DIR=$(echo "$input" | jq -r '.workspace.current_dir')
OUTPUT_STYLE=$(echo "$input" | jq -r '.output_style.name')
SESSION_ID=$(echo "$input" | jq -r '.session_id')

# ANSI color codes (matte)
PURPLE='\033[38;5;135m'
BLUE='\033[38;5;68m'
GREEN='\033[38;5;71m'
YELLOW='\033[38;5;179m'
GREY='\033[38;5;245m'
RESET='\033[0m'

# Git branch or current directory
GIT_INFO=""
if git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git branch --show-current 2>/dev/null)
    if [ -n "$BRANCH" ]; then
        GIT_INFO="$BRANCH"
    else
        GIT_INFO="${CURRENT_DIR##*/}"
    fi
else
    GIT_INFO="${CURRENT_DIR##*/}"
fi

# Last prompt (truncate to 50 chars)
LAST_PROMPT=""
PROMPT_FILE="/tmp/prompts-${SESSION_ID}.txt"
## Check if file exists for the session.
if [ -f "$PROMPT_FILE" ]; then
    ## Get the last prompt for the session.
    LAST_LINE=$(tail -n 1 "$PROMPT_FILE" 2>/dev/null)
    if [ -n "$LAST_LINE" ]; then
        ## Truncate prompt, if it is longer than 50 chars.
        if [ ${#LAST_LINE} -gt 50 ]; then
            LAST_PROMPT=" | ${GREY}${LAST_LINE:0:50}...${RESET}"
        else
            LAST_PROMPT=" | ${GREY}${LAST_LINE}${RESET}"
        fi
    fi
fi

echo -e "${PURPLE}${VERSION}${RESET} | ${BLUE}${MODEL_DISPLAY}${RESET} | ${GREEN}${GIT_INFO}${RESET} | ${YELLOW}${OUTPUT_STYLE}${RESET}${LAST_PROMPT}"
