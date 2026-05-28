---
name: extract-prs
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
- ✅ **Always recursive**: Automatically discovers all descendant issues via `parent = KEY` BFS
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

### Phase 1: Descendant Issue Discovery

Discovers all descendant issues using `parent = KEY` JQL with BFS recursion.

**Implementation**:

1. **Fetch issue metadata** via `getJiraIssue` with the issue key, requesting fields `summary`, `description`, `issuetype`, `status`, `comment`, and `expand: "changelog"`.
   - Extract `fields.description` -- for text-based PR URL extraction
   - Extract `fields.comment.comments` -- for PR URLs mentioned in comments
   - Extract `changelog.histories` -- for remote link PR URLs from `RemoteIssueLink` field changes

2. **Search for descendant issues using BFS** via `searchJiraIssuesUsingJql` with `jql: "parent = <issue-key>"`, `fields: ["key"]`, and `maxResults: 100`. Recursively search `parent = <child-key>` for each result until no more children. Only fetch the `key` field here -- full data (including changelog) is fetched per-issue in Phase 2.

3. **Fetch full data for each issue** (including root + all descendants) via `getJiraIssue` with fields `summary`, `description`, `issuetype`, `status`, `comment`, and `expand: "changelog"`. This fetches description, comments, and changelog (which includes remote links). Excludes issue links (`relates to`, `blocks`, etc.) -- only parent-child relationships.

### 🔗 Phase 2: GitHub PR Extraction

Extracts PR URLs from two sources:

### Source 1: Jira Remote Links via Changelog (primary)
- **Extract remote links from issue changelog** (using MCP with authenticated access):
  1. Fetch the issue via `getJiraIssue` with `issueIdOrKey` and `expand: "changelog"`
  2. From the response, extract `changelog.histories[].items[]` entries where `field == "RemoteIssueLink"`
  3. Parse the `toString` (or `to_string`) value of each entry for GitHub PR URLs matching `https://github.com/{owner}/{repo}/pull/{number}`
  4. Deduplicate the extracted URLs
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
  - If MCP returns 403 for private issues, verify JIRA_API_TOKEN and JIRA_USERNAME are set and match a valid Jira account
  - MCP authentication handles all Jira access (including changelog and remote links)
- **Changelog expansion fails**: If `expand="changelog"` returns error, continue with text-based extraction only (graceful degradation)
- **No PRs found**: Return empty `pull_requests` array (valid result)
- **Too many descendants**: If hierarchy has >100 issues, increase `maxResults` parameter in `searchJiraIssuesUsingJql`
- **GitHub rate limit**: If `gh pr view` fails due to rate limiting, display error with reset time
- **PR metadata fetch fails**: If `gh pr view` returns error (PR deleted/private), exclude that PR from output

## Performance Considerations

**API calls**: BFS `searchJiraIssuesUsingJql` calls + N `getJiraIssue` (with changelog) + M `gh pr view`
- Example: 11 issues = BFS discovery calls + 11 MCP detail calls + M PR fetches
- Changelog expansion includes remote links (no extra calls needed)
- Can parallelize: issue fetching and PR metadata fetching

**File I/O**: Save PR metadata to `.work/extract-prs/{issue-key}/pr-*-metadata.json`, build final JSON by reading files
