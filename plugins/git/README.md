# Git Plugin

Git workflow automation and utilities for Claude Code.

## Commands

### `/git:setup`

Set up a git repository with upstream and downstream remotes for forked development workflows. This command helps configure repositories following the OpenShift/Red Hat development model where you work with:
- **Upstream**: Original repository (e.g., kubernetes)
- **Downstream**: OpenShift/Red Hat fork (e.g., openshift/kubernetes)
- **Origin**: Your personal fork

Key features:
- Create personal forks from upstream repositories
- Clone repositories with proper directory structure
- Configure git remotes (origin, upstream, downstream)
- Create and sync branches across remotes
- Manage existing repositories

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

