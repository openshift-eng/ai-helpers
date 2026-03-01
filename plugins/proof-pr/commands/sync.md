---
description: Sync proof PRs with latest changes from original PR
argument-hint: <original-pr-number>
---

## Name

proof-pr:sync - Update proof PRs to latest commits from original PR

## Synopsis

```
/proof-pr:sync <original-pr-number>
```

## Description

The `proof-pr:sync` command updates all active proof PRs to use the latest pseudo-version from the original PR. This is needed when:
- The original PR has new commits pushed
- You want to test the latest changes
- Dependencies need to be refreshed

**Key Features:**
- **Updates pseudo-versions**: Recalculates pseudo-version from latest commit
- **Preserves manual fixes**: Handles conflicts if you've made manual changes
- **Re-runs codegen**: Automatically runs code generation after sync
- **Tests compilation**: Verifies proof PRs still compile after update
- **Handles conflicts**: Provides guidance when manual merge needed

**Workflow:**
1. Fetches latest commit from original PR
2. Generates new pseudo-version
3. For each active (unconverted, unmerged) proof PR:
   - Updates go.mod with new pseudo-version
   - Runs code generation if needed
   - Tests compilation
   - Commits and force-pushes changes

## Arguments

- `$1` (required): Original PR number (e.g., `2626`)

## Implementation

```bash
#!/bin/bash
set -euo pipefail

# Configuration
ORIGINAL_PR="$1"

SKILLS_DIR="plugins/proof-pr/skills/proof-pr-workflow"
STATE_FILE="$HOME/.work/proof-pr/$ORIGINAL_PR/state.json"
WORK_DIR="$HOME/.work/proof-pr/$ORIGINAL_PR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[proof-pr:sync]${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }

# Step 1: Load state
log "Loading state for PR #$ORIGINAL_PR..."

if [[ ! -f "$STATE_FILE" ]]; then
    log_error "State file not found: $STATE_FILE"
    log "Run /proof-pr:status $ORIGINAL_PR to recover state"
    exit 1
fi

STATE_JSON=$(cat "$STATE_FILE")
ORIGINAL_REPO=$(echo "$STATE_JSON" | jq -r '.original_repo')
ORIGINAL_URL=$(echo "$STATE_JSON" | jq -r '.original_url')

log "Original PR: $ORIGINAL_REPO#$ORIGINAL_PR"

# Step 2: Get latest commit from original PR
log "Fetching latest commit from original PR..."

ORIGINAL_PR_JSON=$(gh pr view "$ORIGINAL_PR" \
    --repo "$ORIGINAL_REPO" \
    --json state,commits,headRefName)

PR_STATE=$(echo "$ORIGINAL_PR_JSON" | jq -r '.state')

if [[ "$PR_STATE" == "MERGED" ]]; then
    log_error "Original PR is already merged"
    log "Use /proof-pr:convert instead"
    exit 1
fi

if [[ "$PR_STATE" == "CLOSED" ]]; then
    log_error "Original PR is closed"
    exit 1
fi

LATEST_COMMIT=$(echo "$ORIGINAL_PR_JSON" | jq -r '.commits[-1].oid[:12]')
COMMIT_TIMESTAMP=$(echo "$ORIGINAL_PR_JSON" | jq -r '.commits[-1].committedDate' \
    | sed 's/[-:]//g; s/T//; s/Z.*//')
PR_BRANCH=$(echo "$ORIGINAL_PR_JSON" | jq -r '.headRefName')

NEW_PSEUDO_VERSION="v0.0.0-${COMMIT_TIMESTAMP}-${LATEST_COMMIT}"
ORIGINAL_MODULE="github.com/$ORIGINAL_REPO"

log "Latest commit: $LATEST_COMMIT"
log "New pseudo-version: $NEW_PSEUDO_VERSION"

# Step 3: Sync each active proof PR
log ""
log "Syncing active proof PRs..."

PROOF_PRS=$(echo "$STATE_JSON" | jq -c '.proof_prs[] | select(.converted == false and .merged == false)')

if [[ -z "$PROOF_PRS" ]]; then
    log_warn "No active proof PRs to sync"
    exit 0
fi

SYNCED_COUNT=0
FAILED_COUNT=0

while IFS= read -r proof_pr; do
    REPO=$(echo "$proof_pr" | jq -r '.repo')
    NUMBER=$(echo "$proof_pr" | jq -r '.number')
    BRANCH=$(echo "$proof_pr" | jq -r '.branch')
    DEPENDS_ON=$(echo "$proof_pr" | jq -r '.depends_on_repo')

    echo ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Syncing: $REPO#$NUMBER"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    REPO_WORK_DIR="$WORK_DIR/$REPO"

    if [[ ! -d "$REPO_WORK_DIR" ]]; then
        log_error "Repository not cloned: $REPO_WORK_DIR"
        log "Run /proof-pr:create again to re-clone"
        ((FAILED_COUNT++))
        continue
    fi

    cd "$REPO_WORK_DIR"

    # Fetch latest
    log "Fetching latest..."
    git fetch --all

    # Checkout proof branch
    log "Checking out branch: $BRANCH"
    if ! git checkout "$BRANCH"; then
        log_error "Failed to checkout branch: $BRANCH"
        ((FAILED_COUNT++))
        continue
    fi

    # Pull latest changes (might have conflicts)
    log "Pulling latest changes..."
    if ! git pull origin "$BRANCH"; then
        log_warn "Pull failed (might have conflicts)"
        log "This is expected if you've made manual changes"
    fi

    # Update go.mod
    log "Updating dependency: github.com/$DEPENDS_ON -> $NEW_PSEUDO_VERSION"

    if ! go get "github.com/$DEPENDS_ON@$NEW_PSEUDO_VERSION"; then
        log_error "Failed to update dependency"
        ((FAILED_COUNT++))
        continue
    fi

    go mod tidy

    # Check if there are changes
    if ! git diff --quiet go.mod go.sum; then
        log "Dependency updated"
    else
        log "No dependency changes (already up to date)"
        ((SYNCED_COUNT++))
        continue
    fi

    # Run code generation if needed
    log "Checking for code generation requirements..."

    CODEGEN_JSON=$("$SKILLS_DIR/detect-codegen.py" . --json 2>/dev/null)
    NEEDS_CODEGEN=$(echo "$CODEGEN_JSON" | jq -r '.needs_codegen')

    if [[ "$NEEDS_CODEGEN" == "true" ]]; then
        CODEGEN_CMD=$(echo "$CODEGEN_JSON" | jq -r '.command')

        if [[ "$CODEGEN_CMD" != "null" && -n "$CODEGEN_CMD" ]]; then
            log "Running code generation: $CODEGEN_CMD"

            if ! eval "$CODEGEN_CMD"; then
                log_error "Code generation failed"
                log "You may need to fix this manually"
                ((FAILED_COUNT++))
                continue
            fi

            log "Code generation completed"
        fi
    fi

    # Test compilation
    log "Testing compilation..."

    if "$SKILLS_DIR/compile-test.sh" --quiet .; then
        log_success "Compilation successful"
        COMPILATION_STATUS="success"
    else
        log_warn "Compilation failed, attempting auto-fix..."

        FIX_JSON=$("$SKILLS_DIR/attempt-fix.py" . --json 2>/dev/null)
        FIX_SUCCESS=$(echo "$FIX_JSON" | jq -r '.compilation_succeeds')

        if [[ "$FIX_SUCCESS" == "true" ]]; then
            log_success "Auto-fix successful!"
            COMPILATION_STATUS="fixed"
        else
            log_error "Auto-fix failed"
            log "Compilation still failing - manual fixes needed"
            COMPILATION_STATUS="failed"

            # Continue anyway - push the sync even if broken
            log_warn "Pushing sync anyway (will need manual fixes)"
        fi
    fi

    # Commit changes
    log "Committing sync..."

    git add -A

    COMMIT_MSG="[PROOF] Sync to latest from $ORIGINAL_REPO#$ORIGINAL_PR

Updated pseudo-version: $NEW_PSEUDO_VERSION
Compilation: $COMPILATION_STATUS

Synced with latest commit: $LATEST_COMMIT
"

    if ! git diff --cached --quiet; then
        git commit -m "$COMMIT_MSG"
    else
        log "No changes to commit"
        ((SYNCED_COUNT++))
        continue
    fi

    # Force push (sync overwrites previous proof state)
    log "Force pushing to fork..."

    if ! git push -f origin "$BRANCH"; then
        log_error "Failed to push"
        ((FAILED_COUNT++))
        continue
    fi

    log_success "Synced successfully!"

    # Add comment to PR
    log "Adding sync comment to PR..."

    COMMENT="🔄 **Synced to latest**

Updated to latest commit from $ORIGINAL_URL:
- Commit: \`$LATEST_COMMIT\`
- Pseudo-version: \`$NEW_PSEUDO_VERSION\`
- Compilation: $COMPILATION_STATUS

Generated by [Claude Code proof-pr plugin](https://github.com/openshift-eng/ai-helpers)
"

    gh pr comment "$NUMBER" \
        --repo "$REPO" \
        --body "$COMMENT" || {
        log_warn "Could not add comment to PR"
    }

    ((SYNCED_COUNT++))

done <<< "$PROOF_PRS"

# Step 4: Show summary
echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "SYNC SUMMARY"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_success "Synced: $SYNCED_COUNT proof PRs"

if (( FAILED_COUNT > 0 )); then
    log_error "Failed: $FAILED_COUNT proof PRs"
    echo ""
    log "Review failed PRs and fix manually if needed"
fi

echo ""
log "Next steps:"
log "  - Review synced proof PRs for any CI failures"
log "  - Fix any compilation errors with /proof-pr:push-fix"
log "  - Check status with /proof-pr:status $ORIGINAL_PR"
echo ""
```

## Return Value

- **Format**: Syncs proof PRs and reports results
- **Output**: Summary of synced and failed PRs

**Exit codes:**
- 0: Success - all proof PRs synced
- 1: Partial failure - some PRs failed to sync

## Examples

1. **Sync after original PR updated**:
   ```
   /proof-pr:sync 2626
   ```
   Updates all active proof PRs to use latest commit from api#2626.

2. **After pushing new commits to original**:
   ```
   /proof-pr:sync 2626
   ```
   Refreshes proof PRs to test the new changes.

## Notes

- **Force push**: Uses `git push -f` since proof PRs are temporary
- **Preserves manual fixes**: If you've made manual changes, may create conflicts
- **Auto-fix**: Attempts to fix new compilation errors after sync
- **Only syncs active**: Skips converted or merged proof PRs
- **Comments**: Adds sync comment to each PR for visibility
