---
name: Add JIRA Triage Link
description: Add a Component Readiness triage record link to a JIRA issue description
---

# Add JIRA Triage Link

This skill adds a Component Readiness triage record link to a JIRA issue description so that anyone viewing the bug can monitor the on-going status of all regressions triaged to it.

## When to Use This Skill

Use this skill after creating or updating a triage record via the `triage-regression` skill. The link gives bug viewers a way to see all regressions associated with the bug in Component Readiness.

## Prerequisites

1. **JIRA_USERNAME** and **JIRA_API_TOKEN** environment variables must be set
2. **Python 3.6+**

## Implementation Steps

### Step 1: Run the Script

```bash
script_path="plugins/ci/skills/add-jira-triage-link/add_jira_triage_link.py"

python3 "$script_path" OCPBUGS-12345 \
  --triage-id 456 \
  --format json
```

**Arguments**:
- `issue_key`: JIRA issue key (e.g., OCPBUGS-12345)

**Required Options**:
- `--triage-id <id>`: Triage record ID from Component Readiness

**Options**:
- `--format json|text`: Output format (default: text)

### Step 2: Parse the Output

```bash
output=$(python3 "$script_path" OCPBUGS-12345 --triage-id 456 --format json)
success=$(echo "$output" | jq -r '.success')

if [ "$success" = "true" ]; then
  already=$(echo "$output" | jq -r '.already_present')
  if [ "$already" = "true" ]; then
    echo "Triage link already in description"
  else
    echo "Triage link added"
  fi
fi
```

## Script Output Format

### JSON Format (--format json)

**Success (link added)**:
```json
{
  "success": true,
  "issue_key": "OCPBUGS-12345",
  "triage_url": "https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/triages/456",
  "already_present": false
}
```

**Success (link already present)**:
```json
{
  "success": true,
  "issue_key": "OCPBUGS-12345",
  "triage_url": "https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/triages/456",
  "already_present": true
}
```

**Error**:
```json
{
  "success": false,
  "error": "Failed to update description: HTTP 403: ...",
  "issue_key": "OCPBUGS-12345"
}
```

## Notes

- The script is idempotent — if the triage link is already in the description, it skips the update
- Uses Atlassian Document Format (ADF) to append a horizontal rule and the triage link section
- Appends to the existing description without modifying existing content
- Requires JIRA API v3 write access to the issue

## See Also

- Related Skill: `triage-regression` (creates triage records that produce the triage ID)
- Related Skill: `set-release-blocker` (similar pattern for updating JIRA issue fields)
- Related Command: `/ci:analyze-regression` (calls this skill after triaging)
