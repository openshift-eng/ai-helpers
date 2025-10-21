# Jira Plugin

Comprehensive Jira integration for Claude Code, providing AI-powered tools to analyze issues, create solutions, and generate status rollups.

## Features

- 🔍 **Issue Analysis and Solutions** - Analyze JIRA issues and create pull requests to solve them
- 📊 **Status Rollups** - Generate comprehensive status rollup comments for any Jira issue given a date range
- 📋 **Backlog Grooming** - Analyze new bugs and cards for grooming meetings
- 🧪 **Test Generation** - Generate comprehensive test steps for JIRA issues by analyzing related PRs
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

OR you can have claude use an already running Jira MCP Server

```bash
# Add the Atlassian MCP server
claude mcp add --transport sse atlassian http https://localhost:8080/sse
```

Configure your Jira credentials according to the [Atlassian MCP documentation](https://github.com/modelcontextprotocol/servers/tree/main/src/atlassian).

### Running Jira MCP Server locally with podman

```bash
# Start the atlassian mcp server using podman
podman run -i --rm -p 8080:8080 -e "JIRA_URL=https://issues.redhat.com" -e "JIRA_USERNAME" -e "JIRA_API_TOKEN" -e "JIRA_PERSONAL_TOKEN" -e "JIRA_SSL_VERIFY" ghcr.io/sooperset/mcp-atlassian:latest --transport sse --port 8080 -vv
```

#### Getting Tokens 
You'll need to generate your own tokens in several of these examples:

- For JIRA API TOKEN, use https://id.atlassian.com/manage-profile/security/api-tokens
- For JIRA PERSONAL TOKEN, use https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens
- For GitHub bearer token, use https://github.com/settings/tokens

### Notes and tips

- Do not commit real tokens. If you must keep a project-local file, prefer committing a `mcp.json.sample` with placeholders, and keep your real `mcp.json` untracked.
- Consider using the [rh-pre-commit](https://source.redhat.com/departments/it/it_information_security/leaktk/leaktk_components/rh_pre_commit) hook to scan for secrets accidentally left in commits.
- The `atlassian` server example uses an MCP container image: `ghcr.io/sooperset/mcp-atlassian:latest`.
- If you prefer Docker, replace the `podman` command with `docker` (arguments are typically the same).
- If Podman is installed via Podman Machine on macOS, ensure it is running: `podman machine start`.
- Keep `JIRA_SSL_VERIFY` as "true" unless you have a specific reason to disable TLS verification.
- Limit active MCP servers: running too many at once can degrade performance or hit limits. Use Cursor's MCP panel to disable those you don't need for the current session.



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

Generate comprehensive status rollup comments for any Jira issue by recursively analyzing all child issues and their activity within a date range. The command extracts insights from changelogs and comments to create well-formatted status summaries.

**Usage:**
```bash
/jira:status-rollup FEATURE-123 --start-date 2025-10-08 --end-date 2025-10-14
```

See [commands/status-rollup.md](commands/status-rollup.md) for full documentation.

---

### `/jira:grooming` - Backlog Grooming Assistant

Analyze and organize new bugs and cards added over a specified time period to prepare for grooming meetings. The command provides automated data collection, intelligent analysis, and generates structured, actionable meeting agendas.

**Usage:**
```bash
# Single project
/jira:grooming OCPSTRAT last-week

# Multiple OpenShift projects
/jira:grooming "OCPSTRAT,OCPBUGS,HOSTEDCP" last-week

# Filter by component
/jira:grooming OCPSTRAT last-week --component "Control Plane"

# Filter by label
/jira:grooming OCPSTRAT last-week --label "technical-debt"

# Combine filters
/jira:grooming OCPSTRAT last-week --component "Control Plane" --label "security"
```
See [commands/grooming.md](commands/grooming.md) for full documentation.

---

### `/jira:generate-test-plan` - Generate Test Steps

Generate comprehensive test steps for a JIRA issue by analyzing related pull requests. The command supports auto-discovery of PRs from the JIRA issue or manual specification of specific PRs to analyze.

**Usage:**
```bash
# Auto-discover all PRs from JIRA
/jira:generate-test-plan CNTRLPLANE-205

# Test only specific PRs
/jira:generate-test-plan CNTRLPLANE-205 https://github.com/openshift/hypershift/pull/6888
```

See [commands/generate-test-plan.md](commands/generate-test-plan.md) for full documentation.

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
