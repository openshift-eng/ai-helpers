#!/bin/bash
# Execute workspace deletion
# Usage: execute.sh <workspace-dir> [--keep-branches|--delete-branches]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source config directly (preflight.sh should only be called from list.sh)
CONFIG_FILE="${HOME}/.claude/plugins/config/workspaces/config.env"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file not found: ${CONFIG_FILE}"
    echo "Please run workspaces:create first to initialize configuration."
    exit 1
fi
# shellcheck disable=SC1090
source "${CONFIG_FILE}"
WORKSPACE_DIR="${1:-}"
BRANCH_ACTION="${2:---delete-branches}"

if [ -z "$WORKSPACE_DIR" ]; then
    echo "=== ERROR ==="
    echo "Usage: execute.sh <workspace-dir> [--keep-branches|--delete-branches]"
    exit 1
fi

FULL_PATH="${CLAUDE_WORKSPACES_ROOT}/$WORKSPACE_DIR"

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

# Check status first and capture output
STATUS_OUTPUT=$("${SCRIPT_DIR}/status.sh" "$WORKSPACE_DIR" 2>&1) || {
    echo "ERROR: Failed to check workspace status"
    exit 1
}

# Parse status
STATUS_CLEAN=false
STATUS_UNCOMMITTED=false
STATUS_UNPUSHED=false

if echo "$STATUS_OUTPUT" | grep -q "^CLEAN$"; then
    STATUS_CLEAN=true
fi
if echo "$STATUS_OUTPUT" | grep -q "^HAS_UNCOMMITTED$"; then
    STATUS_UNCOMMITTED=true
fi
if echo "$STATUS_OUTPUT" | grep -q "^HAS_UNPUSHED$"; then
    STATUS_UNPUSHED=true
fi

# Display status to user
echo "$STATUS_OUTPUT"
echo ""

# If status has issues and no explicit branch action specified, exit with error
if [ -z "${2:-}" ] && { $STATUS_UNCOMMITTED || $STATUS_UNPUSHED; }; then
    # No explicit flag was given, and there are issues
    # Exit with code 2 to signal the agent needs to prompt user
    echo "=== USER INPUT REQUIRED ==="
    echo "This workspace has uncommitted changes or unpushed commits."
    echo "Please specify how to handle branches:"
    echo "  --keep-branches: Delete workspace but keep git branches"
    echo "  --delete-branches: Delete workspace AND branches (uncommitted/unpushed work will be lost)"
    exit 2
fi

set -e

echo "=== STEP 1: Remove worktrees ==="

FOUND_REPOS=false
for repo_path in "$FULL_PATH"/*; do
    [ -d "$repo_path" ] || continue
    repo=$(basename "$repo_path")

    # Skip hidden directories
    [[ "$repo" == .* ]] && continue

    # Check if it's a git worktree (has .git file)
    [ ! -f "$repo_path/.git" ] && [ ! -d "$repo_path/.git" ] && continue

    FOUND_REPOS=true

    echo "--- $repo ---"

    # Get branch name and main repo path before removing
    cd "$repo_path" 2>/dev/null || continue
    branch=$(git branch --show-current 2>/dev/null)
    main_repo="${CLAUDE_GIT_REPOS_ROOT}/$repo"

    # Remove the worktree from git's tracking
    cd "$main_repo" 2>/dev/null || {
        echo "  WARN: Main repo not found at $main_repo"
        continue
    }

    echo "  Removing worktree..."
    git worktree remove "$repo_path" --force 2>/dev/null || {
        echo "  WARN: git worktree remove failed, will remove directory manually"
    }

    # Delete branch if requested
    if [ "$BRANCH_ACTION" = "--delete-branches" ] && [ -n "$branch" ]; then
        echo "  Deleting branch: $branch"
        git branch -D "$branch" 2>/dev/null || echo "  WARN: Could not delete branch $branch"
    else
        echo "  Keeping branch: $branch"
    fi

    echo "  OK"
done

if ! $FOUND_REPOS; then
    echo "No git repositories found"
fi

echo "=== STEP 2: Remove workspace directory ==="
rm -rf "$FULL_PATH"
echo "  OK: Removed $FULL_PATH"

echo "=== DONE ==="
echo "Workspace '$WORKSPACE_DIR' has been deleted"
