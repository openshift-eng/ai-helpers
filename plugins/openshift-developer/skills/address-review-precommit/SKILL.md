---
name: address-review-precommit
description: Fix code review findings before committing. Use when the user wants to address pre-commit review feedback, fix review findings in the current branch, or apply code review fixes and push.
---

## Name
openshift-developer:address-review-precommit

## Synopsis
```
/openshift-developer:address-review-precommit
```

## Description
Applies code review findings to the current branch by editing the code, running verification, and pushing the fixes. Designed to run after `/code-review:pre-commit-review` to close the pre-PR author loop.

## Implementation

### Step 1: Understand the review findings

Parse the provided review findings and identify all actions and improvements that need to be addressed.

### Step 2: Apply fixes

Address all actions and improvements by editing the code. For each finding:

1. Locate the relevant file and code
2. Apply the fix
3. Verify the fix is correct

### Step 3: Verify

Run verification to ensure nothing is broken:

```bash
make test 2>&1
make verify 2>&1
```

- If `make verify` generates new files, commit those too and run `make verify` again to confirm it passes
- Maximum 3 retry attempts if verification fails — fix the issues and re-run
- If verification still fails after 3 attempts, stop and report to the user

### Step 4: Commit and push

1. Amend existing commits or create new commits as appropriate
2. Push the branch to origin:
   ```bash
   git push
   ```

## Return Value
- **Verification result**: pass or fail with error details
- **Git push result**: confirming fixes are on the remote

## Examples

1. **Fix findings from a prior review step**:
   ```
   /openshift-developer:address-review-precommit
   ```
   The review findings are passed from the preceding `/code-review:pre-commit-review` output.

## Arguments
- **REVIEW_FINDINGS**: The review findings to address (passed inline or from a prior review step)
- **SUBAGENT_PROMPT**: Optional additional instructions for the fixing agent

## Guidelines

- Fix every issue identified in the review — all actions and improvements
- Do NOT run commands that reveal git credentials like `git remote -v` or `git remote get-url origin`
- If verification generates new files, commit those and re-verify
- Commit all fixes and push to origin
