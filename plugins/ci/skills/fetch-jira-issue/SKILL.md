---
name: Fetch JIRA Issue
description: Fetch JIRA issue details including status, assignee, comments, and progress classification
---

# Fetch JIRA Issue

This skill fetches detailed information about a JIRA issue from the Red Hat JIRA REST API. It retrieves status, assignee, priority, resolution, comments, linked PRs, and classifies the issue's progress as ACTIVE, STALLED, or NEEDS_ATTENTION.

## When to Use This Skill

Use this skill when you need to:

- Check the status and progress of a JIRA bug linked to a regression triage
- Determine if a bug is being actively worked on or needs attention
- Extract PR links from JIRA comments
- Get assignee and component information for a JIRA issue
- Analyze recent comment activity on a bug

## Prerequisites

1. **JIRA API Token**: Required for authentication
   - Set environment variable: `export JIRA_TOKEN="your-token"`
   - Obtain from: https://issues.redhat.com (Profile > Personal Access Tokens)
   - Alternatively, pass `--token TOKEN` on the command line

2. **Network Access**: Must be able to reach issues.redhat.com
   - Check: `curl -s -o /dev/null -w '%{http_code}' https://issues.redhat.com`
   - VPN may be required

3. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

## Implementation Steps

### Step 1: Run the Python Script

```bash
# Path to the Python script
script_path="plugins/ci/skills/fetch-jira-issue/fetch_jira_issue.py"

# Fetch issue data in JSON format (default)
python3 "$script_path" OCPBUGS-74401 --format json

# Or fetch as human-readable summary
python3 "$script_path" OCPBUGS-74401 --format summary

# Pass token explicitly instead of using JIRA_TOKEN env var
python3 "$script_path" OCPBUGS-74401 --token "your-token" --format json
```

### Step 2: Parse the Output

The script outputs structured JSON data that can be further processed:

```bash
# Store result in variable
jira_data=$(python3 "$script_path" OCPBUGS-74401 --format json)

# Extract key fields
status=$(echo "$jira_data" | jq -r '.status')
assignee=$(echo "$jira_data" | jq -r '.assignee.display_name // "Unassigned"')
progress_level=$(echo "$jira_data" | jq -r '.progress.level')
progress_reason=$(echo "$jira_data" | jq -r '.progress.reason')

# Check progress classification
echo "Status: $status"
echo "Assignee: $assignee"
echo "Progress: $progress_level - $progress_reason"
```

### Step 3: Use Progress Classification

The skill automatically classifies issue progress:

- **ACTIVE**: Issue is being worked on (assigned with recent activity, PRs linked, or active status)
- **STALLED**: Issue is assigned but has no activity in 14+ days
- **NEEDS_ATTENTION**: Issue is NEW/unassigned or has no progress
- **RESOLVED**: Issue is closed/verified

```bash
# Example: Check if a triaged regression's bug needs attention
progress_level=$(echo "$jira_data" | jq -r '.progress.level')

case "$progress_level" in
  "ACTIVE")
    echo "Bug is being worked on - no action needed"
    ;;
  "STALLED")
    echo "Bug may need attention - consider commenting or reassigning"
    ;;
  "NEEDS_ATTENTION")
    echo "Bug needs someone to pick it up"
    ;;
  "RESOLVED")
    echo "Bug is closed"
    ;;
esac
```

## Error Handling

The script exits with code 1 and prints errors to stderr for these cases:

- **No token**: `JIRA_TOKEN` not set and `--token` not provided
- **Auth failure (401)**: Token is invalid or expired
- **Access denied (403)**: Token lacks permissions for the project
- **Not found (404)**: Issue key doesn't exist
- **Network error**: Cannot reach issues.redhat.com (VPN may be required)

```bash
# Example: Handle missing token gracefully
if [ -z "$JIRA_TOKEN" ]; then
  echo "Warning: JIRA_TOKEN not set. Skipping JIRA analysis."
else
  jira_data=$(python3 "$script_path" "$jira_key" --format json 2>/dev/null)
  if [ $? -ne 0 ]; then
    echo "Warning: Failed to fetch JIRA issue. Continuing without JIRA data."
  fi
fi
```

## Output Format

### JSON Format (--format json)

```json
{
  "key": "OCPBUGS-74401",
  "url": "https://issues.redhat.com/browse/OCPBUGS-74401",
  "summary": "ovn-ipsec-host creates duplicate openssl attribute",
  "status": "Modified",
  "resolution": null,
  "priority": "Critical",
  "assignee": {
    "display_name": "Jane Developer",
    "email": "jdeveloper@redhat.com"
  },
  "reporter": {
    "display_name": "John Reporter",
    "email": "jreporter@redhat.com"
  },
  "components": ["Networking / cluster-network-operator"],
  "labels": ["Regression"],
  "fix_versions": ["4.22"],
  "created": "2026-01-20T14:30:00.000+0000",
  "updated": "2026-02-10T09:15:00.000+0000",
  "comment_count": 5,
  "comments": [
    {
      "author": "Jane Developer",
      "created": "2026-02-08T10:00:00.000+0000",
      "body": "PR submitted: https://github.com/openshift/ovn-kubernetes/pull/1234"
    }
  ],
  "linked_prs": [
    "https://github.com/openshift/ovn-kubernetes/pull/1234"
  ],
  "progress": {
    "level": "ACTIVE",
    "label": "ACTIVE",
    "reason": "PR in progress (1 linked)",
    "days_since_update": 2,
    "days_since_last_comment": 4
  }
}
```

### Summary Format (--format summary)

```
JIRA Issue: OCPBUGS-74401
============================================================

Summary: ovn-ipsec-host creates duplicate openssl attribute
URL: https://issues.redhat.com/browse/OCPBUGS-74401
Status: Modified
Priority: Critical

Assignee: Jane Developer
Reporter: John Reporter

Components: Networking / cluster-network-operator
Labels: Regression
Fix Versions: 4.22

Created: 2026-01-20
Updated: 2026-02-10

Progress: ACTIVE - PR in progress (1 linked)
  Days since update: 2
  Days since last comment: 4

Linked PRs (1):
  - https://github.com/openshift/ovn-kubernetes/pull/1234

Recent Comments (1 of 5 total):
  [2026-02-08] Jane Developer:
    PR submitted: https://github.com/openshift/ovn-kubernetes/pull/1234
```

## Notes

- The script uses only Python standard library modules (no pip dependencies)
- All comments are returned in the JSON output; the summary format shows only the last 3
- PR links are extracted from comment bodies using pattern matching for GitHub PR URLs
- Progress classification uses configurable thresholds: 7 days for "recent", 14 days for "stale"
- The `--token` flag takes precedence over the `JIRA_TOKEN` environment variable

## See Also

- Related Command: `/ci:analyze-regression` - Uses this skill to check JIRA progress on triaged regressions
- Related Command: `/ci:check-if-jira-regression-is-ongoing` - Uses this skill for JIRA bug analysis
- Related Skill: `fetch-regression-details` - Fetches regression data that may link to JIRA bugs
- Related Skill: `triage-regression` - Creates triage records linking regressions to JIRA bugs
- JIRA REST API: https://developer.atlassian.com/server/jira/platform/rest-apis/
