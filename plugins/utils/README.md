# Utils Plugin

General-purpose utilities and helper commands for development workflows.

## Commands

### `/utils:generate-test-plan`

Generate comprehensive test steps for one or more related GitHub PRs.

### `/utils:address-reviews`

Process and address code review comments on pull requests.

### `/utils:process-renovate-pr`

Automate processing of Renovate dependency update PRs.

### `/utils:placeholder`

A placeholder command for testing and development.

## Purpose

The utils plugin serves as a catch-all for commands that don't fit into existing specialized plugins. Once we accumulate several related commands, they can be segregated into a new targeted plugin.

See the [commands/](commands/) directory for full documentation of each command.

## Installation

```bash
/plugin install utils@ai-helpers
```

