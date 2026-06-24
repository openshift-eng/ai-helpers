# Confluence Plugin

Confluence page management, documentation generation from Jira, and meeting notes publishing.

## Prerequisites

The [mcp-atlassian](https://github.com/sooperset/mcp-atlassian) MCP server must be configured with Confluence credentials. The same server that provides Jira tools also exposes Confluence tools.

### Required environment variables

| Variable | Description |
|----------|-------------|
| `CONFLUENCE_URL` | Your Confluence instance URL (e.g., `https://yourorg.atlassian.net/wiki`) |
| `CONFLUENCE_USERNAME` | Atlassian account email |
| `CONFLUENCE_API_TOKEN` | Atlassian API token ([generate one here](https://id.atlassian.com/manage-profile/security/api-tokens)) |

If you already have the mcp-atlassian server configured for the `jira` plugin, Confluence tools are available automatically — no additional setup is needed.

## Commands

| Command | Description |
|---------|-------------|
| `/confluence:create-from-jira` | Generate a structured Confluence page from a Jira epic or story |
| `/confluence:search` | Search Confluence for related documentation |
| `/confluence:sync-meeting-notes` | Publish meeting notes or agendas to Confluence |

## Skills

| Skill | Description |
|-------|-------------|
| `page-templates` | Structured templates for design docs, feature specs, meeting notes, runbooks, and decision records |
| `confluence-conventions` | Best practices for space organization, labeling, and page naming |

## Usage Examples

```bash
# Generate a design doc from an Epic
/confluence:create-from-jira PROJ-100 --space DEV --type design-doc

# Search for related docs before starting work
/confluence:search "authentication flow" --space TEAM

# Publish grooming notes after running /jira:grooming
/confluence:sync-meeting-notes TEAM "Sprint 42 Grooming - 2026-05-07"
```

## Works With

This plugin pairs well with:
- **jira** - Create Jira issues, then generate Confluence docs from them
- **agendas** - Generate meeting agendas, then sync them to Confluence
