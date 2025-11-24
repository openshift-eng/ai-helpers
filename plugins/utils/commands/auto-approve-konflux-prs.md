---
description: Automate approving Konflux bot PRs for the given repository by adding /lgtm and /approve
argument-hint: <target-repository>
---

## Name

utils:auto-approve-konflux-prs

## Synopsis

/utils:auto-approve-konflux-prs <target-repository>

## Description

The command automates the approval of open PRs created by the `red-hat-konflux[bot]` for the given repository.

It filters all open PRs from the given repository, checks whether the PR already has `/lgtm` and `/approve` comments, verifies that all required checks (CI jobs or other mandatory checks) have passed, and if any labels/comments are missing and all checks succeed, posts `/lgtm` and `/approve` comments to trigger approval.

This ensures that PRs are only auto-approved if all required checks succeed and the author is `red-hat-konflux[bot]`, reducing the risk of approving failing or unauthorized changes.


## Arguments

- **$1 – target-repositories** *(required)*: GitHub repository in `OWNER/REPO` format.
  - Example: openshift/multiarch-tuning-operator.

## Implementation

The command executes the following workflow:

### 1. Restrict Author

The command only processes PRs authored by `red-hat-konflux[bot]`. If a PR from any other author is encountered, it reports an error such as below:
```
⚠️ Only PRs from red-hat-konflux[bot] can be automatically processed
```
and exits.

### 2. Get Open PRs

Fetch all open PRs authored by `red-hat-konflux[bot]` for the specified repository:

```bash
gh pr list --repo <target-repository> --author app/red-hat-konflux --state open --json number,title,baseRefName,labels
```
- Extract: number,title,baseRefName,labels

### 3. Check CI Status and Labels

#### **For Each PR:**:

1. Fetch detailed PR information:
```bash
gh pr view <PR_NUMBER> --repo <target-repository> --json statusCheckRollup,labels
```
- Extract: statusCheckRollup,labels
- Handle errors: If PR is inaccessible, log warning and skip

2. Verify all required checks:
- Verify all required checks have "conclusion": "SUCCESS"
- If any check has failed or is pending(except one pending tide job), skip adding /lgtm or /approve and log:
```
⚠️ Skipping PR #<PR_NUMBER>: CI checks not all passed
```

3. Inspect labels:
    - Check for lgtm label
    - Check for approved label

4. Add missing labels via comments:
   - If /lgtm is missing, post a comment /lgtm
   - If /approve is missing, post a comment /approve
   - If both are missing, post a single comment containing both commands.

5. Log each action:
```
✅ Added /lgtm and/or /approve to PR #<PR_NUMBER>: <PR_TITLE> (merge into <MERGE_BRANCH>)
```

## Return Value

- **Claude agent text**: Summary of processed PRs and actions taken.
- **Side effects**:
  - Comments posted to PRs to trigger /lgtm and /approve.
  - Progress updates for multiple PRs.

## Examples

1. **Process all open PRs from `red-hat-konflux[bot]` in a repository**:

  ```
  /utils:auto-approve-konflux-prs openshift/multiarch-tuning-operator
  ```
   
  Output:
  ```
  Processing 3 open Konflux PRs...  
  [1/3] PR #84 - chore(deps): update konflux references (merge into main)
  ✅ Added /lgtm and /approve (all CI passed)
  
  [2/3] PR #83 - chore(deps): update konflux references (merge into v1.x)
  ⚠️ Skipping: CI checks not all passed
  
  [3/3] PR #82 - chore(deps): update konflux references (merge into fbc)
  ✅ Added /lgtm (already had /approve, all CI passed)
  
  Summary:
  ✅ Processed 2 PRs successfully, 1 skipped due to CI failures
  ```

## Prerequisites

### Required Tools

1. **GitHub CLI (`gh`)**: Must be installed and authenticated
   - Install: `brew install gh` (macOS) or see [GitHub CLI docs](https://cli.github.com/)
   - Authenticate: `gh auth login`
   - Verify: `gh auth status`

2. **Access to GitHub Repositories**: Must have read access to repos where PRs are located
   - PRs in private repos require appropriate GitHub permissions
   - Public repos should work without additional configuration

### Required Permissions

1. **GitHub Permissions**:
   - Read access to pull requests
   - Write access to create comments on pull requests

## Error Handling

- **Repository inaccessible**: Reports error and exits.
- **PRs authored by someone other than `red-hat-konflux[bot]`**: Reports error and exits.
- **No open PRs from Konflux bot**: Logs "No PRs to process".
- **GitHub authentication failure**: Suggests re-login with `gh auth login`.
- **Comment posting failure**: Logs PR number and error for manual review.

## Notes

- The command only processes open PRs authored by `app/red-hat-konflux`.
- Compatible with repositories in which the user has write permission to post PR comments.
- Designed to minimize manual PR review effort and maintain consistent approvals.
