# Jira Plugin

Comprehensive Jira integration for Claude Code, providing AI-powered tools to analyze issues, create solutions, and generate status rollups.

## Features

- 🔍 **Issue Analysis and Solutions** - Analyze JIRA issues and create pull requests to solve them
- 📊 **Status Rollups** - Generate comprehensive weekly status rollup comments for any Jira issue
- 🤖 **Automated Workflows** - From issue analysis to PR creation, fully automated
- 💬 **Smart Comment Analysis** - Extracts blockers, risks, and key insights from comments

## Prerequisites

- Claude Code installed
- Jira MCP server configured

### Setting up Jira MCP Server

```bash
# Add the Atlassian MCP server
claude mcp add atlassian npx @modelcontextprotocol/server-atlassian
```

Configure your Jira credentials according to the [Atlassian MCP documentation](https://github.com/modelcontextprotocol/servers/tree/main/src/atlassian).

## Installation

### From the OpenShift AI Helpers Marketplace

```bash
# Add the marketplace (one-time setup)
/plugin marketplace add https://raw.githubusercontent.com/openshift-eng/ai-helpers/main/marketplace.json

# Install the plugin
/plugin install jira
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openshift-eng/ai-helpers.git

# Copy to Claude Code plugins directory
cp -r ai-helpers/plugins/jira ~/.claude/plugins/

# Enable the plugin
/plugin enable jira
```

## Available Commands

### `/jira:solve` - Analyze and Solve JIRA Issues

Analyze a JIRA issue and create a pull request to solve it. The command fetches issue details, analyzes the codebase, creates an implementation plan, makes the necessary changes, and creates a PR with conventional commits.

**Usage:**
```bash
/jira:solve OCPBUGS-12345 enxebre
```

See [commands/solve.md](commands/solve.md) for full documentation.

---

### `/jira:status-rollup` - Generate Weekly Status Rollups

Generate comprehensive weekly status rollup comments for any Jira issue by recursively analyzing all child issues and their activity within a date range. The command extracts insights from changelogs and comments to create well-formatted status summaries.

**Usage:**
```bash
/jira:status-rollup FEATURE-123 --start-date 2025-10-08 --end-date 2025-10-14
```

See [commands/status-rollup.md](commands/status-rollup.md) for full documentation.

## Troubleshooting

### "Could not find issue {issue-id}"
- Verify the issue ID is correct
- Ensure you have access to the issue in Jira
- Check that your Jira MCP server is properly configured

For command-specific troubleshooting, see the individual command documentation.

## Contributing

Contributions welcome! Please submit pull requests to the [ai-helpers repository](https://github.com/openshift-eng/ai-helpers).

## License

Apache-2.0
