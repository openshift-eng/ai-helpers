# Jira Plugin

Comprehensive Jira integration for Claude Code, providing AI-powered tools to analyze issues, create solutions, and generate status rollups.

## Features

- 🔍 **Issue Analysis and Solutions** - Analyze JIRA issues and create pull requests to solve them
- 📊 **Status Rollups** - Generate comprehensive status rollup comments for any Jira issue given a date range
- 📋 **Backlog Grooming** - Analyze new bugs and cards for grooming meetings
- 🧪 **Test Generation** - Generate comprehensive test steps for JIRA issues by analyzing related PRs
- ✨ **Issue Creation** - Create well-formed stories, epics, features, tasks, and bugs with guided workflows
- 📝 **Release Note Generation** - Automatically generate bug fix release notes from Jira and linked GitHub PRs
- 🤖 **Automated Workflows** - From issue analysis to PR creation, fully automated
- 💬 **Smart Comment Analysis** - Extracts blockers, risks, and key insights from comments

## Prerequisites

- Claude Code installed
- Jira MCP server configured
- Optional: `gh` CLI tools installed and configured, for GitHub access.

### Setting up Jira MCP Server

```bash
# Start the atlassian mcp server using podman
podman run -i --rm -p 8080:8080 -e "JIRA_URL=https://issues.redhat.com" -e "JIRA_USERNAME" -e "JIRA_PERSONAL_TOKEN" -e "JIRA_SSL_VERIFY" ghcr.io/sooperset/mcp-atlassian:latest --transport sse --port 8080 -vv
```

Add the MCP server to Claude:

```bash
# Add the Atlassian MCP server
claude mcp add --transport sse atlassian http://localhost:8080/sse
```

#### Getting Tokens

For your Jira token, use https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens

### Notes and tips

- Do not commit real tokens. If you must keep a project-local file, prefer committing a `mcp.json.sample` with placeholders, and keep your real `mcp.json` untracked.
- Consider using the [rh-pre-commit](https://source.redhat.com/departments/it/it_information_security/leaktk/leaktk_components/rh_pre_commit) hook to scan for secrets accidentally left in commits.
- The `atlassian` server example uses an MCP container image: `ghcr.io/sooperset/mcp-atlassian:latest`.
- If you prefer Docker, replace the `podman` command with `docker` (arguments are typically the same).
- If Podman is installed via Podman Machine on macOS, ensure it is running: `podman machine start`.
- Keep `JIRA_SSL_VERIFY` as "true" unless you have a specific reason to disable TLS verification.
- Limit active MCP servers: running too many at once can degrade performance or hit limits. Use Cursor's MCP panel to disable those you don't need for the current session.

## Installation

Ensure you have the ai-helpers marketplace enabled, via [the instructions here](/README.md).

```bash
# Install the plugin
/plugin install jira@ai-helpers
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

---

### `/jira:create` - Create Jira Issues

Create well-formed Jira issues (stories, epics, features, tasks, bugs) with intelligent defaults, interactive guidance, and validation. The command applies project-specific conventions, suggests components based on context, and provides templates for consistent issue creation.

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
```

**Key Features:**
- **Universal requirements** - All tickets MUST include Security Level: Red Hat Employee and label: ai-generated-jira
- **Smart defaults** - Project and team-specific conventions applied automatically
- **Interactive templates** - Guides you through user story format, acceptance criteria, bug templates
- **Security validation** - Scans for credentials and secrets before submission
- **Extensible** - Supports project-specific and team-specific skills for custom workflows
- **Hybrid workflow** - Required fields as arguments, optional fields as interactive prompts

**Supported Issue Types:**
- `story` - User stories with acceptance criteria
- `epic` - Epics with parent feature linking
- `feature` - Strategic features with market problem analysis
- `task` - Technical tasks and operational work
- `bug` - Bug reports with structured templates

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
