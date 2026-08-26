#!/bin/bash
# Execute workspace creation
# Usage: execute.sh <workspace-dir> <branch-name> <workspace-type> <repo1> [repo2] ...
# workspace-type: "feature" or "review:<pr-number>"

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

BRANCH="$2"
WORKSPACE_TYPE="$3"
shift 3
REPOS="$*"

# Run validation first
if ! "${SCRIPT_DIR}/validate.sh" "$WORKSPACE_DIR" "$BRANCH" $REPOS; then
    echo "ERROR: Validation failed. Aborting workspace creation."
    exit 1
fi
echo ""

set -e  # Exit on error

echo "=== STEP 1: Copy template ==="
cp -r "${CLAUDE_WORKSPACES_ROOT}/.template" "${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR"
echo "  OK: Created ${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR"

echo "=== STEP 2: Create worktrees ==="
for repo in $REPOS; do
    echo "--- $repo ---"

    cd "${CLAUDE_GIT_REPOS_ROOT}/$repo"

    REMOTE=$(get_remote)
    echo "  Fetching $REMOTE..."
    git fetch "$REMOTE" -q

    # Get default branch
    default=$(git symbolic-ref "refs/remotes/$REMOTE/HEAD" 2>/dev/null | sed "s,refs/remotes/$REMOTE/,,")
    [ -z "$default" ] && default="main"

    echo "  Creating worktree from $REMOTE/$default..."
    git worktree add "${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR/$repo" "$REMOTE/$default"
    echo "  OK"
done

echo "=== STEP 3: Setup branches ==="
for repo in $REPOS; do
    echo "--- $repo ---"

    cd "${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR/$repo"

    REMOTE=$(get_remote)

    if [[ "$WORKSPACE_TYPE" == feature ]]; then
        git checkout -b "$BRANCH"
    elif [[ "$WORKSPACE_TYPE" == review:* ]]; then
        PR_NUM="${WORKSPACE_TYPE#review:}"
        if command -v gh &> /dev/null; then
            gh pr checkout "$PR_NUM"
        else
            git fetch "$REMOTE" "pull/$PR_NUM/head:pr-$PR_NUM"
            git checkout "pr-$PR_NUM"
        fi
    fi

    echo "  OK: $(git branch --show-current)"
done

echo "=== DONE ==="
echo "Workspace: ${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR"
echo "Repositories:"
for repo in $REPOS; do
    branch=$(cd "${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR/$repo" && git branch --show-current)
    echo "  - $repo: $branch"
done
