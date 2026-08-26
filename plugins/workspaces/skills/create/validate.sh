#!/bin/bash
# Validate workspace directory and repos before creation
# Usage: validate.sh <workspace-dir> <branch-name> <repo1> [repo2] [repo3] ...

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source config directly (preflight.sh should only be called from gather.sh)
CONFIG_FILE="${HOME}/.claude/plugins/config/workspaces/config.env"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file not found: ${CONFIG_FILE}"
    echo "Please run gather.sh first to initialize configuration."
    exit 1
fi
# shellcheck disable=SC1090
source "${CONFIG_FILE}"

# Get the primary remote name (prefers 'origin' if it exists, otherwise first remote)
get_remote() {
    if git remote | grep -q '^origin$'; then
        echo "origin"
    else
        git remote | head -n1
    fi
}

WORKSPACE_DIR="$1"
BRANCH="$2"
shift 2
REPOS="$*"

# Handle both absolute paths and relative workspace names
if [[ "$WORKSPACE_DIR" == /* ]]; then
    # Absolute path provided - verify it's within CLAUDE_WORKSPACES_ROOT
    if [[ "$WORKSPACE_DIR" != "$CLAUDE_WORKSPACES_ROOT"/* ]]; then
        echo "ERROR: Absolute path must be within workspace root: $CLAUDE_WORKSPACES_ROOT"
        exit 1
    fi
    # Extract workspace name from path
    WORKSPACE_DIR="${WORKSPACE_DIR#$CLAUDE_WORKSPACES_ROOT/}"
fi

# Validate workspace directory name to prevent path traversal
if [[ "$WORKSPACE_DIR" == *..* ]]; then
    echo "ERROR: Invalid workspace directory name. Must not contain '..'"
    exit 1
fi

ISSUES=""

echo "=== VALIDATION ==="

# Check workspace directory
if [ -d "${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR" ]; then
    echo "WORKSPACEDIR:EXISTS"
    ISSUES="${ISSUES}WORKSPACEDIR "
else
    echo "WORKSPACEDIR:OK"
fi

# Check each repo
for repo in $REPOS; do
    echo "--- $repo ---"

    if [ ! -d "${CLAUDE_GIT_REPOS_ROOT}/$repo" ]; then
        echo "  REPO:MISSING"
        ISSUES="${ISSUES}REPO:$repo "
        continue
    fi

    cd "${CLAUDE_GIT_REPOS_ROOT}/$repo" || exit 1
    git worktree prune 2>/dev/null

    REMOTE=$(get_remote)

    # Get default branch
    default=$(git symbolic-ref "refs/remotes/$REMOTE/HEAD" 2>/dev/null | sed "s,refs/remotes/$REMOTE/,,")
    [ -z "$default" ] && default="main"
    echo "  DEFAULT:$default"

    # Check if branch exists
    if git show-ref --verify "refs/heads/$BRANCH" 2>/dev/null; then
        echo "  BRANCH:EXISTS"
        ISSUES="${ISSUES}BRANCH:$repo "
    else
        echo "  BRANCH:OK"
    fi

    # Check if worktree path exists
    if [ -d "${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR/$repo" ]; then
        echo "  WORKTREE:EXISTS"
        ISSUES="${ISSUES}WORKTREE:$repo "
    else
        echo "  WORKTREE:OK"
    fi
done

echo "=== ISSUES ==="
if [ -z "$ISSUES" ]; then
    echo "NONE"
else
    echo "$ISSUES"
fi
