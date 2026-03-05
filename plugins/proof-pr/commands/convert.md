---
description: Convert proof PRs to normal PRs after original merges (cascading)
argument-hint: <original-pr-number>
---

## Name

proof-pr:convert - Convert proof PRs to normal PRs in cascading waves

## Synopsis

```
/proof-pr:convert <original-pr-number>
```

## Description

The `proof-pr:convert` command converts proof PRs to normal PRs after their proving PR merges. This implements **cascading conversion**:

1. **First run** (after original PR merges): Converts direct dependents
2. **Second run** (after direct dependents merge): Converts next layer
3. **Continue** until all PRs converted

**Key Insight:**
When the original PR merges, only its *direct* dependents can be converted. Downstream PRs remain as proof PRs for the newly-converted PRs, creating a cascade.

**Example (api#2626 → client-go#1234 → MCO#5678):**

```
# After api#2626 merges:
/proof-pr:convert 2626
→ Converts client-go#1234 (direct dependent)
→ MCO#5678 remains PROOF, now proves client-go#1234

# After client-go#1234 merges:
/proof-pr:convert 2626
→ Converts MCO#5678 (now direct dependent of merged client-go)
```

**Conversion process:**
- Removes `do-not-merge/hold` label
- Updates title (removes `[PROOF]`)
- Updates PR body (removes proof markers)
- Marks as converted in state
- Re-targets downstream PRs to prove newly-converted PR

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

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

log() { echo -e "${BLUE}[proof-pr:convert]${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }
log_cascade() { echo -e "${MAGENTA}⮕${NC} $*"; }

# Step 1: Load state
log "Loading state for PR #$ORIGINAL_PR..."

if [[ ! -f "$STATE_FILE" ]]; then
    log_error "State file not found: $STATE_FILE"
    exit 1
fi

STATE_JSON=$(cat "$STATE_FILE")
ORIGINAL_REPO=$(echo "$STATE_JSON" | jq -r '.original_repo')
ORIGINAL_URL=$(echo "$STATE_JSON" | jq -r '.original_url')

log "Original PR: $ORIGINAL_REPO#$ORIGINAL_PR"

# Step 2: Determine what has merged
log ""
log "Checking what has merged..."

# Check if original PR is merged
ORIGINAL_STATE=$(gh pr view "$ORIGINAL_PR" \
    --repo "$ORIGINAL_REPO" \
    --json state,mergedAt \
    | jq -r '.state')

ORIGINAL_MERGED=false
if [[ "$ORIGINAL_STATE" == "MERGED" ]]; then
    ORIGINAL_MERGED=true
    log_success "Original PR is MERGED"
fi

# Check which proof PRs are merged or converted
MERGED_PROOF_PRS=()
CONVERTED_PROOF_PRS=()

while IFS= read -r proof_pr; do
    REPO=$(echo "$proof_pr" | jq -r '.repo')
    NUMBER=$(echo "$proof_pr" | jq -r '.number')
    CONVERTED=$(echo "$proof_pr" | jq -r '.converted')
    MERGED=$(echo "$proof_pr" | jq -r '.merged')

    # Check current GitHub state
    GH_STATE=$(gh pr view "$NUMBER" --repo "$REPO" --json state 2>/dev/null | jq -r '.state // "UNKNOWN"')

    if [[ "$GH_STATE" == "MERGED" ]]; then
        MERGED_PROOF_PRS+=("$REPO#$NUMBER")
        log_success "$REPO#$NUMBER is MERGED"
    elif [[ "$CONVERTED" == "true" ]]; then
        CONVERTED_PROOF_PRS+=("$REPO#$NUMBER")
        log_cascade "$REPO#$NUMBER is CONVERTED (normal PR)"
    fi

done < <(echo "$STATE_JSON" | jq -c '.proof_prs[]')

# Step 3: Find what can be converted in THIS iteration
log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "CASCADE ANALYSIS"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Build list of what's merged (original + converted proof PRs that have merged)
MERGED_REPOS=()

if $ORIGINAL_MERGED; then
    MERGED_REPOS+=("$ORIGINAL_REPO")
fi

for merged_pr in "${MERGED_PROOF_PRS[@]}"; do
    merged_repo=$(echo "$merged_pr" | cut -d'#' -f1)
    MERGED_REPOS+=("$merged_repo")
done

log "Merged repositories: ${MERGED_REPOS[*]}"

# Find proof PRs that can be converted (proving a merged repo)
CAN_CONVERT=()

while IFS= read -r proof_pr; do
    REPO=$(echo "$proof_pr" | jq -r '.repo')
    NUMBER=$(echo "$proof_pr" | jq -r '.number')
    PROVING_REPO=$(echo "$proof_pr" | jq -r '.proving_repo')
    CONVERTED=$(echo "$proof_pr" | jq -r '.converted')
    MERGED=$(echo "$proof_pr" | jq -r '.merged')

    # Skip if already converted or merged
    if [[ "$CONVERTED" == "true" ]] || [[ "$MERGED" == "true" ]]; then
        continue
    fi

    # Check if proving_repo is in merged list
    for merged_repo in "${MERGED_REPOS[@]}"; do
        if [[ "$PROVING_REPO" == "$merged_repo" ]]; then
            CAN_CONVERT+=("$REPO#$NUMBER")
            log_cascade "CAN CONVERT: $REPO#$NUMBER (proves merged $PROVING_REPO)"
            break
        fi
    done

done < <(echo "$STATE_JSON" | jq -c '.proof_prs[]')

if (( ${#CAN_CONVERT[@]} == 0 )); then
    log_warn "No proof PRs ready to convert in this iteration"
    echo ""

    # Check if there are unconverted proof PRs
    UNCONVERTED=$(echo "$STATE_JSON" | jq '[.proof_prs[] | select(.converted == false and .merged == false)] | length')

    if (( UNCONVERTED > 0 )); then
        log "There are $UNCONVERTED unconverted proof PRs"
        log ""
        log "They may be waiting for upstream PRs to merge:"

        while IFS= read -r proof_pr; do
            REPO=$(echo "$proof_pr" | jq -r '.repo')
            NUMBER=$(echo "$proof_pr" | jq -r '.number')
            PROVING_REPO=$(echo "$proof_pr" | jq -r '.proving_repo')
            PROVING_PR=$(echo "$proof_pr" | jq -r '.proving_pr')
            CONVERTED=$(echo "$proof_pr" | jq -r '.converted')
            MERGED=$(echo "$proof_pr" | jq -r '.merged')

            if [[ "$CONVERTED" == "false" && "$MERGED" == "false" ]]; then
                echo "  - $REPO#$NUMBER → waiting for $PROVING_REPO#$PROVING_PR to merge"
            fi

        done < <(echo "$STATE_JSON" | jq -c '.proof_prs[]')

        echo ""
        log "Run /proof-pr:convert again after those PRs merge"
    else
        log_success "All proof PRs have been converted or merged!"
    fi

    exit 0
fi

# Step 4: Convert each PR
log ""
log "Converting ${#CAN_CONVERT[@]} proof PR(s)..."

CONVERTED_COUNT=0

for pr_identifier in "${CAN_CONVERT[@]}"; do
    REPO=$(echo "$pr_identifier" | cut -d'#' -f1)
    NUMBER=$(echo "$pr_identifier" | cut -d'#' -f2)

    echo ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Converting: $REPO#$NUMBER"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Get current PR details
    PR_JSON=$(gh pr view "$NUMBER" \
        --repo "$REPO" \
        --json title,body,labels)

    CURRENT_TITLE=$(echo "$PR_JSON" | jq -r '.title')
    CURRENT_BODY=$(echo "$PR_JSON" | jq -r '.body')
    LABELS=$(echo "$PR_JSON" | jq -r '.labels[].name')

    # Step 4a: Remove [PROOF] from title
    NEW_TITLE="${CURRENT_TITLE//\[PROOF\] /}"
    NEW_TITLE="${NEW_TITLE//\[PROOF\]/}"

    log "Updating title..."
    log "  Old: $CURRENT_TITLE"
    log "  New: $NEW_TITLE"

    gh pr edit "$NUMBER" \
        --repo "$REPO" \
        --title "$NEW_TITLE"

    # Step 4b: Update PR body - remove proof markers
    log "Updating PR body..."

    # Remove HTML comment markers
    NEW_BODY=$(echo "$CURRENT_BODY" | sed '/<!-- PROOF-PR:/d; /<!-- PROVING:/d; /<!-- DEPENDS-ON:/d')

    # Remove proof warning section
    NEW_BODY=$(echo "$NEW_BODY" | sed '/^## 🧪 PROOF PR/,/^---$/d')
    NEW_BODY=$(echo "$NEW_BODY" | sed '/^⚠️ \*\*DO NOT MERGE\*\*/,/Generated by \[Claude Code/d')

    # Add conversion notice at top
    CONVERSION_NOTICE="## ✅ Converted from Proof PR

This PR was originally created as a proof PR to test changes from $ORIGINAL_URL.

The original PR has now merged, and this has been converted to a normal PR.

---

"

    NEW_BODY="$CONVERSION_NOTICE$NEW_BODY"

    gh pr edit "$NUMBER" \
        --repo "$REPO" \
        --body "$NEW_BODY"

    # Step 4c: Remove do-not-merge/hold label
    log "Removing do-not-merge/hold label..."

    HAS_HOLD=$(echo "$LABELS" | grep -cE "^(do-not-merge/hold|hold)$" || true)

    if (( HAS_HOLD > 0 )); then
        gh pr edit "$NUMBER" \
            --repo "$REPO" \
            --remove-label "do-not-merge/hold" || {
            log_warn "Could not remove hold label (may not have permissions)"
        }
    fi

    # Step 4d: Add comment explaining conversion
    log "Adding conversion comment..."

    COMMENT="✅ **Converted to normal PR**

This proof PR has been converted to a normal PR because the original changes have merged.

**What this means:**
- The \`do-not-merge/hold\` label has been removed
- This PR will auto-merge when it gets \`lgtm\`, \`approved\`, and \`verified\` labels
- No further action needed if tests pass

**Required for merge:**
- \`/lgtm\` from a reviewer
- \`/approved\` from an approver
- \`/verified by <test>\` or \`/verified later @user\`

---

Converted by [Claude Code proof-pr plugin](https://github.com/openshift-eng/ai-helpers)
"

    gh pr comment "$NUMBER" \
        --repo "$REPO" \
        --body "$COMMENT"

    log_success "✓ Converted $REPO#$NUMBER"

    # Step 4e: Update state - mark as converted
    STATE_JSON=$(echo "$STATE_JSON" | jq \
        "(.proof_prs[] | select(.repo == \"$REPO\" and .number == $NUMBER) | .converted) = true")

    ((CONVERTED_COUNT++))

done

# Step 5: Re-target downstream proof PRs
log ""
log "Re-targeting downstream proof PRs..."

# For each newly converted PR, find proof PRs that depended on it
for pr_identifier in "${CAN_CONVERT[@]}"; do
    CONVERTED_REPO=$(echo "$pr_identifier" | cut -d'#' -f1)
    CONVERTED_NUMBER=$(echo "$pr_identifier" | cut -d'#' -f2)

    # Find proof PRs that have depends_on_repo == CONVERTED_REPO
    # These should now prove the converted PR instead of the original

    while IFS= read -r proof_pr; do
        REPO=$(echo "$proof_pr" | jq -r '.repo')
        NUMBER=$(echo "$proof_pr" | jq -r '.number')
        DEPENDS_ON=$(echo "$proof_pr" | jq -r '.depends_on_repo')
        CURRENT_PROVING=$(echo "$proof_pr" | jq -r '.proving_repo')
        CONVERTED=$(echo "$proof_pr" | jq -r '.converted')

        # Skip if already converted
        if [[ "$CONVERTED" == "true" ]]; then
            continue
        fi

        # If this PR depends on the newly converted repo
        if [[ "$DEPENDS_ON" == "$CONVERTED_REPO" ]]; then
            # Re-target to prove the converted PR
            log_cascade "Re-targeting $REPO#$NUMBER → proves $CONVERTED_REPO#$CONVERTED_NUMBER"

            STATE_JSON=$(echo "$STATE_JSON" | jq \
                "(.proof_prs[] | select(.repo == \"$REPO\" and .number == $NUMBER) | .proving_repo) = \"$CONVERTED_REPO\" | \
                 (.proof_prs[] | select(.repo == \"$REPO\" and .number == $NUMBER) | .proving_pr) = $CONVERTED_NUMBER")

            # Update PR body with new proving target
            CURRENT_BODY=$(gh pr view "$NUMBER" --repo "$REPO" --json body -q '.body')

            # Update HTML comment
            UPDATED_BODY=$(echo "$CURRENT_BODY" | sed "s|<!-- PROVING: [^#]*#[0-9]* -->|<!-- PROVING: $CONVERTED_REPO#$CONVERTED_NUMBER -->|")

            # Update text description
            CONVERTED_PR_URL="https://github.com/$CONVERTED_REPO/pull/$CONVERTED_NUMBER"
            UPDATED_BODY=$(echo "$UPDATED_BODY" | sed "s|This is a proof PR to test changes from \[.*\](.*)|This is a proof PR to test changes from [$CONVERTED_REPO#$CONVERTED_NUMBER]($CONVERTED_PR_URL)|")

            gh pr edit "$NUMBER" \
                --repo "$REPO" \
                --body "$UPDATED_BODY" || {
                log_warn "Could not update PR body for $REPO#$NUMBER"
            }

            # Add comment explaining re-target
            RE_TARGET_COMMENT="♻️ **Re-targeted to prove $CONVERTED_REPO#$CONVERTED_NUMBER**

This proof PR now tests changes from the converted PR [$CONVERTED_REPO#$CONVERTED_NUMBER]($CONVERTED_PR_URL) instead of the original.

When $CONVERTED_REPO#$CONVERTED_NUMBER merges, this PR will be eligible for conversion.

---

Updated by [Claude Code proof-pr plugin](https://github.com/openshift-eng/ai-helpers)
"

            gh pr comment "$NUMBER" \
                --repo "$REPO" \
                --body "$RE_TARGET_COMMENT" || true
        fi

    done < <(echo "$STATE_JSON" | jq -c '.proof_prs[]')

done

# Step 6: Save updated state
log ""
log "Saving state..."

STATE_JSON=$(echo "$STATE_JSON" | jq ".last_updated = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"")
echo "$STATE_JSON" | jq '.' > "$STATE_FILE"

# Step 7: Show summary
echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "CONVERSION SUMMARY"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_success "Converted $CONVERTED_COUNT proof PR(s) to normal PRs"

if (( CONVERTED_COUNT > 0 )); then
    echo ""
    log "Converted PRs:"
    for pr in "${CAN_CONVERT[@]}"; do
        REPO=$(echo "$pr" | cut -d'#' -f1)
        NUMBER=$(echo "$pr" | cut -d'#' -f2)
        URL="https://github.com/$REPO/pull/$NUMBER"
        echo "  ✓ $REPO#$NUMBER: $URL"
    done
fi

echo ""

# Check if more work remains
REMAINING_UNCONVERTED=$(echo "$STATE_JSON" | jq '[.proof_prs[] | select(.converted == false and .merged == false)] | length')

if (( REMAINING_UNCONVERTED > 0 )); then
    log_cascade "$REMAINING_UNCONVERTED proof PR(s) remain unconverted"
    echo ""
    log "Next steps:"
    log "  1. Wait for newly converted PRs to get labels and merge"
    log "  2. Run /proof-pr:convert $ORIGINAL_PR again to convert next layer"
    log ""
    log "Cascade workflow:"

    while IFS= read -r proof_pr; do
        REPO=$(echo "$proof_pr" | jq -r '.repo')
        NUMBER=$(echo "$proof_pr" | jq -r '.number')
        PROVING_REPO=$(echo "$proof_pr" | jq -r '.proving_repo')
        PROVING_PR=$(echo "$proof_pr" | jq -r '.proving_pr')
        CONVERTED=$(echo "$proof_pr" | jq -r '.converted')
        MERGED=$(echo "$proof_pr" | jq -r '.merged')

        if [[ "$CONVERTED" == "false" && "$MERGED" == "false" ]]; then
            echo "  ⮕ $REPO#$NUMBER waiting for $PROVING_REPO#$PROVING_PR"
        fi

    done < <(echo "$STATE_JSON" | jq -c '.proof_prs[]')

else
    log_success "All proof PRs have been converted or merged!"
    echo ""
    log "Workflow complete for $ORIGINAL_URL"
fi

echo ""
```

## Return Value

- **Format**: Converts proof PRs and updates state
- **Output**: Summary of converted PRs and remaining work

**Exit codes:**
- 0: Success - conversions complete for this iteration

## Examples

1. **First conversion after original merges**:
   ```
   /proof-pr:convert 2626
   ```
   Converts client-go#1234, re-targets MCO#5678 to prove client-go.

2. **Second conversion after first layer merges**:
   ```
   /proof-pr:convert 2626
   ```
   Converts MCO#5678 (now proving merged client-go#1234).

3. **Check if more conversions needed**:
   ```
   /proof-pr:convert 2626
   ```
   Shows "No proof PRs ready to convert" if waiting for upstream merges.

## Notes

- **Cascading**: Only converts PRs whose proving_repo has merged
- **Iterative**: Run after each layer merges to convert next layer
- **Re-targeting**: Downstream PRs automatically re-targeted to newly converted PRs
- **No holds**: Removes do-not-merge/hold label from converted PRs
- **Tide-ready**: Converted PRs will auto-merge when they get required labels
- **State tracking**: Updates proving_repo/proving_pr for cascading relationships
