---
description: Find suitable JIRA tickets from the backlog to work on based on priority and activity
argument-hint: [project-key] [--assignee username] [--days-inactive N]
---

## Name
jira:backlog

## Synopsis
```bash
/jira:backlog [project-key] [--assignee username] [--days-inactive N]
```

## Description

The `jira:backlog` command helps identify suitable tickets from the JIRA backlog to work on by **intelligently analyzing** unassigned tickets and bot-assigned tickets. Unlike simple filtering, this command reads ticket descriptions, comments, and activity patterns to recommend the best candidates for work.

**Key Feature:** The command selects **2 tickets from each priority level** (Critical, High, Normal, Low) that are **actually available to pick up** (unassigned or assigned to bots only), giving you a balanced view across all priorities so you can choose based on your expertise and preference.

**Important:** This command only recommends tickets that are **unassigned** or **assigned to bots** (like "OCP DocsBot"). Tickets assigned to real people are excluded, even if they have no recent activity, because they may already be claimed by someone.

This command is particularly useful for:
- Finding tickets to work on when you have available capacity
- Identifying unassigned or abandoned tickets that need attention
- Getting a mix of priorities to choose from (not just critical)
- Understanding ticket context before starting work

How it works:
- Searches for unassigned tickets or tickets with no activity for 28+ days (configurable)
- **Filters for availability** - keeps only unassigned or bot-assigned tickets
- **Analyzes ticket content** - reads descriptions, comments, and activity patterns
- **Evaluates suitability** - identifies tickets that are ready vs. need verification vs. may be abandoned
- **Selects intelligently** - chooses the most suitable 2 tickets from each priority level
- Provides comprehensive summaries with recommendations for each ticket

## Prerequisites

This command requires JIRA credentials to be configured via the JIRA MCP server setup, even though it uses direct API calls instead of MCP commands.

### 1. Install the Jira Plugin

If you haven't already installed the Jira plugin, see the [Jira Plugin README](../README.md#installation) for installation instructions.

### 2. Configure JIRA Credentials via MCP Configuration File

**⚠️ Important:** While this command does NOT use MCP commands to query JIRA, it DOES read credentials from the MCP server configuration file. You must configure the MCP server settings even if you're only using this command.

**Why not use MCP commands?** The MCP approach has performance issues when fetching large datasets:
- Each MCP response must be processed by Claude, consuming tokens
- Large result sets (even with pagination) cause 413 errors from Claude due to tool result size limits
- Processing hundreds of tickets through MCP commands creates excessive context usage
- Direct API calls allow us to stream data to disk without intermediate processing

**Solution:** This command uses `curl` to fetch data directly from JIRA and save to disk, then processes it with Python. It reads JIRA credentials from `~/.config/claude-code/mcp.json` - the same file used by the MCP server.

**Required Configuration File Format:**

Create or edit `~/.config/claude-code/mcp.json`:

```json
{
  "mcpServers": {
    "atlassian": {
      "command": "npx",
      "args": ["mcp-atlassian"],
      "env": {
        "JIRA_URL": "https://issues.redhat.com",
        "JIRA_USERNAME": "your-email@redhat.com",
        "JIRA_API_TOKEN": "your-atlassian-api-token-here",
        "JIRA_PERSONAL_TOKEN": "your-redhat-jira-personal-token-here"
      }
    }
  }
}
```

**Field Descriptions:**
- `JIRA_URL`: Your JIRA instance URL (e.g., `https://issues.redhat.com` for Red Hat JIRA)
- `JIRA_USERNAME`: Your JIRA username/email address
- `JIRA_API_TOKEN`: Atlassian API token from [Atlassian API Token Management Page](https://id.atlassian.com/manage-profile/security/api-tokens)
- `JIRA_PERSONAL_TOKEN`: Red Hat JIRA Personal Access Token from [Red Hat Jira PAT Management Page](https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens)

**Note:** The command will use `JIRA_PERSONAL_TOKEN` if available (preferred for Red Hat JIRA), otherwise falls back to `JIRA_API_TOKEN`.

### 3. Start Local MCP Server with Podman

**⚠️ Recommended Setup:** Use the podman containerized approach. We tested npx methods on October 31, 2025, and encountered 404 errors and missing dependencies. The containerized setup works reliably.

**Steps:**

1. **First, ensure your `~/.config/claude-code/mcp.json` is created with credentials** (see example above)

2. **Start the MCP server container using credentials from mcp.json:**

   ```bash
   # Extract credentials from your mcp.json file
   JIRA_URL=$(jq -r '.mcpServers.atlassian.env.JIRA_URL' ~/.config/claude-code/mcp.json)
   JIRA_USERNAME=$(jq -r '.mcpServers.atlassian.env.JIRA_USERNAME' ~/.config/claude-code/mcp.json)
   JIRA_API_TOKEN=$(jq -r '.mcpServers.atlassian.env.JIRA_API_TOKEN' ~/.config/claude-code/mcp.json)
   JIRA_PERSONAL_TOKEN=$(jq -r '.mcpServers.atlassian.env.JIRA_PERSONAL_TOKEN' ~/.config/claude-code/mcp.json)

   # Start the container
   podman run -d --name mcp-atlassian -p 8080:8080 \
     -e "JIRA_URL=${JIRA_URL}" \
     -e "JIRA_USERNAME=${JIRA_USERNAME}" \
     -e "JIRA_API_TOKEN=${JIRA_API_TOKEN}" \
     -e "JIRA_PERSONAL_TOKEN=${JIRA_PERSONAL_TOKEN}" \
     -e "JIRA_SSL_VERIFY=true" \
     ghcr.io/sooperset/mcp-atlassian:latest --transport sse --port 8080 -vv
   ```

3. **Verify the container is running:**
   ```bash
   podman ps | grep mcp-atlassian
   ```

4. **Restart Claude Code** to ensure it reads the mcp.json configuration

**Managing the Container:**
```bash
# Check if container is running
podman ps | grep mcp-atlassian

# View logs
podman logs mcp-atlassian

# Stop the container
podman stop mcp-atlassian

# Start the container again
podman start mcp-atlassian

# Remove the container (you'll need to run 'podman run' again)
podman rm mcp-atlassian
```

### 4. Verify MCP Server Configuration

To verify your MCP server is properly configured and can connect to JIRA, you can test it with a simple JIRA query in Claude Code:

```bash
Ask Claude Code to run: "Use the mcp__atlassian__jira_get_issue tool to fetch OCPBUGS-1"
```

If the MCP server is properly configured, you should see issue details returned. If you see an error:
- **"Tool not found"**: The MCP server is not properly registered with Claude Code. Re-run the `claude mcp add` command.
- **"Authentication failed"** or **401/403 errors**: Check your `JIRA_PERSONAL_TOKEN` and `JIRA_USERNAME` are correct.
- **"Connection refused"**: If using a local MCP server, ensure the podman container is running (`podman ps`).
- **"Could not find issue"**: Your authentication works! This just means the specific issue doesn't exist or you don't have access.

See the [full JIRA Plugin README](../README.md) for complete setup instructions and troubleshooting.

## Implementation

The command executes the following workflow:

1. **Extract Credentials from MCP Configuration File**
   - Read credentials from `~/.config/claude-code/mcp.json`
   - Extract from the `atlassian` MCP server configuration:
     ```bash
     MCP_CONFIG="$HOME/.config/claude-code/mcp.json"

     JIRA_URL=$(jq -r '.mcpServers.atlassian.env.JIRA_URL' "$MCP_CONFIG")
     JIRA_EMAIL=$(jq -r '.mcpServers.atlassian.env.JIRA_USERNAME // .mcpServers.atlassian.env.JIRA_EMAIL' "$MCP_CONFIG")
     JIRA_PERSONAL_TOKEN=$(jq -r '.mcpServers.atlassian.env.JIRA_PERSONAL_TOKEN' "$MCP_CONFIG")
     JIRA_API_TOKEN=$(jq -r '.mcpServers.atlassian.env.JIRA_API_TOKEN' "$MCP_CONFIG")

     # Use JIRA_PERSONAL_TOKEN if available, otherwise fall back to JIRA_API_TOKEN
     AUTH_TOKEN="${JIRA_PERSONAL_TOKEN:-$JIRA_API_TOKEN}"
     ```
   - If any required credentials are missing or the file doesn't exist, display error:
     ```bash
     Error: JIRA credentials not configured.

     This command requires JIRA credentials from the MCP server configuration file.
     Please create or edit ~/.config/claude-code/mcp.json with your JIRA credentials.

     See Prerequisites section for the required mcp.json format and setup instructions.
     ```

2. **Parse Arguments and Set Defaults**
   - Parse project key from $1 (required): "OCPBUGS", "JIRA", "HYPE", etc.
   - Parse optional --assignee filter (defaults to "Unassigned")
   - Parse optional --days-inactive (defaults to 28 days)
   - Validate project key format (uppercase, may contain hyphens)
   - Create working directory: `mkdir -p .work/jira-backlog/{project-key}/`

3. **Construct JQL Query**
   - Build base JQL query:
     ```jql
     project = {project-key}
     AND status NOT IN (Closed, Resolved, Done, Verified, Release Pending, ON_QA)
     AND (
       assignee IS EMPTY
       OR updated <= -{days-inactive}d
     )
     ORDER BY priority DESC, updated ASC
     ```
   - If --assignee provided, replace assignee filter with: `AND assignee = {username} AND updated <= -{days-inactive}d`
   - URL-encode the JQL query for use in API requests

4. **Fetch All Backlog Tickets Using curl with Pagination**

   **Fetch Strategy:**
   - Fetch 1000 tickets per request (JIRA's maximum `maxResults` value)
   - Use pagination (`startAt` parameter) to fetch all tickets
   - Save each batch directly to disk to avoid memory issues
   - Continue until all tickets are fetched

   **Authentication:**
   - For Red Hat JIRA (Data Center): Use Bearer token with `JIRA_PERSONAL_TOKEN` (recommended)
   - For JIRA Cloud: Can use Basic Auth with `email:api_token`, but Bearer token also works

   **Important API Details:**
   - Use `/rest/api/2/search` endpoint (API v2 works reliably with Red Hat JIRA)
   - Use `Authorization: Bearer ${JIRA_PERSONAL_TOKEN}` header for authentication
   - Check HTTP response code to detect authentication failures

   **Batch Processing Loop:**
   ```bash
   START_AT=0
   BATCH_NUM=0
   TOTAL_FETCHED=0

   while true; do
     # Construct API URL with pagination
     API_URL="${JIRA_URL}/rest/api/2/search?\
      jql=${ENCODED_JQL}&\
      startAt=${START_AT}&\
      maxResults=1000&\
      fields=summary,status,priority,assignee,reporter,created,updated,description,labels,components,watches,comment"

     # Fetch batch using curl with Bearer token authentication
     HTTP_CODE=$(curl -s -w "%{http_code}" \
       -o "batch-${BATCH_NUM}.json" \
       -H "Authorization: Bearer ${AUTH_TOKEN}" \
       -H "Accept: application/json" \
       "${API_URL}")

     # Check HTTP response code
     if [ "$HTTP_CODE" -ne 200 ]; then
       echo "Error: HTTP $HTTP_CODE received"
       cat "batch-${BATCH_NUM}.json"
       exit 1
     fi

     # Parse response to check if more results exist
     BATCH_SIZE=$(jq '.issues | length' "batch-${BATCH_NUM}.json")
     TOTAL=$(jq '.total' "batch-${BATCH_NUM}.json")

     TOTAL_FETCHED=$((TOTAL_FETCHED + BATCH_SIZE))

     echo "✓ Fetched ${BATCH_SIZE} tickets (${TOTAL_FETCHED}/${TOTAL} total)"

     # Check if done
     if [ ${TOTAL_FETCHED} -ge ${TOTAL} ] || [ ${BATCH_SIZE} -eq 0 ]; then
       break
     fi

     # Move to next batch
     START_AT=$((START_AT + 1000))
     BATCH_NUM=$((BATCH_NUM + 1))
   done

   echo ""
   echo "✓ Fetching complete: ${TOTAL_FETCHED} tickets downloaded in $((BATCH_NUM + 1)) batch(es)"
   ```bash

   **Why curl instead of MCP:**
   - Direct file streaming avoids Claude's tool result size limits (413 errors)
   - Can handle thousands of tickets without token consumption
   - Faster - no intermediate serialization through MCP protocol
   - More reliable for large datasets

5. **Process Batches with Python to Filter and Group by Priority**

   Create a Python script (`.work/jira-backlog/{project-key}/process_batches.py`) that:

   **Inputs:**
   - All batch files: `.work/jira-backlog/{project-key}/batch-*.json`

   **Processing Logic:**
   ```python
   import json
   import glob
   from collections import defaultdict

   # Load all batches
   all_tickets = []
   for batch_file in sorted(glob.glob('.work/jira-backlog/{project-key}/batch-*.json')):
       with open(batch_file) as f:
           data = json.load(f)
           all_tickets.extend(data['issues'])

   # Filter for available tickets
   available_tickets = []
   for ticket in all_tickets:
       assignee = ticket['fields'].get('assignee')

       # Include if unassigned
       if assignee is None:
           available_tickets.append(ticket)
           continue

       # Include if assigned to a bot
       assignee_name = assignee.get('displayName', '').lower()
       if 'bot' in assignee_name:
           available_tickets.append(ticket)
           continue

       # Otherwise exclude (assigned to real person)

   # Group by priority
   priority_buckets = defaultdict(list)
   for ticket in available_tickets:
       priority_name = ticket['fields']['priority']['name']

       # Normalize priority names
       if priority_name in ['Critical', 'Blocker']:
           priority_buckets['Critical'].append(ticket)
       elif priority_name in ['High', 'Major']:
           priority_buckets['High'].append(ticket)
       elif priority_name in ['Normal', 'Medium']:
           priority_buckets['Normal'].append(ticket)
       elif priority_name in ['Low', 'Minor', 'Trivial']:
           priority_buckets['Low'].append(ticket)

   # Save filtered results
   with open('.work/jira-backlog/{project-key}/filtered.json', 'w') as f:
       json.dump(priority_buckets, f, indent=2)

   # Save statistics
   stats = {p: len(tickets) for p, tickets in priority_buckets.items()}
   with open('.work/jira-backlog/{project-key}/stats.json', 'w') as f:
       json.dump(stats, f, indent=2)

   print(f"Filtered {len(available_tickets)} available tickets from {len(all_tickets)} total")
   print(f"Priority distribution: {stats}")
   ```

   **Outputs:**
- `.work/jira-backlog/{project-key}/filtered.json` - All filtered tickets grouped by priority
- `.work/jira-backlog/{project-key}/stats.json` - Priority distribution statistics

   **Run the script:**
   ```bash
   python .work/jira-backlog/${PROJECT_KEY}/process_batches.py
   ```

6. **Intelligently Analyze and Select Best Tickets from Each Priority**

   **CRITICAL:** This is NOT a mechanical selection process. You must read and analyze ticket content to make intelligent decisions.

   **Load Filtered Data:**
   - Read filtered tickets from `.work/jira-backlog/{project-key}/filtered.json`
   - Data is already grouped by priority level (Critical, High, Normal, Low)

   For each priority level (Critical, High, Normal, Low):

   **Step 6a: Extract Tickets for Human-Readable Analysis**
   - Take the first 10 tickets from each priority bucket (or all available if fewer than 10)
   - For each ticket, format in a readable way showing:
     - Key, summary, status, assignee, reporter
     - Days since last update, number of comments, watchers
     - Description preview (first 300-400 characters)
     - Last 1-3 comments (author, date, first 200 characters of body)
     - Components and labels
   - **Output this formatted data** so you can read and analyze it
   - DO NOT analyze inside Python/bash - extract the data in readable format first

   **Step 6b: Analyze Ticket Suitability**
   Read the formatted data and evaluate each ticket for:

   **Age Classifications (consider when prioritizing):**
   - **Very Fresh (< 30 days):** Highest priority - likely still relevant and active
   - **Recent (30-60 days):** Good candidates - still relatively fresh
   - **Getting Stale (60-90 days):** Verify still relevant before recommending
   - **Old (90-120 days):** Lower priority - may need verification/grooming
   - **Very Old (120+ days):** Lowest priority - likely needs re-evaluation before work

   **Disqualifying Factors (skip these tickets):**
   - **Assigned to real people (non-bots)** - these tickets should have been filtered out in Step 3, but double-check
   - Status is "Verified", "Release Pending", "ON_QA", "Done" (already complete)
   - Zero comments AND very old (120+ days) - likely abandoned
   - Comments indicate "duplicate", "won't fix", "closed as"
   - Comments show work is blocked or waiting on external dependencies

   **Positive Indicators (prioritize these):**
   - **Unassigned or bot-assigned** - available for anyone to pick up
   - **Recency matters:** Fresher tickets (< 60 days) should be weighted higher
   - Active discussion in comments showing real investigation (but not claimed by someone)
   - Clear, reproducible issue with steps to reproduce
   - Recent comments (< 30 days) saying "needs investigation", "looking for owner", "ready for work"
   - Has must-gather, logs, or reproduction environment attached/linked
   - Well-defined scope and acceptance criteria
   - Clear description with some comments showing interest

   **Step 6c: Select Best 2 from Each Priority**
   - Based on your analysis, select the 2 MOST SUITABLE tickets from each priority level
   - **Selection Criteria (in order of importance):**
     1. **Recency:** Fresher tickets (< 60 days) strongly preferred to ensure relevance
     2. **Clarity:** Clear reproduction steps, well-defined scope, available resources (must-gather, logs)
     3. **Impact:** User-facing issues, customer cases, or significant system problems
     4. **Activity:** Active discussion/comments showing the issue is real and being tracked
   - If a priority level has fewer than 2 suitable tickets, include what's available
   - Document WHY each ticket was selected (your reasoning, including age classification)
   - Flag tickets that need verification before work can start
   - In your recommendation, mention the ticket age using the classifications above

7. **Format Output Report**
   Generate a formatted report organized by priority:

   ```bash
   # Backlog Tickets for {project-key}

   ## Search Criteria
   - Project: {project-key}
   - Assignee: {assignee or "Unassigned"}
   - Days Inactive: {days-inactive}+
   - Total Tickets Found: {count}

   ---

   ## Critical Priority ({count} tickets)

   ### 1. {ISSUE-KEY}: {Summary}
   **Status:** {status} | **Updated:** {days} days ago | **Reporter:** {name}
   **Components:** {components} | **Labels:** {labels}
   **Watchers:** {count} | **Comments:** {count}

   **Context:**
   {2-3 sentence summary of the ticket}

   **Recent Activity:**
   - {Most recent comment summary or "No recent comments"}
   - {Status change or "No status changes"}
   - {Blocker/Question if identified}

   **Recommendation:** {Why this ticket is suitable to work on or what's needed before starting}

   ---

   ### 2. {ISSUE-KEY}: {Summary}
   ...

   ---

   ## High Priority ({count} tickets)
   ...

   ## Normal Priority ({count} tickets)
   ...

   ## Low Priority ({count} tickets)
   ...

   ---

   ## Summary
   - Critical: {count} tickets available
   - High: {count} tickets available
   - Normal: {count} tickets available
   - Low: {count} tickets available

   **Suggested Next Steps:**
   1. Review the tickets above and select one that matches your expertise
   2. Check if the ticket has clear acceptance criteria - if not, consider grooming it first using `/jira:grooming {issue-key}`
   3. Use `/jira:solve {issue-key} {remote}` to start working on the ticket
   ```

8. **Display Report to User**
   - Show the formatted report
   - Provide guidance on next steps
   - Suggest using `/jira:grooming` for tickets lacking clarity
   - Suggest using `/jira:solve` to start working on selected ticket

9. **Save Report (Optional)**
   - Offer to save report to `.work/jira-backlog/{project-key}-{timestamp}.md`
   - Useful for tracking backlog trends over time

**Error Handling:**
- **Missing credentials file**: If `~/.config/claude-code/mcp.json` doesn't exist, display:
  ```bash
  Error: JIRA credentials not configured.

  This command requires JIRA credentials from the MCP server configuration file.
  File not found: ~/.config/claude-code/mcp.json

  Please create this file with your JIRA credentials.
  See Prerequisites section for the required mcp.json format and setup instructions.
  ```
- **Invalid credentials in file**: If credentials are missing from mcp.json, display:
  ```bash
  Error: JIRA credentials incomplete in ~/.config/claude-code/mcp.json

  Required fields in .mcpServers.atlassian.env:
  - JIRA_URL (e.g., https://issues.redhat.com)
  - JIRA_USERNAME (your JIRA email/username)
  - JIRA_PERSONAL_TOKEN (preferred) or JIRA_API_TOKEN

  See Prerequisites section for the required mcp.json format.
  ```
- **Authentication failure**: If curl returns 401/403, display:
  ```bash
  Error: JIRA authentication failed (HTTP 401/403)

  Please verify your JIRA credentials in ~/.config/claude-code/mcp.json:
  1. Check that JIRA_PERSONAL_TOKEN is correct and not expired
  2. Verify JIRA_USERNAME matches your JIRA account
  3. Ensure JIRA_URL is correct (e.g., https://issues.redhat.com)
  4. Test authentication: curl -H "Authorization: Bearer YOUR_TOKEN" YOUR_JIRA_URL/rest/api/2/myself

  To regenerate your token, visit:
  https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens
  ```
- **Invalid project key**: Display error with example format (e.g., "OCPBUGS", "JIRA", "HYPE")
- **No tickets found**:
  - Explain why (e.g., all tickets have assignees and recent activity)
  - Suggest relaxing search criteria (lower --days-inactive threshold)
  - Suggest trying different project or removing assignee filter
- **curl errors**: Check exit code and display helpful error message
- **jq not found**: Inform user to install jq (`brew install jq` on macOS, `apt-get install jq` on Linux)
- **Rate limiting**: If API returns 429, implement exponential backoff (wait 60s, retry)

**Performance Considerations:**
- **Large batch size:** Fetch 1000 tickets per request (JIRA's maximum) for efficiency
- **Direct file storage:** Stream responses directly to disk, avoid loading into memory
- **No token consumption:** Using curl avoids Claude's context/token limits
- **Parallel-safe:** Can process very large backlogs (10,000+ tickets) without issues
- **Field filtering:** Only request needed fields to minimize response size
- **Python processing:** All filtering/analysis happens in Python, not in Claude context
- **Minimal Claude interaction:** Only present final filtered/analyzed results to user

## Return Value

- **Console Output**: Formatted report showing suggested tickets organized by priority
- **Intermediate Files** (created during processing):
  - `.work/jira-backlog/{project-key}/batch-*.json` - Raw JIRA API responses (one per 1000 tickets)
  - `.work/jira-backlog/{project-key}/process_batches.py` - Python script for filtering
  - `.work/jira-backlog/{project-key}/filtered.json` - All filtered tickets grouped by priority
  - `.work/jira-backlog/{project-key}/stats.json` - Priority distribution statistics
- **Optional Final Report**: `.work/jira-backlog/{project-key}-{timestamp}.md` containing the full report
- **Summary Statistics**: Count of available tickets per priority level

## Examples

**Note:** All examples require JIRA credentials to be configured in `~/.config/claude-code/mcp.json` (see Prerequisites section). The command uses curl to fetch data directly from JIRA's REST API, bypassing MCP commands to avoid 413 errors with large datasets.

1. **Find unassigned tickets in OCPBUGS project**:
   ```bash
   /jira:backlog OCPBUGS
   ```
   Output: Intelligently analyzes tickets and shows 2 recommended tickets from each priority level (Critical, High, Normal, Low)

   Example performance (tested October 31, 2025):
   - Fetched 2,535 tickets in 3 batches
   - Found 817 available tickets (unassigned or bot-assigned)
   - No 413 errors or token limit issues

2. **Find stale tickets with custom inactivity threshold**:
   ```bash
   /jira:backlog OCPBUGS --days-inactive 14
   ```
   Output: Report showing tickets with no activity for 14+ days, 2 per priority level

3. **Find tickets assigned to a specific user that are stale**:
   ```bash
   /jira:backlog OCPBUGS --assignee jsmith --days-inactive 30
   ```
   Output: Report showing tickets assigned to jsmith with 30+ days of inactivity, 2 per priority level

4. **Find tickets in Hypershift project**:
   ```bash
   /jira:backlog HYPE
   ```
   Output: Analyzes backlog and shows best 2 tickets from each priority in HYPE project

5. **Find tickets in CNV project**:
   ```bash
   /jira:backlog CNV
   ```
   Output: Report showing available backlog tickets across all priorities in CNV project

**Performance Note:** The curl-based approach can handle large backlogs efficiently. In testing with OCPBUGS (2,535 tickets), the command successfully fetched and processed all tickets without hitting Claude's token limits or encountering 413 errors.

## Arguments

- **project-key** (required): JIRA project key to search (e.g., OCPBUGS, JIRA, HYPE, CNV)
  - Must be uppercase
  - May contain hyphens (e.g., "MY-PROJECT")
  - If not provided, will prompt user to specify
- `--assignee` (optional): Filter by assignee username
  - Default: Search for unassigned tickets (assignee IS EMPTY)
  - If username provided: Find tickets assigned to that user with stale activity
  - Example: `--assignee jsmith` finds jsmith's stale tickets
- `--days-inactive` (optional): Number of days of inactivity to consider a ticket stale
  - Default: 28 days
  - Lower values find more recently inactive tickets
  - Example: `--days-inactive 14` finds tickets with 14+ days of no activity
