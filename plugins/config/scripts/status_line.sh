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
GREEN_DARK='\033[38;5;28m'
GREEN_LIGHT='\033[38;5;71m'
YELLOW='\033[38;5;179m'
GREY='\033[38;5;245m'
RESET='\033[0m'

# Git branch or current directory with path context
GIT_INFO=""
PARENT_DIR=$(basename "$(dirname "$CURRENT_DIR")")
CURRENT_FOLDER="${CURRENT_DIR##*/}"

# Truncate parent dir to 10 chars, current folder to 20 chars
if [ ${#PARENT_DIR} -gt 10 ]; then
    PARENT_DIR="${PARENT_DIR:0:10}"
fi
if [ ${#CURRENT_FOLDER} -gt 20 ]; then
    CURRENT_FOLDER="${CURRENT_FOLDER:0:20}"
fi

PATH_CONTEXT="${PARENT_DIR}/${CURRENT_FOLDER}"

if git rev-parse --git-dir >/dev/null 2>&1; then
    BRANCH=$(git branch --show-current 2>/dev/null)
    if [ -n "$BRANCH" ]; then
        GIT_INFO="${GREEN_DARK}${PATH_CONTEXT}${RESET}:${GREEN_LIGHT}${BRANCH}${RESET}"
    else
        GIT_INFO="${GREEN_DARK}${PATH_CONTEXT}${RESET}"
    fi
else
    GIT_INFO="${GREEN_DARK}${PATH_CONTEXT}${RESET}"
fi

# Last prompt (truncate to 50 chars)
LAST_PROMPT=""
PROMPT_FILE="${TMPDIR:-/tmp}/claude-sessions/prompts-${SESSION_ID}.txt"
## Check if file exists for the session.
if [ -f "$PROMPT_FILE" ]; then
    ## Get the last prompt for the session.
    LAST_LINE=$(tail -n 1 "$PROMPT_FILE" 2>/dev/null)
    if [ -n "$LAST_LINE" ]; then
        ## Truncate prompt, if it is longer than 50 chars.
        if [ ${#LAST_LINE} -gt 50 ]; then
            LAST_PROMPT=" | 💬 ${GREY}${LAST_LINE:0:50}...${RESET}"
        else
            LAST_PROMPT=" | 💬 ${GREY}${LAST_LINE}${RESET}"
        fi
    fi
fi

echo -e "📦 ${PURPLE}${VERSION}${RESET} | 🧬 ${BLUE}${MODEL_DISPLAY}${RESET} | 🗂️ ${GIT_INFO} | 🎨 ${YELLOW}${OUTPUT_STYLE}${RESET}${LAST_PROMPT}"
