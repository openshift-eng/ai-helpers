---
description: Clean up old and defunct branches that are no longer needed
argument-hint: "[--dry-run] [--merged-only] [--remote]"
---

## Name
git:branch-cleanup

## Synopsis
```
/git:branch-cleanup [--dry-run] [--merged-only] [--remote]
```

## Description
The `git:branch-cleanup` command identifies and removes old, defunct, or merged branches from your local repository (and optionally from remote). It helps maintain a clean repository by removing branches that are no longer needed, such as:
- Branches that have been merged into the main branch
- Branches that no longer exist on the remote
- Stale feature branches from completed work

The command performs safety checks to prevent deletion of:
- The current branch
- Protected branches (main, master, develop, etc.)
- Branches with unmerged commits (unless explicitly overridden)

The spec sections is inspired by https://man7.org/linux/man-pages/man7/man-pages.7.html#top_of_page

## Implementation
The command should follow these steps:

1. **Identify Main Branch**
   - Detect the primary branch (main, master, etc.)
   - Use `git symbolic-ref refs/remotes/origin/HEAD` or `git branch -r` to determine

2. **Gather Branch Information**
   - List all local branches: `git branch`
   - Get current branch: `git branch --show-current`
   - Identify merged branches using multi-layered detection:
     - Standard merge: `git branch --merged <main-branch>`
     - Merge commit messages: `git log <main-branch> --merges --oneline`
     - Content comparison: `git diff <main-branch>...<branch> --quiet`
     - Cherry-pick detection: `git cherry <main-branch> <branch>`
   - Check remote tracking: `git branch -vv`
   - Find remote-deleted branches: `git remote prune origin --dry-run`

3. **Categorize Branches**
   - **Merged branches**: Detected via one of these methods:
     - Standard: Commits directly in main branch history
     - Merge commit: Found in main's merge commit messages
     - Content-identical: All changes present in main (rebased/cherry-picked)
     - Cherry-picked: All commits have equivalents in main
   - **Gone branches**: Remote tracking branch no longer exists
   - **Stale branches**: Last commit older than threshold (e.g., 3 months)
   - **Protected branches**: main, master, develop, release/*, hotfix/*

4. **Present Analysis to User**
   - Show categorized list of branches with:
     - Branch name
     - Last commit date
     - Merge status
     - Remote tracking status
     - Number of commits ahead/behind
   - Recommend branches safe to delete

5. **Confirm Deletion**
   - Ask user to confirm which branches to delete
   - Present options: all merged, all gone, specific branches, or custom selection
   - If `--dry-run` flag is present, only show what would be deleted

6. **Delete Branches**
   - Local deletion: `git branch -d <branch>` (merged) or `git branch -D <branch>` (force)
   - Remote deletion (if `--remote` flag): `git push origin --delete <branch>`
   - Prune remote references: `git remote prune origin`

7. **Report Results**
   - List deleted branches
   - Show any errors or branches that couldn't be deleted
   - Provide summary statistics

Implementation logic:
```bash
# Determine main branch
main_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$main_branch" ]; then
  main_branch="main"  # fallback
fi

# Get current branch
current_branch=$(git branch --show-current)

# Multi-layered merge detection function
# Returns: "merged:<method>" or "not-merged"
check_if_merged() {
    local branch=$1
    local main_branch=$2
    # Escape for grep ERE: ] [ \ . ^ $ * + ? ( ) { } |
    local branch_escaped=$(printf '%s\n' "$branch" | sed -e 's/[][\\.^$*+?(){}|]/\\&/g')

    # Method 1: Standard merge check (commits in main history)
    if git branch --merged "$main_branch" | grep -q "^[* ]*${branch_escaped}$"; then
        echo "merged:standard"
        return 0
    fi

    # Method 2: Merge-commit message heuristic (requires branch mention)
    # Matches examples: "Merge branch 'X'", "Merge pull request ... from org/X"
    # Note: Squash merges are not --merges; those are covered by Method 3 (content-identical).
    local branch_basename=${branch##*/}
    local branch_basename_escaped
    branch_basename_escaped=$(printf '%s\n' "$branch_basename" | sed -e 's/[][\\.^$*+?(){}|]/\\&/g')
    if git log "$main_branch" --merges --oneline \
      | grep -qiE "merge.*(branch[[:space:]]+'${branch_escaped}'|\b${branch_escaped}\b|from[[:space:]]+[^[:space:]]*/${branch_basename_escaped})"; then
        echo "merged:merge-commit"
        return 0
    fi

    # Method 3: Content comparison (handles rebased/cherry-picked branches)
    # Uses three-dot syntax (merge-base comparison) to detect content-identical branches
    # If diff is empty, all content is in main even if commit hashes differ
    # Note: 2>/dev/null suppresses errors for edge cases (no common ancestor, invalid branch)
    if git diff --quiet "$main_branch"..."$branch" 2>/dev/null; then
        echo "merged:content-identical"
        return 0
    fi

    # Method 4: Cherry-pick detection (all commits have equivalents in main)
    # Commits prefixed with '-' have equivalent patches in main
    # Note: Detects patch equivalence, not necessarily commits reachable from main
    # May have rare false positives with coincidentally similar commits
    local unmerged=$(git cherry "$main_branch" "$branch" 2>/dev/null | grep -c '^+')
    if [ "$unmerged" -eq 0 ]; then
        echo "merged:cherry-picked"
        return 0
    fi

    echo "not-merged"
    return 1
}

# Find all merged branches with detection method
for branch in $(git branch | grep -v "^\*" | sed 's/^[ ]*//'); do
    if [ "$branch" != "$main_branch" ]; then
        merge_status=$(check_if_merged "$branch" "$main_branch")
        if [[ "$merge_status" == merged:* ]]; then
            method=${merge_status#merged:}
            echo "$branch|$method"
        fi
    fi
done

# Find branches with deleted remotes ("gone")
git branch -vv | grep ': gone]' | awk '{print $1}'

# Find stale branches (older than 3 months)
git for-each-ref --sort=-committerdate --format='%(refname:short)|%(committerdate:iso)|%(upstream:track)' refs/heads/

# Delete local branch (merged)
git branch -d <branch-name>

# Delete local branch (force)
git branch -D <branch-name>

# Delete remote branch
git push origin --delete <branch-name>

# Prune remote references
git remote prune origin
```

## Return Value
- **Claude agent text**: Analysis and results including:
  - List of branches categorized by status (merged, gone, stale)
  - Recommendation for which branches are safe to delete
  - Confirmation prompt for user approval
  - Summary of deleted branches and any errors
  - Statistics (e.g., "Deleted 5 branches, freed X MB")

## Examples

1. **Basic usage (interactive)**:
   ```
   /git:branch-cleanup
   ```
   Output:
   ```
   Analyzing branches in repository...

   Main branch: main
   Current branch: feature/new-api

   === Merged Branches (safe to delete) ===
   feature/bug-fix-123        Merged (standard) - 2 weeks ago
   feature/update-deps        Merged (merge-commit) - 1 month ago
   feature/rebased-work       Merged (content-identical) - 3 days ago

   === Gone Branches (remote deleted) ===
   feature/old-feature        Remote: gone
   hotfix/urgent-fix          Remote: gone

   === Stale Branches (no activity > 3 months) ===
   experiment/prototype       Last commit: 4 months ago, not merged

   === Protected Branches (will not delete) ===
   main
   develop

   Recommendations:
   - Safe to delete: feature/bug-fix-123, feature/update-deps (merged)
     * Note: feature/rebased-work has different commits but identical content (rebased)
   - Safe to delete: feature/old-feature, hotfix/urgent-fix (remote gone)
   - Review needed: experiment/prototype (unmerged, stale)

   What would you like to delete?
   ```

2. **Dry run (preview only)**:
   ```
   /git:branch-cleanup --dry-run
   ```
   Output:
   ```
   [DRY RUN MODE - No changes will be made]

   Would delete the following merged branches:
   - feature/bug-fix-123
   - feature/update-deps

   Would delete the following gone branches:
   - feature/old-feature
   - hotfix/urgent-fix

   Total: 4 branches would be deleted
   ```

3. **Merged branches only**:
   ```
   /git:branch-cleanup --merged-only
   ```
   Output:
   ```
   Analyzing merged branches...

   Found 3 merged branches:
   - feature/bug-fix-123
   - feature/update-deps
   - feature/ui-improvements

   Delete these branches? (y/n)
   ```

4. **Including remote cleanup**:
   ```
   /git:branch-cleanup --remote
   ```
   Output:
   ```
   Deleting local and remote branches...

   ✓ Deleted local: feature/bug-fix-123
   ✓ Deleted remote: origin/feature/bug-fix-123
   ✓ Deleted local: feature/update-deps
   ✓ Deleted remote: origin/feature/update-deps

   Summary: Deleted 2 branches locally and remotely
   ```

## Arguments
- `--dry-run`: Preview which branches would be deleted without actually deleting them
- `--merged-only`: Only consider branches that have been fully merged into the main branch
- `--remote`: Also delete branches from the remote repository (requires push permissions)
- `--force`: Force delete branches even if they have unmerged commits (use with caution)
- `--older-than=<days>`: Only consider branches with no commits in the last N days (default: 90)

## Safety Considerations
- **Never delete**: Current branch, main, master, develop, or release/* branches
- **Require confirmation**: Always ask user before deleting branches
- **Preserve unmerged work**: By default, only delete merged branches unless `--force` is used
- **Backup suggestion**: Recommend creating a backup of unmerged branches before deletion
- **Remote deletion**: Only delete remote branches if user explicitly requests with `--remote` flag
