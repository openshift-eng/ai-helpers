#!/bin/bash
# Preflight check for git workspace configuration

set -euo pipefail

# Determine config file location
CONFIG_DIR="${HOME}/.claude/plugins/config/workspaces"
CONFIG_FILE="${CONFIG_DIR}/config.env"

# Parse command line arguments (only when executed directly, not when sourced)
REPOS_ROOT=""
WORKSPACES_ROOT=""
RECONFIGURE=false

# Only process arguments if script is being executed directly, not sourced
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    while [[ $# -gt 0 ]]; do
        case $1 in
            --repos-root)
                REPOS_ROOT="$2"
                shift 2
                ;;
            --workspaces-root)
                WORKSPACES_ROOT="$2"
                shift 2
                ;;
            --reconfigure)
                RECONFIGURE=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
fi

# Handle configuration
if [ "$RECONFIGURE" = true ] || [ ! -f "${CONFIG_FILE}" ]; then
    if [ -z "$REPOS_ROOT" ] || [ -z "$WORKSPACES_ROOT" ]; then
        echo "=== CONFIGURATION REQUIRED ==="
        echo "STATUS: NOT_CONFIGURED"
        echo ""
        echo "MESSAGE:"
        echo "This is the first run or reconfiguration was requested."
        echo "Please ask the user for the following paths:"
        echo ""
        echo "1. Git repositories root directory (where your git repos are cloned)"
        echo "   Example: /home/user/git-repos or ~/work/repos"
        echo ""
        echo "2. Workspaces root directory (where workspaces will be created)"
        echo "   Example: /home/user/workspaces or ~/dev/workspaces"
        echo ""
        echo "Then call this script again with:"
        echo "  preflight.sh --repos-root <path1> --workspaces-root <path2>"
        exit 1
    fi

    # Save configuration
    mkdir -p "${CONFIG_DIR}"
    cat > "${CONFIG_FILE}" <<EOF
export CLAUDE_GIT_REPOS_ROOT="${REPOS_ROOT}"
export CLAUDE_WORKSPACES_ROOT="${WORKSPACES_ROOT}"
EOF
    chmod 600 "${CONFIG_FILE}"
    echo "=== CONFIGURATION SAVED ==="
    echo "CONFIG_FILE: ${CONFIG_FILE}"
    echo "REPOS_ROOT: ${REPOS_ROOT}"
    echo "WORKSPACES_ROOT: ${WORKSPACES_ROOT}"

    # Create custom-prompt.md during first-time setup
    CUSTOM_PROMPT_FILE="${CONFIG_DIR}/custom-prompt.md"
    cat > "${CUSTOM_PROMPT_FILE}" <<'CUSTOM_PROMPT_EOF'
# DISABLED - Remove this line to enable custom workspace rules

## Aliases

Example format:
- `FE` → `frontend`
- `BE` → `backend`
- `API` → `api-service`

## Auto-detect Rules

Example format:
- When `frontend` is selected → add `shared-components`
- When `api-service` is selected → add `api-client`

## Workspace Naming

Directory name priority:
1. Jira key (e.g., `BOARD-1234`)
2. PR review format: `review-{repo}-{pr-number}`
3. Custom feature name: `feature-{description}`

CUSTOM_PROMPT_EOF
    echo "CUSTOM_PROMPT_FILE_CREATED: ${CUSTOM_PROMPT_FILE}"
    echo ""
    echo "=== AGENT_INSTRUCTION ==="
    echo "IMPORTANT: You must inform the user about the custom prompt file."
    echo ""
    echo "ACTION REQUIRED: Tell the user they can customize ${CUSTOM_PROMPT_FILE} to add:"
    echo "  - Repository aliases for shorter names (e.g., FE → frontend)"
    echo "  - Auto-detect rules to automatically include dependent repositories"
    echo "  - Workspace naming preferences"
    echo ""
    echo "Explain that this will make workspace creation smarter and tailored to their team's workflow."
    echo "=== END_AGENT_INSTRUCTION ==="
fi

# Source and export
# shellcheck disable=SC1090
source "${CONFIG_FILE}"

# Validate that required variables are set
if [ -z "${CLAUDE_GIT_REPOS_ROOT:-}" ] || [ -z "${CLAUDE_WORKSPACES_ROOT:-}" ]; then
    echo "ERROR: Configuration file exists but does not contain required variables"
    echo "Config file: ${CONFIG_FILE}"
    echo "Please delete the file and reconfigure:"
    echo "  rm ${CONFIG_FILE}"
    echo "  Then run the command again"
    exit 1
fi

export CLAUDE_GIT_REPOS_ROOT CLAUDE_WORKSPACES_ROOT

# Create custom-prompt.md if it doesn't exist
CUSTOM_PROMPT_FILE="${CONFIG_DIR}/custom-prompt.md"
if [ ! -f "${CUSTOM_PROMPT_FILE}" ]; then
    cat > "${CUSTOM_PROMPT_FILE}" <<'CUSTOM_PROMPT_EOF'
# DISABLED - Remove this line to enable custom workspace rules

# Workspace Custom Rules

This file contains organization-specific aliases and auto-detect rules.
Claude reads this file when parsing workspace descriptions during workspaces:create.

## Aliases

Repository name shortcuts (customize for your organization):

Example format:
- `FE` → `frontend`
- `BE` → `backend`
- `API` → `api-service`

Add your team's aliases below:

## Auto-detect Rules

Automatic dependency inclusion (customize for your organization):

Example format:
- When `frontend` is selected → add `shared-components`
- When `api-service` is selected → add `api-client`

Add your team's auto-detect rules below:

## Workspace Naming

Directory name priority:
1. Jira key (e.g., `TEAM-1234`)
2. PR review format: `review-{repo}-{pr-number}`
3. Custom feature name: `feature-{description}`

CUSTOM_PROMPT_EOF
fi

# Check if custom-prompt.md has been customized by the user
# If it still contains the DISABLED marker, show agent instruction
if grep -q "^# DISABLED" "${CUSTOM_PROMPT_FILE}"; then
    # File exists but hasn't been customized yet
    echo ""
    echo "=== AGENT_INSTRUCTION ==="
    echo "IMPORTANT: You must inform the user about the custom prompt file."
    echo ""
    echo "ACTION REQUIRED: Tell the user they can customize ${CUSTOM_PROMPT_FILE} to add:"
    echo "  - Repository aliases for shorter names (e.g., FE → frontend)"
    echo "  - Auto-detect rules to automatically include dependent repositories"
    echo "  - Workspace naming preferences"
    echo ""
    echo "Explain that this will make workspace creation smarter and tailored to their team's workflow."
    echo "=== END_AGENT_INSTRUCTION ==="
    echo ""
fi

# Create .template if it doesn't exist
TEMPLATE_DIR="${CLAUDE_WORKSPACES_ROOT}/.template"
if [ ! -d "${TEMPLATE_DIR}" ]; then
    echo "=== CREATING DEFAULT TEMPLATE ==="
    mkdir -p "${TEMPLATE_DIR}"

    # Create default CLAUDE.md
    cat > "${TEMPLATE_DIR}/CLAUDE.md" <<'TEMPLATE_EOF'
# Workspace Context

This is a multi-repository workspace managed by git worktrees.

## Structure

- Repository directories - Git worktrees for each repository in this workspace

## Working with this workspace

Each repository directory is a separate git worktree pointing to a specific branch.
All repositories in this workspace are typically on the same feature branch or reviewing the same PR.

You can customize this template at: ${CLAUDE_WORKSPACES_ROOT}/.template/
TEMPLATE_EOF

    echo "TEMPLATE_CREATED: ${TEMPLATE_DIR}"
    echo "Users can customize the template at this location."
fi
