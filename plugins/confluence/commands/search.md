---
description: Search Confluence for related documentation using natural language or CQL
argument-hint: "<query> [--space <key>] [--limit <n>]"
---

## Name
confluence:search

## Synopsis
```
/confluence:search <query> [--space <key>] [--limit <n>]
```

## Description
The `confluence:search` command searches Confluence for documentation related to a topic, Jira issue, or natural language question. It goes beyond simple keyword search — it interprets the user's intent, constructs appropriate CQL queries, and returns a ranked, summarized list of relevant pages.

This command requires AI reasoning to:
- Translate natural language queries into effective CQL search expressions
- Summarize each result's relevance to the original query
- Identify the most useful pages and explain why they matter
- Suggest follow-up searches when initial results are insufficient

## Key Features
- Accepts natural language queries, Jira issue keys, or raw CQL
- Summarizes each result with a relevance explanation
- Supports space filtering to narrow scope
- Detects Jira issue keys in the query and automatically expands context (searches for the issue summary)

## Implementation

### Phase 1: Parse and Interpret Query
1. Parse `$1` as the search query. Detect if it is:
   - A Jira issue key (matches `[A-Z]+-\d+`) -> fetch the issue summary and use it as search terms
   - Raw CQL (contains operators like `=`, `~`, `AND`, `OR`) -> pass through directly
   - Natural language -> construct a CQL `siteSearch` query
2. Parse optional flags: `--space` for space filtering, `--limit` for result count (default 10).

### Phase 2: Execute Search
1. Build and execute the search:
   ```python
   mcp__mcp-atlassian__confluence_search(
       query="siteSearch ~ \"<interpreted-terms>\"",
       limit=<limit>,
       spaces_filter="<space-key>"  # if --space provided
   )
   ```
2. If the query was a Jira issue key, also search for pages linking to that issue:
   ```python
   mcp__mcp-atlassian__confluence_search(
       query="text ~ \"<issue-key>\"",
       limit=5,
       spaces_filter="<space-key>"
   )
   ```

### Phase 3: Analyze and Rank Results
1. For each result, read the page title, space, last modified date, and excerpt.
2. Rank results by relevance to the original query intent.
3. Group results by space if results span multiple spaces.
4. Flag any results that appear outdated (last modified > 6 months ago).

### Phase 4: Present Results
Format the output as a ranked list:
```
## Search Results for "<query>"

### 1. [Page Title](url) - Space: TEAM
**Last updated:** 2025-12-01 | **Relevance:** High
Summary of why this page is relevant...

### 2. [Page Title](url) - Space: DEV
**Last updated:** 2024-06-15 | **Relevance:** Medium | **Note:** Potentially outdated
Summary of relevance...
```

If no results are found, suggest alternative search terms or broader queries.

## Usage Examples

1. **Search by topic:**
   ```
   /confluence:search "authentication flow for HyperShift"
   ```

2. **Search related to a Jira issue:**
   ```
   /confluence:search OCPBUGS-1234
   ```

3. **Search within a specific space:**
   ```
   /confluence:search "deployment runbook" --space OPS --limit 5
   ```

4. **Raw CQL query:**
   ```
   /confluence:search "label = architecture AND lastModified > startOfMonth(\"-3M\")"
   ```

## Arguments
| Argument | Required | Description |
|----------|----------|-------------|
| `<query>` | Yes | Natural language query, Jira issue key, or CQL expression |
| `--space <key>` | No | Restrict search to a specific Confluence space |
| `--limit <n>` | No | Maximum number of results (default: 10, max: 50) |

## Return Value
- Ranked list of matching Confluence pages with titles, URLs, spaces, and last-modified dates
- Relevance summary for each result
- Suggestions for refined searches if results are sparse

## Error Handling
| Error | Cause | Resolution |
|-------|-------|------------|
| No results found | Query too specific or wrong space | Suggest broader terms or remove space filter |
| CQL syntax error | Malformed CQL expression | Re-interpret as natural language and retry |
| Authentication failure | MCP Atlassian server not configured | Guide user to set up Confluence credentials |

## See Also
- `confluence:create-from-jira` - Create new docs from Jira context
- `confluence:sync-meeting-notes` - Publish meeting notes
