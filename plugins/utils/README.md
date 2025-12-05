# Utils Plugin

General-purpose utilities and helper commands for development workflows.

## Commands

### `/utils:generate-test-plan`

Generate comprehensive test steps for one or more related GitHub PRs.

### `/utils:address-reviews`

Process and address code review comments on pull requests.

### `/utils:process-renovate-pr`

Automate processing of Renovate dependency update PRs.

### `/utils:auto-approve-konflux-prs`

Automate approving Konflux bot PRs for the given repository by adding /lgtm and /approve

### `/utils:review-security`

Orchestrate security scanners and provide contextual triage of findings.

### `/utils:placeholder`

A placeholder command for testing and development.

### `/utils:review-ai-helpers-overlap`

Review potential overlaps with existing ai-helpers (Claude Code Plugins, Commands, Skills, Sub-agents, or Hooks) and open PRs.

## Purpose

The utils plugin serves as a catch-all for commands that don't fit into existing specialized plugins. Once we accumulate several related commands, they can be segregated into a new targeted plugin.

See the [commands/](commands/) directory for full documentation of each command.

## Installation

```bash
/plugin install utils@ai-helpers
```

