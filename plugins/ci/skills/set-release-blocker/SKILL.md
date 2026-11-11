---
name: set-release-blocker
description: Set the Release Blocker field on a JIRA issue
---

# Set Release Blocker

Sets the "Release Blocker" custom field on a JIRA issue. Component Readiness regressions are treated as release blockers, so any bug filed for a regression should have this field set to "Approved".

See the [release blocker definition](https://github.com/openshift/enhancements/blob/master/dev-guide/release-blocker-definition.md) for details on the criteria and process.

## Prerequisites

Jira credentials in the environment, either:

- **JIRA_API_TOKEN** and **JIRA_USERNAME**: a JIRA API token and your Atlassian account email
  - Obtain the token from: https://id.atlassian.com/manage-profile/security/api-tokens
- **JIRA_CLIENT_ID**, **JIRA_CLIENT_SECRET** and **JIRA_CLOUD_ID**: a service-account OAuth credential. Used whenever the client ID or secret is set, with no fallback to the API token

## Usage

```bash
# Set Release Blocker to Approved (default)
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523

# Explicitly set to Approved
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523 --value Approved

# Set to Proposed
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523 --value Proposed

# Set to Rejected
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523 --value Rejected

# Clear the field
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523 --value ""

# JSON output
python3 plugins/ci/skills/set-release-blocker/set_release_blocker.py OCPBUGS-76523 --format json
```

## JIRA Field Details

- **Field ID**: `customfield_10847`
- **Field name**: Release Blocker
- **Type**: Select dropdown
- **Options**:
  - `Approved` (option ID: `16772`)
  - `Proposed` (option ID: `16773`)
  - `Rejected` (option ID: `16774`)

## Output

### Text format (default)

```
Release Blocker set to 'Approved' on OCPBUGS-76523
  https://redhat.atlassian.net/browse/OCPBUGS-76523
```

### JSON format

```json
{
  "success": true,
  "issue_key": "OCPBUGS-76523",
  "value": "Approved",
  "url": "https://redhat.atlassian.net/browse/OCPBUGS-76523"
}
```

## Error Handling

- If the Jira credentials are missing or incomplete, the script exits with an error message
- If the API call fails, returns `success: false` with the HTTP error details
- The script verifies the update after setting it and reports the confirmed value
