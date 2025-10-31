# Git Plugin

Git workflow automation and utilities for Claude Code.

## Commands

### `/git:branch-resolve`

Analyze and resolve git branch issues (conflicts, divergence, push/pull problems)

### `/git:cherry-pick-by-patch`

Cherry-pick a git commit into the current branch using the patch command instead of git cherry-pick.

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

