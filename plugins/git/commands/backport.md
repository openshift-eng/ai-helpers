---
description: Backport commits to multiple branches
argument-hint: <commit> <branch1> [branch2...] [--new-branch]
---

## Name
git:backport

## Synopsis
```
/git:backport <commit> <branch1> [branch2...] [--new-branch|-b]
```

## Description
The `git:backport` command helps backport a commit to multiple branches. It automates the process of cherry-picking a commit to one or more target branches, with optional support for creating new branches for each backport (useful for creating pull requests).

This command provides:
- Automated commit backporting to one or multiple branches
- Validation of commit and branch existence
- Safe state management (saves and restores current branch)
- Conflict detection and user-guided resolution
- Optional new branch creation for PR workflows
- Support for branches with or without remote tracking

## Implementation
The command executes the following workflow:

1. **Validates inputs:**
   - Checks that at least 2 arguments are provided (commit + at least one branch)
   - Parses the `--new-branch` or `-b` flag if present
   - Verifies the commit exists using `git cat-file -t <commit>`
   - Shows commit details: `git log -1 --oneline <commit>`
   - Filters out flag arguments and verifies all remaining target branches exist

2. **ASK FOR USER PERMISSION:**
   - **IMPORTANT: After validating inputs, you MUST present the complete backport plan to the user and ask for explicit permission to proceed**
   - Show what will happen: which branches will be checked out, which new branches will be created, and that commits will be made
   - Wait for user confirmation before proceeding with any git operations
   - Example: "I'm going to checkout release/v1.35, pull latest changes, create branch backport-abc1234-to-release/v1.35, cherry-pick the commit, then repeat for release/v1.34. This will create new branches and commits. Should I proceed?"

3. **Saves current state (only after user permission):**
   - Records the current branch: `git branch --show-current`
   - Checks for uncommitted changes: `git status --porcelain`
   - If there are uncommitted changes, warns the user and stops

4. **For each target branch (only after user permission):**
   - Shows which target branch is being worked on
   - Checks out the target branch: `git checkout <branch>`
   - Checks if the branch tracks a remote branch: `git rev-parse --abbrev-ref <branch>@{upstream}`
   - **If the branch tracks a remote branch:**
     - Pulls latest changes to ensure it's up to date: `git pull`
   - **If the branch doesn't track a remote branch:**
     - Skips pulling and informs the user the branch is local-only
   - **If `--new-branch` flag is set:**
     - Creates a new branch for the backport: `git checkout -b backport-<commit-short-hash>-to-<branch>`
       - Uses the short commit hash (first 7 chars) in the branch name
       - Example: `backport-abc1234-to-release-1.0`
   - Attempts to cherry-pick: `git cherry-pick <commit>`
   - **If conflicts occur:**
     - Shows the conflicting files: `git status`
     - Shows the conflicts: `git diff`
     - **STOPS and asks the user to resolve conflicts**
     - Tells them to run `git cherry-pick --continue` when done, or `git cherry-pick --abort` to skip
     - Asks if they want to continue to the next branch or abort the entire operation
   - **If successful:**
     - Shows success message with the new commit hash
     - If a new branch was created, shows the branch name
     - Continues to next branch

5. **Restores original state:**
   - Returns to the original branch: `git checkout <original-branch>`
   - Shows final summary of all backports:
     - Lists successful backports with their branch names (if `--new-branch` was used)
     - Lists failed backports
     - If `--new-branch` was used, reminds user they can now create PRs from the new branches

The command is interactive and waits for user input when conflicts occur and **REQUIRES USER PERMISSION before executing any git operations**. It tracks success/failure for each branch and provides a comprehensive summary at the end.

## Return Value
- **Claude agent text**:
  - Success summary showing which branches were successfully backported
  - List of any failed backports
  - New branch names (if `--new-branch` flag was used)
  - Instructions for next steps (e.g., creating PRs from new branches)

## Examples

1. **Basic backport to a single branch**:
   ```bash
   /git:backport abc1234 release-1.0
   ```
   Cherry-picks commit `abc1234` directly to the `release-1.0` branch.

2. **Backport to multiple branches**:
   ```bash
   /git:backport abc1234 release-1.0 release-1.1 release-1.2
   ```
   Cherry-picks commit `abc1234` to three different release branches.

3. **Backport with new branch creation (for PRs)**:
   ```bash
   /git:backport abc1234 release-1.0 release-1.1 --new-branch
   ```
   Creates new branches `backport-abc1234-to-release-1.0` and `backport-abc1234-to-release-1.1`, each containing the cherry-picked commit. These branches can then be used to create pull requests.

4. **Using short flag syntax**:
   ```bash
   /git:backport abc1234 main -b
   ```
   Same as `--new-branch`, creates a new branch `backport-abc1234-to-main`.

## Arguments
- $1: Commit hash or reference to backport (required)
- $2+: Target branch names to backport to (space-separated, at least one required)
- `--new-branch` or `-b`: Create a new branch from each target branch before cherry-picking (optional flag)
