---
description: List and analyze JIRA issues organized by component with flexible filtering
argument-hint: <project-key> [time-period] [--component name] [--assignee username] [--reporter username] [--status status] [--search term] [--search-description]
---

## Name
jira:issues-by-component

## Synopsis
```
/jira:issues-by-component <project-key> [time-period] [--component component-name] [--assignee username] [--reporter username] [--status status] [--search search-term] [--search-description]
```

## Description

The `jira:issues-by-component` command provides a comprehensive view of JIRA issues organized by component. It supports two modes of operation:

1. **Overview Mode** (no `--component` flag): Lists all components with high-level statistics
2. **Detail Mode** (`--component` specified): Shows detailed issue information for a specific component

This command is particularly useful for:
- Understanding component-level workload distribution
- Finding issues by component and user assignment
- Identifying component-specific patterns or problems
- Sprint/release planning by component
- Searching for specific issues within component contexts
- Team capacity planning and workload analysis

**Key Features:**
- **Component organization** - Issues grouped by JIRA component
- **Flexible time filtering** - Filter by creation date or update date
- **User filtering** - Filter by assignee or reporter
- **Status filtering** - Focus on specific workflow states
- **Text search** - Find issues by keywords in summary or description
- **Dual-mode output** - Overview or detailed views based on your needs

## Prerequisites

This command requires JIRA credentials to be configured as environment variables. It uses direct API calls with a secure wrapper script to prevent token exposure.

### 1. Install the Jira Plugin

If you haven't already installed the Jira plugin, see the [Jira Plugin README](../README.md#installation) for installation instructions.

### 2. Configure JIRA Credentials

**Why not use MCP commands?** MCP commands have performance issues when fetching large datasets:
- Each MCP response must be processed by Claude, consuming LLM tokens
- Large result sets (even with pagination) cause 413 errors from Claude due to tool result size limits
- Processing hundreds of tickets through MCP commands creates excessive context usage
- Direct API calls allow us to stream data to disk without intermediate processing

**Solution:** This command uses a secure curl wrapper script that:
- Reads credentials from environment variables
- Prevents token exposure in process listings or command history
- Streams data directly to disk for efficient processing

**Required Environment Variables:**

Set the following environment variables:

```bash
export JIRA_URL="https://issues.redhat.com"
export JIRA_PERSONAL_TOKEN="your-redhat-jira-personal-token-here"
```

**Or for JIRA Cloud:**

```bash
export JIRA_URL="https://your-domain.atlassian.net"
export JIRA_API_TOKEN="your-atlassian-api-token-here"
```

**Getting Your Tokens:**
- **Red Hat JIRA PAT** (preferred for Red Hat JIRA): [Personal Access Tokens Page](https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens)
- **Atlassian API Token** (for JIRA Cloud): [API Token Management](https://id.atlassian.com/manage-profile/security/api-tokens)

**Recommended: Create a credentials file**

To avoid setting variables every time, create `~/.jira-credentials`:

```bash
# ~/.jira-credentials
export JIRA_URL="https://issues.redhat.com"
export JIRA_PERSONAL_TOKEN="your-token-here"
```

Then make it readable only by you:
```bash
chmod 600 ~/.jira-credentials
```

And source it when needed:
```bash
source ~/.jira-credentials
```

**Note:** The command will use `JIRA_PERSONAL_TOKEN` if available (preferred for Red Hat JIRA), otherwise falls back to `JIRA_API_TOKEN`.

## Implementation

The command executes the following workflow:

### 1. Verify Environment Variables

- Check that required environment variables are set:
  ```bash
  if [ -z "${JIRA_URL:-}" ]; then
    echo "Error: JIRA_URL environment variable is required"
    echo "Please run: export JIRA_URL='https://issues.redhat.com'"
    exit 1
  fi

  if [ -z "${JIRA_PERSONAL_TOKEN:-}" ] && [ -z "${JIRA_API_TOKEN:-}" ]; then
    echo "Error: JIRA authentication token is required"
    echo "Please set: export JIRA_PERSONAL_TOKEN='your-token-here'"
    exit 1
  fi
  ```
- If credentials are missing, display error message with setup instructions from Prerequisites section
- The wrapper script (`jira_curl.sh`) will handle these checks automatically

### 2. Parse Arguments and Set Defaults

- Parse project key from $1 (required): "OCPBUGS", "JIRA", "HYPE", etc.
- Parse optional time-period from $2:
  - `last-week` (default if not specified)
  - `last-2-weeks`
  - `last-month`
  - Custom range: `YYYY-MM-DD:YYYY-MM-DD`
- Parse optional flags:
  - `--component <name>`: Filter to specific component (enables Detail Mode)
  - `--assignee <username>`: Filter by assignee
  - `--reporter <username>`: Filter by reporter
  - `--status <status>`: Filter by status (comma-separated for multiple)
  - `--search <term>`: Search term for summary (space or comma-separated for multiple keywords)
  - `--search-description`: Include description in search (only works with `--search`)
- Validate project key format (uppercase, may contain hyphens)
- Create working directory: `mkdir -p .work/jira-issues-by-component/{project-key}/`

### 3. Construct JQL Query

Build JQL query based on provided filters:

**Base query:**
```jql
project = {project-key}
```

**Add time filter (if time-period provided):**
```jql
AND created >= -{time-period}
```

**Add component filter (if --component provided):**
```jql
AND component = "{component-name}"
```

**Add assignee filter (if --assignee provided):**
```jql
AND assignee = {username}
```

**Add reporter filter (if --reporter provided):**
```jql
AND reporter = {username}
```

**Add status filter (if --status provided):**
```jql
AND status IN ({status1}, {status2}, ...)
```

**Note:** Text search (`--search`) is applied post-fetch in Python for better performance and flexibility.

**Example JQL:**
```jql
project = OCPBUGS
AND created >= -7d
AND component = "Cluster Version Operator"
AND assignee = jsmith
AND status IN (Open, In Progress)
ORDER BY component ASC, priority DESC, updated DESC
```

- URL-encode the JQL query for use in API requests

### 4. Fetch All Issues Using Secure Curl Wrapper with Pagination

**Fetch Strategy:**
- Fetch 1000 tickets per request (JIRA's maximum `maxResults` value)
- Use pagination (`startAt` parameter) to fetch all matching tickets
- Save each batch directly to disk to avoid memory issues
- Continue until all tickets are fetched

**Security:**
- Use `jira_curl.sh` wrapper script to prevent token exposure
- Token is read from environment variables inside the script
- Never appears in process listings (`ps aux`) or command history
- Wrapper script path: `plugins/jira/skills/jira-issues-by-component/jira_curl.sh`

**Important API Details:**
- Use `/rest/api/2/search` endpoint (API v2 works reliably with Red Hat JIRA)
- Wrapper automatically adds `Authorization: Bearer` header
- Check HTTP response code to detect authentication failures
- Request fields: `summary,status,priority,assignee,reporter,created,updated,description,labels,components,issuetype`

**Batch Processing Loop:**
```bash
# Get path to secure curl wrapper
PLUGIN_DIR="plugins/jira/skills/jira-issues-by-component"
JIRA_CURL="${PLUGIN_DIR}/jira_curl.sh"

# Verify wrapper script exists
if [ ! -x "$JIRA_CURL" ]; then
  echo "Error: Secure curl wrapper not found at: $JIRA_CURL"
  exit 1
fi

START_AT=0
BATCH_NUM=0
TOTAL_FETCHED=0

while true; do
  # Construct API URL with pagination
  API_URL="${JIRA_URL}/rest/api/2/search?\
jql=${ENCODED_JQL}&\
startAt=${START_AT}&\
maxResults=1000&\
fields=summary,status,priority,assignee,reporter,created,updated,description,labels,components,issuetype"

  # Fetch batch using secure wrapper (token not exposed in process list)
  HTTP_CODE=$("$JIRA_CURL" -s -w "%{http_code}" \
    -o ".work/jira-issues-by-component/${PROJECT_KEY}/batch-${BATCH_NUM}.json" \
    "${API_URL}")

  # Check HTTP response code
  if [ "$HTTP_CODE" -ne 200 ]; then
    echo "Error: HTTP $HTTP_CODE received"
    cat ".work/jira-issues-by-component/${PROJECT_KEY}/batch-${BATCH_NUM}.json"
    exit 1
  fi

  # Parse response to check if more results exist
  BATCH_SIZE=$(jq '.issues | length' ".work/jira-issues-by-component/${PROJECT_KEY}/batch-${BATCH_NUM}.json")
  TOTAL=$(jq '.total' ".work/jira-issues-by-component/${PROJECT_KEY}/batch-${BATCH_NUM}.json")

  TOTAL_FETCHED=$((TOTAL_FETCHED + BATCH_SIZE))

  echo "✓ Fetched ${BATCH_SIZE} issues (${TOTAL_FETCHED}/${TOTAL} total)"

  # Check if done
  if [ ${TOTAL_FETCHED} -ge ${TOTAL} ] || [ ${BATCH_SIZE} -eq 0 ]; then
    break
  fi

  # Move to next batch
  START_AT=$((START_AT + 1000))
  BATCH_NUM=$((BATCH_NUM + 1))
done

echo ""
echo "✓ Fetching complete: ${TOTAL_FETCHED} issues downloaded in $((BATCH_NUM + 1)) batch(es)"
```

**Why secure wrapper instead of direct curl:**
- **Security**: Token never exposed in process listings or command history
- **Reliability**: Direct file streaming avoids Claude's tool result size limits (413 errors)
- **Performance**: Can handle thousands of tickets without LLM token consumption
- **Speed**: No intermediate serialization through MCP protocol
- **Consistency**: Same security pattern as `oc auth` skill


### 5. Generate Output Report

Load the grouped data and generate the appropriate report based on mode:

#### Overview Mode (no --component flag)

**Format:**
```markdown
# Issues by Component - {PROJECT_KEY}

**Period**: {time-period}
**Filters**: {list active filters}
**Total Issues**: {count}
**Components**: {count}

---

## Component Summary

### 1. Cluster Version Operator (45 issues)
**Status Distribution**: 30 Open, 10 In Progress, 5 Closed
**Priority Distribution**: 15 Critical/High, 20 Normal, 10 Low
**Types**: 25 Bug, 15 Story, 5 Task

**Top Issues**:
- OCPBUGS-1234: CVE update fails - Critical, Open
- OCPBUGS-1235: Upgrade timeout - High, In Progress
- OCPBUGS-1236: Version skew detection - Normal, Open

---

### 2. Networking (32 issues)
**Status Distribution**: 20 Open, 8 In Progress, 4 Closed
**Priority Distribution**: 8 Critical/High, 18 Normal, 6 Low
**Types**: 18 Bug, 10 Story, 4 Task

**Top Issues**:
- OCPBUGS-5678: DNS resolution issue - High, Open
- OCPBUGS-5679: Network policy conflict - Normal, In Progress

---

### Issues Without Component (12)
12 issues are not assigned to any component
```

#### Detail Mode (--component specified)

**Format:**
```markdown
# Component: {COMPONENT_NAME}

**Project**: {PROJECT_KEY}
**Period**: {time-period}
**Filters**: {list active filters}
**Total Issues**: {count}

---

## Statistics

**Status Distribution**: 30 Open, 10 In Progress, 5 Closed
**Priority Distribution**: 15 Critical/High, 20 Normal, 10 Low
**Type Distribution**: 25 Bug, 15 Story, 5 Task

---

## Critical Priority (3 issues)

### OCPBUGS-1234: CVE update fails on multi-arch clusters
**Status**: Open | **Priority**: Critical | **Type**: Bug
**Assignee**: jsmith | **Reporter**: asmith
**Created**: 2024-12-01 | **Updated**: 2 days ago
**Labels**: security, multi-arch

**Description**:
{First 300 chars of description}

---

### OCPBUGS-1235: Security vulnerability in API endpoint
**Status**: In Progress | **Priority**: Critical | **Type**: Bug
...

---

## High Priority (12 issues)

### OCPBUGS-1240: Upgrade timeout after 30 minutes
**Status**: Open | **Priority**: High | **Type**: Bug
**Assignee**: jdoe | **Reporter**: user1
**Created**: 2024-11-28 | **Updated**: 5 days ago
**Labels**: upgrade, performance

**Description**:
{First 300 chars of description}

---

## Normal Priority (20 issues)
...

## Low Priority (10 issues)
...
```

### 6. Display Report to User

- Show the formatted report (overview or detail mode)
- Provide guidance on next steps:
  - Suggest using `/jira:issues-by-component {project} --component "{name}"` to drill down
  - Suggest using `/jira:solve {issue-key}` to start working on an issue
  - Suggest refining filters if too many/too few results

### 7. Save Report (Optional)

- Offer to save report to `.work/jira-issues-by-component/{project-key}-{component-name}-{timestamp}.md`
- Useful for documentation and tracking

## Error Handling

**Missing environment variables**: If JIRA_URL is not set:
```
Error: JIRA_URL environment variable is required

Please set JIRA credentials:
  export JIRA_URL='https://issues.redhat.com'
  export JIRA_PERSONAL_TOKEN='your-token-here'

Alternatively, source a credentials file:
  source ~/.jira-credentials
```

**Missing authentication token**: If neither JIRA_PERSONAL_TOKEN nor JIRA_API_TOKEN is set:
```
Error: JIRA authentication token is required

Please set either:
  export JIRA_PERSONAL_TOKEN='your-token-here'  # Preferred for Red Hat JIRA
  export JIRA_API_TOKEN='your-token-here'       # For JIRA Cloud

Get your token from:
  - Red Hat JIRA PAT: https://issues.redhat.com/secure/ViewProfile.jspa?...
  - Atlassian API Token: https://id.atlassian.com/manage-profile/security/api-tokens
```

**Authentication failure**: If curl returns 401/403:
```
Error: JIRA authentication failed (HTTP 401/403)

Please verify your JIRA credentials:
1. Check that JIRA_URL is correct: echo $JIRA_URL
2. Check that your token is valid and not expired
3. Try generating a new token from the JIRA web interface
```

**Invalid project key**: Display error with example format

**No issues found**:
- Explain why (filters may be too restrictive)
- Suggest relaxing filters
- Verify project key and component name are correct

**Component not found**: If `--component` specified but component doesn't exist in project:
```
Error: Component "{component-name}" not found in project {project-key}

Available components:
- Cluster Version Operator
- Networking
- Storage
...
```

**Invalid time period**: Display supported formats with examples

**curl errors**: Check exit code and display helpful error message

**jq not found**: Inform user to install jq

**Rate limiting**: If API returns 429, implement exponential backoff (wait 60s, retry)

## Return Value

- **Console Output**: Formatted report showing issues organized by component
- **Intermediate Files** (created during processing):
  - `.work/jira-issues-by-component/{project-key}/batch-*.json` - Raw JIRA API responses
  - `.work/jira-issues-by-component/{project-key}/process_batches.py` - Python processing script
  - `.work/jira-issues-by-component/{project-key}/grouped.json` - Issues grouped by component with statistics
- **Optional Final Report**: `.work/jira-issues-by-component/{project-key}-{component-name}-{timestamp}.md`

## Examples

**Note:** All examples require JIRA credentials to be set as environment variables (see Prerequisites section).

**Before running any examples, set your credentials:**
```bash
# Option 1: Export directly
export JIRA_URL="https://issues.redhat.com"
export JIRA_PERSONAL_TOKEN="your-token-here"

# Option 2: Source from credentials file
source ~/.jira-credentials
```

### Overview Mode Examples

1. **Basic overview - all components from last week**:
   ```
   /jira:issues-by-component OCPBUGS last-week
   ```
   Output: High-level summary of all components with issue counts and top issues

2. **Overview with status filter**:
   ```
   /jira:issues-by-component OCPBUGS last-month --status "Open,In Progress"
   ```
   Output: All components showing only open and in-progress issues

3. **Overview with assignee filter**:
   ```
   /jira:issues-by-component OCPBUGS last-2-weeks --assignee jsmith
   ```
   Output: All components showing only issues assigned to jsmith

4. **Overview with search**:
   ```
   /jira:issues-by-component OCPBUGS last-week --search "upgrade timeout"
   ```
   Output: All components showing only issues with "upgrade" or "timeout" in summary

### Detail Mode Examples

5. **Detailed view of specific component**:
   ```
   /jira:issues-by-component OCPBUGS --component "Cluster Version Operator"
   ```
   Output: Detailed listing of all issues in the Cluster Version Operator component

6. **Component detail with time filter**:
   ```
   /jira:issues-by-component OCPBUGS last-week --component "Networking"
   ```
   Output: Detailed issues from Networking component created in the last week

7. **Component detail with user and status filters**:
   ```
   /jira:issues-by-component OCPBUGS --component "Storage" --assignee jsmith --status Open
   ```
   Output: Detailed view of open Storage issues assigned to jsmith

8. **Component detail with search in summary and description**:
   ```
   /jira:issues-by-component OCPBUGS --component "Networking" --search "DNS timeout" --search-description
   ```
   Output: Detailed Networking issues containing "DNS" or "timeout" in summary or description

### Advanced Examples

9. **Custom date range with multiple filters**:
   ```
   /jira:issues-by-component OCPBUGS 2024-11-01:2024-11-30 --component "Cluster Version Operator" --status "Open,In Progress" --search CVE
   ```
   Output: CVE-related issues in CVO component from November that are still active

10. **Reporter-based filtering**:
    ```
    /jira:issues-by-component OCPBUGS last-month --reporter asmith --status Closed
    ```
    Output: Overview of all components showing closed issues reported by asmith

11. **Multiple search terms**:
    ```
    /jira:issues-by-component OCPBUGS --search "authentication authorization security"
    ```
    Output: Overview showing issues mentioning any security-related keywords

## Arguments

- **project-key** (required, $1): JIRA project key to search
  - Must be uppercase
  - May contain hyphens (e.g., "OCPBUGS", "HYPE")
  - If not provided, will prompt user

- **time-period** (optional, $2): Time range for issue filtering
  - `last-week` (default)
  - `last-2-weeks`
  - `last-month`
  - `YYYY-MM-DD:YYYY-MM-DD` (custom range)
  - If not provided, defaults to `last-week`

- **--component** (optional): Filter to specific component
  - Enables Detail Mode with verbose issue information
  - Component name must match exactly (case-sensitive)
  - Example: `--component "Cluster Version Operator"`

- **--assignee** (optional): Filter by assignee username
  - Only shows issues assigned to specified user
  - Example: `--assignee jsmith`

- **--reporter** (optional): Filter by reporter username
  - Only shows issues reported by specified user
  - Example: `--reporter asmith`

- **--status** (optional): Filter by issue status
  - Single status: `--status Open`
  - Multiple statuses (comma-separated): `--status "Open,In Progress,Reopened"`
  - Common statuses: Open, In Progress, Closed, Resolved, Verified

- **--search** (optional): Search term(s) for filtering
  - Searches in issue summary (title) by default
  - Multiple keywords (space or comma-separated): `--search "upgrade timeout failure"`
  - Case-insensitive matching
  - Any keyword match includes the issue

- **--search-description** (optional): Include description in search
  - Only works when `--search` is also specified
  - Searches both summary and description text
  - May return more results but slower
  - Example: `--search "DNS" --search-description`

## See Also

- `/jira:backlog` - Find suitable backlog tickets to work on
- `/jira:grooming` - Generate grooming meeting agendas
- `/jira:solve` - Start working on a specific issue
