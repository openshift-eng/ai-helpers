---
description: Fix a cherrypick-robot PR that needs manual intervention
argument-hint: <pr-url> [error-messages]
---

## Name
git:fix-cherrypick-robot-pr

## Synopsis
```
/git:fix-cherrypick-robot-pr <pr-url> [error-messages]
```

## Description

The `git:fix-cherrypick-robot-pr` command replaces a cherrypick-robot PR with a clean, manually-crafted cherry-pick PR that includes fixes the robot cannot handle.

The cherrypick-robot creates automated PRs but cannot:
- Fix verification failures (JSON validation, missing annotations)
- Resolve merge conflicts
- Add context-specific fixes
- Handle edge cases requiring human judgment
- Apply repository-specific cleanup

This command helps you create a replacement PR with all necessary fixes applied.

## Implementation

### 1. Extract Information from the Robot PR

Use `gh pr view <pr-url>` to extract:
- Base branch (e.g., `release-4.19`)
- PR title (to extract bug ID like `OCPBUGS-65944`)
- All commit hashes included in the PR
- PR number for later closure
- Current PR checks/CI status

Example:
```bash
gh pr view <pr-url> --json baseRefName,title,commits,number,statusCheckRollup
```

### 2. Analyze Error Messages

Parse the provided error output to identify:
- Root causes (JSON validation, missing annotations, conflicts, etc.)
- Affected files
- Required fixes
- Fix strategy

**Error sources (in priority order):**
1. User-provided error messages (from command arguments)
2. File path if provided (e.g., `/path/to/ci-errors.log`)
3. CI failure URL if provided
4. Automatically fetch from PR status checks

### 3. Discover Git Remotes and Create Branch

```bash
# Discover the upstream remote (the main repository)
# Look for a remote that's not owned by the current user
UPSTREAM_REMOTE=$(git remote -v | grep "fetch" | grep -v "$(git config user.name)" | awk '{print $1}' | head -1)

# Discover the fork remote (your fork)
FORK_REMOTE=$(git remote -v | grep "$(git config user.name).*push" | awk '{print $1}' | head -1)

# If not found, fall back to common names
UPSTREAM_REMOTE=${UPSTREAM_REMOTE:-upstream}
FORK_REMOTE=${FORK_REMOTE:-origin}

# Fetch the latest base branch
git fetch $UPSTREAM_REMOTE <base-branch>

# Create new branch following naming convention
git checkout -b cherry-pick-<issue-number>-to-<base-branch> $UPSTREAM_REMOTE/<base-branch>
```

Example branch name: `cherry-pick-12345-to-release-1.0`

### 4. Cherry-Pick Commits

Cherry-pick all commits from the robot PR in order:

```bash
# For each commit hash extracted from the robot PR
git cherry-pick <commit-hash>

# OR use the cherry-pick-by-patch command
/git:cherry-pick-by-patch <commit-hash>
```

Handle any conflicts that arise during cherry-picking.

### 5. Apply Necessary Fixes Based on Errors

Based on the error analysis from step 2, apply the necessary fixes:

**Analyze the errors to determine:**
1. Which files are causing failures
2. What type of failure (validation, conflict, test, build)
3. What fix strategy is appropriate for the repository

**Common fix strategies:**

- **Validation failures**: Check if files can be excluded from validation or need correction
- **Generated file mismatches**: Run repository update/regeneration scripts (e.g., `make update`, `make generate`)
- **Merge conflicts**: Resolve conflicts by reviewing both sides and understanding the target branch context
- **Test failures**: Update tests to be compatible with the target branch
- **Build failures**: Update dependencies or build configuration for the target branch

**Apply fixes with clear commits:**
```bash
# Make necessary changes based on error analysis
# Stage and commit each logical fix separately
git add <affected-files>
git commit -m "<clear description of what was fixed and why>"
```

**Note**: The specific fix commands will vary by repository. Consult the repository's documentation for:
- Verification script locations and options
- Code generation/update commands
- Testing conventions
- Contribution guidelines

### 6. Push and Create Replacement PR

```bash
# Use the discovered fork remote (from step 3)
# If running this step separately, rediscover the fork remote:
FORK_REMOTE=$(git remote -v | grep "$(git config user.name).*push" | awk '{print $1}' | head -1)
FORK_REMOTE=${FORK_REMOTE:-origin}

# Push to your fork
git push -u $FORK_REMOTE cherry-pick-<issue-number>-to-<base-branch>

# Create PR using gh CLI
gh pr create \
  --base <base-branch> \
  --title "[<base-branch>] <BUG-ID>: <Description>" \
  --body "$(cat <<'EOF'
## Summary
Cherry-pick of <original-commits> to <base-branch> with manual fixes.

## Commits
- <commit-1-hash>: <commit-1-message>
- <commit-2-hash>: <commit-2-message>

## Fixes Applied
- <description-of-fix-1>
- <description-of-fix-2>

## References
- Original PR: #<robot-pr-number>
- JIRA: <bug-id>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 7. Close the Old Robot PR

Add a comment to the robot PR explaining the closure:

```bash
gh pr comment <robot-pr-number> --body "Closing this PR in favor of #<new-pr-number> which includes the following fixes:
- <specific-fix-1>
- <specific-fix-2>

/close"
```

The `/close` command triggers the bot to close the PR.

## Return Value

- **Success**: New PR URL and confirmation that old PR is closed
- **Failure**: Error message with specific issue encountered

## Examples

### Example 1: With Error Messages Pasted Directly

```
/git:fix-cherrypick-robot-pr https://github.com/org/repo/pull/12345

Error messages:
[paste CI error output here]
```

**The command will:**
1. Extract PR information (base branch, commits, bug ID)
2. Analyze the error messages to identify failure types
3. Cherry-pick commits to a new branch
4. Guide you through applying appropriate fixes based on repository conventions
5. Create a new PR with fixes applied
6. Close the old robot PR with explanation

### Example 2: With Error Log File Reference

```
/git:fix-cherrypick-robot-pr https://github.com/org/repo/pull/12345

Error log file: /path/to/ci-errors.log
```

The command reads the error log file and processes it the same way as Example 1.

### Example 3: With CI Failure Page Link

```
/git:fix-cherrypick-robot-pr https://github.com/org/repo/pull/12345

CI failure: https://ci-system.example.com/logs/...
```

The command fetches the CI logs from the provided URL and analyzes them.

### Example 4: No Error Messages (Auto-detect)

```
/git:fix-cherrypick-robot-pr https://github.com/org/repo/pull/12345
```

If no error messages are provided, the command will:
1. Check PR status using `gh pr view`
2. Identify failing checks
3. Fetch CI logs automatically
4. Analyze and fix based on detected issues

## Arguments

- **$1** (required): PR URL - The URL of the cherrypick-robot PR to fix (e.g., `https://github.com/org/repo/pull/12345`)
- **$2** (optional): Error messages - Can be:
  - Error messages pasted directly
  - File path to error log (e.g., `/path/to/ci-errors.log`)
  - CI failure page URL
  - Omitted (will auto-detect from PR status)

## Common Issues This Handles

Beyond what the robot can do:
- ✅ **Validation errors** - Apply exclusions or corrections based on repository conventions
- ✅ **Generated file mismatches** - Run appropriate update/regeneration commands
- ✅ **Merge conflicts** - Resolve using context
- ✅ **Test failures** - Update tests for target branch compatibility
- ✅ **Build failures** - Update dependencies or configuration
- ✅ **Context-specific fixes** - Apply fixes appropriate for the target branch
- ✅ **Edge cases** - Handle with human judgment

## Notes

- Works with cherrypick-robot PRs across different repositories
- Error messages help determine exactly what to fix
- Automatically discovers git remote names (no hardcoded assumptions)
- All changes pushed to your fork (auto-discovered remote)
- New PRs target the upstream repository
- Branch naming convention: `cherry-pick-<issue>-to-<release>`
- Maintains full control to add any fixes needed
- If no error messages provided, will check PR status and CI logs automatically
- Remote discovery uses `git remote -v` and `git config user.name` to identify fork vs upstream
- Falls back to common names (`origin` for fork, `upstream` for main repo) if auto-discovery fails
- Fix strategies will vary by repository - consult repository documentation for specific commands
