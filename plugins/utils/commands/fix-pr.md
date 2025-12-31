---
description: Iteratively fix PR checks and address review comments until PR is mergeable
argument-hint: "[PR number] [-n N] [--skip-reviews] [--skip-rebase]"
---

## Name
utils:fix-pr

## Synopsis
```
/utils:fix-pr [PR number] [-n N] [--skip-reviews] [--skip-rebase]
```

## Description
The `utils:fix-pr` command automates the complete PR remediation workflow by iteratively resolving merge conflicts, addressing review comments, and fixing failing CI checks until the PR achieves mergeable status. Each iteration performs up to three steps in order: (1) rebase to resolve conflicts, (2) address review comments, (3) fix CI check failures. Flags allow skipping specific phases or configuring iteration count.

This command is ideal for:
- Getting a PR ready to merge automatically with minimal manual intervention
- Handling complex scenarios where review fixes might break CI or create conflicts
- Ensuring the PR stays up-to-date with the base branch throughout the process
- Recovering from multiple rounds of feedback and test failures

## Implementation

### Step 0: Parse Arguments

1. **Determine PR number**:
   - Use first non-flag argument if provided
   - Otherwise detect from current branch: `gh pr list --head <current-branch>`

2. **Parse flags**:
   - `--skip-reviews`: Skip the review comment addressing phase (Phase 2)
   - `--skip-rebase`: Skip the conflict resolution phase (Phase 1)
   - `-n N`: Set maximum iterations (default: 5 if not specified)
   - Store flag state for later decision

3. **Checkout PR branch**:
   ```bash
   gh pr checkout <PR_NUMBER>
   git pull
   ```

4. **Verify clean working tree**:
   - Run `git status`
   - If uncommitted changes exist, ask user how to proceed

### Step 1: Main Remediation Loop

This loop runs until the PR is mergeable or max iterations reached (default: 5, configurable via `-n`).

**Each iteration performs up to three phases in order:**

#### Phase 1: Resolve Merge Conflicts (Conditional)

**If `--skip-rebase` flag IS set:**
- Skip Phase 1 entirely
- Log: `⏭️  Skipping rebase (--skip-rebase flag set)`

**If `--skip-rebase` flag is NOT set:**

1. **Check for conflicts**:
   ```bash
   gh pr view <PR_NUMBER> --json mergeable,mergeStateStatus
   ```

   Parse response:
   - `mergeable: "MERGEABLE"` → No conflicts, skip to Phase 2
   - `mergeable: "CONFLICTING"` → Has conflicts, proceed with rebase
   - `mergeable: "UNKNOWN"` → Checks running, wait and retry

2. **If conflicts detected**:

   a. **Fetch latest base branch**:
   ```bash
   git fetch origin
   # Determine base branch from PR metadata
   BASE_BRANCH=$(gh pr view <PR_NUMBER> --json baseRefName -q .baseRefName)
   ```

   b. **Attempt rebase**:
   ```bash
   git rebase origin/${BASE_BRANCH}
   ```

   c. **Handle rebase outcome**:

   - **Success (no conflicts)**:
     ```bash
     git push --force-with-lease
     ```
     Log: `✅ Successfully rebased on ${BASE_BRANCH}`

   - **Conflicts encountered**:
     - Read conflicted files using `git diff --name-only --diff-filter=U`
     - For each conflicted file:
       - Read conflict markers using `git diff <file>`
       - Analyze both sides of conflict (HEAD vs incoming)
       - Intelligently resolve keeping PR changes + incorporating base changes
       - Stage resolved file: `git add <file>`
     - Continue rebase: `git rebase --continue`
     - Push: `git push --force-with-lease`
     - Log: `✅ Resolved N conflicts in M files`

   - **Cannot auto-resolve** (complex conflicts):
     - Run `git rebase --abort`
     - Report to user:
       ```
       ⚠️  Cannot automatically resolve conflicts in:
       - path/to/file1.go (complex logic conflict)
       - path/to/file2.py (structural changes)

       Manual resolution required.
       ```
     - Ask user: Abort / Skip conflict resolution / Manual intervention
     - If user chooses abort: Exit command
     - If user chooses skip: Continue to Phase 2 (may fail CI due to conflicts)

3. **Wait for rebase to reflect in PR**:
   - Poll `gh pr view` for 30 seconds to ensure GitHub recognizes rebase
   - Verify `mergeable` status updated

#### Phase 2: Address Review Comments (Conditional)

**If `--skip-reviews` flag is NOT set:**

1. **Fetch review comments** (using same logic as `/utils:address-reviews`):
   - Fetch all comments, reviews, and review comments
   - Filter out outdated, bot-generated, and oversized comments
   - See [/utils:address-reviews](./address-reviews.md) Step 1 for detailed filtering logic

2. **Categorize and prioritize**:
   - BLOCKING → CHANGE_REQUEST → QUESTION → SUGGESTION
   - Group by file and proximity

3. **Address each comment**:
   - For code changes:
     - Implement fix
     - Commit using same strategy (amend relevant commit)
     - Push: `git push --force-with-lease`
     - Reply: `gh api repos/{owner}/{repo}/pulls/<PR_NUMBER>/comments/<comment_id>/replies -f body="..."`

   - For questions/clarifications:
     - Post detailed reply without code changes

   - For declined changes:
     - Post technical justification

   - **All replies include footer**: `---\n*AI-assisted response via Claude Code*`

4. **After addressing reviews**:
   - Log: `✅ Addressed N review comments (M code changes, P replies)`
   - New pushes may trigger CI, handled in Phase 3

**If `--skip-reviews` flag IS set:**
- Skip Phase 2 entirely
- Log: `⏭️  Skipping review comments (--skip-reviews flag set)`

#### Phase 3: Fix CI Check Failures

1. **Fetch PR check status**:
   ```bash
   gh pr checks <PR_NUMBER>
   ```

   Parse output:
   - ✅ Passing checks
   - ❌ Failed checks (with check name and URL)
   - ⏳ Pending/running checks

2. **Wait for pending checks** (if any):
   - Show status: `⏳ Waiting for N checks to complete...`
   - Poll every 30 seconds
   - Timeout after 10 minutes (ask user to continue waiting or proceed)

3. **If all checks pass**:
   - Log: `✅ All CI checks passing!`
   - Exit Phase 3, check loop termination condition

4. **If checks failed**:

   a. **Fetch failure details**:
   ```bash
   gh run view <RUN_ID> --log-failed
   ```

   b. **Analyze failures**:
   - Parse error messages, stack traces, test failures
   - Identify root causes (compilation, tests, lint, etc.)
   - Group related failures

   c. **Show summary**:
   ```
   ❌ Failed checks (3):
   1. unit-tests: 2 test failures in pkg/api/handler_test.go
   2. lint: 5 golangci-lint issues
   3. build: compilation error in cmd/server/main.go:45
   ```

   d. **Fix issues**:
   - Read relevant files
   - Implement fixes for each failure
   - **Code coverage failures**: CRITICAL - If coverage check fails, this is a hard requirement, not aspirational:
     - Add targeted unit tests to cover new/modified code
     - DO NOT flag as "nice to have" - treat as blocking issue
     - Ensure tests exercise all new branches/functions
     - Verify coverage locally before pushing
   - Run local validation:
     - Tests: `go test ./pkg/api/...` or equivalent
     - Lint: Run local linter
     - Build: Run local build
     - Coverage: Run coverage tool if check failed

   e. **Commit and push**:
   ```bash
   git add .
   # Amend most relevant commit
   git commit --amend --no-edit  # or update message if scope changed
   git push --force-with-lease
   ```

   f. **Wait for new checks to start**:
   - Poll `gh pr checks` for 2 minutes
   - Verify new checks are queued/running

#### Loop Termination Conditions

After completing all three phases, check:

1. **Success - PR is mergeable**:
   ```bash
   gh pr view <PR_NUMBER> --json mergeable,mergeStateStatus
   ```
   - `mergeable: "MERGEABLE"` AND all checks passing
   - Exit loop, proceed to Step 2 (Final Verification)

2. **Max iterations reached** (default 5, or value from `-n` flag):
   ```
   ⚠️  Reached maximum iterations (N). PR status:
   - Conflicts: ✅ Resolved / ❌ Present
   - Reviews: ✅ Addressed (N comments) / ⏭️  Skipped
   - CI Checks: ✅ M passing, ❌ N failing
   ```
   - Ask user:
     - Continue for N more iterations
     - Stop and review manually
     - Abort

3. **No changes made in iteration**:
   - If Phase 1, 2, and 3 all skipped (no work to do)
   - But PR still not mergeable
   - Likely issue: External blocker (required reviewer approval, etc.)
   - Exit loop with warning

4. **Continue next iteration**: Loop back to Phase 1

### Step 2: Final Verification

1. **Fetch final PR status**:
   ```bash
   gh pr view <PR_NUMBER> --json mergeable,mergeStateStatus
   ```

2. **Check mergeable status**:
   - `mergeable: "MERGEABLE"` ✅
   - `mergeable: "CONFLICTING"` ❌ (merge conflicts)
   - `mergeable: "UNKNOWN"` ⚠️ (checks still running)

3. **Report final state**:
   ```
   ✅ PR #123 is ready to merge!

   Status:
   - All CI checks passing
   - Review comments addressed
   - No merge conflicts

   You can merge with: gh pr merge <PR_NUMBER>
   ```

   OR

   ```
   ⚠️  PR #123 status:

   CI Checks: ✅ All passing
   Reviews: ✅ Addressed
   Mergeable: ❌ Has merge conflicts

   Resolve conflicts with: git merge origin/main
   ```

### Step 3: Summary

Show comprehensive summary:
- **Loop Statistics**:
  - Total iterations run
  - Conflicts resolved
  - Review comments addressed (if not skipped)
  - CI checks fixed (by category)
  - Commits created/amended

- **Phase Breakdown**:
  - **Phase 1 (Conflicts)**: Number of rebases, conflicts resolved
  - **Phase 2 (Reviews)**: Comments addressed, replies posted, code changes
  - **Phase 3 (CI)**: Checks fixed, test failures resolved, lint issues fixed

- **Final Status**: Mergeable / Not Mergeable (with reason)

## Return Value

- **Exit status**: Success (PR is mergeable) or Partial (still has issues)
- **Summary report**: Statistics on fixes applied and current PR state
- **Actionable next steps**: If not fully mergeable, what remains to be done

## Examples

1. **Fix PR on current branch (default behavior - all three phases)**:
   ```
   /utils:fix-pr
   ```

   Output:
   ```
   🔄 Fixing PR #456 on branch feature/new-api

   === Iteration 1/5 ===

   [Phase 1: Conflicts]
   ✅ No merge conflicts detected

   [Phase 2: Review Comments]
   📝 Found 8 review comments (2 blocking, 4 change requests, 2 questions)
   - Addressing blocking: Fix null pointer in handler.go:123
   - Addressing change request: Refactor error handling in api.go
   ...
   ✅ Addressed 8 comments (6 code changes, 2 replies)

   [Phase 3: CI Checks]
   ⏳ Waiting for checks to complete...
   ❌ Found 3 failing checks
   - Fixing unit-tests: 2 failures in pkg/api/handler_test.go
   - Fixing lint: 5 golangci-lint issues
   ✅ Pushed fixes, waiting for checks...

   === Iteration 2/5 ===

   [Phase 1: Conflicts]
   ⚠️  Merge conflict detected (base branch updated)
   🔄 Rebasing on main...
   ✅ Resolved 2 conflicts in handler.go, api.go

   [Phase 2: Review Comments]
   📝 Found 2 new review comments
   ✅ Addressed 2 comments (1 code change, 1 reply)

   [Phase 3: CI Checks]
   ✅ All checks passing!

   === Final Status ===
   ✅ PR #456 is ready to merge!

   Summary:
   - Iterations: 2/5
   - Conflicts resolved: 2 files
   - Review comments: 10 addressed
   - CI checks: 3 fixed
   - Commits amended: 4
   ```

2. **Fix specific PR number**:
   ```
   /utils:fix-pr 789
   ```

3. **Skip review comments (only handle conflicts + CI)**:
   ```
   /utils:fix-pr --skip-reviews
   ```

   Output:
   ```
   🔄 Fixing PR #456 (skipping review comments)

   === Iteration 1/5 ===

   [Phase 1: Conflicts]
   ✅ No merge conflicts

   [Phase 2: Review Comments]
   ⏭️  Skipping (--skip-reviews flag set)

   [Phase 3: CI Checks]
   ❌ Found 2 failing checks
   - Fixing build errors...
   ✅ Pushed fixes

   === Iteration 2/5 ===
   ✅ All checks passing!

   Summary:
   - Review comments not addressed (--skip-reviews)
   - CI checks: 2 fixed
   ```

4. **Fix specific PR, skip reviews**:
   ```
   /utils:fix-pr 789 --skip-reviews
   ```

5. **Skip rebase, only fix reviews and CI**:
   ```
   /utils:fix-pr --skip-rebase
   ```

6. **Custom iteration count**:
   ```
   /utils:fix-pr -n 10
   ```

7. **Combine flags**:
   ```
   /utils:fix-pr 123 -n 3 --skip-rebase
   ```

## Arguments
- $1: PR number (optional - uses current branch if omitted)
- `-n N`: Maximum number of iterations (optional - default: 5)
- `--skip-reviews`: Skip the review comment addressing phase (Phase 2)
- `--skip-rebase`: Skip the conflict resolution phase (Phase 1)

## Guidelines

- **Max iterations**: Default 5, configurable via `-n`, ask user if more needed when limit reached
- **Timeout handling**: Always provide escape hatches for long-running checks
- **User confirmation**: Ask before expensive operations or when auto-resolution fails
- **Progress tracking**: Use TodoWrite to track each phase and iteration
- **Error recovery**: If a fix causes new failures, detect regression and warn user
- **Local validation**: Run tests/build/lint/coverage locally before pushing when possible
- **Commit hygiene**: Prefer amending over new commits (keep history clean)
- **Transparency**: Show what's being fixed and why at each phase
- **Conflict resolution**: Attempt intelligent auto-resolution, fall back to user for complex cases
- **Review integration**: Reuse logic from `/utils:address-reviews` command
- **Idempotency**: Safe to run multiple times, detects when no work needed
- **Code coverage**: CRITICAL - Coverage failures are BLOCKING, not optional. Must add tests to meet coverage requirements.

## Notes

- This command integrates three distinct workflows in each iteration:
  1. **Conflict resolution** (via rebase)
  2. **Review addressing** (reuses `/utils:address-reviews` logic)
  3. **CI fixing** (analyzes failures and implements fixes)

- The key innovation is running all three in a loop, ensuring:
  - Review fixes don't create conflicts (rebased first)
  - Review + conflict fixes don't break CI (checked last)
  - New reviews/conflicts from CI pushes are handled in next iteration

- Designed to be idempotent and safe to run multiple times
- Complex scenarios (unresolvable conflicts, flaky tests) handled gracefully with user input
- Command should detect when external blockers prevent mergeability (e.g., required approvals)
