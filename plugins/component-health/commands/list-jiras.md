---
description: Query and list raw JIRA bug data for a specific project
argument-hint: <project> [--component comp1 comp2 ...] [--status status1 status2 ...] [--include-closed] [--limit N]
---

## Name

component-health:list-jiras

## Synopsis

```
/component-health:list-jiras <project> [--component comp1 comp2 ...] [--status status1 status2 ...] [--include-closed] [--limit N]
```

## Description

The `component-health:list-jiras` command queries JIRA bugs for a specified project and returns raw issue data. It fetches JIRA issues with all their fields and metadata without performing any summarization or aggregation.

By default, the command includes:
- All currently open bugs
- Bugs closed in the last 30 days (to track recent closure activity)

This command is useful for:

- Fetching raw JIRA issue data for further processing
- Accessing complete issue details including all fields
- Building custom analysis workflows
- Providing data to other commands (like `summarize-jiras`)
- Exporting JIRA data for offline analysis

## Implementation

1. **Verify Prerequisites**: Check that Python 3 is installed

   - Run: `python3 --version`
   - Verify version 3.6 or later is available

2. **Verify Environment Variables**: Ensure JIRA authentication is configured

   - Check that the following environment variables are set:
     - `JIRA_URL`: Base URL for JIRA instance (e.g., "https://issues.redhat.com")
     - `JIRA_PERSONAL_TOKEN`: Your JIRA bearer token or personal access token

   - Verify with:
     ```bash
     echo "JIRA_URL: ${JIRA_URL}"
     echo "JIRA_PERSONAL_TOKEN: ${JIRA_PERSONAL_TOKEN:+***set***}"
     ```

   - If missing, guide the user to set them:
     ```bash
     export JIRA_URL="https://issues.redhat.com"
     export JIRA_PERSONAL_TOKEN="your-token-here"
     ```

3. **Parse Arguments**: Extract project key and optional filters from arguments

   - Project key: Required first argument (e.g., "OCPBUGS", "OCPSTRAT")
   - Optional filters:
     - `--component`: Space-separated list of component search strings (fuzzy match)
     - `--status`: Space-separated list of status values
     - `--include-closed`: Flag to include closed bugs
     - `--limit`: Maximum number of issues to fetch per component (default: 100, max: 1000)

4. **Resolve Component Names** (if component filter provided): Use fuzzy matching to find actual component names

   - Extract release from context or ask user for release version
   - Run list_components.py to get all available components:
     ```bash
     python3 plugins/component-health/skills/list-components/list_components.py --release <release>
     ```
   - For each search string in `--component`:
     - Find all components containing that string (case-insensitive)
     - Combine all matches into a single list
     - Remove duplicates
     - If no matches found for a search string, warn the user and show available components

5. **Execute Python Script**: Run the list_jiras.py script for each component

   - Script location: `plugins/component-health/skills/list-jiras/list_jiras.py`
   - **Important**: Iterate over each resolved component separately to avoid overly large queries
   - For each component:
     - Build command with project, single component, and other filters
     - Execute: `python3 list_jiras.py --project <project> --component "<component>" [other args]`
     - Capture JSON output from stdout
   - Aggregate results from all components into a combined response

6. **Parse Output**: Process the aggregated JSON response

   - Extract metadata:
     - `project`: Project key queried
     - `total_count`: Total matching issues in JIRA
     - `fetched_count`: Number of issues actually fetched
     - `query`: JQL query that was executed
     - `filters`: Applied filters
   - Extract raw issues array:
     - `issues`: Array of complete JIRA issue objects with all fields

7. **Present Results**: Display or store the raw JIRA data

   - Show which components were matched (if fuzzy search was used)
   - The command returns the aggregated JSON response with metadata and raw issues from all components
   - Inform the user about total count vs fetched count per component
   - The raw issue data can be passed to other commands for analysis
   - Suggest using `/component-health:summarize-jiras` for summary statistics
   - Highlight any truncation (if fetched_count < total_count for any component)
   - Suggest increasing --limit if results are truncated

8. **Error Handling**: Handle common error scenarios

   - Network connectivity issues
   - Invalid JIRA credentials
   - Invalid project key
   - HTTP errors (401, 404, 500, etc.)
   - Rate limiting (429)

## Return Value

The command outputs **raw JIRA issue data** in JSON format with the following structure:

### Metadata

- **project**: JIRA project key that was queried
- **total_count**: Total number of matching issues in JIRA
- **fetched_count**: Number of issues actually fetched (may be less than total if limited)
- **query**: JQL query that was executed (includes filters)
- **filters**: Object containing applied filters:
  - `components`: List of component filters or null
  - `statuses`: List of status filters or null
  - `include_closed`: Boolean indicating if closed bugs were included
  - `limit`: Maximum number of issues fetched

### Issues Array

- **issues**: Array of raw JIRA issue objects, each containing:
  - `key`: Issue key (e.g., "OCPBUGS-12345")
  - `fields`: Object containing all issue fields:
    - `summary`: Issue title/summary
    - `status`: Status object with name and ID
    - `priority`: Priority object with name and ID
    - `components`: Array of component objects
    - `assignee`: Assignee object with user details
    - `created`: Creation timestamp
    - `updated`: Last updated timestamp
    - `resolutiondate`: Resolution timestamp (if closed)
    - `versions`: Affects Version/s array
    - `fixVersions`: Fix Version/s array
    - `customfield_12319940`: Target Version (custom field)
    - And other JIRA fields as applicable

### Additional Information

- **note**: (Optional) If results are truncated, includes a note suggesting to increase the limit

### Example Output Structure

```json
{
  "project": "OCPBUGS",
  "total_count": 1500,
  "fetched_count": 100,
  "query": "project = OCPBUGS AND (status != Closed OR (status = Closed AND resolved >= \"2025-10-11\"))",
  "filters": {
    "components": null,
    "statuses": null,
    "include_closed": false,
    "limit": 100
  },
  "issues": [
    {
      "key": "OCPBUGS-12345",
      "fields": {
        "summary": "Bug title here",
        "status": {"name": "New", "id": "1"},
        "priority": {"name": "Major", "id": "3"},
        "components": [{"name": "kube-apiserver"}],
        "created": "2025-11-01T10:30:00.000+0000",
        ...
      }
    },
    ...
  ],
  "note": "Showing first 100 of 1500 total results. Increase --limit for more data."
}
```

## Examples

1. **List all open bugs for a project**:

   ```
   /component-health:list-jiras OCPBUGS
   ```

   Fetches all open bugs in the OCPBUGS project (up to default limit of 100) and returns raw issue data.

2. **Filter by specific component (exact match)**:

   ```
   /component-health:list-jiras OCPBUGS --component "kube-apiserver"
   ```

   Returns raw data for bugs in the kube-apiserver component only.

3. **Filter by fuzzy search**:

   ```
   /component-health:list-jiras OCPBUGS --component network
   ```

   Finds all components containing "network" (case-insensitive) and returns bugs for all matches (e.g., "Networking / ovn-kubernetes", "Networking / DNS", etc.).
   Makes separate JIRA queries for each component and aggregates results.

4. **Filter by multiple search strings**:

   ```
   /component-health:list-jiras OCPBUGS --component etcd kube-
   ```

   Finds all components containing "etcd" OR "kube-" and returns combined bug data.
   Iterates over each component separately to avoid overly large queries.

5. **Include closed bugs**:

   ```
   /component-health:list-jiras OCPBUGS --include-closed --limit 500
   ```

   Returns both open and closed bugs, fetching up to 500 issues per component.

6. **Filter by status**:

   ```
   /component-health:list-jiras OCPBUGS --status New "In Progress" Verified
   ```

   Returns only bugs in New, In Progress, or Verified status.

7. **Combine fuzzy search with other filters**:

   ```
   /component-health:list-jiras OCPBUGS --component network --status New Assigned --limit 200
   ```

   Returns bugs for all networking components that are in New or Assigned status.

## Arguments

- `$1` (required): JIRA project key
  - Format: Project key in uppercase (e.g., "OCPBUGS", "OCPSTRAT")
  - Must be a valid JIRA project you have access to

- `$2+` (optional): Filter flags
  - `--component <search1> [search2 ...]`: Filter by component names using fuzzy search
    - Space-separated list of component search strings
    - Case-insensitive substring matching
    - Each search string matches all components containing that substring
    - Makes separate JIRA queries for each matched component to avoid overly large results
    - Example: "network" matches "Networking / ovn-kubernetes", "Networking / DNS", etc.
    - Example: "kube-" matches "kube-apiserver", "kube-controller-manager", etc.
    - Note: Requires release context (inferred from recent commands or specified by user)

  - `--status <status1> [status2 ...]`: Filter by status values
    - Space-separated list of status names
    - Examples: `New`, `"In Progress"`, `Verified`, `Modified`, `ON_QA`

  - `--include-closed`: Include closed bugs in results
    - By default, only open bugs are returned
    - When specified, closed bugs are included

  - `--limit <N>`: Maximum number of issues to fetch per component
    - Default: 100
    - Range: 1-1000
    - When using component filters, this limit applies to each component separately
    - Higher values provide more accurate statistics but slower performance

## Prerequisites

1. **Python 3**: Required to run the data fetching script

   - Check: `which python3`
   - Version: 3.6 or later

2. **JIRA Authentication**: Environment variables must be configured

   - `JIRA_URL`: Your JIRA instance URL
   - `JIRA_PERSONAL_TOKEN`: Your JIRA bearer token or personal access token

   How to get a JIRA token:
   - Navigate to JIRA → Profile → Personal Access Tokens
   - Generate a new token with appropriate permissions
   - Export it as an environment variable

3. **Network Access**: Must be able to reach your JIRA instance

   - Ensure HTTPS requests can be made to JIRA_URL
   - Check firewall and VPN settings if needed

## Notes

- The script uses Python's standard library only (no external dependencies)
- Output is JSON format for easy parsing and further processing
- Diagnostic messages are written to stderr, data to stdout
- The script has a 30-second timeout for HTTP requests
- For large projects, consider using component filters to reduce query size
- The returned data includes ALL JIRA fields for each issue, providing complete information
- If you need summary statistics, use `/component-health:summarize-jiras` instead
- If results show truncation, increase the --limit parameter to fetch more issues

## See Also

- Skill Documentation: `plugins/component-health/skills/list-jiras/SKILL.md`
- Script: `plugins/component-health/skills/list-jiras/list_jiras.py`
- Related Command: `/component-health:summarize-jiras` (for summary statistics)
- Related Command: `/component-health:analyze-regressions`
