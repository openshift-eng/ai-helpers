---
description: Push manual compilation fixes to a proof PR
argument-hint: <original-pr-number> <repo>
---

## Name

proof-pr:push-fix - Push manual fixes for compilation errors in proof PRs

## Synopsis

```
/proof-pr:push-fix <original-pr-number> <repo>
```

## Description

The `proof-pr:push-fix` command helps you push manual compilation fixes to proof PRs when auto-fix fails. This command:

1. Checks out the proof PR branch locally
2. Lets you make manual fixes
3. Tests compilation
4. Commits and pushes your fixes
5. Updates the PR with a comment

**Use this when:**
- Auto-fix couldn't resolve all compilation errors
- You need to make manual code changes
- Complex refactoring is required

**Workflow:**
1. Command checks out proof PR branch
2. You make manual edits in your editor
3. Command tests compilation
4. If successful, commits and pushes

## Arguments

- `$1` (required): Original PR number (e.g., `2626`)
- `$2` (required): Repository with proof PR to fix (e.g., `openshift/machine-config-operator`)

## Implementation

```bash
#!/bin/bash
set -euo pipefail

# Configuration
ORIGINAL_PR="$1"
REPO="$2"

SKILLS_DIR="plugins/proof-pr/skills/proof-pr-workflow"
STATE_FILE="$HOME/.work/proof-pr/$ORIGINAL_PR/state.json"
WORK_DIR="$HOME/.work/proof-pr/$ORIGINAL_PR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[proof-pr:push-fix]${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }

# Step 1: Load state
log "Loading state for PR #$ORIGINAL_PR..."

if [[ ! -f "$STATE_FILE" ]]; then
    log_error "State file not found: $STATE_FILE"
    exit 1
fi

STATE_JSON=$(cat "$STATE_FILE")
ORIGINAL_REPO=$(echo "$STATE_JSON" | jq -r '.original_repo')
ORIGINAL_URL=$(echo "$STATE_JSON" | jq -r '.original_url')

# Step 2: Find proof PR for this repo
log "Finding proof PR in $REPO..."

PROOF_PR=$(echo "$STATE_JSON" | jq -c ".proof_prs[] | select(.repo == \"$REPO\")")

if [[ -z "$PROOF_PR" ]]; then
    log_error "No proof PR found for repository: $REPO"
    log "Available repositories:"
    echo "$STATE_JSON" | jq -r '.proof_prs[].repo' | sed 's/^/  - /'
    exit 1
fi

PR_NUMBER=$(echo "$PROOF_PR" | jq -r '.number')
PR_BRANCH=$(echo "$PROOF_PR" | jq -r '.branch')
PR_URL=$(echo "$PROOF_PR" | jq -r '.url')

log "Found: $REPO#$PR_NUMBER"
log "Branch: $PR_BRANCH"
log "URL: $PR_URL"

# Step 3: Check out the proof PR branch
REPO_WORK_DIR="$WORK_DIR/$REPO"

if [[ ! -d "$REPO_WORK_DIR" ]]; then
    log_error "Repository not cloned: $REPO_WORK_DIR"
    log "Run /proof-pr:sync to re-clone"
    exit 1
fi

cd "$REPO_WORK_DIR"

log "Checking out branch: $PR_BRANCH"

git fetch origin
git checkout "$PR_BRANCH"
git pull origin "$PR_BRANCH" || {
    log_warn "Could not pull latest changes"
}

# Step 4: Show current compilation status
log ""
log "Testing current compilation status..."

if "$SKILLS_DIR/compile-test.sh" --quiet .; then
    log_success "✓ Already compiles successfully!"
    log "No fixes needed. You may still want to make changes."
else
    log_error "✗ Compilation currently failing"
    log ""
    log "Showing compilation errors:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    go build ./... 2>&1 | head -50
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

# Step 5: Pause for manual fixes
echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "MANUAL FIX MODE"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log "Repository location: $REPO_WORK_DIR"
log ""
log "Please make your fixes now in your editor."
log "Files to review:"

# Show files that might need fixing
if command -v fd >/dev/null 2>&1; then
    fd -e go --type f | head -10 | sed 's/^/  - /'
else
    find . -name "*.go" -type f | head -10 | sed 's/^/  - /'
fi

echo ""
log "When done making changes, press ENTER to continue..."
read -r

# Step 6: Check what changed
log ""
log "Checking for changes..."

if ! git diff --quiet; then
    log_success "Found uncommitted changes:"
    git diff --stat | sed 's/^/  /'
else
    log_warn "No changes detected"
    log "If you made changes, make sure they're saved"
    echo ""
    log "Continue anyway? (y/N)"
    read -r answer
    if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
        log "Aborted"
        exit 0
    fi
fi

# Step 7: Test compilation after fixes
log ""
log "Testing compilation after your fixes..."

if "$SKILLS_DIR/compile-test.sh" .; then
    log_success "✓ Compilation successful!"
    COMPILATION_STATUS="success"
else
    log_error "✗ Compilation still failing"
    log ""
    log "Showing errors:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    go build ./... 2>&1 | head -50
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    log "Push anyway? (y/N)"
    read -r answer
    if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
        log "Aborted - fixes not pushed"
        log "You can continue editing and run this command again"
        exit 1
    fi
    COMPILATION_STATUS="partial-fix"
fi

# Step 8: Commit changes
log ""
log "Committing your fixes..."

git add -A

COMMIT_MSG="Fix compilation errors for $ORIGINAL_REPO#$ORIGINAL_PR

Manual fixes applied.
Compilation status: $COMPILATION_STATUS

Testing changes from $ORIGINAL_URL
"

if ! git diff --cached --quiet; then
    git commit -m "$COMMIT_MSG"
else
    log_warn "No changes to commit"
    exit 0
fi

# Step 9: Push changes
log "Pushing to remote..."

if ! git push origin "$PR_BRANCH"; then
    log_error "Failed to push"
    log "You may need to force push if there are conflicts"
    log "Run: cd $REPO_WORK_DIR && git push -f origin $PR_BRANCH"
    exit 1
fi

log_success "✓ Fixes pushed successfully!"

# Step 10: Add comment to PR
log "Adding comment to PR..."

COMMENT="🔧 **Manual fixes applied**

Compilation status: $COMPILATION_STATUS

"

if [[ "$COMPILATION_STATUS" == "success" ]]; then
    COMMENT+="✓ Repository now compiles successfully!"
else
    COMMENT+="⚠️ Compilation still has some errors - additional fixes may be needed."
fi

COMMENT+="

Generated by [Claude Code proof-pr plugin](https://github.com/openshift-eng/ai-helpers)
"

gh pr comment "$PR_NUMBER" \
    --repo "$REPO" \
    --body "$COMMENT" || {
    log_warn "Could not add comment to PR"
}

# Step 11: Show summary
echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "SUMMARY"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_success "Fixes pushed to $PR_URL"
log "Compilation status: $COMPILATION_STATUS"
echo ""

if [[ "$COMPILATION_STATUS" == "success" ]]; then
    log "✓ Next steps:"
    log "  - Monitor CI results"
    log "  - Check status: /proof-pr:status $ORIGINAL_PR"
else
    log "⚠ Next steps:"
    log "  - Review compilation errors above"
    log "  - Run /proof-pr:push-fix $ORIGINAL_PR $REPO again to fix remaining issues"
fi

echo ""
```

## Return Value

- **Format**: Commits and pushes manual fixes
- **Output**: Summary of changes and compilation status

**Exit codes:**
- 0: Success - fixes pushed and compilation works
- 1: Error - compilation still failing or push failed

## Examples

1. **Fix compilation errors in MCO**:
   ```
   /proof-pr:push-fix 2626 openshift/machine-config-operator
   ```
   Checks out MCO proof PR branch, lets you fix errors, then pushes.

2. **After auto-fix failed**:
   ```
   /proof-pr:push-fix 2626 openshift/client-go
   ```
   Manually fix client-go proof PR that auto-fix couldn't handle.

## Notes

- **Interactive**: Pauses for you to make edits in your editor
- **Tests compilation**: Verifies fixes work before pushing
- **Optional push**: Can push even if compilation still fails (with confirmation)
- **Adds comment**: Updates PR with manual fix comment
- **Repository location**: Shows exact path for editing
