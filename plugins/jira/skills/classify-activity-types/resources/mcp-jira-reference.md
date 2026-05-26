# MCP Jira Tool Reference

Instructions for using MCP Jira tools (mcp-atlassian) for activity type classification.

## Prerequisites

This workflow requires the mcp-atlassian MCP server configured with access to:
- **Jira instance**: `redhat.atlassian.net` (Jira Cloud)
- **Required tools**: `jira_search`, `jira_update_issue`, `jira_get_issue`

**Setup options**:
- **Local (Claude Code)**: Configure in `~/.claude.json` under the `mcpServers` key
- **ACP**: Configure as a platform plugin in workspace settings

If the tools are not available, the workflow cannot proceed. Inform the user and stop.

**Tool name format**: MCP tool names are prefixed with the server name. The exact prefix depends on the configuration. Common patterns:
- `mcp-atlassian:jira_search`
- `mcp__plugin_hcm-jira-administrator-agent_mcp-atlassian-prod__jira_search`

Use whichever form is available in the current session.

## Activity Type Field

The Activity Type custom field ID is `customfield_10464`. This is constant across all projects — no discovery needed.

## Batch Fetching Issues

### Constructing the JQL Query

Template (substitute `{PROJECT}` and `{TYPE}`):

```
project = {PROJECT} AND issuetype = {TYPE} AND "Activity Type" is EMPTY
```

The `"Activity Type" is EMPTY` condition is mandatory. Always include it — never omit it or ask the user whether to include it.

Common additions:
- Date filter: `AND resolved >= "2025-01-01"`
- Exclude filter: `AND filter = 12424661` (example: ARO project filter)
- Open issues only: `AND status != Closed`

### Executing the Search

1. Call `jira_search` with:
   - `jql`: The constructed query
   - `limit`: `50` (max per request)
2. If more results exist, make a second call with `start_at: 50` to get up to 100 total
3. Combine both result sets

### Extracting Fields

From each issue in the results, extract:
- `key` — Issue key (e.g., OCM-12345)
- `summary` — Issue title
- `description` — Issue description (truncate to 2000 chars for classification)
- `labels` — Issue labels
- `issuetype` — Issue type name
- `status` — Current status
- `priority` — Priority level
- `comment` — Comments (if available)
- `parent` — Parent issue key and fields (if present)

Save all extracted data to `.work/activity-type-classifier/issues.json`.

## Parent Activity Type Lookup

Before classifying an issue, check if it has a parent with an Activity Type already set. This avoids redundant classification — children inherit from their parent.

1. From the fetched issue data, check if the `parent` field is present
2. If a parent exists, call `jira_get_issue` with the parent's key
3. Check the parent's `customfield_10464` field
4. If the parent has an Activity Type value, the child inherits it directly — skip classification

To reduce API calls, cache parent Activity Type lookups. Multiple child issues may share the same parent.

## Batch Updating Activity Types

### Update Format

Call `jira_update_issue` for each issue with:
- `issue_key`: The issue key (e.g., `OCM-12345`)
- `fields`: Include the Activity Type field using `customfield_10464`

The Activity Type is a select-list field. Set it using the value name directly:
```json
{"customfield_10464": {"value": "Product / Portfolio Work"}}
```

If the above format fails, try without the `value` wrapper:
```json
{"customfield_10464": "Product / Portfolio Work"}
```

### Rate Limiting

- **Max 2 concurrent MCP update calls** — do not exceed this
- If rate limit errors occur (HTTP 429), wait 5 seconds and retry
- Report progress to the user every 10 issues

### Error Handling

- On update failure: log the issue key and error, then continue with remaining issues
- After all updates complete, report:
  - Total attempted
  - Successful updates
  - Failed updates (with issue keys and errors)
- Do not retry failed updates automatically — let the user decide
