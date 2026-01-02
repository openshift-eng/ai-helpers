# Git Plugin

Git workflow automation and utilities for Claude Code.

## Commands

### `/git:bisect`

Interactive git bisect assistant with pattern detection and automation. Helps find the exact commit that introduced a specific change using binary search.

### `/git:cherry-pick-by-patch`

Cherry-pick a git commit into the current branch using the patch command instead of git cherry-pick.

### `/git:fix-robot-pr`

Fix a cherrypick-robot PR that needs manual intervention by creating a replacement PR with all necessary fixes applied.

### `/git:commit-suggest`

Generate Conventional Commits style commit messages for staged changes or recent commits.

### `/git:debt-scan`

Scan the codebase for technical debt markers and generate a report.

### `/git:summary`

Generate a summary of git repository changes and activity.

See the [commands/](commands/) directory for full documentation of each command.

## Installation

```bash
/plugin install git@ai-helpers
```

