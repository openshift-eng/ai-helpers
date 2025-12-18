# GitHub Plugin

GitHub workflow automation and utilities for Claude Code.

## Commands

| Command | Description |
|---------|-------------|
| `/github:what-next` | Identify what to focus on next based on PRs, issues, and milestones |

## Installation

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the plugin
/plugin install github@ai-helpers
```

## Prerequisites

- **GitHub CLI (`gh`)** must be installed and authenticated
  - Check: `gh auth status`
  - Install: https://cli.github.com/
- Must be run from within a Git repository with a GitHub remote

## Usage

### What Next

Get a prioritized list of what to work on:

```
/github:what-next
```

This analyzes:
- PRs needing your review
- Your open PRs and their status
- Priority issues from the next milestone
- Your draft PRs

With a custom contributing file:

```
/github:what-next --contributing docs/CONTRIBUTING.md
```
