---
description: Interactive git bisect assistant with pattern detection and automation
argument-hint: "[good-commit] [bad-commit]"
---

## Name

git:bisect

## Synopsis

```
/git:bisect                       # Fully interactive - will ask for all inputs
/git:bisect [good-commit] [bad-commit]  # With commit references
```

## Description

The `git:bisect` command is an interactive git bisect assistant that helps find the exact commit that introduced a specific change (bug, behavior change, feature, performance regression, etc.) using binary search.

**What This Command Does:**

1. **Guides you through setup** - Validates commits, checks for conflicts
2. **Presents commits for evaluation** - Shows relevant info about each commit
3. **Learns from your decisions** - Detects patterns in your choices
4. **Can automate** - If it understands your criterion, it can evaluate automatically (with your permission)
5. **Reports the result** - Shows the culprit commit with full details

### Terminology

Git bisect uses confusing terms. This command uses clearer labels:

| What You See                | Git Term | Meaning                                             |
| --------------------------- | -------- | --------------------------------------------------- |
| "Change IS in the code"     | `bad`    | The change you're looking for EXISTS in this commit |
| "Change is NOT in the code" | `good`   | The change you're looking for does NOT exist yet    |

**Never use "good" or "bad" alone - always explain what they mean in context.**

### Workflow

```
1. Provide (or select) reference commits
         ↓
2. Describe what change you're looking for
         ↓
3. [If criterion is clear] Confirm understanding → Choose manual/auto
         ↓
4. Evaluate commits (manually or automatically)
         ↓
5. Receive final report with culprit commit
         ↓
6. Clean up (git bisect reset)
```

### Commands During Bisect

At any point during the bisect, you can:

- **"show diff"** or **"more details"** - See the full diff for the current commit
- **"skip"** - Skip a commit that cannot be tested (won't build, etc.)
- **"abort"** - Cancel the bisect and return to your original branch
- **"automate"** - Ask to enable automation (if pattern detected)

### Tips

- You can test the current state by building/running your project between steps
- Use `skip` if a commit cannot be tested (build failure, unrelated issue)
- The process uses binary search: ~log₂(N) steps for N commits
- You can abort at any time; the session will be cleanly terminated

## Implementation

Arguments provided: $ARGUMENTS

Parse arguments:

- If two arguments: first = commit where change is NOT present, second = commit where change IS present
- If one argument: ask which one it represents
- If no arguments: proceed to interactive mode

---

### Critical Rules

#### Rule 1: Never decide without asking first

You may NEVER execute `git bisect good` or `git bisect bad` without explicit user confirmation.
Even if you're 100% certain, you MUST ask first. No exceptions.

#### Rule 2: Early criterion detection (≥70% confidence)

If the user describes a criterion that you can verify programmatically (e.g., "when dependency X was updated to version > Y"), and you have ≥70% confidence you understand it correctly:

1. **BEFORE evaluating any commit**, present your understanding with maximum precision:

   > "Based on your description, I believe you're looking for:
   > **[exact criterion with specific details]**
   >
   > To verify this, I would check: [specific file/command/method]
   >
   > Is this correct?"

2. **Wait for user response.** Then:
   - **If user confirms** the criterion is correct, ask:

     > "Would you like me to automatically evaluate commits based on this criterion?
     > I will show each decision as I make it."
     - If user says **yes** → Enable automation mode
     - If user says **no** → Continue in manual mode (ask for each commit)

   - **If user says the criterion is wrong**:
     - Say: "I understand. Please clarify what you're looking for."
     - Reset your understanding completely
     - Enter manual mode
     - Continue learning from user responses

#### Rule 3: Learning from manual decisions

If you don't have ≥70% confidence initially, or after a criterion reset:

1. Present commit info and ask the user for their verdict
2. Analyze patterns in their decisions (files, authors, keywords)
3. When confidence reaches ≥70%, present your understanding and follow Rule 2

#### Rule 4: Automation flow

When automation is enabled (user explicitly said yes):

1. For each commit:
   - Show the commit being evaluated
   - Show your decision and the reasoning
   - Execute `git bisect good` or `git bisect bad`
2. If any commit doesn't clearly match the criterion, STOP and ask the user
3. Continue until bisect completes

---

### Phase 1: Initialization

#### Step 1.1: Check for Existing Bisect Session

Run `git bisect log` to check if a bisect is in progress.

**If bisect IS in progress:**

1. Show the current state: how many steps done, current commit
2. Ask the user:
   - **Continue**: Resume the existing session
   - **Abort**: Run `git bisect reset` and optionally start fresh
   - **View details**: Show full bisect log before deciding

**If NO bisect in progress:** Continue to Step 1.2

#### Step 1.2: Check for Uncommitted Changes

Run `git status --porcelain` to check for uncommitted changes.

**If there are uncommitted changes:**

1. Warn: "You have uncommitted changes. Git bisect will checkout different commits which may conflict with your changes."
2. Offer options:
   - **Stash changes**: Run `git stash push -m "Pre-bisect stash"`
   - **Proceed anyway**: Continue (user accepts the risk)
   - **Abort**: Stop to handle manually

#### Step 1.3: Get Reference Commits

**If commits were provided as arguments:**

1. Validate using `git rev-parse <commit>`
2. Show what each commit represents (run `git log -1 --format="%h %s" <commit>`)
3. Confirm: "Commit X is where the change is NOT present, commit Y is where it IS present. Correct?"

**If commits were NOT provided:**

1. Show recent history: `git log --oneline -20`
2. Ask: "Which commit is known to NOT have the change you're looking for? (This will be the 'good' starting point)"
3. Ask: "Which commit IS known to have the change? (This will be the 'bad' starting point)"

**Validate the relationship:**

- The "good" commit (without change) should be an ancestor of the "bad" commit (with change)
- If they appear reversed, explain and offer to swap

#### Step 1.4: Understand the Search Criterion

Ask the user:

> **What change are you looking for?**
>
> Please describe:
>
> - What behavior or code changed?
> - How can you determine if a commit has or doesn't have this change?
> - Is there a specific file, function, or behavior to check?

Store this description for analysis.

#### Step 1.5: Early Criterion Detection (CRITICAL)

**After the user describes the change, analyze their response:**

If you have ≥70% confidence that you understand a verifiable criterion:

1. Present your understanding with maximum precision:

   > "Based on your description, I believe you're looking for:
   > **[exact criterion]**
   >
   > To verify this, I would check: [specific method]
   >
   > Is this correct?"

2. **WAIT for user response before proceeding.**

3. If user confirms:

   > "Would you like me to automatically evaluate commits based on this criterion?
   > I will show each decision as I make it."
   - If **yes** → Set automation mode = true
   - If **no** → Set automation mode = false (manual mode)

4. If user says criterion is wrong:
   - Ask for clarification
   - Set automation mode = false
   - Proceed to bisect in manual mode

**Only proceed to Step 1.6 after this interaction is complete.**

#### Step 1.6: Start Bisect

Execute:

```bash
git bisect start
git bisect bad <commit-with-change>
git bisect good <commit-without-change>
```

Parse the output to show:

- Number of revisions to test
- Estimated number of steps (approximately log2 of revisions)
- The first commit to test

---

### Phase 2: Evaluation Loop

#### Internal State to Track

Maintain a session log throughout the bisect:

```
## Session Log

**Search criterion**: [user's description]
**Detected pattern**: [none yet / description]
**Confidence level**: [0-100%]
**Automation enabled**: [no / yes]

| Step | Commit | Files Changed | Verdict | Observation |
|------|--------|---------------|---------|-------------|
```

#### For Each Commit

##### Step 2.1: Present Commit Information

Display:

```
═══════════════════════════════════════════════════════════
TESTING COMMIT [step X of ~Y estimated]
═══════════════════════════════════════════════════════════

Commit:  [short hash]
Author:  [author name]
Date:    [date]
Message: [subject line]

Files Changed:
[output of: git show --stat --format="" HEAD]

Summary: [X files changed, Y insertions(+), Z deletions(-)]
═══════════════════════════════════════════════════════════
```

##### Step 2.2: Evaluate Commit (depends on mode)

**If AUTOMATION MODE is enabled:**

1. Verify the criterion for this commit (run the check you described to user)
2. Show the result:
   ```
   Commit [hash]: Checking [criterion]...
   Result: [what you found]
   Decision: Change [IS / is NOT] in the code → marking as [bad/good]
   ```
3. Execute `git bisect bad` or `git bisect good`
4. If the result is unclear or doesn't match the criterion cleanly, STOP and ask user

**If MANUAL MODE (automation not enabled):**

Ask the user:

```
Is the change you're looking for present in this commit?

[1] Change IS in the code (will mark as 'bad')
[2] Change is NOT in the code (will mark as 'good')
[3] Cannot test this commit (skip)
[4] Show more details (diff, full message)
[5] Abort bisect
```

**If in manual mode and confidence reaches ≥70%:**

Before showing options, present your understanding:

```
I've noticed a pattern: [description of what you've observed]

Based on this, I believe the change [IS / is NOT] in this commit.

Is this the criterion you're using? If so, would you like me to automate?

[1] Yes, that's correct - please automate
[2] Yes, that's correct - but I'll decide manually
[3] No, that's not what I'm looking for
[4] Show more details first
```

If user chooses [1] → Enable automation mode
If user chooses [2] → Stay in manual mode but show suggestions
If user chooses [3] → Reset pattern analysis, continue manual

##### Step 2.3: Process Response

Based on user response:

| Response           | Action                                 |
| ------------------ | -------------------------------------- |
| Change IS in code  | Run `git bisect bad`, record in log    |
| Change NOT in code | Run `git bisect good`, record in log   |
| Skip               | Run `git bisect skip`, note why in log |
| Show details       | Display requested info, ask again      |
| Abort              | Confirm, then run `git bisect reset`   |

##### Step 2.4: Update Session Log

After each decision, update the internal log with:

- Commit hash
- Key files changed
- User's verdict
- Any observations about patterns

##### Step 2.5: Pattern Analysis (Manual Mode Only)

When in manual mode, after each user decision:

1. **Analyze correlations:**
   - File patterns: Do "change present" commits touch specific files?
   - Author patterns: Is a specific author correlated?
   - Message patterns: Are there specific keywords?

2. **Update confidence** based on how well patterns predict user decisions

3. **When confidence reaches ≥70%:**
   - Present your understanding in Step 2.2 (as described above)
   - This may result in switching to automation mode if user accepts

---

### Phase 3: Completion

#### Detecting Completion

Git bisect outputs "X is the first bad commit" when complete. Watch for this phrase.

#### Final Report

When bisect completes, present:

```
═══════════════════════════════════════════════════════════
BISECT COMPLETE - CULPRIT FOUND
═══════════════════════════════════════════════════════════

THE COMMIT THAT INTRODUCED THE CHANGE
─────────────────────────────────────

Commit:  [full hash]
Author:  [author name] <[email]>
Date:    [full date]

Message:
[full commit message]

Files Changed:
[git show --stat --format="" <hash>]

CHANGE SUMMARY
─────────────────────────────────────

Based on your search criterion: "[user's original description]"

This commit appears to have introduced the change by:
[Analysis of what changed in this commit that matches the criterion]

EVALUATION HISTORY
─────────────────────────────────────

| Step | Commit  | Verdict              | Key Files        |
|------|---------|----------------------|------------------|
| 1    | abc1234 | Change present       | src/main.rs      |
| 2    | def5678 | Change NOT present   | tests/test.rs    |
| ...  | ...     | ...                  | ...              |

SUGGESTED NEXT STEPS
─────────────────────────────────────

1. View full diff: git show [hash]
2. Compare with parent: git diff [hash]^..[hash]
3. Revert this commit: git revert [hash]
4. Blame specific file: git blame [file] | grep [hash]

═══════════════════════════════════════════════════════════
```

#### Cleanup

Ask:

> "The bisect session is complete. Would you like me to run `git bisect reset` to return to your original branch?"

If yes, run `git bisect reset` and confirm the branch returned to.

---

### Error Handling

#### Common Errors and Solutions

| Error                                             | Solution                                                             |
| ------------------------------------------------- | -------------------------------------------------------------------- |
| "You need to start by 'git bisect start'"         | Bisect was interrupted; restart the process                          |
| "Bad rev input: X"                                | Invalid commit reference; ask for correction and show recent commits |
| "Some good revs are not ancestors of the bad rev" | Commits are in wrong order; explain and offer to swap                |
| Merge conflict during checkout                    | Suggest `git bisect skip` for this commit                            |
| "Cannot bisect on a detached HEAD"                | This shouldn't happen normally; offer to reset                       |

#### Abort Handling

If user requests abort at any point:

1. Confirm: "Are you sure you want to abort? The bisect progress will be lost."
2. If confirmed: Run `git bisect reset`
3. Show the branch/commit returned to
4. Optionally: Offer to save the bisect log first with `git bisect log > bisect-log-$(date +%Y%m%d-%H%M%S).txt`

## Examples

1. **Fully interactive - no arguments**:

   ```
   /git:bisect
   ```

   Will show recent history and ask you to select commits.

2. **With commit references**:

   ```
   /git:bisect v1.28.0 HEAD
   ```

   Uses tag v1.28.0 as the "good" commit (change NOT present) and HEAD as the "bad" commit (change IS present).

3. **With commit hashes**:

   ```
   /git:bisect abc1234 def5678
   ```

4. **Mixed references**:
   ```
   /git:bisect v1.0.0 main
   ```

## Return Value

- **Final Report**: A comprehensive report showing:
  - The culprit commit (full hash, author, date, message)
  - Files changed in that commit
  - Analysis of how the commit matches the search criterion
  - Evaluation history table
  - Suggested next steps (view diff, revert, blame)

- **Session cleanup**: Offers to run `git bisect reset` to return to original branch

## Arguments

- **$1** `[good-commit]` (optional): A commit reference (hash, tag, branch) where the change is **NOT present**. This is the older, "known good" state.
- **$2** `[bad-commit]` (optional): A commit reference where the change **IS present**. This is the newer state that contains the change you're looking for.

**Notes:**

- If no arguments are provided, the command will show recent history and ask you to select commits
- If only one argument is provided, the command will ask which one it represents (good or bad)
- Commit references can be: hashes, tags, branch names, HEAD, HEAD~N, etc.
