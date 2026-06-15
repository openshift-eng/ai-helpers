# Worktrees: Parallel Multi-Repo Workspaces

Create isolated workspaces using `git worktree` with a `wt/<name>` branch under `.worktrees/<name>/`. When submodules are present, each one gets its own worktree and branch inside the workspace.

## Create a Workspace

```bash
# Sync submodules first
git fetch --quiet origin
git submodule update --init --quiet
git submodule foreach --quiet 'git fetch --quiet origin; git checkout main --quiet 2>/dev/null; git merge --ff-only origin/main --quiet 2>/dev/null || true'

# Create root worktree
git worktree add .worktrees/<name> -b wt/<name> HEAD

# Create submodule worktrees
git submodule foreach --quiet 'git worktree add "$toplevel/.worktrees/<name>/$sm_path" -b "wt/<name>" HEAD'

cd .worktrees/<name>/
```

## Merge Back

```bash
# For each submodule: merge wt/<name> into main
git submodule foreach --quiet '
  git checkout main --quiet
  git merge --ff-only wt/<name> --quiet 2>/dev/null || git merge wt/<name> --no-edit --quiet
'

# Merge root
git checkout main
git merge --ff-only wt/<name> --quiet 2>/dev/null || git merge wt/<name> --no-edit --quiet

# Update submodule pointers
git add -A && git diff --cached --quiet || git commit -m "Merge workspace <name>"
```

## Remove

```bash
git submodule foreach --quiet 'git worktree remove --force "$toplevel/.worktrees/<name>/$sm_path" 2>/dev/null; git branch -D "wt/<name>" 2>/dev/null'
git worktree remove --force .worktrees/<name>
git branch -D wt/<name>
```

## Non-Obvious Details

- **Branch prefix is `wt/`** — every workspace creates `wt/<name>` branches in the root and all submodules. Don't manually create branches with this prefix.
- **Always sync submodules before branching** — fetch and fast-forward all submodules to their tracked branch so your workspace starts from the latest remote state.
- **Remote agent pushes** — if an agent pushed commits to `origin/wt/<name>`, fetch and merge them before merging into main: `git fetch origin; git merge origin/wt/<name>`.
- **Reconcile submodule pointers after merge** — ensure each submodule's main matches the commit the root repo expects. Prevents pointer drift.
- **Only fast-forward during sync** — never rebase or create merge commits during sync. If a submodule has diverged, warn and skip.
