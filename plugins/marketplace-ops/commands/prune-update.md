---
description: Process /save comments on a pruning PR, restore items, and update .pruneprotect
argument-hint: "[PR number or URL]"
---

## Name
marketplace-ops:prune-update

## Synopsis
```
/marketplace-ops:prune-update [PR number or URL]
```

## Description
Reads comments on a pruning PR to find `/save <path>` directives. For each saved item:
1. Restores the files from the base branch.
2. Adds the path to `.pruneprotect` permanently, with a comment noting who requested it and when.
3. Pushes a new commit to the PR branch (never force-pushes).
4. Updates the PR body to mark saved items.

## Arguments
- `$1`: (Optional) PR number or URL. If omitted, searches for the most recent open pruning PR by the current user.

## Implementation

### Step 1: Find the Pruning PR

If a PR number or URL was provided, use it directly. Otherwise, find the most recent open pruning PR:

```bash
gh pr list --author="@me" --state=open --search="prune stale marketplace" --json number,title,url,headRefName --limit 5
```

Select the first result. If no pruning PR is found, report this to the user and stop.

### Step 2: Read PR Comments for /save Directives

Fetch all comments on the PR (both issue comments and review comments):

```bash
# Issue comments
gh api repos/{owner}/{repo}/issues/{pr_number}/comments --jq '.[] | {author: .user.login, body: .body}'

# Review comments
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments --jq '.[] | {author: .user.login, body: .body}'
```

Parse each comment body for lines matching `/save <path>`. For each match, record:
- The path to save
- The GitHub username of the commenter

Deduplicate paths. If no `/save` directives are found, report this and stop.

### Step 3: Validate Save Paths

Cross-reference each `/save <path>` against the removal manifest table in the PR body. The path must appear in the manifest — if it does not, it was either already saved, was not part of this pruning cycle, or is a typo. Report invalid paths to the user but continue processing valid ones.

### Step 4: Checkout the PR Branch

```bash
gh pr checkout {pr_number}
```

### Step 5: Restore Saved Items

Get the base branch from the PR:
```bash
base_branch=$(gh pr view {pr_number} --json baseRefName --jq '.baseRefName')
```

For each valid saved path, restore from the base branch:
```bash
git checkout {upstream_remote}/{base_branch} -- {path}
```

Use the upstream remote (not origin) to ensure the base branch is current.

### Step 6: Update .pruneprotect

Append each saved path to `.pruneprotect` with a comment indicating who requested the save:

```
# Saved by @username on 2026-05-05
plugins/foo/
```

If `.pruneprotect` does not exist, create it with the saved entries.

### Step 7: Sync and Commit

Run `make update` to regenerate marketplace.json and docs after restoring items:
```bash
make update
git add -A
```

Create a new commit (never amend, never force-push):
```bash
git commit -m "$(cat <<'EOF'
chore: restore saved items from pruning PR

Restored and added to .pruneprotect:
- plugins/foo/ — saved by @username
- plugins/bar/commands/baz.md — saved by @otherperson

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Step 8: Push

Push the new commit with a regular push:
```bash
git push
```

### Step 9: Update PR Body

Read the current PR body:
```bash
gh pr view {pr_number} --json body --jq '.body'
```

In the removal manifest table, find the rows for saved paths and apply strikethrough with a `[SAVED]` tag. For example, change:

```
| plugin | `plugins/foo/` | No commits in 7 months, v0.0.1 |
```

To:

```
| ~~plugin~~ | ~~`plugins/foo/`~~ | ~~SAVED by @username~~ |
```

Update the PR body:
```bash
gh pr edit {pr_number} --body "{updated_body}"
```

### Step 10: Comment on PR

Add a summary comment:
```bash
gh pr comment {pr_number} --body "$(cat <<'EOF'
Processed `/save` comments. Restored and added to `.pruneprotect`:

- `plugins/foo/` — saved by @username
- `plugins/bar/commands/baz.md` — saved by @otherperson

Remaining removals: N items.
EOF
)"
```

### Step 11: Report Results

Print a summary to the user: what was restored, what remains in the PR, and the updated PR URL.

## Return Value
A summary of restored items and the updated PR state.

## Examples

1. **Process saves on a specific PR:**
   ```
   /marketplace-ops:prune-update 42
   ```

2. **Auto-detect the pruning PR:**
   ```
   /marketplace-ops:prune-update
   ```
