---
name: update
description: Use when processing /save and /drop comments on a marketplace pruning PR. Reads PR comments, validates directives from trusted collaborators, restores saved items, removes dropped items, updates .pruneprotect, and pushes changes.
---

# Marketplace Prune Update

Processes `/save` and `/drop` directives from comments on a pruning PR.

## Arguments

- `$1`: (Optional) PR number or URL. If omitted, searches for the most recent open pruning PR.

## Procedure

### Step 1: Find the Pruning PR

If a PR number or URL was provided, use it. Otherwise find the most recent open pruning PR:

```bash
gh pr list --state=open --search="prune stale marketplace" --json number,title,url,headRefName --limit 5
```

Select the first result. If no pruning PR is found, report this and stop.

### Step 2: Collect Directives

Run the comment processing script to extract validated `/save` and `/drop` directives:

```bash
python3 plugins/marketplace-ops/scripts/process-comments.py \
  --repo openshift-eng/ai-helpers \
  --pr-number <PR_NUMBER>
```

The script filters to trusted collaborators (OWNER, MEMBER, COLLABORATOR), validates paths, and deduplicates (last-writer-wins). If no valid directives are found, report this and stop.

### Step 3: Checkout the PR Branch

```bash
gh pr checkout <PR_NUMBER>
```

### Step 4: Process Changes

Get the base branch:
```bash
base_branch=$(gh pr view <PR_NUMBER> --json baseRefName --jq '.baseRefName')
```

For each `/save` path, restore from the base branch and update `.pruneprotect`:
```bash
python3 plugins/marketplace-ops/scripts/apply-changes.py \
  --action save \
  --paths <comma-separated-paths> \
  --base-branch "$base_branch" \
  --repo-root . \
  --usernames <comma-separated-usernames>
```

For each `/drop` path, remove files and update `.pruneprotect`:
```bash
python3 plugins/marketplace-ops/scripts/apply-changes.py \
  --action drop \
  --paths <comma-separated-paths> \
  --base-branch "$base_branch" \
  --repo-root . \
  --usernames <comma-separated-usernames>
```

### Step 5: Commit and Push

```bash
make update
git add -A
git commit -m "chore: process save/drop directives from pruning PR

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

### Step 6: Update PR Body and Comment

```bash
python3 plugins/marketplace-ops/scripts/update-pr-body.py \
  --repo openshift-eng/ai-helpers \
  --pr-number <PR_NUMBER> \
  --saves <comma-separated-save-paths> \
  --drops <comma-separated-drop-paths>
```

Post a summary comment with `gh pr comment`.

### Step 7: Report

Print a summary of saved/dropped items and the updated PR URL.
