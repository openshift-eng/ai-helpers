# Jira Plugin

Jira integration for Claude Code. Analyze issues, create solutions, and generate status rollups.

**Note:** This plugin is configured for Red Hat's Jira instance (issues.redhat.com) with templates and workflows designed for Red Hat product teams. Templates use Red Hat-specific custom fields and project conventions.

## Features

- 🔍 **Issue Analysis and Solutions** - Analyze JIRA issues and create pull requests to solve them
- 📊 **Status Rollups** - Generate status rollup comments for any Jira issue given a date range
- 📋 **Backlog Grooming** - Analyze new bugs and cards for grooming meetings
- 🧪 **Test Generation** - Generate test steps for JIRA issues by analyzing related PRs
- ✨ **Issue Creation** - Create well-formed stories, epics, features, tasks, bugs, and feature requests with guided workflows
- 📝 **Release Note Generation** - Automatically generate bug fix release notes from Jira and linked GitHub PRs
- 🤖 **Automated Workflows** - From issue analysis to PR creation, fully automated
- 💬 **Smart Comment Analysis** - Extracts blockers, risks, and key insights from comments

## Prerequisites

- Claude Code installed
- Jira MCP server configured (see Setup below)
- Optional: `gh` CLI tools installed and configured, for GitHub access

## Setup

### First-Time MCP Server Setup

**The Jira plugin will guide you through MCP server setup automatically** the first time you use a Jira command.

When you run a command like `/jira:create`, the plugin will:
1. Check if the Atlassian MCP server is available
2. If not configured, offer to walk you through setup step-by-step
3. Guide you through obtaining a Jira token, setting environment variables, and configuring mcp.json
4. Save setup status so you're not prompted again

**For manual setup or troubleshooting**, see the [MCP Setup Guide](docs/MCP_SETUP.md).

### Quick Setup (If You Want to Configure Manually)

1. **Get a Jira Personal Access Token:**
   - Visit: https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens
   - Create token with 1-year expiration

2. **Set environment variable** for token in `~/.bashrc` or `~/.zshrc`:
   ```bash
   export JIRA_PERSONAL_TOKEN="your-token-here"
   source ~/.bashrc  # or ~/.zshrc
   ```

3. **Edit `~/.claude/mcp.json`** and add:
   ```json
   {
     "mcpServers": {
       "atlassian": {
         "command": "podman",
         "args": [
           "run",
           "--rm",
           "-i",
           "-e",
           "JIRA_URL",
           "-e",
           "JIRA_USERNAME",
           "-e",
           "JIRA_PERSONAL_TOKEN",
           "ghcr.io/sooperset/mcp-atlassian:latest",
           "--transport",
           "stdio"
         ],
         "env": {
           "JIRA_URL": "https://issues.redhat.com",
           "JIRA_USERNAME": "your-email@example.com"
         }
       }
     }
   }
   ```

   Replace with your Jira URL and username.
   If using Docker, change `"command": "podman"` to `"command": "docker"`.

4. **Restart Claude Code**

Claude Code will automatically start the MCP server container when needed.

See [docs/MCP_SETUP.md](docs/MCP_SETUP.md) for detailed instructions, troubleshooting, and running as a service.

### Configuration File

The plugin stores settings in `~/.claude/jira-config.json`:

```json
{
  "default_security_level": "Red Hat Employee",
  "skip_security_confirmation": false,
  "mcp_setup_complete": false
}
```

This file is managed automatically - you don't need to edit it manually.

## Installation

Ensure you have the ai-helpers marketplace enabled, via [the instructions here](/README.md).

```bash
# Install the plugin
/plugin install jira@ai-helpers
```

## Common Conventions

### Jira Formatting

**Heading Standards:**

Templates use Jira Wiki markup headings:
- Main headings: `h4.`
- Subheadings: `h5.`
- Bullet lists: `* Item`

**MCP vs Direct API:**

**CRITICAL:** When using bold text in descriptions, formatting differs based on tool used.

**When using MCP tools** (`mcp__atlassian__jira_create_issue`, `mcp__atlassian__jira_update_issue`):
- Bold text: `**text**` (double asterisks)
- MCP tools automatically convert Markdown to Jira Wiki markup

**When using Jira REST API directly** (curl commands):
- Bold text: `*text*` (single asterisks)
- API requires native Jira Wiki markup (no conversion)

**Always check before creating/updating issues:**
1. Are you using an MCP tool? → Use `**text**` for bold
2. Are you using the API directly? → Use `*text*` for bold

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

Generate status rollup comments for any Jira issue by recursively analyzing all child issues and their activity within a date range. The command extracts insights from changelogs and comments to create well-formatted status summaries.

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

Generate test steps for a JIRA issue by analyzing related pull requests. The command supports auto-discovery of PRs from the JIRA issue or manual specification of specific PRs to analyze.

**Usage:**
```bash
# Auto-discover all PRs from JIRA
/jira:generate-test-plan CNTRLPLANE-205

# Test only specific PRs
/jira:generate-test-plan CNTRLPLANE-205 https://github.com/openshift/hypershift/pull/6888
```

See [commands/generate-test-plan.md](commands/generate-test-plan.md) for full documentation.

---

### `/jira:create` - Create Jira Issues

Create well-formed Jira issues (stories, epics, features, tasks, bugs, feature requests) with intelligent defaults, interactive guidance, and validation. The command applies project-specific conventions, suggests components based on context, and provides templates for consistent issue creation.

**Usage:**
```bash
# Create a story
/jira:create story MYPROJECT "Add user dashboard"

# Create a story with options
/jira:create story MYPROJECT "Add search functionality" --component "Frontend" --version "2.5.0"

# Create an epic with parent
/jira:create epic MYPROJECT "Mobile application redesign" --parent MYPROJECT-100

# Create a bug
/jira:create bug MYPROJECT "Login button doesn't work on mobile"

# Create a bug with component
/jira:create bug MYPROJECT "API returns 500 error" --component "Backend"

# Create a task
/jira:create task MYPROJECT "Update API documentation" --parent MYPROJECT-456

# Create a feature
/jira:create feature MYPROJECT "Advanced search capabilities"

# Create a feature request
/jira:create feature-request RFE "Support custom SSL certificates for ROSA HCP"
```

**Key Features:**
- **Universal requirements** - All tickets MUST include label: ai-generated-jira
- **Smart defaults** - Project and team-specific conventions applied automatically (including security level from global config or template)
- **Interactive templates** - Guides you through user story format, acceptance criteria, bug templates
- **Security validation** - Scans for credentials and secrets before submission
- **Security workflow** - Prompts for global security default on first use, supports template overrides
- **Extensible** - Supports project-specific and team-specific skills for custom workflows
- **Hybrid workflow** - Required fields as arguments, optional fields as interactive prompts

**Supported Issue Types:**
- `story` - User stories with acceptance criteria
- `epic` - Epics with parent feature linking
- `feature` - Strategic features with market problem analysis
- `task` - Technical tasks and operational work
- `bug` - Bug reports with structured templates
- `feature-request` - Customer-driven feature requests for RFE project with business justification

**Project-Specific Conventions:**

Different projects may have different conventions (security levels, labels, versions, components, etc.). The command automatically detects your project and applies the appropriate conventions via project-specific skills.

**Team-Specific Conventions:**

Teams may have additional conventions layered on top of project conventions (component selection, custom fields, workflows, etc.). The command automatically detects team context and applies team-specific skills.

See [commands/create.md](commands/create.md) for full documentation.

---

### `/jira:create-release-note` - Generate Bug Fix Release Notes

Automatically generate bug fix release notes by analyzing Jira bug tickets and their linked GitHub pull requests. The command extracts Cause and Consequence from the bug description, analyzes PR content (description, commits, code changes, comments), synthesizes the information into a cohesive release note, and updates the Jira ticket.

**Usage:**
```bash
/jira:create-release-note OCPBUGS-38358
```

**What it does:**
1. Fetches the bug ticket from Jira
2. Extracts Cause and Consequence sections from bug description
3. Finds all linked GitHub PRs
4. Analyzes each PR (description, commits, diff, comments)
5. Synthesizes Fix, Result, and Workaround information
6. Validates content for security (no credentials)
7. Prompts for Release Note Type selection
8. Updates Jira ticket fields

**Release Note Format:**
```
Cause: <extracted from bug description>
Consequence: <extracted from bug description>
Fix: <analyzed from PRs>
Result: <analyzed from PRs>
Workaround: <analyzed from PRs if applicable>
```

**Prerequisites:**
- MCP Jira server configured
- GitHub CLI (`gh`) installed and authenticated
- Access to linked GitHub repositories
- Jira permissions to update Release Note fields

**Example Output:**
```
✓ Release Note Created for OCPBUGS-38358

Type: Bug Fix

Text:
---
Cause: hostedcontrolplane controller crashes when hcp.Spec.Platform.AWS.CloudProviderConfig.Subnet.ID is undefined
Consequence: control-plane-operator enters a crash loop
Fix: Added nil check for CloudProviderConfig.Subnet before accessing Subnet.ID field
Result: The control-plane-operator no longer crashes when CloudProviderConfig.Subnet is not specified
---

Updated: https://issues.redhat.com/browse/OCPBUGS-38358
```

See [commands/create-release-note.md](commands/create-release-note.md) for full documentation.

---

## Available Templates

The Jira plugin includes templates for consistent issue creation.

**Common templates** (work with any project):
- `common-story` - User stories with acceptance criteria
- `common-epic` - Epics with scope and timeline
- `common-bug` - Bug reports with reproduction steps
- `common-spike` - Research and investigation
- `common-task` - Technical work and operational tasks
- `common-feature` - Strategic features with market analysis

**Product-specific templates:**
- Templates for OCPBUGS, RHEL, and other product organizations
- Includes specialized bug formats and feature request workflows

**Team-specific templates:**
- Teams can publish custom templates (e.g., `ocpedge-spike` demonstrates OCPEDGE team format)

**Usage:**
```bash
# List all available templates
/jira:template list

# Create issue with specific template
/jira:create story MYPROJECT "My Story" --template common-story

# Create your own template
/jira:template create my-custom-template
```

See [Template Documentation](templates/README.md) for creating custom templates.

---

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
