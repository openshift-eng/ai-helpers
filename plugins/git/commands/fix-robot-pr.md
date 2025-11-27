---
description: Fix a cherrypick-robot PR that needs manual intervention
argument-hint: <pr-url> [error-messages]
---

## Name
git:fix-robot-pr

## Synopsis
```
/git:fix-robot-pr <pr-url> [error-messages]
```

## Description

The `git:fix-robot-pr` command replaces a cherrypick-robot PR with a clean, manually-crafted cherry-pick PR that includes fixes the robot cannot handle.

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
gh pr view https://github.com/openshift/origin/pull/30524 --json baseRefName,title,commits,number,statusCheckRollup
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

Common error patterns:
- `hack/verify-jsonformat.sh` → JSON validation failure
- `hack/verify-generated.sh` → Missing test annotations
- `CONFLICT` → Merge conflicts
- `hack/verify-*.sh` → Other verification failures

### 3. Create a New Clean Branch

```bash
# Fetch the latest base branch
git fetch upstream <base-branch>

# Create new branch following naming convention
git checkout -b cherry-pick-<issue-number>-to-<base-branch> upstream/<base-branch>
```

Example: `cherry-pick-29611-to-release-4.19`

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

**For JSON validation errors:**
```bash
# Add files to exclusion list in hack/verify-jsonformat.sh
# Edit the excluded_files array to include the problematic JSON file
```

**For missing test annotations:**
```bash
# Regenerate annotations
hack/update-generated.sh
git add test/extended/util/annotate/generated/zz_generated.annotations.go
git commit -m "Update generated test annotations"
```

**For merge conflicts:**
- Resolve using context from error messages
- Review the conflicting sections
- Apply appropriate resolution
- Stage and commit resolved files

**For other verification failures:**
- Identify the specific verification script failing
- Apply repository-specific fixes
- Commit with clear explanation

### 6. Push and Create Replacement PR

```bash
# Push to your fork (assuming 'origin' is your fork)
git push -u origin cherry-pick-<issue-number>-to-<base-branch>

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
/git:fix-robot-pr https://github.com/openshift/origin/pull/30524

Error messages:
hack/verify-jsonformat.sh
2025/11/24 20:07:50 ERROR: Invalid JSON file 'test/extended/util/compat_otp/testdata/opm/render/validate/catalog-error/operator-2/index.json': invalid character '{' after top-level value
exit status 1

hack/verify-generated.sh
FAILURE: hack/verify-generated.sh:14: executing 'git diff --exit-code' expecting success: the command returned the wrong error code
diff --git a/test/extended/util/annotate/generated/zz_generated.annotations.go
+    "[sig-api-machinery][Feature:APIServer] TestTLSMinimumVersions": " [Suite:openshift/conformance/parallel]",
```

**What gets extracted:**
- Base branch: `release-4.19`
- Bug ID: `OCPBUGS-65944`
- Commits: `3f8cbdc94c`, `0a70b81572`
- PR to close: `30524`

**What gets analyzed from errors:**
- JSON validation failure → Add file to exclusion list
- Missing annotation → Run `hack/update-generated.sh`

**What gets fixed:**
- Add `catalog-error/operator-2/index.json` to `excluded_files` in `hack/verify-jsonformat.sh`
- Run `hack/update-generated.sh` to regenerate annotations
- Commit fixes with clear message

**Result:**
- New PR created: `https://github.com/openshift/origin/pull/30529`
- Old robot PR closed with explanation

### Example 2: With Error Log File Reference

```
/git:fix-robot-pr https://github.com/openshift/origin/pull/30524

Error log file: /path/to/ci-errors.log
```

The command reads the error log file and processes it the same way as Example 1.

### Example 3: With CI Failure Page Link

```
/git:fix-robot-pr https://github.com/openshift/origin/pull/30524

CI failure: https://prow.ci.openshift.org/view/gs/test-platform-results/pr-logs/pull/30524/...
```

The command fetches the CI logs from the provided URL and analyzes them.

### Example 4: No Error Messages (Auto-detect)

```
/git:fix-robot-pr https://github.com/openshift/origin/pull/30524
```

If no error messages are provided, the command will:
1. Check PR status using `gh pr view`
2. Identify failing checks
3. Fetch CI logs automatically
4. Analyze and fix based on detected issues

## Arguments

- **$1** (required): PR URL - The URL of the cherrypick-robot PR to fix (e.g., `https://github.com/openshift/origin/pull/30524`)
- **$2** (optional): Error messages - Can be:
  - Error messages pasted directly
  - File path to error log (e.g., `/path/to/ci-errors.log`)
  - CI failure page URL
  - Omitted (will auto-detect from PR status)

## Common Issues This Handles

Beyond what the robot can do:
- ✅ **JSON validation errors** - Add exclusions for intentionally broken test files
- ✅ **Missing annotations** - Regenerate test annotations
- ✅ **Merge conflicts** - Resolve using context
- ✅ **Verification failures** - Apply appropriate fixes
- ✅ **Context-specific fixes** - Apply fixes for the target branch
- ✅ **Edge cases** - Handle with human judgment

## Notes

- Works with any `openshift-cherrypick-robot` PR
- Error messages help determine exactly what to fix
- All changes pushed to your fork (`origin` remote)
- New PRs target the upstream repository (e.g., `openshift/origin`)
- Branch naming convention: `cherry-pick-<issue>-to-<release>`
- Maintains full control to add any fixes needed
- If no error messages provided, will check PR status and CI logs automatically
- Assumes `upstream` remote points to the main repository (e.g., `openshift/origin`)
- Assumes `origin` remote points to your fork
