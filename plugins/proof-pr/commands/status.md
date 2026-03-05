---
description: Check status of proof PRs and merge preparation
argument-hint: <original-pr-number> [--original-pr-url]
---

## Name

proof-pr:status - Display status of proof PRs with merge preparation information

## Synopsis

```
/proof-pr:status <original-pr-number>
/proof-pr:status --original-pr-url <url>
```

## Description

The `proof-pr:status` command shows the current status of all proof PRs in a workflow, including:
- CI/test status for each PR
- Compilation status
- Merge readiness (lgtm, approve, verified labels)
- Recommendations for next steps

This command is **information-only** and does not make any changes. It provides guidance on what actions to take to satisfy Tide auto-merge requirements.

**Key Features:**
- **Auto-recovery**: Can reconstruct state from GitHub if state file missing
- **Auto-sync**: Detects if GitHub state differs from saved state
- **Merge preparation**: Shows what labels/approvals are needed for Tide
- **Clear recommendations**: Tells you exactly what to do next

## Arguments

- `$1` (required): Original PR number (e.g., `2626`)
- `--original-pr-url` (optional): Original PR URL for auto-recovery if state missing

## Implementation

```bash
#!/bin/bash
set -euo pipefail

# Configuration
ORIGINAL_PR="$1"
ORIGINAL_PR_URL="${2:-}"  # Optional for recovery

SKILLS_DIR="plugins/proof-pr/skills/proof-pr-workflow"
STATE_FILE="$HOME/.work/proof-pr/$ORIGINAL_PR/state.json"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[proof-pr:status]${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }

# Step 1: Load or recover state
log "Loading state for PR #$ORIGINAL_PR..."

if [[ ! -f "$STATE_FILE" ]]; then
    log_warn "State file not found"

    if [[ -n "$ORIGINAL_PR_URL" ]]; then
        log "Attempting recovery from GitHub..."
        "$SKILLS_DIR/state-manager.py" recover "$ORIGINAL_PR" >/dev/null
    else
        log_error "State file not found. Provide --original-pr-url for recovery."
        log "Example: /proof-pr:status $ORIGINAL_PR https://github.com/org/repo/pull/$ORIGINAL_PR"
        exit 1
    fi
fi

# Load state
STATE_JSON=$(cat "$STATE_FILE")
ORIGINAL_REPO=$(echo "$STATE_JSON" | jq -r '.original_repo')
ORIGINAL_URL=$(echo "$STATE_JSON" | jq -r '.original_url')
PROOF_PRS_COUNT=$(echo "$STATE_JSON" | jq -r '.proof_prs | length')

log "Original PR: $ORIGINAL_REPO#$ORIGINAL_PR"
log "Proof PRs: $PROOF_PRS_COUNT"

# Step 2: Check if state is out of sync
log "Checking sync status..."

SYNC_CHECK=$("$SKILLS_DIR/state-manager.py" sync "$ORIGINAL_PR" 2>&1 | grep -c "Out of sync" || true)

if (( SYNC_CHECK > 0 )); then
    log_warn "State is out of sync with GitHub"
    log "Auto-syncing..."
    "$SKILLS_DIR/state-manager.py" sync "$ORIGINAL_PR" >/dev/null
    STATE_JSON=$(cat "$STATE_FILE")
fi

# Step 3: Get original PR status
log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "ORIGINAL PR STATUS"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ORIGINAL_PR_JSON=$(gh pr view "$ORIGINAL_PR" \
    --repo "$ORIGINAL_REPO" \
    --json state,isDraft,mergeable,statusCheckRollup,reviewDecision,labels,title)

ORIGINAL_STATE=$(echo "$ORIGINAL_PR_JSON" | jq -r '.state')
ORIGINAL_DRAFT=$(echo "$ORIGINAL_PR_JSON" | jq -r '.isDraft')
ORIGINAL_MERGEABLE=$(echo "$ORIGINAL_PR_JSON" | jq -r '.mergeable')
ORIGINAL_TITLE=$(echo "$ORIGINAL_PR_JSON" | jq -r '.title')
ORIGINAL_REVIEW=$(echo "$ORIGINAL_PR_JSON" | jq -r '.reviewDecision // "PENDING"')

echo "PR: $ORIGINAL_REPO#$ORIGINAL_PR"
echo "Title: $ORIGINAL_TITLE"
echo "URL: $ORIGINAL_URL"
echo ""

if [[ "$ORIGINAL_STATE" == "MERGED" ]]; then
    log_success "State: MERGED"
    echo ""
    log "✓ Original PR has merged!"
    log "  You can now run: /proof-pr:convert $ORIGINAL_PR"
    echo ""
else
    echo "State: $ORIGINAL_STATE"

    if [[ "$ORIGINAL_DRAFT" == "true" ]]; then
        log_warn "Draft: YES (must mark as ready for review)"
    fi

    # Check Tide labels
    LABELS=$(echo "$ORIGINAL_PR_JSON" | jq -r '.labels[].name')

    HAS_LGTM=$(echo "$LABELS" | grep -c "^lgtm$" || true)
    HAS_APPROVE=$(echo "$LABELS" | grep -c "^approved$" || true)
    HAS_VERIFIED=$(echo "$LABELS" | grep -c "^verified$" || true)
    HAS_HOLD=$(echo "$LABELS" | grep -cE "^(do-not-merge/hold|hold)$" || true)

    echo ""
    echo "Tide Labels:"

    if (( HAS_LGTM > 0 )); then
        log_success "lgtm"
    else
        log_error "lgtm (missing - need /lgtm from reviewer)"
    fi

    if (( HAS_APPROVE > 0 )); then
        log_success "approved"
    else
        log_error "approved (missing - need /approve from approver)"
    fi

    if (( HAS_VERIFIED > 0 )); then
        log_success "verified"
    else
        log_error "verified (missing - use /verified by <test> or /verified later @user)"
    fi

    if (( HAS_HOLD > 0 )); then
        log_warn "do-not-merge/hold (remove with /hold cancel when ready)"
    fi

    # Check CI status
    echo ""
    echo "CI Status:"

    STATUS_CHECKS=$(echo "$ORIGINAL_PR_JSON" | jq -r '.statusCheckRollup // [] | length')

    if (( STATUS_CHECKS == 0 )); then
        log_warn "No status checks found"
    else
        PASSING=$(echo "$ORIGINAL_PR_JSON" | jq -r '[.statusCheckRollup[] | select(.conclusion == "SUCCESS" or .state == "SUCCESS")] | length')
        FAILING=$(echo "$ORIGINAL_PR_JSON" | jq -r '[.statusCheckRollup[] | select(.conclusion == "FAILURE" or .state == "FAILURE")] | length')
        PENDING=$(echo "$ORIGINAL_PR_JSON" | jq -r '[.statusCheckRollup[] | select(.state == "PENDING" or .state == "IN_PROGRESS")] | length')

        if (( FAILING > 0 )); then
            log_error "$FAILING failing, $PASSING passing, $PENDING pending"
        elif (( PENDING > 0 )); then
            log_warn "$PASSING passing, $PENDING pending"
        else
            log_success "All $PASSING checks passing"
        fi
    fi

    echo ""
    echo "Merge Readiness:"

    READY_TO_MERGE=true

    if [[ "$ORIGINAL_DRAFT" == "true" ]]; then
        log_error "Must mark as ready for review"
        READY_TO_MERGE=false
    fi

    if (( HAS_LGTM == 0 )); then
        log_error "Need /lgtm from reviewer with write access"
        READY_TO_MERGE=false
    fi

    if (( HAS_APPROVE == 0 )); then
        log_error "Need /approve from approver (usually from OWNERS file)"
        READY_TO_MERGE=false
    fi

    if (( HAS_VERIFIED == 0 )); then
        log_error "Need verified label via /verified command"
        echo "    Options:"
        echo "      - /verified by \"<test-name>\" (pre-merge testing - recommended)"
        echo "      - /verified by @<username> (pre-merge verification by person)"
        echo "      - /verified later @<username> (post-merge verification)"
        READY_TO_MERGE=false
    fi

    if (( HAS_HOLD > 0 )); then
        log_warn "Has hold label - use /hold cancel when ready"
        READY_TO_MERGE=false
    fi

    if (( FAILING > 0 )); then
        log_error "Has failing CI checks"
        READY_TO_MERGE=false
    fi

    echo ""

    if $READY_TO_MERGE; then
        log_success "Original PR is ready for Tide auto-merge!"
        echo ""
        log "Once merged, run: /proof-pr:convert $ORIGINAL_PR"
    else
        log_warn "Original PR not yet ready for merge"
        echo ""
        log "Recommendations:"
        if (( HAS_LGTM == 0 )) || (( HAS_APPROVE == 0 )); then
            echo "  1. Request review from team members"
        fi
        if (( HAS_VERIFIED == 0 )); then
            echo "  2. Use /verified by <test> to mark as verified"
        fi
        if (( FAILING > 0 )); then
            echo "  3. Fix failing CI checks"
        fi
        if (( HAS_HOLD > 0 )); then
            echo "  4. Remove hold label when ready: /hold cancel"
        fi
    fi
fi

# Step 4: Show proof PR statuses
echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "PROOF PR STATUS"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PROOF_PRS=$(echo "$STATE_JSON" | jq -c '.proof_prs[]')

if [[ -z "$PROOF_PRS" ]]; then
    log_warn "No proof PRs found"
    exit 0
fi

while IFS= read -r proof_pr; do
    REPO=$(echo "$proof_pr" | jq -r '.repo')
    NUMBER=$(echo "$proof_pr" | jq -r '.number')
    URL=$(echo "$proof_pr" | jq -r '.url')
    CONVERTED=$(echo "$proof_pr" | jq -r '.converted')
    MERGED=$(echo "$proof_pr" | jq -r '.merged')
    PROVING_REPO=$(echo "$proof_pr" | jq -r '.proving_repo')
    PROVING_PR=$(echo "$proof_pr" | jq -r '.proving_pr')

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$REPO#$NUMBER"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "URL: $URL"
    echo "Proving: $PROVING_REPO#$PROVING_PR"

    if [[ "$MERGED" == "true" ]]; then
        log_success "Status: MERGED"
        echo ""
        continue
    fi

    if [[ "$CONVERTED" == "true" ]]; then
        echo "Status: CONVERTED (normal PR)"
    else
        echo "Status: ACTIVE (proof PR)"
    fi

    # Get PR details
    PR_JSON=$(gh pr view "$NUMBER" \
        --repo "$REPO" \
        --json state,isDraft,statusCheckRollup,labels,mergeable 2>/dev/null || echo '{}')

    if [[ "$PR_JSON" == "{}" ]]; then
        log_error "Could not fetch PR details"
        echo ""
        continue
    fi

    PR_STATE=$(echo "$PR_JSON" | jq -r '.state // "UNKNOWN"')
    PR_DRAFT=$(echo "$PR_JSON" | jq -r '.isDraft // false')

    echo ""

    # Check for hold label
    PR_LABELS=$(echo "$PR_JSON" | jq -r '.labels[]?.name // empty')
    PR_HAS_HOLD=$(echo "$PR_LABELS" | grep -cE "^(do-not-merge/hold|hold)$" || true)

    if (( PR_HAS_HOLD > 0 )) && [[ "$CONVERTED" == "false" ]]; then
        log_success "do-not-merge/hold present (expected for proof PR)"
    elif (( PR_HAS_HOLD > 0 )) && [[ "$CONVERTED" == "true" ]]; then
        log_warn "do-not-merge/hold still present (should be removed after conversion)"
    fi

    # Check CI status
    STATUS_CHECKS=$(echo "$PR_JSON" | jq -r '.statusCheckRollup // [] | length')

    if (( STATUS_CHECKS == 0 )); then
        log_warn "No CI checks"
    else
        PASSING=$(echo "$PR_JSON" | jq -r '[.statusCheckRollup[] | select(.conclusion == "SUCCESS" or .state == "SUCCESS")] | length')
        FAILING=$(echo "$PR_JSON" | jq -r '[.statusCheckRollup[] | select(.conclusion == "FAILURE" or .state == "FAILURE")] | length')

        if (( FAILING > 0 )); then
            log_error "CI: $FAILING failing, $PASSING passing"
            echo "  ⮕ May need /proof-pr:push-fix to apply manual fixes"
        else
            log_success "CI: All $PASSING checks passing"
        fi
    fi

    echo ""

done <<< "$PROOF_PRS"

# Step 5: Show recommendations
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "RECOMMENDATIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ "$ORIGINAL_STATE" == "MERGED" ]]; then
    log "✓ Original PR is merged"
    log "⮕ Run: /proof-pr:convert $ORIGINAL_PR"
    echo ""
else
    UNCONVERTED=$(echo "$STATE_JSON" | jq '[.proof_prs[] | select(.converted == false and .merged == false)] | length')

    if (( UNCONVERTED > 0 )); then
        log "✓ $UNCONVERTED active proof PRs"
        log "⮕ Monitor and fix any failing CIs"
        log "⮕ When original PR gets labels and merges, run: /proof-pr:convert $ORIGINAL_PR"
    else
        log "⮕ All proof PRs have been converted or merged"
        log "⮕ You may be done with this workflow"
    fi

    echo ""

    if ! $READY_TO_MERGE; then
        log "⮕ Work on getting original PR ready for merge (see above)"
    fi
fi

echo ""
log "State file: $STATE_FILE"
echo ""
```

## Return Value

- **Format**: Human-readable status report
- **Output**: Multi-section report showing original PR and proof PR statuses

**Exit codes:**
- 0: Success - status displayed
- 1: Error - could not load or recover state

## Examples

1. **Check status with state file present**:
   ```
   /proof-pr:status 2626
   ```
   Shows status of all proof PRs for original PR #2626.

2. **Check status with auto-recovery**:
   ```
   /proof-pr:status 2626 https://github.com/openshift/api/pull/2626
   ```
   If state file missing, recovers from GitHub using the PR URL.

3. **Monitor progress before merge**:
   ```
   /proof-pr:status 2626
   ```
   Shows which labels are missing for Tide auto-merge and current CI status.

## Notes

- **Information-only**: Makes no changes, only displays status
- **Auto-sync**: Automatically syncs with GitHub if state is out of date
- **Merge guidance**: Shows exactly what's needed for Tide to auto-merge
- **Tide requirements**: Checks for lgtm, approved, verified labels and CI status
- **No interaction**: Just displays information and recommendations
