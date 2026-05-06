---
description: Process /save and /drop comments on a pruning PR, restore or remove items, and update .pruneprotect
argument-hint: "[PR number or URL]"
---

## Name
marketplace-ops:prune-update

## Synopsis
```text
/marketplace-ops:prune-update [PR number or URL]
```

## Description
Reads comments on a pruning PR to find `/save <path>` and `/drop <path>` directives.

For each **saved** item:
1. Restores the files from the base branch.
2. Adds the path to `.pruneprotect` permanently, with a comment noting who requested it and when.
3. Pushes a new commit to the PR branch (never force-pushes).
4. Updates the PR body to mark saved items.

For each **dropped** item:
1. If the item was previously `/save`d: removes its files again, removes it from `.pruneprotect`.
2. If the item is a new addition (not in the original manifest): removes its files and adds a new row to the manifest.
3. For surviving plugins that lose commands or skills, bumps the patch version in `plugin.json`.
4. Pushes a new commit to the PR branch (never force-pushes).
5. Updates the PR body to reflect the drop.

## Arguments
- `$1`: (Optional) PR number or URL. If omitted, searches for the most recent open pruning PR by the current user.

## Implementation

### Step 1: Find the Pruning PR

If a PR number or URL was provided, use it directly. Otherwise, find the most recent open pruning PR:

```bash
gh pr list --author="@me" --state=open --search="prune stale marketplace" --json number,title,url,headRefName --limit 5
```

Select the first result. If no pruning PR is found, report this to the user and stop.

### Step 2: Read PR Comments for /save and /drop Directives

Fetch all comments on the PR (both issue comments and review comments), including the author's association to the repository:

```bash
# Issue comments
gh api repos/{owner}/{repo}/issues/{pr_number}/comments \
  --jq '.[] | {author: .user.login, association: .author_association, body: .body}'

# Review comments
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments \
  --jq '.[] | {author: .user.login, association: .author_association, body: .body}'
```

Parse each comment body for lines matching `/save <path>` or `/drop <path>`. **Only accept directives from trusted participants** — those with `author_association` of `OWNER`, `MEMBER`, or `COLLABORATOR`. Skip directives from other associations and log a warning (e.g., "Ignoring `/drop` from @user — not a repository collaborator").

For each accepted match, record:
- The directive type (`save` or `drop`)
- The path
- The GitHub username of the commenter

Deduplicate paths. If a path has both `/save` and `/drop` from different comments, the **latest comment wins** (last-writer-wins). If no valid directives are found, report this and stop.

### Step 3: Validate Paths

**For `/save` paths:** Cross-reference against the removal manifest table in the PR body. The path must appear in the manifest (and not already be marked `[SAVED]`) — if it does not, it was either already saved, was not part of this pruning cycle, or is a typo. Report invalid paths to the user but continue processing valid ones.

**For `/drop` paths — two valid cases:**
1. **Undo a previous save:** The path appears in the manifest with `[SAVED]` strikethrough markup. This reverses the save.
2. **New drop:** The path does NOT appear in the manifest but exists on the base branch. The reviewer is requesting an additional removal beyond what the automated pruning flagged. Verify the path exists on the base branch before accepting. Also verify the path is not listed in `.pruneprotect` — if it is, warn that the item is protected and skip it unless the `/drop` comment explicitly says to override (e.g., `/drop --force plugins/foo/`).

Report paths that fail validation but continue processing valid ones.

### Step 4: Checkout the PR Branch

```bash
gh pr checkout {pr_number}
```

### Step 5: Process Saved Items

Get the base branch from the PR:
```bash
base_branch=$(gh pr view {pr_number} --json baseRefName --jq '.baseRefName')
```

For each valid `/save` path, restore from the base branch:
```bash
git checkout {upstream_remote}/{base_branch} -- {path}
```

Use the upstream remote (not origin) to ensure the base branch is current.

### Step 6: Process Dropped Items

For each valid `/drop` path:

**If undoing a previous save:**
1. Remove the files from the working tree:
   ```bash
   # Full plugin removal
   git rm -rf {path}
   # Individual file removal
   git rm {path}
   ```
2. Remove the path's entry from `.pruneprotect` (including its comment line).

**If adding a new drop:**
1. Remove the files from the working tree (same `git rm` commands as above).
2. For surviving plugins that lose commands or skills (not a full plugin removal), bump the patch version in `plugins/{plugin-name}/.claude-plugin/plugin.json` (e.g., `0.0.5` → `0.0.6`).

### Step 7: Update .pruneprotect

For `/save` items: append each saved path to `.pruneprotect` with a comment indicating who requested the save:

```
# Saved by @username on 2026-05-05
plugins/foo/
```

For `/drop` items that undo a save: remove the path and its comment from `.pruneprotect`.

If `.pruneprotect` does not exist, create it with the saved entries.

### Step 8: Sync and Commit

Run `make update` to regenerate marketplace.json and docs after changes:
```bash
make update
git add -A
```

Create a new commit (never amend, never force-push):
```bash
git commit -m "$(cat <<'EOF'
chore: process save/drop directives from pruning PR

Restored and added to .pruneprotect:
- plugins/foo/ — saved by @username

Dropped:
- plugins/bar/commands/baz.md — dropped by @otherperson

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Step 9: Push

Push the new commit with a regular push:
```bash
git push
```

### Step 10: Update PR Body

Read the current PR body:
```bash
gh pr view {pr_number} --json body --jq '.body'
```

**For `/save` paths:** In the removal manifest table, find the rows for saved paths and apply strikethrough with a `[SAVED]` tag. For example, change:

```
| plugin | `plugins/foo/` | No commits in 7 months, v0.0.1 |
```

To:

```
| ~~plugin~~ | ~~`plugins/foo/`~~ | ~~SAVED by @username~~ |
```

**For `/drop` paths that undo a save:** Remove the strikethrough and `[SAVED]` tag, restoring the row to its original state with the original reason (if available from git history of the PR body), or use a new reason:

```
| plugin | `plugins/foo/` | Dropped by @username |
```

**For new `/drop` paths:** Add a new row to the manifest table:

```
| command | `plugins/bar/commands/baz.md` | Manually dropped by @username |
```

Update the PR body:
```bash
gh pr edit {pr_number} --body "{updated_body}"
```

### Step 11: Comment on PR

Add a summary comment:
```bash
gh pr comment {pr_number} --body "$(cat <<'EOF'
Processed `/save` and `/drop` comments.

**Saved** (restored and added to `.pruneprotect`):
- `plugins/foo/` — saved by @username

**Dropped** (removed):
- `plugins/bar/commands/baz.md` — dropped by @otherperson

Remaining removals: N items.
EOF
)"
```

Omit the **Saved** or **Dropped** section if there are no items for that category.

### Step 12: Report Results

Print a summary to the user: what was restored, what was dropped, what remains in the PR, and the updated PR URL.

## Return Value
A summary of saved/dropped items and the updated PR state.

## Examples

1. **Process saves and drops on a specific PR:**
   ```text
   /marketplace-ops:prune-update 42
   ```

2. **Auto-detect the pruning PR:**
   ```text
   /marketplace-ops:prune-update
   ```

## Comment Format Reference

On the pruning PR, trusted collaborators can comment:

```text
/save plugins/foo/                    # Restore and permanently protect
/drop plugins/bar/commands/baz.md     # Undo a /save, or manually add a removal
/drop --force plugins/protected/      # Drop even if listed in .pruneprotect
```
