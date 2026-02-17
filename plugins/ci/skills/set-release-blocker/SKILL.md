---
name: Set Release Blocker
description: Set the Release Blocker field on a JIRA issue
---

# Set Release Blocker

Sets the "Release Blocker" custom field on a JIRA issue. Component Readiness regressions are treated as release blockers, so any bug filed for a regression should have this field set to "Approved".

See the [release blocker definition](https://github.com/openshift/enhancements/blob/master/dev-guide/release-blocker-definition.md) for details on the criteria and process.

## Prerequisites

- **JIRA_TOKEN**: Environment variable must be set with a valid JIRA API token
  - Obtain from: https://issues.redhat.com (Profile -> Personal Access Tokens)

## Usage

```bash
# Set Release Blocker to Approved (default)
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523

# Explicitly set to Approved
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523 --value Approved

# Set to Rejected
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523 --value Rejected

# Clear the field
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523 --value ""

# JSON output
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523 --format json
```

## JIRA Field Details

- **Field ID**: `customfield_12319743`
- **Field name**: Release Blocker
- **Type**: Select dropdown
- **Options**:
  - `Approved` (option ID: `25755`)
  - `Rejected` (option ID: `25756`)

## Output

### Text format (default)

```
Release Blocker set to 'Approved' on OCPBUGS-76523
  https://issues.redhat.com/browse/OCPBUGS-76523
```

### JSON format

```json
{
  "success": true,
  "issue_key": "OCPBUGS-76523",
  "value": "Approved",
  "url": "https://issues.redhat.com/browse/OCPBUGS-76523"
}
```

## Error Handling

- If `JIRA_TOKEN` is not set, the script exits with an error message
- If the API call fails, returns `success: false` with the HTTP error details
- The script verifies the update after setting it and reports the confirmed value
