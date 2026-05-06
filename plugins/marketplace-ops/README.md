# marketplace-ops

Maintenance commands for Claude Code plugin marketplaces. Identifies stale or low-value plugins, commands, and skills, then opens a PR to remove them with a structured review workflow.

## Commands

### `/marketplace-ops:prune`

Analyzes the repository for inactive content using git history, structural signals, and LLM judgment. Creates a branch removing candidates and opens a PR with a removal manifest.

Use `--dry-run` to see what would be pruned without creating a branch or PR.

### `/marketplace-ops:prune-update`

Processes `/save <path>` comments on a pruning PR. Restores saved items, adds them to `.pruneprotect` permanently, and pushes a new commit to the PR branch.

## Protection

Create a `.pruneprotect` file at the repo root to permanently exclude paths from pruning:

```
# Canonical example plugin
plugins/hello-world/

# Saved by @username on 2026-05-05
plugins/foo/
```

Lines starting with `#` are comments. Each non-comment line is a path prefix that protects everything under it.
