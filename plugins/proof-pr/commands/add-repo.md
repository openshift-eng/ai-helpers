---
description: Add additional repositories to existing proof PR workflow
argument-hint: <original-pr-number> <repo>
---

## Name

proof-pr:add-repo - Add more repositories to an existing proof PR session

## Synopsis

```
/proof-pr:add-repo <original-pr-number> <repo> [additional-repos...]
```

## Description

The `proof-pr:add-repo` command adds new proof PRs to an existing workflow. This is useful when:
- You discover another repository needs testing
- You want to expand test coverage
- A new dependency was added

The command will create proof PRs in the specified repositories using the same pseudo-version as existing proof PRs.

**Key Features:**
- **Reuses existing pseudo-version**: Uses same commit as other proof PRs
- **Auto-detects dependencies**: Checks if repo actually depends on changes
- **Preserves state**: Updates existing state file with new PRs
- **Handles full workflow**: Fork, clone, update, codegen, compile, create PR

## Arguments

- `$1` (required): Original PR number (e.g., `2626`)
- `$2+` (required): Repository names to add (e.g., `openshift/oc`)

## Implementation

```bash
#!/bin/bash
set -euo pipefail

# Configuration
ORIGINAL_PR="$1"
shift
NEW_REPOS=("$@")

if (( ${#NEW_REPOS[@]} == 0 )); then
    echo "Error: No repositories specified"
    echo "Usage: /proof-pr:add-repo <original-pr-number> <repo> [repo...]"
    exit 1
fi

SKILLS_DIR="plugins/proof-pr/skills/proof-pr-workflow"
STATE_FILE="$HOME/.work/proof-pr/$ORIGINAL_PR/state.json"
WORK_DIR="$HOME/.work/proof-pr/$ORIGINAL_PR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[proof-pr:add-repo]${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }

# Step 1: Load state
log "Loading state for PR #$ORIGINAL_PR..."

if [[ ! -f "$STATE_FILE" ]]; then
    log_error "State file not found: $STATE_FILE"
    log "No existing proof PR workflow found for PR #$ORIGINAL_PR"
    log "Use /proof-pr:create instead"
    exit 1
fi

STATE_JSON=$(cat "$STATE_FILE")
ORIGINAL_REPO=$(echo "$STATE_JSON" | jq -r '.original_repo')
ORIGINAL_URL=$(echo "$STATE_JSON" | jq -r '.original_url')
ORIGINAL_BRANCH=$(echo "$STATE_JSON" | jq -r '.original_branch')

log "Original PR: $ORIGINAL_REPO#$ORIGINAL_PR"
log "Adding repositories: ${NEW_REPOS[*]}"

# Step 2: Get pseudo-version from existing proof PRs
log "Getting pseudo-version from existing proof PRs..."

FIRST_PROOF_PR=$(echo "$STATE_JSON" | jq -r '.proof_prs[0]')

if [[ "$FIRST_PROOF_PR" == "null" ]] || [[ -z "$FIRST_PROOF_PR" ]]; then
    log_error "No existing proof PRs found in state"
    log "Use /proof-pr:create instead"
    exit 1
fi

# Get pseudo-version by checking go.mod in first proof PR repo
FIRST_REPO=$(echo "$FIRST_PROOF_PR" | jq -r '.repo')
FIRST_REPO_DIR="$WORK_DIR/$FIRST_REPO"

if [[ ! -d "$FIRST_REPO_DIR" ]]; then
    log_error "First proof PR repository not found: $FIRST_REPO_DIR"
    exit 1
fi

cd "$FIRST_REPO_DIR"

ORIGINAL_MODULE="github.com/$ORIGINAL_REPO"
PSEUDO_VERSION=$(grep "$ORIGINAL_MODULE" go.mod | awk '{print $2}')

if [[ -z "$PSEUDO_VERSION" ]]; then
    log_error "Could not determine pseudo-version from existing proof PRs"
    exit 1
fi

log "Using pseudo-version: $PSEUDO_VERSION"

# Extract commit for comments
COMMIT_SHA=$(echo "$PSEUDO_VERSION" | grep -oE '[a-f0-9]{12}$')

# Step 3: Check which repos already have proof PRs
EXISTING_REPOS=$(echo "$STATE_JSON" | jq -r '.proof_prs[].repo')

for repo in "${NEW_REPOS[@]}"; do
    if echo "$EXISTING_REPOS" | grep -q "^$repo$"; then
        log_warn "Proof PR already exists for $repo, skipping"
        NEW_REPOS=("${NEW_REPOS[@]/$repo}")
    fi
done

if (( ${#NEW_REPOS[@]} == 0 )); then
    log_warn "All specified repositories already have proof PRs"
    exit 0
fi

# Function to create proof PR (reused from create.md)
create_proof_pr() {
    local repo="$1"
    local depends_on_repo="$ORIGINAL_REPO"  # New repos depend on original

    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Creating proof PR in: $repo"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local repo_work_dir="$WORK_DIR/$repo"

    # Check if repo actually depends on original
    log "Checking if $repo depends on $ORIGINAL_MODULE..."

    # Clone repo temporarily to check
    local temp_check_dir=$(mktemp -d)
    gh repo clone "$repo" "$temp_check_dir" >/dev/null 2>&1 || {
        log_error "Failed to clone $repo"
        rm -rf "$temp_check_dir"
        return 1
    }

    cd "$temp_check_dir"

    if ! grep -q "$ORIGINAL_MODULE" go.mod 2>/dev/null; then
        log_warn "$repo does not depend on $ORIGINAL_MODULE"
        log_warn "Creating proof PR anyway (you may need to add the dependency)"
    fi

    cd - >/dev/null
    rm -rf "$temp_check_dir"

    # Fork repository if needed
    log "Checking fork status..."

    local my_username=$(gh api user -q .login)
    local fork_check=$(gh repo view "$repo" --json owner -q '.owner.login' 2>/dev/null || echo "")

    if [[ "$fork_check" != "$my_username" ]]; then
        log "Forking $repo..."
        gh repo fork "$repo" --clone=false || log_warn "Fork may already exist"
        local fork_repo="$my_username/$(basename "$repo")"
    else
        local fork_repo="$repo"
    fi

    log "Using fork: $fork_repo"

    # Clone forked repository
    log "Cloning fork..."
    gh repo clone "$fork_repo" "$repo_work_dir"
    cd "$repo_work_dir"

    if [[ "$fork_repo" != "$repo" ]]; then
        git remote add upstream "https://github.com/$repo.git" || true
        git fetch upstream
    fi

    # Create proof branch
    local proof_branch="proof-pr-${ORIGINAL_REPO//\//-}-${ORIGINAL_PR}"

    log "Creating branch: $proof_branch"

    git checkout -B "$proof_branch" origin/master || \
        git checkout -B "$proof_branch" origin/main || \
        git checkout -B "$proof_branch" HEAD

    # Update go.mod
    log "Updating go.mod: $ORIGINAL_MODULE -> $PSEUDO_VERSION"

    go get "$ORIGINAL_MODULE@$PSEUDO_VERSION" || {
        log_warn "Dependency may not exist yet, adding manually"
        # Try to add it manually if it doesn't exist
        echo "require $ORIGINAL_MODULE $PSEUDO_VERSION" >> go.mod
    }

    go mod tidy

    # Run code generation if needed
    CODEGEN_JSON=$("$SKILLS_DIR/detect-codegen.py" . --json 2>/dev/null)
    NEEDS_CODEGEN=$(echo "$CODEGEN_JSON" | jq -r '.needs_codegen')

    if [[ "$NEEDS_CODEGEN" == "true" ]]; then
        CODEGEN_CMD=$(echo "$CODEGEN_JSON" | jq -r '.command')
        if [[ "$CODEGEN_CMD" != "null" ]]; then
            log "Running codegen: $CODEGEN_CMD"
            eval "$CODEGEN_CMD" || log_warn "Codegen failed"
        fi
    fi

    # Test compilation
    if "$SKILLS_DIR/compile-test.sh" . >/dev/null 2>&1; then
        compilation_status="success"
    else
        # Try auto-fix
        "$SKILLS_DIR/attempt-fix.py" . >/dev/null 2>&1 && \
            compilation_status="fixed" || \
            compilation_status="failed"
    fi

    # Commit
    git add -A

    local commit_msg="[PROOF] Add $ORIGINAL_MODULE for $ORIGINAL_REPO#$ORIGINAL_PR

Testing changes from $ORIGINAL_URL
Pseudo-version: $PSEUDO_VERSION
Compilation: $compilation_status

🧪 This is a PROOF PR - DO NOT MERGE
"

    git commit -m "$commit_msg"
    git push -f origin "$proof_branch"

    # Create PR
    local pr_body="<!-- PROOF-PR: $ORIGINAL_URL -->
<!-- PROVING: $ORIGINAL_REPO#$ORIGINAL_PR -->
<!-- DEPENDS-ON: $ORIGINAL_REPO -->

## 🧪 PROOF PR

Testing changes from [$ORIGINAL_REPO#$ORIGINAL_PR]($ORIGINAL_URL).

### Changes

- Added \`$ORIGINAL_MODULE@$PSEUDO_VERSION\`

### Status

Compilation: $compilation_status

---

**⚠️ DO NOT MERGE**

Added to proof workflow for $ORIGINAL_URL

Generated by [Claude Code proof-pr plugin](https://github.com/openshift-eng/ai-helpers)
"

    local new_pr_url=$(gh pr create \
        --repo "$repo" \
        --title "[PROOF] Add $ORIGINAL_MODULE for #$ORIGINAL_PR" \
        --body "$pr_body" \
        --base master \
        --head "$my_username:$proof_branch" 2>&1 || \
        gh pr create \
        --repo "$repo" \
        --title "[PROOF] Add $ORIGINAL_MODULE for #$ORIGINAL_PR" \
        --body "$pr_body" \
        --base main \
        --head "$my_username:$proof_branch" 2>&1 || echo "FAILED")

    if [[ "$new_pr_url" == "FAILED" ]]; then
        log_error "Failed to create PR"
        return 1
    fi

    local new_pr_number=$(echo "$new_pr_url" | grep -oE '[0-9]+$')

    log_success "Created: $new_pr_url"

    # Add hold label
    gh pr edit "$new_pr_number" --repo "$repo" --add-label "do-not-merge/hold" 2>/dev/null || true

    # Update state
    local new_proof_pr=$(cat <<EOF
{
  "repo": "$repo",
  "number": $new_pr_number,
  "url": "$new_pr_url",
  "branch": "$proof_branch",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "proving_repo": "$ORIGINAL_REPO",
  "proving_pr": $ORIGINAL_PR,
  "depends_on_repo": "$ORIGINAL_REPO",
  "converted": false,
  "merged": false
}
EOF
)

    local temp_state=$(mktemp)
    jq ".proof_prs += [$new_proof_pr] | .last_updated = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$STATE_FILE" > "$temp_state"
    mv "$temp_state" "$STATE_FILE"

    return 0
}

# Step 4: Create proof PRs for new repos
for repo in "${NEW_REPOS[@]}"; do
    [[ -z "$repo" ]] && continue
    create_proof_pr "$repo" || log_error "Failed to add $repo"
done

# Step 5: Show summary
log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "SUMMARY"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""
log "Added repositories to proof workflow:"

jq -r '.proof_prs[] | select(.created_at > (now - 300 | todate)) | "  - \(.repo)#\(.number): \(.url)"' "$STATE_FILE"

log ""
log "Check status: /proof-pr:status $ORIGINAL_PR"
```

## Return Value

- **Format**: Creates new proof PRs and updates state
- **Output**: List of created PRs

**Exit codes:**
- 0: Success - all repositories added
- 1: Error - no existing workflow or failed to add repos

## Examples

1. **Add single repository**:
   ```
   /proof-pr:add-repo 2626 openshift/oc
   ```
   Adds oc to existing proof workflow for api#2626.

2. **Add multiple repositories**:
   ```
   /proof-pr:add-repo 2626 openshift/console openshift/oc
   ```
   Adds both console and oc to the workflow.

## Notes

- **Requires existing workflow**: Must have created proof PRs with `/proof-pr:create` first
- **Same pseudo-version**: Uses same commit as existing proof PRs
- **Dependency check**: Warns if repository doesn't depend on original module
- **State update**: Adds new PRs to existing state file
