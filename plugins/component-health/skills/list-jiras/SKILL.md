---
name: List JIRAs
description: Query and return raw JIRA bug data for a specific project
---

# List JIRAs

This skill provides functionality to query JIRA bugs for a specified project and return raw issue data. It uses the JIRA REST API to fetch complete bug information with all fields and metadata, without performing any summarization.

## When to Use This Skill

Use this skill when you need to:

- Fetch raw JIRA issue data for further processing
- Access complete issue details including all fields
- Build custom analysis workflows
- Provide data to other commands (like `summarize-jiras`)
- Export JIRA data for offline analysis

## Prerequisites

1. **Python 3 Installation**

   - Check if installed: `which python3`
   - Python 3.6 or later is required
   - Comes pre-installed on most systems

2. **JIRA Authentication**

   - Requires environment variables to be set:
     - `JIRA_URL`: Base URL for JIRA instance (e.g., "https://issues.redhat.com")
     - `JIRA_PERSONAL_TOKEN`: Your JIRA bearer token or personal access token
   - How to get a JIRA token:
     - Navigate to JIRA → Profile → Personal Access Tokens
     - Generate a new token with appropriate permissions
     - Export it as an environment variable

3. **Network Access**
   - The script requires network access to reach your JIRA instance
   - Ensure you can make HTTPS requests to the JIRA URL

## Implementation Steps

### Step 1: Verify Prerequisites

First, ensure Python 3 is available:

```bash
python3 --version
```

If Python 3 is not installed, guide the user through installation for their platform.

### Step 2: Verify Environment Variables

Check that required environment variables are set:

```bash
# Verify JIRA credentials are configured
echo "JIRA_URL: ${JIRA_URL}"
echo "JIRA_PERSONAL_TOKEN: ${JIRA_PERSONAL_TOKEN:+***set***}"
```

If any are missing, guide the user to set them:

```bash
export JIRA_URL="https://issues.redhat.com"
export JIRA_PERSONAL_TOKEN="your-token-here"
```

### Step 3: Locate the Script

The script is located at:

```
plugins/component-health/skills/list-jiras/list_jiras.py
```

### Step 4: Run the Script

Execute the script with appropriate arguments:

```bash
# Basic usage - all open bugs in a project
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS

# Filter by component
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver"

# Filter by multiple components
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver" "Management Console"

# Include closed bugs
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --include-closed

# Filter by status
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --status New "In Progress"

# Set maximum results limit (default 100)
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --limit 500
```

### Step 5: Process the Output

The script outputs JSON data with the following structure:

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
        "status": {
          "name": "New",
          "id": "1"
        },
        "priority": {
          "name": "Major",
          "id": "3"
        },
        "components": [
          {"name": "kube-apiserver", "id": "12345"}
        ],
        "assignee": {
          "displayName": "John Doe",
          "emailAddress": "jdoe@example.com"
        },
        "created": "2025-11-01T10:30:00.000+0000",
        "updated": "2025-11-05T14:20:00.000+0000",
        "resolutiondate": null,
        "versions": [
          {"name": "4.21"}
        ],
        "fixVersions": [
          {"name": "4.22"}
        ],
        "customfield_12319940": "4.22.0"
      }
    },
    ...more issues...
  ],
  "note": "Showing first 100 of 1500 total results. Increase --limit for more data."
}
```

**Field Descriptions**:

- `project`: The JIRA project queried
- `total_count`: Total number of matching issues in JIRA (from search results)
- `fetched_count`: Number of issues actually fetched (limited by --limit parameter)
- `query`: The JQL query executed (includes filter for recently closed bugs)
- `filters`: Applied filters (components, statuses, include_closed, limit)
- `issues`: Array of raw JIRA issue objects, each containing:
  - `key`: Issue key (e.g., "OCPBUGS-12345")
  - `fields`: Object containing all JIRA fields for the issue:
    - `summary`: Issue title/summary
    - `status`: Status object with name and ID
    - `priority`: Priority object with name and ID
    - `components`: Array of component objects
    - `assignee`: Assignee object with user details
    - `created`: Creation timestamp
    - `updated`: Last updated timestamp
    - `resolutiondate`: Resolution timestamp (null if not closed)
    - `versions`: Affects Version/s array
    - `fixVersions`: Fix Version/s array
    - `customfield_12319940`: Target Version (custom field)
    - And many other JIRA fields as applicable
- `note`: Informational message if results are truncated

**Important Notes**:

- **By default, the query includes**: Open bugs + bugs closed in the last 30 days
- This allows tracking of recent closure activity alongside current open bugs
- The script fetches a maximum number of issues (default 1000, configurable with `--limit`)
- The `total_count` represents all matching issues in JIRA
- The returned data includes ALL fields for each issue, providing complete information
- For large datasets, increase the `--limit` parameter to fetch more issues
- Issues can have multiple components
- All JIRA field data is preserved in the raw format

### Step 6: Present Results

Based on the raw JIRA data:

1. Inform the user about the total count vs fetched count
2. Explain that the raw data includes all JIRA fields
3. Suggest using `/component-health:summarize-jiras` if they need summary statistics
4. The raw issue data can be passed to other commands for further processing
5. Highlight any truncation and suggest increasing --limit if needed

## Error Handling

### Common Errors

1. **Authentication Errors**

   - **Symptom**: HTTP 401 Unauthorized
   - **Solution**: Verify JIRA_PERSONAL_TOKEN is correct
   - **Check**: Ensure token has not expired

2. **Network Errors**

   - **Symptom**: `URLError` or connection timeout
   - **Solution**: Check network connectivity and JIRA_URL is accessible
   - **Retry**: The script has a 30-second timeout, consider retrying

3. **Invalid Project**

   - **Symptom**: HTTP 400 or empty results
   - **Solution**: Verify the project key is correct (e.g., "OCPBUGS", not "ocpbugs")

4. **Missing Environment Variables**

   - **Symptom**: Error message about missing credentials
   - **Solution**: Set required environment variables (JIRA_URL, JIRA_USERNAME, JIRA_PERSONAL_TOKEN)

5. **Rate Limiting**
   - **Symptom**: HTTP 429 Too Many Requests
   - **Solution**: Wait before retrying, reduce query frequency

### Debugging

Enable verbose output by examining stderr:

```bash
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS 2>&1 | tee debug.log
```

## Script Arguments

### Required Arguments

- `--project`: JIRA project key to query
  - Format: Project key (e.g., "OCPBUGS", "OCPSTRAT")
  - Must be a valid JIRA project

### Optional Arguments

- `--component`: Filter by component names

  - Values: Space-separated list of component names
  - Default: None (returns all components)
  - Case-sensitive matching
  - Examples: `--component "kube-apiserver" "Management Console"`

- `--status`: Filter by status values

  - Values: Space-separated list of status names
  - Default: None (returns all statuses except Closed)
  - Examples: `--status New "In Progress" Verified`

- `--include-closed`: Include closed bugs in the results

  - Default: false (only open bugs)
  - When specified, includes bugs in "Closed" status

- `--limit`: Maximum number of issues to fetch
  - Default: 100
  - Maximum: 1000 (JIRA API limit per request)
  - Higher values provide more accurate statistics but slower performance

## Output Format

The script outputs JSON with metadata and raw issue data:

```json
{
  "project": "OCPBUGS",
  "total_count": 5430,
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
        "summary": "Example bug",
        "status": {"name": "New"},
        "priority": {"name": "Major"},
        "components": [{"name": "kube-apiserver"}],
        "created": "2025-11-01T10:30:00.000+0000",
        ...
      }
    },
    ...
  ],
  "note": "Showing first 100 of 5430 total results. Increase --limit for more data."
}
```

## Examples

### Example 1: List All Open Bugs

```bash
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS
```

**Expected Output**: JSON containing raw issue data for all open bugs in OCPBUGS project

### Example 2: Filter by Component

```bash
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver"
```

**Expected Output**: JSON containing raw issue data for the kube-apiserver component only

### Example 3: Include Closed Bugs

```bash
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --include-closed \
  --limit 500
```

**Expected Output**: JSON containing raw issue data for both open and closed bugs (up to 500 issues)

### Example 4: Filter by Multiple Components

```bash
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver" "etcd" "Networking"
```

**Expected Output**: JSON containing raw issue data for bugs in specified components

## Integration with Commands

This skill is designed to:

- Provide raw JIRA data to other commands (like `summarize-jiras`)
- Be used directly for ad-hoc JIRA queries
- Serve as a data source for custom analysis workflows
- Export JIRA data for offline processing

## Related Skills

- `summarize-jiras`: Calculate summary statistics from JIRA data
- `list-regressions`: Fetch regression data for releases
- `analyze-regressions`: Grade component health based on regressions
- `get-release-dates`: Fetch OpenShift release dates

## Notes

- The script uses Python's `urllib` and `json` modules (no external dependencies)
- Output is always JSON format for easy parsing and further processing
- Diagnostic messages are written to stderr, data to stdout
- The script has a 30-second timeout for HTTP requests
- For large projects, consider using component filters to reduce query size
- The returned data includes ALL JIRA fields for complete information
- Use `/component-health:summarize-jiras` if you need summary statistics instead of raw data
