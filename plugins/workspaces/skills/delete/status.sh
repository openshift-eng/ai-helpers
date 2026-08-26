#!/bin/bash
# Check status of a workspace before deletion
# Usage: status.sh <workspace-dir>
# Outputs structured status for each worktree

set -euo pipefail

# Source config directly (preflight.sh should only be called from list.sh)
CONFIG_FILE="${HOME}/.claude/plugins/config/workspaces/config.env"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file not found: ${CONFIG_FILE}"
    echo "Please run workspaces:create first to initialize configuration."
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

if [ -z "$WORKSPACE_DIR" ]; then
    echo "=== ERROR ==="
    echo "Usage: status.sh <workspace-dir>"
    exit 1
fi

# Handle both absolute paths and relative workspace names
if [[ "$WORKSPACE_DIR" == /* ]]; then
    # Absolute path provided - verify it's within CLAUDE_WORKSPACES_ROOT
    if [[ "$WORKSPACE_DIR" != "$CLAUDE_WORKSPACES_ROOT"/* ]]; then
        echo "ERROR: Absolute path must be within workspace root: $CLAUDE_WORKSPACES_ROOT"
        exit 1
    fi
    # Extract workspace name from path
    WORKSPACE_DIR="${WORKSPACE_DIR#"$CLAUDE_WORKSPACES_ROOT"/}"
fi

# Validate workspace directory name to prevent path traversal
if [[ "$WORKSPACE_DIR" == *..* ]]; then
    echo "ERROR: Invalid workspace directory name. Must not contain '..'"
    exit 1
fi

# Construct full path
FULL_PATH="${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR"

if [ ! -d "$FULL_PATH" ]; then
    echo "=== ERROR ==="
    echo "Workspace directory does not exist: $FULL_PATH"
    exit 1
fi

echo "=== WORKSPACE ==="
echo "DIR: $WORKSPACE_DIR"
echo "PATH: $FULL_PATH"

echo "=== REPOSITORIES ==="

HAS_UNCOMMITTED=false
HAS_UNPUSHED=false
REPOS_WITH_ISSUES=""
FOUND_REPOS=false

for repo_path in "$FULL_PATH"/*; do
    [ -d "$repo_path" ] || continue
    repo=$(basename "$repo_path")

    # Skip hidden directories and template
    [[ "$repo" == .* ]] && continue

    # Check if it's a git worktree (has .git file)
    [ ! -f "$repo_path/.git" ] && [ ! -d "$repo_path/.git" ] && continue

    FOUND_REPOS=true

    cd "$repo_path" 2>/dev/null || continue

    branch=$(git branch --show-current 2>/dev/null)
    [ -z "$branch" ] && branch="(detached)"

    # Check for uncommitted changes
    uncommitted=$(git status --porcelain 2>/dev/null | wc -l)

    # Check for unpushed commits
    unpushed=0
    if git rev-parse --verify "@{u}" &>/dev/null; then
        unpushed=$(git log "@{u}..HEAD" --oneline 2>/dev/null | wc -l)
    else
        # No upstream - compare against remote's main branch or HEAD
        REMOTE=$(get_remote)
        base_ref=""
        if git rev-parse --verify "$REMOTE/main" &>/dev/null; then
            base_ref="$REMOTE/main"
        elif git rev-parse --verify "$REMOTE/master" &>/dev/null; then
            base_ref="$REMOTE/master"
        elif git rev-parse --verify "refs/remotes/$REMOTE/HEAD" &>/dev/null; then
            base_ref="$REMOTE/HEAD"
        fi

        if [ -n "$base_ref" ]; then
            unpushed=$(git log "$base_ref..HEAD" --oneline 2>/dev/null | wc -l)
        else
            unpushed=0
        fi
    fi

    echo "REPO: $repo"
    echo "  BRANCH: $branch"
    echo "  UNCOMMITTED: $uncommitted"
    echo "  UNPUSHED: $unpushed"

    if [ "$uncommitted" -gt 0 ]; then
        HAS_UNCOMMITTED=true
        REPOS_WITH_ISSUES="$REPOS_WITH_ISSUES $repo:uncommitted"
    fi

    if [ "$unpushed" -gt 0 ] 2>/dev/null; then
        HAS_UNPUSHED=true
        REPOS_WITH_ISSUES="$REPOS_WITH_ISSUES $repo:unpushed"
    fi
done

if ! $FOUND_REPOS; then
    echo "NONE"
fi

echo "=== STATUS ==="
if $HAS_UNCOMMITTED; then
    echo "HAS_UNCOMMITTED"
fi
if $HAS_UNPUSHED; then
    echo "HAS_UNPUSHED"
fi
if ! $HAS_UNCOMMITTED && ! $HAS_UNPUSHED; then
    echo "CLEAN"
fi
