---
description: Analyze and resolve git branch issues (conflicts, divergence, push/pull problems)
argument-hint: [issue-description]
---

## Name
git:branch-resolve

## Synopsis
```
/git:branch-resolve [issue-description]
```

## Description
The `git:branch-resolve` command is an AI-powered git troubleshooting assistant that analyzes and resolves branch-related issues, enabling developers to smoothly pulling or pushing code. It helps identify and fix common problems such as:
- Diverged branches (local and remote have different commits)
- Merge conflicts from pull/merge operations
- Push rejections (non-fast-forward errors)
- Missing upstream tracking branches
- Uncommitted changes blocking pull/merge/rebase operations
- Detached HEAD state
- Stale references or tracking issues

The command performs comprehensive diagnostics and provides step-by-step solutions with clear explanations, helping developers focus on coding instead of fighting git issues.

The spec format is inspired by https://man7.org/linux/man-pages/man7/man-pages.7.html#top_of_page

## Implementation
The command should follow these steps:

### 1. Analysis Phase - Gather Repository State

Collect comprehensive information about the repository:

**Check repository status:**
```bash
# Working tree state
git status

# Branch information with tracking details
git branch -vv

# Remote configuration
git remote -v

# Current branch name
git branch --show-current
```

**Check branch divergence (if upstream exists):**
```bash
# Count commits ahead/behind
git rev-list --left-right --count HEAD...@{upstream} 2>/dev/null

# Visualize recent history
git log --oneline --graph --all -20
```

**Check for uncommitted changes:**
```bash
# Unstaged changes
git diff --stat

# Staged changes
git diff --cached --stat

# Untracked files
git ls-files --others --exclude-standard
```

**Check for conflicts:**
```bash
# List conflicted files
git diff --name-only --diff-filter=U

# Check merge/rebase in progress
test -f .git/MERGE_HEAD && echo "Merge in progress"
test -d .git/rebase-merge && echo "Rebase in progress"
```

### 2. Diagnosis Phase - Identify Issues

Pattern match against common scenarios:

**Issue: Diverged Branch**
- Symptoms: `git status` shows "have diverged" or push rejected with "non-fast-forward"
- Detection: `git rev-list --left-right --count HEAD...@{upstream}` shows both ahead and behind
- Cause: Local commits exist while remote also moved forward

**Issue: Merge Conflicts**
- Symptoms: Files marked as "both modified" or CONFLICT messages
- Detection: `git diff --name-only --diff-filter=U` returns files
- Cause: Overlapping changes that git cannot auto-merge

**Issue: Rejected Push**
- Symptoms: `git push` fails with "rejected" or "non-fast-forward"
- Detection: Remote has commits not in local history
- Cause: Remote branch moved ahead of local

**Issue: Missing Upstream**
- Symptoms: `git branch -vv` shows no upstream for current branch
- Detection: `git rev-parse --abbrev-ref @{upstream}` fails
- Cause: Branch created locally without setting upstream

**Issue: Uncommitted Changes**
- Symptoms: Modified/staged files preventing operations
- Detection: `git status --porcelain` returns non-empty
- Cause: Working directory has changes not committed

**Issue: Detached HEAD**
- Symptoms: `git status` shows "HEAD detached at..."
- Detection: `git symbolic-ref HEAD` fails
- Cause: Checked out specific commit instead of branch

### 3. Solution Strategy - Propose Fixes

For each identified issue, provide solutions with explanations:

**For Diverged Branches:**

Ask user preference:
```bash
# Option 1: Rebase (cleaner history)
git pull --rebase

# Option 2: Merge (preserves all history)
git pull --no-rebase

# Option 3: Force push (⚠️ dangerous - only if local is correct)
git push --force-with-lease
```

**For Merge Conflicts:**

```bash
# Show conflicted files
git diff --name-only --diff-filter=U

# For each file, show conflicts and help resolve:
# - Accept theirs: git checkout --theirs <file>
# - Accept ours: git checkout --ours <file>
# - Manual resolution: edit file to resolve markers

# After resolution
git add <resolved-files>
git commit  # or git merge --continue / git rebase --continue
```

**For Rejected Push:**

```bash
# Safe sequence
git fetch origin
git pull origin <branch>
# Resolve any conflicts if they occur
git push origin <branch>
```

**For Missing Upstream:**

```bash
# Set upstream and push
git push --set-upstream origin <branch-name>

# Or just set upstream
git branch --set-upstream-to=origin/<branch-name>
```

**For Uncommitted Changes:**

Ask user preference:
```bash
# Option 1: Commit them
git add -A
git commit -m "message"

# Option 2: Stash them
git stash push -m "description"

# Option 3: Discard them (⚠️ destructive)
git reset --hard
```

**For Detached HEAD:**

```bash
# If changes to keep
git switch -c <new-branch-name>

# If no changes needed
git switch <existing-branch>
```

### 4. Execution Phase - Apply Solutions

Before executing commands that modify state:

1. **Explain** what will be done and why
2. **Warn** about potentially destructive operations
3. **Get confirmation** for risky operations (force push, reset --hard, etc.)
4. **Execute** commands step by step
5. **Verify** results with `git status`

### 5. Safety Guidelines

The implementation must follow these rules:

- **NEVER** force push to main/master without explicit user confirmation
- **NEVER** run `git reset --hard` or discard changes without user approval
- **ALWAYS** explain implications of destructive operations
- **ALWAYS** suggest safer alternatives when they exist
- **PREFER** `--force-with-lease` over `--force` for safety
- **RECOMMEND** creating backup branches for complex operations
- **VERIFY** authorship before amending commits
- **AVOID** skipping hooks unless explicitly requested

## Return Value
- **Claude agent text**: Analysis and resolution results including:
  - Clear diagnosis of identified issue(s)
  - Summary of current git state (branch, divergence, conflicts, etc.)
  - Recommended solution with step-by-step commands
  - Risk warnings for destructive operations
  - Execution confirmation and results
  - Verification of successful resolution

## Examples

### 1. Basic usage (analyze current issues)
```
/git:branch-resolve
```
Output:
```
## Diagnosis
Your branch has diverged from the remote. You have 3 local commits that aren't on
the remote, and the remote has 2 commits that you don't have locally.

## Current State
- Branch: feature-auth
- Local commits ahead: 3
- Remote commits behind: 2
- Working tree: clean (no uncommitted changes)

## Recommended Solution

I recommend using **rebase** to create a cleaner, linear history:

git pull --rebase origin feature-auth

This will:
1. Temporarily remove your 3 local commits
2. Apply the 2 remote commits to your branch
3. Replay your 3 commits on top

Alternative: git pull (creates merge commit, preserves all history)

## Risks & Considerations
- Rebase rewrites commit history (changes commit SHAs)
- Safe because your working tree is clean

Proceed with rebase? (y/n)
```

### 2. With specific issue context
```
/git:branch-resolve "can't push my changes"
```
Output:
```
## Diagnosis
Your push was rejected because the remote branch has commits that you don't
have locally. This protects against overwriting others' work.

## Current State
- Branch: main
- Remote has new commits: yes
- Local commits to push: yes
- Working tree: clean

## Recommended Solution

Safe resolution:
1. git fetch origin
2. git pull origin main
3. git push origin main

If step 2 creates conflicts, I'll help resolve them.

DO NOT force push - this would overwrite others' work!

## Execution
Proceeding with safe pull and push sequence...
```

### 3. Merge conflict scenario
```
/git:branch-resolve "merge conflict after pull"
```
Output:
```
## Diagnosis
You have merge conflicts in 2 files that need resolution.

## Current State
- Merge in progress
- Conflicted files:
  - src/auth.js
  - README.md
- Other files: merged successfully

## Recommended Solution

### File 1: src/auth.js
Showing conflicts:

<<<<<<< HEAD
function authenticate(user) {
  return jwt.sign({ id: user.id }, SECRET_KEY);
}
=======
function authenticate(user, options) {
  return jwt.sign({ id: user.id, role: user.role }, SECRET_KEY, options);
}
>>>>>>> origin/main

Analysis: Both versions modified authenticate(). Remote added 'role' field
and 'options' parameter.

Recommendation: Accept remote version

Choose resolution:
1. Accept remote version (--theirs)
2. Accept your version (--ours)
3. Manual edit
4. Show more context

[After resolution]
git add src/auth.js README.md
git commit -m "Merge branch 'main' - resolved conflicts"
```

### 4. Uncommitted changes blocking operation
```
/git:branch-resolve "can't pull"
```
Output:
```
## Diagnosis
You have uncommitted changes that would conflict with incoming changes.
Git is protecting your work from being overwritten.

## Current State
- Modified files: 2
  - src/config.js (15 lines changed)
  - src/utils.js (3 lines changed)
- Staged files: 0
- Branch: main (behind origin by 2 commits)

## Recommended Solution

Choose an option:

1. Commit your changes (recommended if work is complete)
   git add src/config.js src/utils.js
   git commit -m "Update config and utils"
   git pull

2. Stash your changes (for temporary save)
   git stash push -m "WIP: config changes"
   git pull
   git stash pop

3. Discard your changes ⚠️ (permanently deletes work)
   git reset --hard
   git pull

Which option do you prefer?
```

### 5. Detached HEAD state
```
/git:branch-resolve
```
Output:
```
## Diagnosis
You're in "detached HEAD" state. HEAD points to commit abc1234 instead of a branch.
New commits won't belong to any branch and could be lost.

## Current State
- HEAD: detached at abc1234
- Working tree: clean
- No new commits since detaching

## Recommended Solution

Choose based on your intent:

1. Return to your branch (discard detached position)
   git switch main

2. Create branch from current position (keep this location)
   git switch -c feature-from-abc1234

3. Continue exploring (no action needed, but be aware commits may be lost)

What would you like to do?
```

## Arguments
- `issue-description` (optional): Additional context about the problem you're facing (e.g., "can't push", "merge conflict", "branch diverged"). This helps focus the analysis on specific issues.

## Safety Considerations
- **Protected operations**: Never force push to main/master, reset --hard, or discard changes without explicit user confirmation
- **Explanation first**: Always explain what commands will do and their implications before execution
- **Safer alternatives**: Suggest `--force-with-lease` instead of `--force`, stash instead of reset, rebase with backup
- **Step-by-step**: Execute complex operations incrementally with verification between steps
- **User control**: Require confirmation for all destructive operations
- **Educational**: Explain why issues occurred to help prevent future problems