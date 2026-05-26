# openshift-developer

Bundle of curated plugins, skills, and MCP servers useful to any OpenShift engineer.

## What's included

### Plugins

- `jira` — Jira automation
- `ci` — OpenShift CI / Prow job analysis
- `golang` — Go development tools
- `prodsec-skills` — Product security skills

### MCP Servers

- **atlassian** — Atlassian MCP server (`https://mcp.atlassian.com/v1/mcp`)

## Installation

```sh
claude plugin install openshift-developer
```

## Commands

| Command | Description |
|---------|-------------|
| `/openshift-developer:info` | Show what this meta-plugin installs |

## Note for non-Claude Code editors

This bundle can also be installed via APM with `--target`:

```sh
apm install openshift-eng/ai-helpers/plugins/openshift-developer --global --target cursor
```
