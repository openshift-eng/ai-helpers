---
name: jira-issues-by-component-mcp
description: Provides Atlassian MCP server integration guidance for the jira:issues-by-component command
---

# JIRA Issues by Component - MCP Backend Skill

This skill provides the MCP backend implementation for the `jira:issues-by-component` command. It fetches issues using the Atlassian MCP server (`searchJiraIssuesUsingJql`) instead of direct REST API calls, eliminating the need for environment variable configuration.

## When to Use This Skill

This skill is automatically invoked by the `jira:issues-by-component` command when using the MCP backend (default). You do not need to invoke it directly.

The command invokes this skill when:
- No `--backend` flag is specified (MCP is the default)
- `--backend mcp` is explicitly specified
- MCP connectivity check passes

## Prerequisites

The Atlassian MCP server must be configured. It is bundled with the Jira plugin via `.mcp.json` — no separate installation is needed. On first use, the user will be prompted to authenticate via browser (OAuth).

## Workflow

### Phase 0 — MCP Prerequisite Check

Before fetching any data, verify MCP Jira tools are available:

1. Call `searchJiraIssuesUsingJql` with a minimal query:
   - `jql`: `"project = {PROJECT_KEY} ORDER BY created DESC"`
   - `maxResults`: `1`
2. If the tool is not found or returns an MCP connection error, **stop immediately** and inform the user:
   ```
   MCP backend is not available.

   Options:
   1. Ensure the Atlassian Rovo MCP server is configured (bundled via .mcp.json)
   2. Use the API backend: /jira:issues-by-component PROJECT --backend api
      (requires JIRA_URL, JIRA_API_TOKEN, JIRA_USERNAME env vars)
   ```
3. Do NOT proceed to Phase 1 if this check fails

### Phase 1 — Fetch Issues via MCP

Fetch issues using `searchJiraIssuesUsingJql` with pagination. The behavior differs between Overview and Detail modes.

#### Field Selection

- **Overview Mode** (no `--component`): Request fields `summary,status,priority,assignee,reporter,created,updated,labels,components,issuetype`. Exclude `description` to reduce response size.
- **Detail Mode** (`--component` specified): Request fields `summary,status,priority,assignee,reporter,created,updated,description,labels,components,issuetype`. Include `description` for detailed issue display.

#### Pagination Strategy

- Fetch **100 issues per call** using `maxResults: 100`
- Use `nextPageToken` from each response to request the next page
- **Cap at 500 issues** (5 pages maximum)
- If the total result count exceeds 500, warn the user:
  ```
  Query returned more than 500 issues (showing first 500).

  For the complete dataset, use:
    /jira:issues-by-component PROJECT [filters] --backend api
  ```

#### JQL Query

Use the same JQL query constructed by the command (Step 3 of the command implementation). The `searchJiraIssuesUsingJql` MCP tool accepts the same JQL syntax as the REST API, so `--search` and `--search-description` work identically:

- Without `--search-description`: `AND summary ~ "{term}"`
- With `--search-description`: `AND (summary ~ "{term}" OR description ~ "{term}")`

#### Overview Mode — Progressive Aggregation

In Overview Mode, progressively aggregate data per page to manage context size:

For each page of results:

1. **Group issues by component** (using `fields.components[].name`; issues with no component go into an "Unassigned" group)
2. **Accumulate per-component statistics**:
   - Total issue count
   - Status distribution (count per status name)
   - Priority distribution (count per priority name)
   - Issue type distribution (count per issue type name)
3. **Keep top 3 issues per component** (by priority descending, then updated descending):
   - Store: `key`, `summary`, `priority.name`, `status.name`, `updated`
   - Compare candidates against the lowest-ranked entry: replace if the candidate has higher priority, or same priority and a more recent `updated` timestamp
   - Drop `updated` from the final output only after all pages have been processed and the top 3 are settled
4. **Discard raw issue data** after aggregation — do not accumulate full issue objects across pages

This keeps memory usage constant regardless of total issue count.

**Aggregation data structure** (maintained across pages):

```json
{
  "components": {
    "Networking / ovn-kubernetes": {
      "count": 45,
      "statuses": {"Open": 30, "In Progress": 10, "Closed": 5},
      "priorities": {"Critical": 5, "Major": 10, "Normal": 20, "Minor": 10},
      "types": {"Bug": 25, "Story": 15, "Task": 5},
      "topIssues": [
        {"key": "OCPBUGS-1234", "summary": "CVE update fails", "priority": "Critical", "status": "Open", "updated": "2024-12-10"},
        {"key": "OCPBUGS-1235", "summary": "Upgrade timeout", "priority": "Major", "status": "In Progress", "updated": "2024-12-09"},
        {"key": "OCPBUGS-1236", "summary": "Version skew", "priority": "Normal", "status": "Open", "updated": "2024-12-08"}
      ]
    }
  },
  "totalIssues": 0,
  "totalFetched": 0,
  "capped": false
}
```

#### Detail Mode — Full Issue Retention

In Detail Mode (with `--component`), retain all issue details for the report:

For each page of results:

1. **Keep all issue fields**: `key`, `summary`, `status`, `priority`, `assignee`, `reporter`, `created`, `updated`, `description` (truncated to 300 chars), `labels`, `components`, `issuetype`
2. **Accumulate statistics** (same as Overview Mode)
3. **Store all issues** — typically a single component has <100 issues, well within the 500-issue cap

**Detail data structure**:

```json
{
  "component": "Networking / ovn-kubernetes",
  "stats": {
    "count": 28,
    "statuses": {"Open": 20, "In Progress": 8},
    "priorities": {"Critical": 3, "Major": 12, "Normal": 10, "Minor": 3},
    "types": {"Bug": 18, "Story": 10}
  },
  "issues": [
    {
      "key": "OCPBUGS-5678",
      "summary": "DNS resolution issue",
      "status": "Open",
      "priority": "Critical",
      "type": "Bug",
      "assignee": "jsmith",
      "reporter": "asmith",
      "created": "2024-12-01",
      "updated": "2024-12-10",
      "description": "First 300 chars...",
      "labels": ["networking", "dns"]
    }
  ],
  "totalIssues": 0,
  "totalFetched": 0,
  "capped": false
}
```

#### Fetch Loop

```
page = 0
nextPageToken = null

while page < 5:
  call searchJiraIssuesUsingJql with:
    jql: <constructed JQL>
    maxResults: 100
    nextPageToken: <from previous response, or omit for first call>
    fields: <based on mode>

  process response:
    - extract issues from response
    - aggregate into data structure (overview or detail mode)
    - update totalFetched count
    - capture totalAvailable from response's total field (full result count reported by Jira)

  if no nextPageToken in response OR totalFetched >= 500:
    break

  page += 1

if totalAvailable > 500:
  set capped = true
  warn user about 500-issue cap
```

### Phase 2 — Return Data

Return the aggregated data structure to the calling command for report generation (Step 5 of the command implementation). The output format is identical to what the API backend produces, so the same report generation logic applies.

**Overview Mode returns**: Component-level aggregation with stats and top issues
**Detail Mode returns**: Full issue list with stats for the specified component

The command handles formatting and display (Steps 5-7) identically for both backends.

## Error Handling

| Error | Handling |
|-------|----------|
| MCP tool not found | Stop and display MCP availability error with fallback guidance |
| MCP connection error | Stop and display connectivity error, suggest re-running or using `--backend api` |
| OAuth expired | User will be prompted to re-authenticate via browser automatically |
| 413 response (result too large) | Suggest adding filters or using `--backend api` |
| Empty result set | Return empty aggregation, command will display "No issues found" guidance |
| Rate limiting | Pause and retry; if persistent, suggest using `--backend api` |

## Comparison with API Backend

| | MCP Backend (this skill) | API Backend (jira-issues-by-component) |
|---|---|---|
| Auth | OAuth via browser | API token env vars |
| Setup | None | Export 3 env vars |
| Max issues | 500 | Unlimited |
| Dependencies | None | `curl`, `jq` |
| Data flow | MCP tool results in context | Streamed to disk |
| Best for | Quick queries, <500 issues | Large datasets, bulk analysis |

## See Also

- [jira:issues-by-component command](../../commands/issues-by-component.md) - Command that uses this skill
- [jira-issues-by-component skill](../jira-issues-by-component/SKILL.md) - API backend skill (secure curl wrapper)
- [categorize-activity-types skill](../categorize-activity-types/SKILL.md) - Another MCP-based skill (reference pattern)
