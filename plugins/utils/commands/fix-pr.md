---
description: Iteratively fix PR/MR checks and address review comments until PR/MR is mergeable
argument-hint: "[PR/MR number] [-n N] [--skip-reviews] [--skip-rebase] [--auto-approve=no|ai|human|all]"
---

## Name
utils:fix-pr

## Synopsis
```text
/utils:fix-pr [PR/MR number] [-n N] [--skip-reviews] [--skip-rebase] [--auto-approve=no|ai|human|all]
```

## Description
The `utils:fix-pr` command automates the complete PR/MR remediation workflow by iteratively resolving merge conflicts, addressing review comments, and fixing failing CI checks until the PR/MR achieves mergeable status. Each iteration performs up to three steps in order: (1) rebase to resolve conflicts, (2) address review comments, (3) fix CI check failures. Flags allow skipping specific phases or configuring iteration count.

Works with both **GitHub Pull Requests** and **GitLab Merge Requests**. The `review` tool auto-detects the forge from the git remote.

This command is ideal for:
- Getting a PR/MR ready to merge automatically with minimal manual intervention
- Handling complex scenarios where review fixes might break CI or create conflicts
- Ensuring the PR/MR stays up-to-date with the base branch throughout the process
- Recovering from multiple rounds of feedback and test failures

## Implementation

### Step 0: Prerequisites and Setup

1. **Check `review` tool is installed**:
   ```bash
   which review
   ```
   If not found, install from `cardil/review`:
   ```bash
   git clone https://github.com/cardil/review.git ~/.local/share/review
   chmod +x ~/.local/share/review/review
   # Pick a bin dir already in PATH, or fall back to ~/.local/bin
   REVIEW_BIN_DIR=$(echo "$PATH" | tr ':' '\n' | grep -E "^$HOME/(bin|\.local/bin)$" | head -1)
   REVIEW_BIN_DIR="${REVIEW_BIN_DIR:-$HOME/.local/bin}"
   mkdir -p "$REVIEW_BIN_DIR"
   ln -sf ~/.local/share/review/review "$REVIEW_BIN_DIR/review"
   ```
   After symlinking, resolve the full path for use in this session:
   ```bash
   REVIEW=$(which review 2>/dev/null || echo "$HOME/.local/share/review/review")
   ```
   Use `$REVIEW` instead of bare `review` for all subsequent calls if needed. Optionally inform the user to add `$REVIEW_BIN_DIR` to their PATH if it was not already present.

2. **Determine PR/MR number**:
   - Use first non-flag argument if provided
   - Otherwise detect from current branch: `review get` (auto-detects current branch's PR/MR)

3. **Parse flags**:
   - `--skip-reviews`: Skip the review comment addressing phase (Phase 2)
   - `--skip-rebase`: Skip the conflict resolution phase (Phase 1)
   - `-n N`: Set maximum iterations (default: 5 if not specified)
   - `--auto-approve=VALUE`: Controls which reply types are posted without user confirmation (default: `ai`):
     - `no` -- always ask for confirmation before posting any reply
     - `ai` -- auto-post replies to AI/bot reviewers (default); always confirm before replying to humans
     - `human` -- auto-post replies to human reviewers; always confirm before replying to bots
     - `all` -- never ask for confirmation, post all replies immediately
   - Store flag state for later decision

4. **Checkout PR/MR branch**:
   ```bash
   gh pr checkout <PR_NUMBER>   # GitHub
   # or for GitLab: glab mr checkout <MR_NUMBER>
   git pull
   ```

5. **Verify clean working tree**:
   - Run `git status`
   - If uncommitted changes exist, ask user how to proceed

### Step 1: Main Remediation Loop

This loop runs until the PR/MR is mergeable or max iterations reached (default: 5, configurable via `-n`).

**At the start of each iteration, fetch full PR/MR state**:
```bash
review get <PR_NUMBER>
```

This call provides the initial snapshot for all phases:
- Unresolved review threads with thread IDs and comment content
- Review decisions (APPROVED, CHANGES_REQUESTED, etc.)
- Mergeability status and merge state (CLEAN, BLOCKED, CONFLICTING, etc.)
- CI/CD checks breakdown (failed with links, pending, passed)

`review get` is also re-run mid-iteration when polling is needed: after a rebase (to confirm mergeability updated), and while waiting for CI checks to finish. Each re-run reflects the current live state.

**Each iteration performs up to three phases in order:**

#### Phase 1: Resolve Merge Conflicts (Conditional)

**If `--skip-rebase` flag IS set:**
- Skip Phase 1 entirely
- Log: `⏭️  Skipping rebase (--skip-rebase flag set)`

**If `--skip-rebase` flag is NOT set:**

1. **Check for conflicts** from the `review get` output:
   - `Mergeable: YES` → No conflicts, skip to Phase 2
   - `Mergeable: NO` or `State: CONFLICTING` → Has conflicts, proceed with rebase
   - State `BEHIND` or `UNKNOWN` → Checks running, wait and retry

2. **If conflicts detected**:

   a. **Fetch latest base branch**:
   ```bash
   git fetch origin
   # Determine base branch from PR/MR metadata
   BASE_BRANCH=$(gh pr view <PR_NUMBER> --json baseRefName -q .baseRefName)
   # or for GitLab: glab mr view <MR_NUMBER> --output json | jq -r .target_branch
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
       - Intelligently resolve keeping PR/MR changes + incorporating base changes
       - Stage resolved file: `git add <file>`
     - Continue rebase: `git rebase --continue`
     - Push: `git push --force-with-lease`
     - Log: `✅ Resolved N conflicts in M files`

   - **Cannot auto-resolve** (complex conflicts):
      - Run `git rebase --abort`
      - Report to user:
        ```text
        ⚠️  Cannot automatically resolve conflicts in:
        - path/to/file1.go (complex logic conflict)
        - path/to/file2.py (structural changes)

        Manual resolution required.
        ```
     - Ask user: Abort / Skip conflict resolution / Manual intervention
     - If user chooses abort: Exit command
     - If user chooses skip: Continue to Phase 2 (may fail CI due to conflicts)

3. **Wait for rebase to reflect in PR/MR**:
   - Poll `review get <PR_NUMBER>` for 30 seconds to ensure the forge recognizes rebase
   - Verify mergeability status updated

#### Phase 2: Address Review Comments (Conditional)

**If `--skip-reviews` flag is NOT set:**

1. **Use data from `review get` output** fetched at the start of the iteration:
   - The output already contains all unresolved review threads with thread IDs
   - Each thread includes: thread ID, file location, comment body, author, link
   - Threads are already filtered to unresolved only

2. **Categorize and prioritize**:
   - BLOCKING → CHANGE_REQUEST → QUESTION → SUGGESTION
   - Group by file and proximity

3. **Address each comment**:

   **Before posting any reply**, determine if the reviewer is human or a bot (e.g. `coderabbitai`, `openshift-ci-robot`, `cubic-dev-ai`), then apply the `--auto-approve` policy (default: `ai`):

   | `--auto-approve` | Human reviewer | Bot/AI reviewer |
   |---|---|---|
   | `no` | confirm | confirm |
   | `ai` (default) | confirm | auto-post |
   | `human` | auto-post | confirm |
   | `all` | auto-post | auto-post |

   - **When confirmation is required**:
     - Draft the reply text and print it in a normal message:
       ```text
       📝 Drafted reply to @reviewer (thread 3423986075 in handler.go:45):
       ───────────────────────────────
       Done. Moved the context manager to wrap the file open call.
       ───────────────────────────────
       ```
     - Then use the question-type tool to ask for approval (examples: `ask_followup_question` in Roo/Zoo, `question` in Opencode, equivalent in other AI assistants):
       ```text
       Post this reply? [Yes / No / Edit]
       ```
     - Wait for user approval before calling `review reply`
     - If user chooses to edit, ask for the revised text, then post the edited version

   - **When auto-posting** (no confirmation needed):
     - Post reply immediately:
       ```bash
       echo "<reply body>" | review reply <thread_id> -
       ```

   - For code changes:
     - Implement fix
     - Commit using same strategy (amend relevant commit)
     - Push: `git push --force-with-lease`
     - Then draft and post reply as described above

   - For questions/clarifications:
     - Draft a detailed reply, confirm with user if human reviewer, then post using `review reply`

   - For declined changes:
     - Draft a technical justification, confirm with user if human reviewer, then post using `review reply`

4. **After addressing reviews**:
   - Log: `✅ Addressed N review comments (M code changes, P replies)`
   - New pushes may trigger CI, handled in Phase 3

**If `--skip-reviews` flag IS set:**
- Skip Phase 2 entirely
- Log: `⏭️  Skipping review comments (--skip-reviews flag set)`

#### Phase 3: Fix CI Check Failures

1. **Parse CI check status** from the `review get` output fetched at start of iteration:
   - The output contains the checks breakdown: failed (with links), pending, passed
   - ✅ Passing checks
   - ❌ Failed checks (with check name and URL)
   - ⏳ Pending/running checks

2. **Wait for pending checks** (if any):
   - Show status: `⏳ Waiting for N checks to complete...`
   - Re-run `review get <PR_NUMBER>` every 30 seconds to poll
   - Timeout after 10 minutes (ask user to continue waiting or proceed)

3. **If all checks pass**:
   - Log: `✅ All CI checks passing!`
   - Exit Phase 3, check loop termination condition

4. **If checks failed**:

   a. **Fetch failure details** using the URL from `review get` output:

   - **GitHub**:
     ```bash
     gh run view <RUN_ID> --log-failed
     ```
   - **GitLab** (no direct equivalent -- use interactive view or trace specific failed job):
     ```bash
     glab ci view              # interactive: navigate to failed job and view logs
     glab ci trace <JOB_ID>   # stream logs for a specific failed job ID
     ```

   b. **Analyze failures**:
   - Parse error messages, stack traces, test failures
   - Identify root causes (compilation, tests, lint, etc.)
   - Group related failures

   c. **Show summary**:
   ```text
   ❌ Failed checks (3):
   1. unit-tests: 2 test failures in pkg/api/handler_test.go
   2. lint: 5 golangci-lint issues
   3. build: compilation error in cmd/server/main.go:45
   ```

   d. **Fix issues**:
   - Read relevant files
   - Implement fixes for each failure
   - **Code coverage failures**: CRITICAL -- If coverage check fails, this is a hard requirement, not aspirational:
     - Add targeted unit tests to cover new/modified code
     - DO NOT flag as "nice to have" -- treat as blocking issue
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
   git commit --amend --no-edit
   git push --force-with-lease
   ```

   f. **Wait for new checks to start**:
   - Poll `review get <PR_NUMBER>` for 2 minutes
   - Verify new checks are queued/running

#### Loop Termination Conditions

After completing all three phases, check using `review get <PR_NUMBER>`:

1. **Success - PR/MR is mergeable**:
   - `Mergeable: YES` AND `State: CLEAN` AND all checks passing
   - Exit loop, proceed to Step 2 (Final Verification)

2. **Max iterations reached** (default 5, or value from `-n` flag):
   ```text
   ⚠️  Reached maximum iterations (N). PR/MR status:
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
   - But PR/MR still not mergeable
   - Likely issue: External blocker (required reviewer approval, blocking discussions, etc.)
   - Exit loop with warning

4. **Continue next iteration**: Loop back to start (re-run `review get`)

### Step 2: Final Verification

1. **Fetch final PR/MR status**:
   ```bash
   review get <PR_NUMBER>
   ```

2. **Check status from output**:
   - `Mergeable: YES` + `State: CLEAN` ✅
   - `Mergeable: NO` ❌ (merge conflicts)
   - `State: BLOCKED` ⚠️ (checks still running or required approvals missing)

3. **Report final state**:
   ```text
   ✅ PR/MR #123 is ready to merge!

   Status:
   - All CI checks passing
   - Review comments addressed
   - No merge conflicts

   You can merge with: gh pr merge <PR_NUMBER>
   # or for GitLab: glab mr merge <MR_NUMBER>
   ```

   OR

   ```text
   ⚠️  PR/MR #123 status:

   CI Checks: ✅ All passing
   Reviews: ✅ Addressed
   Mergeable: ❌ Has merge conflicts

   Resolve conflicts with: git rebase origin/main
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

- **Exit status**: Success (PR/MR is mergeable) or Partial (still has issues)
- **Summary report**: Statistics on fixes applied and current PR/MR state
- **Actionable next steps**: If not fully mergeable, what remains to be done

## Examples

1. **Fix PR/MR on current branch (default behavior -- all three phases)**:
   ```text
   /utils:fix-pr
   ```

   Output:
   ```text
   🔄 Fixing PR #456 on branch feature/new-api

   === Iteration 1/5 ===
   Fetching PR state... (review get 456)

   [Phase 1: Conflicts]
   ✅ No merge conflicts detected

   [Phase 2: Review Comments]
   📝 Found 8 review threads (2 blocking, 4 change requests, 2 questions)
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
   Fetching PR state... (review get 456)

   [Phase 1: Conflicts]
   ⚠️  Merge conflict detected (base branch updated)
   🔄 Rebasing on main...
   ✅ Resolved 2 conflicts in handler.go, api.go

   [Phase 2: Review Comments]
   📝 Found 2 new review threads
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

2. **Fix specific PR/MR number**:
   ```text
   /utils:fix-pr 789
   ```

3. **Skip review comments (only handle conflicts + CI)**:
   ```text
   /utils:fix-pr --skip-reviews
   ```

   Output:
   ```text
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

4. **Fix specific PR/MR, skip reviews**:
   ```text
   /utils:fix-pr 789 --skip-reviews
   ```

5. **Skip rebase, only fix reviews and CI**:
   ```text
   /utils:fix-pr --skip-rebase
   ```

6. **Custom iteration count**:
   ```text
   /utils:fix-pr -n 10
   ```

7. **Combine flags**:
   ```text
   /utils:fix-pr 123 -n 3 --skip-rebase
   ```

## Arguments
- $1: PR/MR number (optional -- uses current branch if omitted)
- `-n N`: Maximum number of iterations (optional -- default: 5)
- `--skip-reviews`: Skip the review comment addressing phase (Phase 2)
- `--skip-rebase`: Skip the conflict resolution phase (Phase 1)
- `--auto-approve=VALUE`: Controls reply confirmation behavior (default: `ai`):
  - `no` -- confirm all replies before posting
  - `ai` -- auto-post to bots, confirm for humans (default)
  - `human` -- auto-post to humans, confirm for bots
  - `all` -- post all replies without confirmation

## Guidelines

- **`review` tool**: Single `review get` call per iteration provides all data -- review threads, mergeability, and CI status. Do not make separate API calls to fetch this information.
- **Replies**: Always use `review reply <thread_id> -` (stdin) or `review reply <thread_id> <file>` -- never raw `gh api` or `glab api` calls for replies.
- **Reply confirmation**: Determined by `--auto-approve` (default: `ai`). Human reviewers require confirmation by default. Use the question-type tool (e.g. `ask_followup_question`) when available for a better UX. Always draft the reply first so the user can review or edit it when confirmation is required.
- **Max iterations**: Default 5, configurable via `-n`, ask user if more needed when limit reached
- **Timeout handling**: Always provide escape hatches for long-running checks
- **User confirmation**: Ask before expensive operations or when auto-resolution fails
- **Progress tracking**: Use TodoWrite to track each phase and iteration
- **Error recovery**: If a fix causes new failures, detect regression and warn user
- **Local validation**: Run tests/build/lint/coverage locally before pushing when possible
- **Commit hygiene**: Prefer amending over new commits (keep history clean)
- **Transparency**: Show what's being fixed and why at each phase
- **Conflict resolution**: Attempt intelligent auto-resolution, fall back to user for complex cases
- **Idempotency**: Safe to run multiple times, detects when no work needed
- **Code coverage**: CRITICAL -- Coverage failures are BLOCKING, not optional. Must add tests to meet coverage requirements.

## Notes

- This command integrates three distinct workflows in each iteration:
  1. **Conflict resolution** (via rebase)
  2. **Review addressing** (uses `review get` + `review reply`)
  3. **CI fixing** (analyzes failures and implements fixes)

- The key innovation is running all three in a loop, ensuring:
  - Review fixes don't create conflicts (rebased first)
  - Review + conflict fixes don't break CI (checked last)
  - New reviews/conflicts from CI pushes are handled in next iteration

- `review get` is the single source of truth per iteration for: unresolved threads, mergeability, and CI status.
- Works with both GitHub PRs (via `gh`) and GitLab MRs (via `glab`) -- forge is auto-detected.
- Designed to be idempotent and safe to run multiple times
- Complex scenarios (unresolvable conflicts, flaky tests) are handled by aborting the failing operation, reporting the specific error to the user, and asking whether to skip, retry, or abort the command
- Command should detect when external blockers prevent mergeability (e.g., required approvals, unresolved blocking discussions on GitLab)
