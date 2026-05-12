# marketplace-ops

Maintenance skills and scripts for Claude Code plugin marketplaces. Identifies stale or low-value plugins, commands, and skills, then opens a PR to remove them with a structured review workflow.

## Skills

### `marketplace-ops:prune`

LLM-assisted review of flagged items. Receives scored/flagged items from the deterministic scoring scripts and applies qualitative judgment to decide which items should be removed. Used by CI during the pruning workflow.

### `marketplace-ops:update`

Processes `/save <path>` and `/drop <path>` comments on a pruning PR. Restores saved items, removes dropped items, updates `.pruneprotect`, and pushes changes.

## Scripts

Deterministic Python scripts in `scripts/` handle all mechanical operations:

| Script | Purpose |
|--------|---------|
| `score-plugins.py` | Score entire plugins for staleness based on git history |
| `score-items.py` | Score individual commands/skills within plugins |
| `process-comments.py` | Parse and validate `/save`/`/drop` directives from PR comments |
| `apply-changes.py` | Apply save/drop changes to the working tree |
| `build-pr-body.py` | Generate the PR body with removal manifest |
| `update-pr-body.py` | Update PR body after processing directives |
| `cross-reference-scan.py` | Detect cross-references to items being removed |

## CI Integration

A weekly Prow job runs this workflow automatically:
1. If no open prune PR exists: scores plugins/items, invokes Claude for item review, creates a PR
2. If a prune PR exists: processes new `/save` and `/drop` comments from collaborators

## Protection

Create a `.pruneprotect` file at the repo root to permanently exclude paths from pruning:

```
# Canonical example plugin
plugins/hello-world/

# Saved by @username on 2026-05-05
plugins/foo/
```

Lines starting with `#` are comments. Each non-comment line is a path prefix that protects everything under it.
