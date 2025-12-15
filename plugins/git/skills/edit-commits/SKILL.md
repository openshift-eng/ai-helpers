---
name: git-edit-commits
description: Edit a series of existing commits in a Git branch using fixup commits or interactive rebase, resolving any merge conflicts that result. Use when you need to reorder commits or amend commits other than the current branch HEAD. This will often occur e.g. when fixing errors in previous local commits, or when addressing review feedback.
---

Before editing existing commits, you MUST ALWAYS check the current log of commits in the branch. This is MANDATORY. Do NOT rely on your memory of how you left the branch, because I may have edited the branch directly in the meantime without you seeing it. Previous edits or rebases that you have done can also change the commit hashes.

Git commits contain metadata beyond just the diff and commit message, so preserve this by having Git modify existing commits by amending or squashing instead of doing a soft reset and recreating a brand new commit.

Avoid actually moving the branch to a different base commit when editing branches, even though you have to use the "rebase" command. Use the `--keep-base` argument to avoid pulling in more recent changes from the upstream branch. If you are specifically asked to move to a new base commit, do so in a separate step. Always prefer a remote tracking branch over a local branch as the base branch (e.g. `origin/main` instead of `main`), since you don't know what state the local branch is in.

Amending commits with fixups
----------------------------

To commit an amendment to a previous commit, use the command:

```bash
git commit -m '<commit message>' --fixup=<commit-hash>
```

This creates a new commit at the head of the branch that is identified to Git as a fix to the specified one. To also provide a new commit message, use the command:

```bash
git commit -m '<commit message>' --fixup=amend:<commit-hash>
```

You may need to do several commits with different targets, as often the sources of e.g. lint errors in a CI run originate in several different commits within a PR.

Once all changes are committed, squash them into the intended commits by running:

```bash
git rebase --autosquash --keep-base <tracking-branch>
```

Amending commits with interactive rebase
----------------------------------------

An alternative is to do an interactive rebase. When doing an interactive rebase, remember that you are not running bash commands in an interactive console and cannot use the regular editor. You MUST use the environment variable `GIT_SEQUENCE_EDITOR` to pass a command to edit the patch sequence non-interactively. For example:

```bash
GIT_SEQUENCE_EDITOR="sed -i -e '/<commit-hash>/ s/^pick/edit/'" git rebase --interactive --keep-base <tracking-branch>
```

If you run an interactive rebase without `GIT_SEQUENCE_EDITOR` it will complete immediately without allowing you to edit commits.

If necessary, you can alter the course of an in-progress rebase with `git rebase --edit-todo` - note that you MUST use `GIT_SEQUENCE_EDITOR` in this case also.

Use interactive rebase:

- When there are significant changes to the code that needs to be edited in patches subsequent to where it needs to first be modified (e.g. the code has moved in a later patch).
- When moving changes between two existing commits on the branch.
- When you need to re-run tests on patches prior to the current HEAD.

Resolving conflicts
-------------------

When resolving conflicts from rebases or merges, focus on incorporating each of the changes in the patch or merge being applied. Occasionally the preceding changes may have moved or removed code that is modified by the new patch, and sometimes preceding changes add new code that needs to be modified in ways similar to other code already modified in the new patch. But in general a rebase is not the time to be changing the functionality of the applied patch.

Final verification
------------------

If, during a `git rebase` command that is not moving to a new base commit, you have to resolve conflicts then you MUST verify that no unintended changes were introduced at the end of the rebase. Verify by doing a `git diff` between the working directory at the end of the rebase and the commit that was the current HEAD before you started the rebase. In most cases, the diff should be empty; if there are changes they must be intended ones. This check is MANDATORY - do not skip it or wait for me to remind you.
