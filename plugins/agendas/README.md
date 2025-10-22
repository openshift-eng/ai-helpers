# Agendas Plugin

Generate structured meeting agendas to streamline team collaboration and decision-making processes.

## Features

- 📋 **Outcome Refinement Agendas** - Analyze OCPSTRAT outcome issues and generate structured refinement meeting agendas
- 🚨 **Issue Hygiene Detection** - Automatically identify missing assignments, incorrect issue types, and other routine problems
- 📊 **Team Overload Analysis** - Detect component teams that may be overloaded based on issue assignments
- ⏰ **Age-Based Prioritization** - Flag outcomes that have been open too long or stuck in "New" status
- ✅ **Actionable Output** - Ready-to-use Markdown agendas that can be copied directly into Confluence

## Prerequisites

- Claude Code installed
- Jira MCP server configured (same as Jira plugin)

### Setting up Jira MCP Server

```bash
# Add the Atlassian MCP server
claude mcp add atlassian npx @modelcontextprotocol/server-atlassian
```

OR you can use an already running Jira MCP Server:

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
You'll need to generate your own tokens:

- For JIRA API TOKEN, use https://id.atlassian.com/manage-profile/security/api-tokens
- For JIRA PERSONAL TOKEN, use https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens

## Installation

### From the OpenShift AI Helpers Marketplace

```bash
# Add the marketplace (one-time setup)
/plugin marketplace add https://raw.githubusercontent.com/openshift-eng/ai-helpers/main/marketplace.json

# Install the plugin
/plugin install agendas
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openshift-eng/ai-helpers.git

# Copy to Claude Code plugins directory
cp -r ai-helpers/plugins/agendas ~/.claude/plugins/

# Enable the plugin
/plugin enable agendas
```

## Available Commands

### `/agendas:outcome-refinement` - Outcome Refinement Meeting Agenda

Analyze OCPSTRAT outcome issues and generate a structured meeting agenda for outcome refinement sessions. The command automatically identifies common issues that require human follow-up and organizes them into actionable discussion points.

**Usage:**
```bash
/agendas:outcome-refinement
```

**What It Checks:**

The command analyzes outcome issues and flags:

- **Missing Assignments**: Outcomes without assignee, architect, QA contact, or doc contact
- **Incorrect Child Issues**: Outcomes with non-Feature child issue types
- **Status Mismatches**: Child issues being actively worked on while parent outcome shows wrong status
- **Age Analysis**: Outcomes that have been open too long (especially in "New" status for over a year)
- **Scope Concerns**: Outcomes with active child issues but open for years, indicating potential scope creep
- **Team Overload**: Components commonly assigned across multiple outcomes, indicating team capacity issues

**Output Format:**

The command generates a ready-to-use Markdown agenda:

```markdown
# Outcome Refinement Agenda
**Outcome Issues**: [count]

## 🚨 Critical Issues ([count])
- **[OCPSTRAT-1234]** BGP integration with public clouds - *Critical, needs immediate attention*
- **[OCPSTRAT-1235]** Consistent Ingress/Egress into OpenShift clusters - *High, assign to team lead*

## 📝 Needs Clarification ([count])
- **[OCPSTRAT-1238]** Missing architect
- **[OCPSTRAT-1239]** Component team is overloaded
- **[OCPSTRAT-1240]** Outcome has been open for years with no delivery

## 📋 Action Items
- [ ] Set architect for OCPSTRAT-1236 to SME architect (immediate)
- [ ] Schedule review for OCPSTRAT-1236 (this week)
```

See [commands/outcome-refinement.md](commands/outcome-refinement.md) for full documentation.

## Troubleshooting

### "Could not find issues"
- Verify you have access to OCPSTRAT project in Jira
- Check that your Jira MCP server is properly configured
- Ensure your credentials have permission to query the project

### Empty or incomplete agenda
- Verify the JQL query is returning results
- Check that the outcome issues have child issues
- Ensure the date ranges are appropriate for your analysis

## Contributing

Contributions welcome! Please submit pull requests to the [ai-helpers repository](https://github.com/openshift-eng/ai-helpers).

## License

Apache-2.0
