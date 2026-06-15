#!/bin/bash
# create_merge_request.sh
#
# Consolidated git workflow script for the docs pipeline.
# Creates a feature branch (if needed), commits manifest files,
# pushes, and creates an MR/PR via gh or glab.
#
# Usage: bash create_merge_request.sh <ticket> --base-path <path> [--draft] [--repo-path <path>]
# Requires: git, jq, gh (for GitHub) or glab (for GitLab)

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

TICKET=""
BASE_PATH=""
REPO_PATH=""
DRAFT=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --base-path)  BASE_PATH="$2"; shift 2 ;;
        --repo-path)  REPO_PATH="$2"; shift 2 ;;
        --draft)      DRAFT=true; shift ;;
        -*)           echo "Unknown flag: $1" >&2; exit 1 ;;
        *)            TICKET="$1"; shift ;;
    esac
done

TICKET="${TICKET:?Usage: create_merge_request.sh <ticket> --base-path <path> [--draft] [--repo-path <path>]}"
BASE_PATH="${BASE_PATH:?--base-path is required}"
TICKET_UPPER=$(echo "$TICKET" | tr '[:lower:]' '[:upper:]')
TICKET_LOWER=$(echo "$TICKET" | tr '[:upper:]' '[:lower:]')

OUT="$BASE_PATH/create-merge-request"
mkdir -p "$OUT"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

git_cmd() {
    if [[ -n "$REPO_PATH" ]]; then
        git -C "$REPO_PATH" "$@"
    else
        git "$@"
    fi
}

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

write_sidecar() {
    jq -n \
        --argjson schema_version 1 \
        --arg step "create-merge-request" \
        --arg ticket "$TICKET_UPPER" \
        --arg completed_at "$(timestamp)" \
        --arg commit_sha "${1:-}" \
        --arg branch "${2:-}" \
        --argjson pushed "${3:-false}" \
        --arg url "${4:-}" \
        --arg action "${5:-skipped}" \
        --arg platform "${6:-unknown}" \
        --argjson skipped "${7:-false}" \
        --arg skip_reason "${8:-}" \
        '{
            schema_version: $schema_version,
            step: $step,
            ticket: $ticket,
            completed_at: $completed_at,
            commit_sha: (if $commit_sha == "" then null else $commit_sha end),
            branch: (if $branch == "" then null else $branch end),
            pushed: $pushed,
            url: (if $url == "" then null else $url end),
            action: $action,
            platform: $platform,
            skipped: $skipped,
            skip_reason: (if $skip_reason == "" then null else $skip_reason end)
        }' > "$OUT/step-result.json"
}

# ---------------------------------------------------------------------------
# Draft mode — skip everything
# ---------------------------------------------------------------------------

if [[ "$DRAFT" == true ]]; then
    echo "Draft mode — skipped commit and MR/PR creation."
    write_sidecar "" "" false "" "skipped" "unknown" true "draft"
    exit 0
fi

# ---------------------------------------------------------------------------
# Resolve git context
# ---------------------------------------------------------------------------

repo_dir=$(git_cmd rev-parse --show-toplevel)
branch=$(git_cmd rev-parse --abbrev-ref HEAD)
remote_url=$(git_cmd remote get-url origin 2>/dev/null || true)

platform="unknown"
if [[ "$remote_url" == *github* ]]; then
    platform="github"
elif [[ "$remote_url" == *gitlab* ]]; then
    platform="gitlab"
fi

# ---------------------------------------------------------------------------
# Branch creation — if on main/master and no --repo-path
# ---------------------------------------------------------------------------

if [[ "$branch" == "main" || "$branch" == "master" ]]; then
    if [[ -n "$REPO_PATH" ]]; then
        echo "ERROR: --repo-path is set but repo is on '$branch'. Switch to a feature branch first." >&2
        write_sidecar "" "$branch" false "" "skipped" "$platform" true "on_default_branch"
        exit 1
    fi

    # Use upstream remote for forks, origin otherwise
    if git_cmd remote get-url upstream &>/dev/null; then
        base_remote="upstream"
    else
        base_remote="origin"
    fi

    echo "Fetching latest '$branch' from $base_remote..."
    git_cmd fetch "$base_remote" "$branch"

    # Stash working tree (includes untracked files from writing step)
    stash_count_before=$(git_cmd stash list 2>/dev/null | wc -l)
    git_cmd stash push --include-untracked -m "docs-pipeline: pre-branch stash"
    stash_count_after=$(git_cmd stash list 2>/dev/null | wc -l)

    git_cmd reset --hard "${base_remote}/${branch}"

    echo "Creating feature branch '$TICKET_LOWER' from ${base_remote}/${branch}."
    if git_cmd rev-parse --verify "refs/heads/$TICKET_LOWER" &>/dev/null; then
        echo "Branch '$TICKET_LOWER' already exists — switching to it."
        git_cmd checkout "$TICKET_LOWER"
    else
        git_cmd checkout -b "$TICKET_LOWER"
    fi

    # Restore written files (only if this run actually stashed something)
    if [[ $stash_count_after -gt $stash_count_before ]]; then
        git_cmd stash pop
    fi

    branch="$TICKET_LOWER"
fi

# ---------------------------------------------------------------------------
# Read manifest from writing step sidecar
# ---------------------------------------------------------------------------

writing_sidecar="$BASE_PATH/writing/step-result.json"
if [[ ! -f "$writing_sidecar" ]]; then
    echo "No writing step-result.json found — nothing to commit."
    write_sidecar "" "$branch" false "" "skipped" "$platform" true "no_files"
    exit 0
fi

repo_prefix=$(realpath "$repo_dir")
mapfile -t files < <(jq -r '.files[]' "$writing_sidecar" 2>/dev/null | grep "^$repo_prefix" || true)

if [[ ${#files[@]} -eq 0 ]]; then
    echo "No files in manifest under $repo_prefix."
    write_sidecar "" "$branch" false "" "skipped" "$platform" true "no_files"
    exit 0
fi

# ---------------------------------------------------------------------------
# Stage files
# ---------------------------------------------------------------------------

staged=()
for f in "${files[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "WARNING: $f not found, skipping" >&2
        continue
    fi
    git_cmd add "$f"
    staged+=("${f#"$repo_prefix/"}")
done

if [[ ${#staged[@]} -eq 0 ]] || git_cmd diff --cached --quiet 2>/dev/null; then
    echo "No changes to commit."
    write_sidecar "" "$branch" false "" "skipped" "$platform" true "no_changes"
    exit 0
fi

# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

file_list=$(printf '  - %s\n' "${staged[@]}")
commit_msg="docs($TICKET_LOWER): add generated documentation

Files:
$file_list

Generated by docs-pipeline for $TICKET_UPPER"

if ! git_cmd commit -m "$commit_msg"; then
    echo "ERROR: git commit failed" >&2
    write_sidecar "" "$branch" false "" "skipped" "$platform" true "commit_failed"
    exit 1
fi

sha=$(git_cmd rev-parse HEAD)
echo "Committed: $sha"

# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------

git_cmd fetch origin "$branch" 2>/dev/null || true
if ! git_cmd push --force-with-lease -u origin "$branch" 2>&1; then
    echo "ERROR: Push failed" >&2
    write_sidecar "$sha" "$branch" false "" "skipped" "$platform" true "push_failed"
    exit 1
fi
echo "Pushed $branch ($sha)"

# ---------------------------------------------------------------------------
# Build MR/PR title
# ---------------------------------------------------------------------------

mr_summary=""
if [[ -f "$BASE_PATH/requirements/discovery.json" ]]; then
    mr_summary=$(jq -r '.ticket_summary // empty' "$BASE_PATH/requirements/discovery.json" 2>/dev/null || true)
fi
if [[ -z "$mr_summary" && -f "$BASE_PATH/requirements/step-result.json" ]]; then
    mr_summary=$(jq -r '.title // empty' "$BASE_PATH/requirements/step-result.json" 2>/dev/null || true)
fi
if [[ -z "$mr_summary" && -f "$BASE_PATH/requirements/requirements.md" ]]; then
    mr_summary=$(grep -m1 '^#' "$BASE_PATH/requirements/requirements.md" 2>/dev/null \
        | sed 's/^#\+[[:space:]]*//' | head -c 80 || true)
    mr_summary=$(echo "$mr_summary" | sed "s/^${TICKET_UPPER}[[:space:]]*[-:][[:space:]]*//I")
fi
mr_summary="${mr_summary:-generated documentation}"
pr_title="[AI generated docs] $TICKET_UPPER: $mr_summary"

# ---------------------------------------------------------------------------
# Build MR/PR description
# ---------------------------------------------------------------------------

files_block=$(printf -- '- \`%s\`\n' "${staged[@]}")

desc_file=$(mktemp)
trap 'rm -f "$desc_file"' EXIT
cat > "$desc_file" << DESCEOF
Documentation generated by the docs pipeline.

**JIRA ticket:** $TICKET_UPPER
**Branch:** $branch

**Files:**
$files_block
DESCEOF

# ---------------------------------------------------------------------------
# Detect target branch
# ---------------------------------------------------------------------------

default_branch="main"
if [[ -f "$BASE_PATH/repo-info.json" ]]; then
    default_branch=$(jq -r '.default_branch // "main"' "$BASE_PATH/repo-info.json" 2>/dev/null || echo "main")
fi

# ---------------------------------------------------------------------------
# Create MR/PR
# ---------------------------------------------------------------------------

mr_url=""
action="skipped"

if [[ "$platform" == "github" ]]; then
    mr_url=$(gh pr list --head "$branch" --json url --jq '.[0].url // empty' 2>/dev/null || true)
    if [[ -n "$mr_url" ]]; then
        action="found_existing"
        echo "Found existing PR: $mr_url"
    else
        if mr_url=$(gh pr create --title "$pr_title" --body-file "$desc_file" --base "$default_branch" 2>&1); then
            action="created"
            echo "Created PR: $mr_url"
        else
            echo "ERROR: Failed to create PR: $mr_url" >&2
            write_sidecar "$sha" "$branch" true "" "skipped" "$platform" true "create_failed"
            exit 1
        fi
    fi

elif [[ "$platform" == "gitlab" ]]; then
    is_fork=false
    origin_project=$(echo "$remote_url" | sed 's|\.git$||' | sed 's|^https\?://[^/]*/||; s|^[^:]*:||; s|^//[^/]*/||')

    if git_cmd remote get-url upstream &>/dev/null; then
        is_fork=true
        upstream_url=$(git_cmd remote get-url upstream)
        upstream_project=$(echo "$upstream_url" | sed 's|\.git$||' \
            | sed 's|^https\?://[^/]*/||; s|^[^:]*:||; s|^//[^/]*/||')
    fi

    # Check for existing MRs
    if [[ "$is_fork" == true ]]; then
        upstream_encoded=$(echo "$upstream_project" | sed 's|/|%2F|g')
        mr_url=$(glab api "projects/$upstream_encoded/merge_requests?source_branch=$branch&state=opened" \
            2>/dev/null | jq -r '.[0].web_url // empty' || true)
    else
        mr_url=$(glab mr list --source-branch "$branch" -F json 2>/dev/null \
            | jq -r '.[0].web_url // empty' || true)
    fi

    if [[ -n "$mr_url" ]]; then
        action="found_existing"
        echo "Found existing MR: $mr_url"
    else
        if [[ "$is_fork" == true ]]; then
            # Fork: POST to fork's endpoint with target_project_id
            fork_encoded=$(echo "$origin_project" | sed 's|/|%2F|g')
            upstream_id=$(glab api "projects/$upstream_encoded" 2>/dev/null | jq -r '.id // empty' || true)

            if [[ -z "$upstream_id" ]]; then
                echo "ERROR: Cannot resolve upstream project ID for '$upstream_project'" >&2
                write_sidecar "$sha" "$branch" true "" "skipped" "$platform" true "create_failed"
                exit 1
            fi

            if mr_response=$(glab api --method POST "projects/$fork_encoded/merge_requests" \
                -f source_branch="$branch" \
                -f target_branch="$default_branch" \
                -f "target_project_id=$upstream_id" \
                -f "title=$pr_title" \
                -f "description=$(cat "$desc_file")" 2>&1); then
                mr_url=$(echo "$mr_response" | jq -r '.web_url // empty' 2>/dev/null || true)
                action="created"
                echo "Created MR (fork → upstream): $mr_url"
            else
                echo "ERROR: Failed to create MR: $mr_response" >&2
                write_sidecar "$sha" "$branch" true "" "skipped" "$platform" true "create_failed"
                exit 1
            fi
        else
            # Non-fork: glab mr create directly
            if create_output=$(glab mr create \
                --source-branch "$branch" \
                --target-branch "$default_branch" \
                --title "$pr_title" \
                --description "$(cat "$desc_file")" \
                --yes 2>&1); then
                mr_url=$(echo "$create_output" | grep -o 'https://[^ ]*' | head -1)
                action="created"
                echo "Created MR: $mr_url"
            else
                echo "ERROR: Failed to create MR: $create_output" >&2
                write_sidecar "$sha" "$branch" true "" "skipped" "$platform" true "create_failed"
                exit 1
            fi
        fi
    fi

else
    echo "WARNING: Unknown platform '$platform'. Branch pushed but no MR/PR created." >&2
    write_sidecar "$sha" "$branch" true "" "skipped" "$platform" true "unknown_platform"
    exit 0
fi

# ---------------------------------------------------------------------------
# Write final sidecar
# ---------------------------------------------------------------------------

write_sidecar "$sha" "$branch" true "$mr_url" "$action" "$platform" false ""
echo "Done."
