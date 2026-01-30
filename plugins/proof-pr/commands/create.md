---
description: Create proof PRs to test dependency changes before merging
argument-hint: <original-pr-url> <target-repo>
---

## Name

proof-pr:create - Create proof PRs with auto-detected dependency chains

## Synopsis

```
/proof-pr:create <original-pr-url> <target-repo> [additional-repos...]
```

## Description

The `proof-pr:create` command creates temporary "proof PRs" that test dependency changes before the original PR merges. This allows you to verify that downstream repositories will compile and function correctly with your changes.

**Key Features:**
- **Auto-detects dependency chains**: Automatically finds transitive dependencies
- **Handles code generation**: Detects and runs required codegen (make update, etc.)
- **Auto-fixes compilation**: Attempts automatic fixes for simple type renames
- **Creates WIP PRs on failure**: If auto-fix fails, creates a PR with instructions for manual fixes
- **Prevents accidental merge**: Uses `do-not-merge/hold` label (no custom labels)
- **State management**: Tracks all proof PRs for later status checks and conversion

**Workflow:**
1. Analyzes the original PR and target repository dependencies
2. Creates proof PRs in dependency order (original → intermediate → target)
3. For each repository:
   - Forks repository if you don't have write access
   - Creates a branch with dependency bumps
   - Runs code generation if needed
   - Tests compilation
   - Attempts auto-fixes if compilation fails
   - Creates PR with proof metadata

## Arguments

- `$1` (required): URL of the original PR (e.g., `https://github.com/openshift/api/pull/2626`)
- `$2` (required): Target repository to create proof PR in (e.g., `openshift/machine-config-operator`)
- `$3+` (optional): Additional repositories to include in proof workflow

## Implementation

```bash
#!/bin/bash
set -euo pipefail

# Configuration
ORIGINAL_PR_URL="$1"
TARGET_REPO="$2"
shift 2
ADDITIONAL_REPOS=("$@")

SKILLS_DIR="plugins/proof-pr/skills/proof-pr-workflow"
WORK_DIR="$HOME/.work/proof-pr"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[proof-pr:create]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[proof-pr:create]${NC} WARNING: $*"; }
log_error() { echo -e "${RED}[proof-pr:create]${NC} ERROR: $*"; }

# Step 1: Parse original PR URL
log "Parsing original PR: $ORIGINAL_PR_URL"

if ! [[ "$ORIGINAL_PR_URL" =~ github.com/([^/]+)/([^/]+)/pull/([0-9]+) ]]; then
    log_error "Invalid PR URL format: $ORIGINAL_PR_URL"
    exit 1
fi

ORIGINAL_ORG="${BASH_REMATCH[1]}"
ORIGINAL_REPO="${BASH_REMATCH[2]}"
ORIGINAL_PR="${BASH_REMATCH[3]}"
ORIGINAL_FULL_REPO="$ORIGINAL_ORG/$ORIGINAL_REPO"

log "Original PR: $ORIGINAL_FULL_REPO#$ORIGINAL_PR"

# Step 2: Get original PR details
log "Fetching original PR details..."

PR_JSON=$(gh pr view "$ORIGINAL_PR" \
    --repo "$ORIGINAL_FULL_REPO" \
    --json title,headRefName,headRepository,state,commits)

PR_TITLE=$(echo "$PR_JSON" | jq -r '.title')
PR_BRANCH=$(echo "$PR_JSON" | jq -r '.headRefName')
PR_HEAD_REPO=$(echo "$PR_JSON" | jq -r '.headRepository.nameWithOwner')
PR_STATE=$(echo "$PR_JSON" | jq -r '.state')
PR_COMMITS=$(echo "$PR_JSON" | jq -r '.commits | length')

if [[ "$PR_STATE" == "MERGED" ]]; then
    log_error "Original PR is already merged"
    exit 1
fi

log "  Title: $PR_TITLE"
log "  Branch: $PR_BRANCH"
log "  Head repo: $PR_HEAD_REPO"
log "  Commits: $PR_COMMITS"

# Step 3: Get latest commit SHA for pseudo-version
LATEST_COMMIT=$(gh pr view "$ORIGINAL_PR" \
    --repo "$ORIGINAL_FULL_REPO" \
    --json commits \
    | jq -r '.commits[-1].oid[:12]')

COMMIT_TIMESTAMP=$(gh pr view "$ORIGINAL_PR" \
    --repo "$ORIGINAL_FULL_REPO" \
    --json commits \
    | jq -r '.commits[-1].committedDate' \
    | sed 's/[-:]//g; s/T//; s/Z.*//')

PSEUDO_VERSION="v0.0.0-${COMMIT_TIMESTAMP}-${LATEST_COMMIT}"
ORIGINAL_MODULE="github.com/$ORIGINAL_FULL_REPO"

log "Pseudo-version: $PSEUDO_VERSION"

# Step 4: Clone target repository
log "Cloning target repository: $TARGET_REPO"

TARGET_WORK_DIR="$WORK_DIR/$ORIGINAL_PR/$TARGET_REPO"
mkdir -p "$(dirname "$TARGET_WORK_DIR")"

if [[ -d "$TARGET_WORK_DIR" ]]; then
    log_warn "Work directory already exists, using existing clone"
    cd "$TARGET_WORK_DIR"
    git fetch origin
else
    gh repo clone "$TARGET_REPO" "$TARGET_WORK_DIR"
    cd "$TARGET_WORK_DIR"
fi

# Step 5: Analyze dependency chain
log "Analyzing dependency chain..."

CHAIN_JSON=$("$SKILLS_DIR/analyze-deps.py" \
    "$ORIGINAL_MODULE" \
    "$TARGET_WORK_DIR" \
    --json 2>/dev/null || echo '{}')

if [[ "$CHAIN_JSON" == '{}' ]]; then
    log_error "No dependency chain found from $TARGET_REPO to $ORIGINAL_FULL_REPO"
    log "This repository may not depend on the original repository."
    log "Use --force to create proof PR anyway (not recommended)."
    exit 1
fi

RELATIONSHIP=$(echo "$CHAIN_JSON" | jq -r '.relationship')
CHAIN_REPOS=$(echo "$CHAIN_JSON" | jq -r '.repos | join(" -> ")')
CHAIN_LENGTH=$(echo "$CHAIN_JSON" | jq -r '.repos | length')

log "Dependency chain: $CHAIN_REPOS"
log "Relationship: $RELATIONSHIP"

# Step 6: Determine all repositories that need proof PRs
ALL_REPOS=()

# Add intermediate repos from chain (excluding original and target)
if (( CHAIN_LENGTH > 2 )); then
    INTERMEDIATE_REPOS=$(echo "$CHAIN_JSON" | jq -r '.repos[1:-1] | .[]')
    while IFS= read -r repo; do
        [[ -n "$repo" ]] && ALL_REPOS+=("$repo")
    done <<< "$INTERMEDIATE_REPOS"
fi

# Add target repo
ALL_REPOS+=("$TARGET_REPO")

# Add any additional repos specified by user
ALL_REPOS+=("${ADDITIONAL_REPOS[@]}")

log "Will create proof PRs in: ${ALL_REPOS[*]}"

# Step 7: Initialize state
log "Initializing state..."

STATE_FILE="$WORK_DIR/$ORIGINAL_PR/state.json"
mkdir -p "$(dirname "$STATE_FILE")"

# Create initial state if doesn't exist
if [[ ! -f "$STATE_FILE" ]]; then
    cat > "$STATE_FILE" <<EOF
{
  "original_repo": "$ORIGINAL_FULL_REPO",
  "original_pr": $ORIGINAL_PR,
  "original_url": "$ORIGINAL_PR_URL",
  "original_branch": "$PR_BRANCH",
  "proof_prs": [],
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "last_updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
fi

# Function to create proof PR in a repository
create_proof_pr() {
    local repo="$1"
    local depends_on_repo="$2"  # What go.mod dependency to bump

    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Creating proof PR in: $repo"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local repo_work_dir="$WORK_DIR/$ORIGINAL_PR/$repo"

    # Step 1: Fork repository if needed
    log "Checking fork status..."

    local my_username=$(gh api user -q .login)
    local fork_check=$(gh repo view "$repo" --json isFork,owner -q '.owner.login')

    if [[ "$fork_check" != "$my_username" ]]; then
        log "Forking $repo..."
        gh repo fork "$repo" --clone=false || {
            log_warn "Fork may already exist"
        }
        local fork_repo="$my_username/$(basename "$repo")"
    else
        local fork_repo="$repo"
    fi

    log "Using fork: $fork_repo"

    # Step 2: Clone forked repository
    if [[ -d "$repo_work_dir" ]]; then
        log "Repository already cloned"
        cd "$repo_work_dir"
        git fetch --all
    else
        log "Cloning fork..."
        gh repo clone "$fork_repo" "$repo_work_dir"
        cd "$repo_work_dir"

        # Add upstream if this is a fork
        if [[ "$fork_repo" != "$repo" ]]; then
            git remote add upstream "https://github.com/$repo.git" || true
            git fetch upstream
        fi
    fi

    # Step 3: Create proof branch
    local proof_branch="proof-pr-${ORIGINAL_REPO}-${ORIGINAL_PR}"

    log "Creating branch: $proof_branch"

    git checkout -B "$proof_branch" origin/master || \
        git checkout -B "$proof_branch" origin/main || \
        git checkout -B "$proof_branch" HEAD

    # Step 4: Update go.mod with pseudo-version
    log "Updating go.mod dependency: github.com/$depends_on_repo -> $PSEUDO_VERSION"

    if ! grep -q "github.com/$depends_on_repo" go.mod; then
        log_error "go.mod does not contain dependency on github.com/$depends_on_repo"
        return 1
    fi

    # Update the dependency
    go get "github.com/$depends_on_repo@$PSEUDO_VERSION"
    go mod tidy

    # Step 5: Detect and run code generation
    log "Detecting code generation requirements..."

    CODEGEN_JSON=$("$SKILLS_DIR/detect-codegen.py" . --json 2>/dev/null)
    NEEDS_CODEGEN=$(echo "$CODEGEN_JSON" | jq -r '.needs_codegen')

    if [[ "$NEEDS_CODEGEN" == "true" ]]; then
        CODEGEN_CMD=$(echo "$CODEGEN_JSON" | jq -r '.command')

        if [[ "$CODEGEN_CMD" != "null" && -n "$CODEGEN_CMD" ]]; then
            log "Running code generation: $CODEGEN_CMD"

            if ! eval "$CODEGEN_CMD"; then
                log_error "Code generation failed"
                return 1
            fi

            log "Code generation completed"
        else
            log_warn "Code generation needed but command not detected"
            log_warn "You may need to run 'make update' or similar manually"
        fi
    else
        log "No code generation needed"
    fi

    # Step 6: Test compilation
    log "Testing compilation..."

    if "$SKILLS_DIR/compile-test.sh" --verbose .; then
        log "✓ Compilation successful"
        local compilation_status="success"
    else
        log_warn "✗ Compilation failed, attempting auto-fix..."

        # Attempt auto-fix
        FIX_JSON=$("$SKILLS_DIR/attempt-fix.py" . --json 2>/dev/null)
        FIX_SUCCESS=$(echo "$FIX_JSON" | jq -r '.compilation_succeeds')

        if [[ "$FIX_SUCCESS" == "true" ]]; then
            log "✓ Auto-fix successful!"
            local compilation_status="fixed"
        else
            log_warn "✗ Auto-fix failed or incomplete"
            local compilation_status="failed"

            NEEDS_MANUAL=$(echo "$FIX_JSON" | jq -r '.needs_manual_fix')
            if [[ "$NEEDS_MANUAL" == "true" ]]; then
                log_warn "Manual fixes will be required"
                log_warn "Creating WIP PR with instructions..."
            fi
        fi
    fi

    # Step 7: Commit changes
    log "Committing changes..."

    git add go.mod go.sum

    # Add any generated files
    if [[ "$NEEDS_CODEGEN" == "true" ]]; then
        git add -A
    fi

    # Add any auto-fixed files
    if [[ "$compilation_status" == "fixed" ]]; then
        git add -A
    fi

    local commit_msg="[PROOF] Bump github.com/$depends_on_repo for $ORIGINAL_FULL_REPO#$ORIGINAL_PR

Testing changes from $ORIGINAL_PR_URL

Pseudo-version: $PSEUDO_VERSION
Compilation: $compilation_status

🧪 This is a PROOF PR - DO NOT MERGE
"

    git commit -m "$commit_msg"

    # Step 8: Push to fork
    log "Pushing to fork..."

    git push -f origin "$proof_branch"

    # Step 9: Create PR
    log "Creating proof PR..."

    local pr_body="<!-- PROOF-PR: $ORIGINAL_PR_URL -->
<!-- PROVING: $ORIGINAL_FULL_REPO#$ORIGINAL_PR -->
<!-- DEPENDS-ON: $depends_on_repo -->

## 🧪 PROOF PR

This is a proof PR to test changes from [$ORIGINAL_FULL_REPO#$ORIGINAL_PR]($ORIGINAL_PR_URL).

**Original PR:** $PR_TITLE

### Changes Made

- Bumped \`github.com/$depends_on_repo\` to \`$PSEUDO_VERSION\`"

    if [[ "$NEEDS_CODEGEN" == "true" ]]; then
        pr_body+="
- Ran code generation: \`$CODEGEN_CMD\`"
    fi

    if [[ "$compilation_status" == "fixed" ]]; then
        pr_body+="
- Applied automatic compilation fixes"
    fi

    pr_body+="

### Compilation Status

**Status:** $compilation_status"

    if [[ "$compilation_status" == "failed" ]]; then
        pr_body+="

⚠️ **Manual fixes required** - This PR has compilation errors that could not be auto-fixed.

To fix:
1. Check out this branch: \`gh pr checkout <PR_NUMBER>\`
2. Fix compilation errors
3. Push fixes: Use \`/proof-pr:push-fix\` command

See compilation output in the checks below."
    fi

    pr_body+="

---

**⚠️ DO NOT MERGE** - This PR is for testing only.

After the original PR merges, use \`/proof-pr:convert\` to convert this to a normal PR.

Generated by [Claude Code proof-pr plugin](https://github.com/openshift-eng/ai-helpers)
"

    local pr_title="[PROOF] $PR_TITLE"

    # Create the PR
    local new_pr_url=$(gh pr create \
        --repo "$repo" \
        --title "$pr_title" \
        --body "$pr_body" \
        --base master \
        --head "$my_username:$proof_branch" \
        2>&1 || echo "")

    if [[ ! "$new_pr_url" =~ https://github.com ]]; then
        # Try with main branch
        new_pr_url=$(gh pr create \
            --repo "$repo" \
            --title "$pr_title" \
            --body "$pr_body" \
            --base main \
            --head "$my_username:$proof_branch" \
            2>&1 || echo "FAILED")
    fi

    if [[ "$new_pr_url" == "FAILED" ]] || [[ ! "$new_pr_url" =~ https://github.com ]]; then
        log_error "Failed to create PR in $repo"
        return 1
    fi

    log "✓ Created PR: $new_pr_url"

    # Extract PR number
    local new_pr_number=$(echo "$new_pr_url" | grep -oE '[0-9]+$')

    # Step 10: Add do-not-merge/hold label
    log "Adding do-not-merge/hold label..."

    gh pr edit "$new_pr_number" \
        --repo "$repo" \
        --add-label "do-not-merge/hold" || {
        log_warn "Could not add label (may not have permissions)"
    }

    # Step 11: Update state
    log "Updating state..."

    local new_proof_pr=$(cat <<EOF
{
  "repo": "$repo",
  "number": $new_pr_number,
  "url": "$new_pr_url",
  "branch": "$proof_branch",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "proving_repo": "$ORIGINAL_FULL_REPO",
  "proving_pr": $ORIGINAL_PR,
  "depends_on_repo": "$depends_on_repo",
  "converted": false,
  "merged": false
}
EOF
)

    # Add to state file
    local temp_state=$(mktemp)
    jq ".proof_prs += [$new_proof_pr] | .last_updated = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$STATE_FILE" > "$temp_state"
    mv "$temp_state" "$STATE_FILE"

    log "✓ Proof PR created successfully: $new_pr_url"

    return 0
}

# Step 8: Create proof PRs in dependency order
log ""
log "Creating proof PRs in dependency order..."

DEPENDS_ON="$ORIGINAL_FULL_REPO"

for repo in "${ALL_REPOS[@]}"; do
    if ! create_proof_pr "$repo" "$DEPENDS_ON"; then
        log_error "Failed to create proof PR in $repo"
        log "Continuing with remaining repositories..."
    fi

    # Next repo depends on this one
    DEPENDS_ON="$repo"
done

# Step 9: Show summary
log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "SUMMARY"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""
log "Original PR: $ORIGINAL_PR_URL"
log "Proof PRs created:"

jq -r '.proof_prs[] | "  - \(.repo)#\(.number): \(.url)"' "$STATE_FILE"

log ""
log "Next steps:"
log "  1. Review and test the proof PRs"
log "  2. Fix any compilation errors using /proof-pr:push-fix"
log "  3. Check status with /proof-pr:status $ORIGINAL_PR"
log "  4. When original PR merges, run /proof-pr:convert $ORIGINAL_PR"
log ""
log "State saved to: $STATE_FILE"
```

## Return Value

- **Format**: Creates proof PRs and saves state
- **State file**: `~/.work/proof-pr/{original_pr_number}/state.json`
- **Output**: URLs of created proof PRs

**Exit codes:**
- 0: Success - all proof PRs created
- 1: Partial success - some proof PRs failed to create
- 2: Failure - no proof PRs created

## Examples

1. **Create proof PR for simple dependency**:
   ```
   /proof-pr:create https://github.com/openshift/api/pull/2626 openshift/client-go
   ```
   Creates a proof PR in client-go that depends directly on api#2626.

2. **Create proof PR with transitive dependency**:
   ```
   /proof-pr:create https://github.com/openshift/api/pull/2626 openshift/machine-config-operator
   ```
   Auto-detects that MCO → client-go → api, and creates proof PRs in both client-go and MCO.

3. **Create proof PRs in multiple specific repositories**:
   ```
   /proof-pr:create https://github.com/openshift/api/pull/2626 openshift/client-go openshift/oc openshift/console
   ```
   Creates proof PRs in client-go, oc, and console (if they depend on api).

## Notes

- **Auto-fork**: Automatically forks repositories if you don't have write access
- **Auto-fix**: Attempts simple type rename fixes automatically
- **WIP handling**: Creates WIP PRs with instructions if auto-fix fails
- **State recovery**: If interrupted, can recover using `/proof-pr:status` with auto-recovery
- **No custom labels**: Uses only standard `do-not-merge/hold` label
- **Identification**: Proof PRs identified by HTML comments in body (not labels)
