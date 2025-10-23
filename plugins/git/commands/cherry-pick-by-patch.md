---
argument-hint: <commit_hash>
description: Cherry-pick git commit into current branch by "patch" command
---

## Name
git:cherry-pick-by-patch

## Synopsis
```
/git:cherry-pick-by-patch commit_hash
```

## Description

The `/git-cherry-pick-by-patch commit_hash` command cherry-picks commit with hash
`commit_hash` into current branch. Rather then doing `git cherry-pick commit_hash`,
the command streams the output of `git show commit_hash` to
`patch -p1 --no-backup-if-mismatch`, and then commit changes with commit message
from `commit_hash` commit.

## Workflow

### Pre-requisites

The commit with hash `commit_hash` must exist. To verify that use:
```bash
git show commit_hash
```
and check if exit code is zero.

Fail, if there is no `commit_hash` in the current repository checkout.

### Cherry-pick `commit_hash` into current branch

1. Execute command
    ```bash
    git show commit_hash | patch -p1 --no-backup-if-mismatch
    ```
and check if exit code is zero. Fail if exit code is not zero.

2. Find files removed from local checkout by the patch command and execute `git rm` for them.

3. Find files added or modified by the patch command and execute `git add` for them.

4. Commit changes by `git commit` command and use commit title and description from `commit_hash` commit.

## Arguments

- **$1** (required): Commit hash (e.g., `902409c0`) of commit to cherry-pick.
