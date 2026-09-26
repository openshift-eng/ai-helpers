# Worktrees: Parallel Multi-Repo Workspaces

Create isolated workspaces using `git worktree` with a `wt/<name>` branch under `.worktrees/<name>/`. When submodules are present, each one gets its own worktree and branch inside the workspace. For single repos without submodules, [../SETUP.md](../SETUP.md) is enough.

The default branch differs per repo (`main` for cri-o and MCO, `master` for openshift/kubernetes). Resolve it instead of assuming, and use `$DEFAULT` below:

```bash
DEFAULT=$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||')
```

## Create a Workspace

```bash
# Sync submodules first
git fetch --quiet origin
git submodule update --init --quiet
git submodule foreach --quiet 'b=$(git symbolic-ref --short refs/remotes/origin/HEAD | sed "s|^origin/||"); git fetch --quiet origin; git checkout "$b" --quiet 2>/dev/null; git merge --ff-only "origin/$b" --quiet 2>/dev/null || true'

# Create root worktree
git worktree add .worktrees/<name> -b wt/<name> HEAD

# Create submodule worktrees
git submodule foreach --quiet 'git worktree add "$toplevel/.worktrees/<name>/$sm_path" -b "wt/<name>" HEAD'

cd .worktrees/<name>/
```

## Merge Back

For team repos (cri-o, kubernetes, MCO, ...) do not merge into the default
branch locally: push `wt/<name>` to your fork and open a pull request, as
[../SETUP.md](../SETUP.md) says.

Local merge-back is only for personal multi-repo workspaces (a root repo that
tracks submodules) where no PR flow exists. It creates commits on the default
branch, so confirm with the user first:

```bash
# For each submodule: merge wt/<name> into its default branch
git submodule foreach --quiet '
  b=$(git symbolic-ref --short refs/remotes/origin/HEAD | sed "s|^origin/||")
  git checkout "$b" --quiet
  git merge --ff-only wt/<name> --quiet 2>/dev/null || git merge wt/<name> --no-edit --quiet
'

# Merge root
git checkout "$DEFAULT"
git merge --ff-only wt/<name> --quiet 2>/dev/null || git merge wt/<name> --no-edit --quiet

# Update submodule pointers (stage only the submodule paths, not everything)
git submodule foreach --quiet 'git -C "$toplevel" add "$sm_path"'
git diff --cached --quiet || git commit -s -m "Merge workspace <name>"
```

## Remove

Use the safe forms first. They refuse to delete uncommitted or unmerged work:

```bash
git submodule foreach --quiet 'git worktree remove "$toplevel/.worktrees/<name>/$sm_path"; git branch -d "wt/<name>"'
git worktree remove .worktrees/<name>
git branch -d wt/<name>
```

If a command refuses, show the user what would be lost (`git status`,
`git log <default>..wt/<name>`) and only then, with their confirmation, repeat
it with `--force` / `-D`.

## Non-Obvious Details

- **Branch prefix is `wt/`**: every workspace creates `wt/<name>` branches in the root and all submodules. Don't manually create branches with this prefix.
- **Always sync submodules before branching**: fetch and fast-forward all submodules to their tracked branch so your workspace starts from the latest remote state.
- **Remote agent pushes**: if an agent pushed commits to `origin/wt/<name>`, fetch and merge them before merging into the default branch: `git fetch origin; git merge origin/wt/<name>`.
- **Reconcile submodule pointers after merge**: ensure each submodule's default branch matches the commit the root repo expects. Prevents pointer drift.
- **Only fast-forward during sync**: never rebase or create merge commits during sync. If a submodule has diverged, warn and skip.
