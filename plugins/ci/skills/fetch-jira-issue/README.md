# Fetch JIRA Issue Skill

This skill fetches detailed information about a JIRA issue from the Red Hat JIRA REST API.

## Overview

The `fetch-jira-issue` skill retrieves comprehensive JIRA issue data including:

- Status, priority, and resolution
- Assignee and reporter
- Components and fix versions
- All comments with timestamps
- GitHub PR links extracted from comments
- Automatic progress classification (ACTIVE / STALLED / NEEDS_ATTENTION / RESOLVED)

## Usage

This skill is used internally by CI commands such as `/ci:analyze-regression` and `/ci:check-if-jira-regression-is-ongoing`, but can also be invoked directly.

### Input

- **JIRA Key**: Issue key (e.g., OCPBUGS-74401)
- **JIRA_USERNAME**: Atlassian account email set as environment variable (or passed via `--username`)
- **JIRA_API_TOKEN**: API token set as environment variable (or passed via `--token`)

### Output

Structured JSON data containing:

```json
{
  "key": "OCPBUGS-74401",
  "url": "https://redhat.atlassian.net/browse/OCPBUGS-74401",
  "summary": "ovn-ipsec-host creates duplicate openssl attribute",
  "status": "Modified",
  "resolution": null,
  "priority": "Critical",
  "assignee": {"display_name": "Jane Developer", "email": "jdeveloper@redhat.com"},
  "components": ["Networking / cluster-network-operator"],
  "fix_versions": ["4.22"],
  "comment_count": 5,
  "comments": [...],
  "linked_prs": ["https://github.com/openshift/ovn-kubernetes/pull/1234"],
  "progress": {
    "level": "ACTIVE",
    "reason": "PR in progress (1 linked)",
    "days_since_update": 2,
    "days_since_last_comment": 4
  }
}
```

## API Endpoint

The skill fetches data from:

```
https://redhat.atlassian.net/rest/api/2/issue/{key}
```

Authentication via Basic auth (email + API token) is required.

## Prerequisites

- JIRA username (`JIRA_USERNAME` environment variable)
- JIRA API token (`JIRA_API_TOKEN` environment variable)
- Network access to redhat.atlassian.net
- Python 3.6 or later (uses standard library only)

## Usage

```bash
# Fetch as JSON (default)
python3 plugins/ci/skills/fetch-jira-issue/fetch_jira_issue.py OCPBUGS-74401

# Fetch as human-readable summary
python3 plugins/ci/skills/fetch-jira-issue/fetch_jira_issue.py OCPBUGS-74401 --format summary
```

## Related Commands

- `/ci:analyze-regression` - Uses this skill to check JIRA progress on triaged regressions
- `/ci:check-if-jira-regression-is-ongoing` - Uses this skill for JIRA bug analysis
