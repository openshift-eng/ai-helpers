---
name: List JIRAs
description: Query and summarize JIRA bugs for a specific project
---

# List JIRAs

This skill provides functionality to query JIRA bugs for a specified project and generate summary statistics. It uses the JIRA REST API to fetch bug information and provides counts by status, priority, and component.

## When to Use This Skill

Use this skill when you need to:

- Get a count of open bugs in a JIRA project
- Analyze bug distribution by status, priority, or component
- Generate summary reports for bug backlog
- Track bug trends over time
- Compare bug counts across different components

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
  "total": 1500,
  "maxResults": 50,
  "startAt": 0,
  "issues": [
    {
      "key": "OCPBUGS-12345",
      "fields": {
        "summary": "Bug summary text",
        "status": {
          "name": "New"
        },
        "priority": {
          "name": "Major"
        },
        "components": [
          {
            "name": "kube-apiserver"
          }
        ],
        "assignee": {...},
        "created": "2024-01-15T10:30:00.000+0000",
        "updated": "2024-01-20T15:45:00.000+0000"
      }
    },
    ...
  ]
}
```

### Step 5: Generate Summary Statistics

Process the issues to create summary counts:

1. **Count by Status**: Iterate through issues and group by `fields.status.name`
2. **Count by Priority**: Iterate through issues and group by `fields.priority.name`
3. **Count by Component**: Iterate through issues and extract all `fields.components[].name`
   - Note: Issues can have multiple components
   - Issues with no components should be counted as "No Component"

4. Sort each summary by count (descending order)

5. Create the final summary object:

```json
{
  "project": "OCPBUGS",
  "total_count": 1500,
  "fetched_count": 50,
  "query": "project = OCPBUGS AND status != Closed",
  "filters": {
    "components": null,
    "statuses": null,
    "include_closed": false,
    "limit": 50
  },
  "summary": {
    "by_status": {
      "New": 15,
      "In Progress": 12,
      "Verified": 8,
      ...
    },
    "by_priority": {
      "Critical": 2,
      "Major": 10,
      "Normal": 25,
      ...
    },
    "by_component": {
      "kube-apiserver": 8,
      "Management Console": 15,
      ...
    }
  },
  "note": "Showing first 50 of 1500 total results. Summary based on fetched issues only."
}
```

**Important Notes**:

- The MCP JIRA search tool has a maximum limit of 50 results per query
- The `total` field represents all matching issues in JIRA
- Summary statistics are based on the fetched issues only (up to 50)
- For more complete statistics, you may need multiple queries with pagination
- Summary percentages should note they are based on the sample, not the full dataset

### Step 6: Present Results

Based on the JIRA data:

1. Present total bug counts
2. Highlight distribution by status (e.g., how many in "New" vs "In Progress")
3. Identify priority breakdown (Critical, Major, Normal, etc.)
4. Show component distribution
5. Calculate actionable metrics (e.g., New + Assigned = bugs needing triage/work)

## Error Handling

### Common Errors

1. **Authentication Errors**
   - **Symptom**: HTTP 401 Unauthorized
   - **Solution**: Verify JIRA_USERNAME and JIRA_PERSONAL_TOKEN are correct
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

The script outputs JSON with summary statistics and metadata:

```json
{
  "project": "OCPBUGS",
  "total_count": 5430,
  "query": "project = OCPBUGS AND status != Closed",
  "filters": {
    "components": null,
    "include_closed": false,
    "limit": 100
  },
  "summary": {
    "by_status": {
      "New": 1250,
      "In Progress": 800,
      "Verified": 650
    },
    "by_priority": {
      "Critical": 50,
      "Major": 450,
      "Normal": 2100
    },
    "by_component": {
      "kube-apiserver": 146,
      "Management Console": 392
    }
  },
  "fetched_count": 100,
  "note": "Showing first 100 of 5430 total results. Increase --limit for more accurate statistics."
}
```

## Examples

### Example 1: List All Open Bugs

```bash
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS
```

**Expected Output**: JSON containing summary of all open bugs in OCPBUGS project

### Example 2: Filter by Component

```bash
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver"
```

**Expected Output**: JSON containing bugs for the kube-apiserver component only

### Example 3: Include Closed Bugs

```bash
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --include-closed \
  --limit 500
```

**Expected Output**: JSON containing both open and closed bugs (up to 500 issues)

### Example 4: Filter by Multiple Components

```bash
python3 plugins/component-health/skills/list-jiras/list_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver" "etcd" "Networking"
```

**Expected Output**: JSON containing bugs for specified components

## Integration with Commands

This skill is designed to be used by component health analysis commands and bug triage workflows, but can also be invoked directly for ad-hoc JIRA queries.

## Related Skills

- `list-regressions`: Fetch regression data for releases
- `analyze-regressions`: Grade component health based on regressions
- `get-release-dates`: Fetch OpenShift release dates

## Notes

- The script uses Python's `urllib` and `json` modules (no external dependencies)
- Output is always JSON format for easy parsing
- Diagnostic messages are written to stderr, data to stdout
- The script has a 30-second timeout for HTTP requests
- For large projects, consider using component filters to reduce query size
- Summary statistics are based on fetched issues (controlled by --limit), not total matching issues
