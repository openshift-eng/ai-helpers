---
name: Summarize JIRAs
description: Query and summarize JIRA bugs for a specific project with counts by component
---

# Summarize JIRAs

This skill provides functionality to query JIRA bugs for a specified project and generate summary statistics. It leverages the `list-jiras` skill to fetch raw JIRA data, then calculates counts by status, priority, and component to provide insights into the bug backlog.

## When to Use This Skill

Use this skill when you need to:

- Get a count of open bugs in a JIRA project
- Analyze bug distribution by status, priority, or component
- Generate summary reports for bug backlog
- Track bug trends and velocity over time (opened vs closed in last 30 days)
- Compare bug counts across different components
- Monitor component health based on bug metrics

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
plugins/component-health/skills/summarize-jiras/summarize_jiras.py
```

### Step 4: Run the Script

Execute the script with appropriate arguments:

```bash
# Basic usage - summarize all open bugs in a project
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
  --project OCPBUGS

# Filter by component
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver"

# Filter by multiple components
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver" "Management Console"

# Include closed bugs
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
  --project OCPBUGS \
  --include-closed

# Filter by status
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
  --project OCPBUGS \
  --status New "In Progress"

# Set maximum results limit (default 100)
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
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
  "summary": {
    "total": 100,
    "opened_last_30_days": 15,
    "closed_last_30_days": 8,
    "by_status": {
      "New": 35,
      "In Progress": 25,
      "Verified": 20,
      "Modified": 15,
      "ON_QA": 5,
      "Closed": 8
    },
    "by_priority": {
      "Normal": 50,
      "Major": 30,
      "Minor": 12,
      "Critical": 5,
      "Undefined": 3
    },
    "by_component": {
      "kube-apiserver": 25,
      "Management Console": 30,
      "Networking": 20,
      "etcd": 15,
      "No Component": 10
    }
  },
  "components": {
    "kube-apiserver": {
      "total": 25,
      "opened_last_30_days": 4,
      "closed_last_30_days": 2,
      "by_status": {
        "New": 10,
        "In Progress": 8,
        "Verified": 5,
        "Modified": 2,
        "Closed": 2
      },
      "by_priority": {
        "Major": 12,
        "Normal": 10,
        "Minor": 2,
        "Critical": 1
      }
    },
    "Management Console": {
      "total": 30,
      "opened_last_30_days": 6,
      "closed_last_30_days": 3,
      "by_status": {
        "New": 12,
        "In Progress": 10,
        "Verified": 6,
        "Modified": 2,
        "Closed": 3
      },
      "by_priority": {
        "Normal": 18,
        "Major": 8,
        "Minor": 3,
        "Critical": 1
      }
    },
    "etcd": {
      "total": 15,
      "opened_last_30_days": 3,
      "closed_last_30_days": 2,
      "by_status": {
        "New": 8,
        "In Progress": 4,
        "Verified": 3,
        "Closed": 2
      },
      "by_priority": {
        "Normal": 10,
        "Major": 4,
        "Critical": 1
      }
    }
  },
  "note": "Showing first 100 of 1500 total results. Increase --limit for more accurate statistics."
}
```

**Field Descriptions**:

- `project`: The JIRA project queried
- `total_count`: Total number of matching issues (from JIRA search results)
- `fetched_count`: Number of issues actually fetched (limited by --limit parameter)
- `query`: The JQL query executed (includes filter for recently closed bugs)
- `filters`: Applied filters (components, statuses, include_closed, limit)
- `summary`: Overall statistics across all fetched issues
  - `total`: Count of fetched issues (same as `fetched_count`)
  - `opened_last_30_days`: Number of issues created in the last 30 days
  - `closed_last_30_days`: Number of issues closed/resolved in the last 30 days
  - `by_status`: Count of issues per status (includes recently closed issues)
  - `by_priority`: Count of issues per priority
  - `by_component`: Count of issues per component (note: issues can have multiple components)
- `components`: Per-component breakdown with individual summaries
  - Each component key maps to:
    - `total`: Number of issues assigned to this component
    - `opened_last_30_days`: Number of issues created in the last 30 days for this component
    - `closed_last_30_days`: Number of issues closed in the last 30 days for this component
    - `by_status`: Status distribution for this component
    - `by_priority`: Priority distribution for this component
- `note`: Informational message if results are truncated

**Important Notes**:

- **By default, the query includes**: Open bugs + bugs closed in the last 30 days
- This allows tracking of recent closure activity alongside current open bugs
- The script fetches a maximum number of issues (default 100, configurable with `--limit`)
- The `total_count` represents all matching issues in JIRA
- Summary statistics are based on the fetched issues only
- For accurate statistics across large datasets, increase the `--limit` parameter
- Issues can have multiple components, so component totals may sum to more than the overall total
- `opened_last_30_days` and `closed_last_30_days` help track recent bug flow and velocity

### Step 6: Present Results

Based on the summary data:

1. Present total bug counts
2. Highlight distribution by status (e.g., how many in "New" vs "In Progress")
3. Identify priority breakdown (Critical, Major, Normal, etc.)
4. Show component distribution
5. Display per-component breakdowns with status and priority counts
6. Calculate actionable metrics (e.g., New + Assigned = bugs needing triage/work)
7. Highlight recent activity (opened/closed in last 30 days) per component

## Error Handling

### Common Errors

1. **Authentication Errors**
   - **Symptom**: HTTP 401 Unauthorized
   - **Solution**: Verify JIRA_URL and JIRA_PERSONAL_TOKEN are correct
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
   - **Solution**: Set required environment variables (JIRA_URL, JIRA_PERSONAL_TOKEN)

5. **Rate Limiting**
   - **Symptom**: HTTP 429 Too Many Requests
   - **Solution**: Wait before retrying, reduce query frequency

### Debugging

Enable verbose output by examining stderr:

```bash
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
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

The script outputs JSON with summary statistics and per-component breakdowns:

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
  "summary": {
    "total": 100,
    "opened_last_30_days": 15,
    "closed_last_30_days": 8,
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
  "components": {
    "kube-apiserver": {
      "total": 146,
      "opened_last_30_days": 20,
      "closed_last_30_days": 12,
      "by_status": {...},
      "by_priority": {...}
    }
  },
  "note": "Showing first 100 of 5430 total results. Increase --limit for more accurate statistics."
}
```

## Examples

### Example 1: Summarize All Open Bugs

```bash
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
  --project OCPBUGS
```

**Expected Output**: JSON containing summary statistics of all open bugs in OCPBUGS project

### Example 2: Filter by Component

```bash
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver"
```

**Expected Output**: JSON containing summary for the kube-apiserver component only

### Example 3: Include Closed Bugs

```bash
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
  --project OCPBUGS \
  --include-closed \
  --limit 500
```

**Expected Output**: JSON containing summary of both open and closed bugs (up to 500 issues)

### Example 4: Filter by Multiple Components

```bash
python3 plugins/component-health/skills/summarize-jiras/summarize_jiras.py \
  --project OCPBUGS \
  --component "kube-apiserver" "etcd" "Networking"
```

**Expected Output**: JSON containing summary for specified components

## Integration with Commands

This skill is designed to:
- Provide summary statistics for JIRA bug analysis
- Be used by component health analysis workflows
- Generate reports for bug triage and planning
- Track component health metrics over time
- Leverage the `list-jiras` skill for raw data fetching

## Related Skills

- `list-jiras`: Fetch raw JIRA issue data
- `list-regressions`: Fetch regression data for releases
- `analyze-regressions`: Grade component health based on regressions
- `get-release-dates`: Fetch OpenShift release dates

## Notes

- The script uses Python's standard library only (no external dependencies)
- Output is always JSON format for easy parsing
- Diagnostic messages are written to stderr, data to stdout
- The script internally calls `list_jiras.py` to fetch raw data
- The script has a 30-second timeout for HTTP requests (inherited from list_jiras.py)
- For large projects, consider using component filters to reduce query size
- Summary statistics are based on fetched issues (controlled by --limit), not total matching issues
- For raw JIRA data without summarization, use `/component-health:list-jiras` instead
