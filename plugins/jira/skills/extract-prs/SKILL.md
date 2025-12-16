---
name: Jira Pull Request Extractor
description: Recursively extract GitHub Pull Request links from Jira issues
---

# Jira Pull Request Extractor

This skill recursively discovers Jira issues and extracts all associated GitHub Pull Request links.

**IMPORTANT FOR AI**: This is a **procedural skill** - when invoked, you should directly execute the implementation steps defined in this document. Do NOT look for or execute external scripts (like `extract_prs.py`). Follow the step-by-step instructions in the "Implementation" section below.

## When to Use This Skill

Use this skill when you need to:
- Discover all GitHub PRs associated with a Jira feature and its subtasks
- Extract PR metadata without analyzing PR content
- Build a complete map of PRs for documentation or release notes

**Key characteristics**:
- ✅ **Always recursive**: Automatically discovers all descendant issues via `childIssuesOf()` JQL
- ✅ **PR-only**: Extracts only Pull Request URLs (ignores Issue and Commit URLs)
- ✅ **Dual-source**: Extracts from both changelog remote links and text content (description/comments)
- ✅ **Structured output**: Returns JSON with PR metadata and deduplication across sources

## Prerequisites

- **MCP Jira server configured and running** (required - see `plugins/jira/README.md` for setup)
- `jq` installed for JSON parsing
- GitHub CLI (`gh`) installed and authenticated for fetching PR metadata
- User has read permissions for target Jira issues (including private issues via MCP authentication)
- User has read access to linked GitHub repositories

## Output Format

**Purpose**: This skill returns structured JSON that serves as an interface contract for consuming skills and commands.

**Delivery Method**:
- **Primary**: Output JSON directly to the response (no file writes, no user prompts)
- **Secondary**: Only save to `.work/extract-prs/{issue-key}/output.json` if user explicitly requests to save results

**Schema Version**: `1.0`

### Structure

```json
{
  "schema_version": "1.0",
  "metadata": {
    "generated_at": "2025-11-24T10:30:00Z",
    "command": "extract_prs",
    "input_issue": "OCPSTRAT-1612"
  },
  "pull_requests": [
    {
      "url": "https://github.com/openshift/hypershift/pull/6444",
      "state": "MERGED",
      "title": "Add support for custom OVN subnets",
      "isDraft": false,
      "sources": ["comment", "description", "remote_link"],
      "found_in_issues": ["CNTRLPLANE-1201", "OCPSTRAT-1612"]
    }
  ]
}
```

**Fields**:
- `schema_version`: Format version (`"1.0"`)
- `metadata`: Generation timestamp, command name, and input issue
- `pull_requests`: Array of PR objects with `url`, `state`, `title`, `isDraft`, `sources`, and `found_in_issues`


## Implementation

The skill operates in three main phases:

### 🔍 Phase 1: Descendant Issue Discovery

Discovers all descendant issues using Jira's `childIssuesOf()` JQL function (automatically recursive).

**Implementation**:

1. **Fetch issue metadata using MCP Jira tool**:
   ```
   mcp__atlassian__jira_get_issue(
     issue_key=<issue-key>,
     fields="summary,description,issuetype,status,comment",
     expand="changelog"
   )
   ```
   - Extract `fields.description` - for text-based PR URL extraction
   - Extract `fields.comment.comments` - for PR URLs mentioned in comments
   - Extract `changelog.histories` - for remote link PR URLs from `RemoteIssueLink` field changes

2. **Search for ALL descendant issues using JQL**:
   ```
   mcp__atlassian__jira_search(
     jql="issue in childIssuesOf(<issue-key>)",
     fields="key",
     limit=100
   )
   ```
   - **Important**: `childIssuesOf()` is **already recursive** - returns ALL descendant issues (Epics, Stories, Subtasks, etc.) regardless of depth
   - Single JQL query gets everything - no manual recursion needed
   - Only fetch `key` field here - will fetch full data (including changelog) per-issue in Phase 2
   - **Note**: `jira_search` does NOT support `expand` parameter - use `jira_get_issue` with `expand="changelog"` for each issue

3. **Fetch full data for each issue** (including root + all descendants):
   ```
   for each issue_key:
     mcp__atlassian__jira_get_issue(
       issue_key=<issue-key>,
       fields="summary,description,issuetype,status,comment",
       expand="changelog"
     )
   ```
   - This fetches description, comments, and changelog (which includes remote links)
   - Excludes issue links (`relates to`, `blocks`, etc.) - only parent-child relationships

### 🔗 Phase 2: GitHub PR Extraction

Extracts PR URLs from two sources:

### Source 1: Jira Remote Links via Changelog (primary)
- **Extract remote links from issue changelog** (using MCP with authenticated access):
  ```bash
  # Fetch issue with changelog expansion (store in variable)
  issue_json=$(mcp__atlassian__jira_get_issue \
    issue_key="${issue_key}" \
    expand="changelog")

  # Extract RemoteIssueLink entries from changelog
  pr_urls=$(echo "$issue_json" | jq -r '
    .changelog.histories[]?.items[]? |
    select(.field == "RemoteIssueLink") |
    .toString // .to_string |
    match("https://github\\.com/[^/]+/[^/]+/(pull|pulls)/[0-9]+") |
    .string
  ' | sort -u)
  ```
- **Important**:
  - Remote links appear in changelog as `RemoteIssueLink` field changes
  - Changelog contains link creation events with GitHub PR URLs in `toString` or `to_string` field
  - Store results in variables, not temporary files
  - Uses MCP authentication (no separate curl needed)
- Filters for GitHub PR URLs matching `/pull/` or `/pulls/` pattern

### Source 2: Text Content (backup)
- Searches both `fields.description` and `fields.comment.comments[]` (already fetched in Phase 1)
- **Description**: Extract from `fields.description` (plain text or Jira wiki format)
- **Comments**: Iterate through `fields.comment.comments[]` array and search each `comment.body`
- Uses regex: `https?://github\.com/([\w-]+)/([\w-]+)/pulls?/(\d+)`
- **Example extraction (using variables)**:
  ```bash
  # From description (stored in variable from MCP response)
  description_prs=$(echo "$description" | \
    grep -oE 'https?://github\.com/[^/]+/[^/]+/pulls?/[0-9]+')

  # From comments (parse JSON in memory)
  comment_prs=$(echo "$issue_json" | \
    jq -r '.fields.comment.comments[]?.body // empty' | \
    grep -oE 'https?://github\.com/[^/]+/[^/]+/pulls?/[0-9]+')

  # Combine all PRs
  all_prs=$(echo -e "${description_prs}\n${comment_prs}" | sort -u)
  ```

**Deduplication**:
- Merges URLs found in multiple sources/issues
- Tracks `sources` array: `["comment", "description", "remote_link"]` (alphabetically sorted)
  - `"comment"`: Found in issue comments
  - `"description"`: Found in issue description
  - `"remote_link"`: Found via Jira Remote Links API
- Tracks `found_in_issues` array: `["OCPSTRAT-1612", "CNTRLPLANE-1201"]` (alphabetically sorted)
- **Important**: If same PR URL found in multiple sources or issues, merge into single entry with combined arrays

### 📊 Phase 3: Data Structuring and Output

**PR Metadata**: Fetch via `gh pr view {url} --json state,title,isDraft`. **CRITICAL**: When building the output JSON, you MUST use the exact values returned by `gh pr view` - do NOT manually type or guess PR states/titles.

**Output**: Build JSON in memory using `jq -n`, output to console. Only save to `.work/extract-prs/{issue-key}/output.json` if user explicitly requests.

**Important**: Use bash variables for all data - no temporary files to avoid user confirmation prompts.

## Error Handling

- **MCP server not available**: Display error message directing user to configure MCP server (see Prerequisites)
- **Issue not found**: Log warning and continue with remaining issues
- **Permission denied**:
  - If MCP returns 403 for private issues, verify JIRA_PERSONAL_TOKEN is configured correctly
  - MCP authentication handles all Jira access (including changelog and remote links)
- **Changelog expansion fails**: If `expand="changelog"` returns error, continue with text-based extraction only (graceful degradation)
- **No PRs found**: Return empty `pull_requests` array (valid result)
- **Too many descendants**: If hierarchy has >100 issues, increase `limit` parameter in `jira_search`
- **GitHub rate limit**: If `gh pr view` fails due to rate limiting, display error with reset time
- **PR metadata fetch fails**: If `gh pr view` returns error (PR deleted/private), exclude that PR from output

## Performance Considerations

**API calls**: 1 `jira_search` + N `jira_get_issue` (with changelog) + M `gh pr view`
- Example: 11 issues = 12 MCP calls + M PR fetches
- Changelog expansion includes remote links (no extra calls needed)
- Can parallelize: issue fetching and PR metadata fetching

**File I/O**: Save PR metadata to `.work/extract-prs/{issue-key}/pr-*-metadata.json`, build final JSON by reading files
