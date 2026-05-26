# openshift-developer

Bundle of curated plugins, skills, and MCP servers useful to any OpenShift engineer.

## What's included

### Plugins (via APM)

- `openshift-eng/ai-helpers/plugins/jira` — Jira automation
- `openshift-eng/ai-helpers/plugins/ci` — OpenShift CI / Prow job analysis
- `openshift-eng/ai-helpers/plugins/golang` — Go development tools
- `RedHatProductSecurity/prodsec-skills` — Product security skills

### MCP Servers

- **atlassian** — Atlassian MCP server (`https://mcp.atlassian.com/v1/mcp`)

## Installation

### Claude Code

```sh
claude plugin add openshift-eng/ai-helpers/plugins/openshift-developer
```

### APM (other editors)

Install globally for all projects:

```sh
apm install openshift-eng/ai-helpers/plugins/openshift-developer --global
```

Target a specific editor with `--target`:

```sh
apm install openshift-eng/ai-helpers/plugins/openshift-developer --global --target cursor
```

## Commands

| Command | Description |
|---------|-------------|
| `/openshift-developer:info` | Show what this meta-plugin installs |
