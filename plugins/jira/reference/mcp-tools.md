---
name: Jira Custom Fields and JQL Reference
description: Custom field documentation and JQL queries for the Red Hat Jira instance
---

# Jira Custom Fields and JQL Reference

Custom field definitions, format requirements, and common JQL queries for the Red Hat Jira instance (redhat.atlassian.net). For tool signatures and parameters, refer to the official Atlassian plugin documentation.

**Note:** All Atlassian MCP tools require `cloudId: "redhat.atlassian.net"` as a parameter.

## Table of Contents

- [Custom Fields for redhat.atlassian.net](#custom-fields-for-redhatatlassiannet)
  - [Field Format Notes](#field-format-notes)
- [Field Format Requirements](#field-format-requirements)
  - [Epic Link Field](#epic-link-field)
  - [Parent Link Field](#parent-link-field)
  - [Target Version Field](#target-version-field)
  - [Epic Name Field (Required for Epics)](#epic-name-field-required-for-epics)
- [Parent Linking Fallback Strategy](#parent-linking-fallback-strategy)
- [Common JQL Queries](#common-jql-queries)
- [Reference](#reference)

## Custom Fields for redhat.atlassian.net

The Red Hat Jira instance (redhat.atlassian.net) uses the following custom fields for issue hierarchy and versions:

| Field Name | Custom Field ID | Type | Usage | Example |
|-----------|-----------------|------|-------|---------|
| **Epic Name** | `customfield_10011` | String | Required when creating Epics (must match summary) | `"Multi-cluster monitoring"` |
| **Epic Link** | `customfield_10014` | String | Link Story/Task to Epic | `"GCP-456"` |
| **Parent Link** | `customfield_10018` | String | Link Epic to Feature | `"GCP-100"` |
| **Target Version** | `customfield_10855` | Array of Objects | Set target release version | `[{"id": "12448830"}]` |

### Field Format Notes

**Epic Name (customfield_10011):**
- Type: String
- Format: Plain text string
- Required: Yes, when creating Epics
- Value: Must match the Epic's summary
- Example: `"customfield_10011": "Multi-cluster metrics aggregation"`

**Epic Link (customfield_10014):**
- Type: String
- Format: Issue key string
- Usage: Link Story/Task to parent Epic
- Value: Parent Epic key
- Example: `"customfield_10014": "GCP-456"`

**Parent Link (customfield_10018):**
- Type: String
- Format: Issue key string
- Usage: Link Epic to parent Feature
- Value: Parent Feature key
- Example: `"customfield_10018": "GCP-100"`

**Target Version (customfield_10855):**
- Type: Array of Objects
- Format: Array with objects containing `id` field
- Usage: Set the target release version
- Value: Array of version objects
- Example: `"customfield_10855": [{"id": "12448830"}]`
- Note: Must be array format, not string

## Field Format Requirements

### Epic Link Field

Use the Epic Link custom field (customfield_10014) to link Stories and Tasks to parent Epics. The field accepts a string value containing the Epic's issue key:

```python
# In createJiraIssue additional_fields:
additional_fields={
    "customfield_10014": "GCP-456"  # Epic Link - string format with issue key
}

# In editJiraIssue fields:
fields={
    "customfield_10014": "GCP-456"  # Epic Link - string format with issue key
}
```

### Parent Link Field

Use the Parent Link custom field (customfield_10018) to link Epics to parent Features. The field accepts a string value containing the Feature's issue key:

```python
# In createJiraIssue additional_fields:
additional_fields={
    "customfield_10018": "GCP-100"  # Parent Link - string format with issue key
}

# In editJiraIssue fields:
fields={
    "customfield_10018": "GCP-100"  # Parent Link - string format with issue key
}
```

### Target Version Field

Use the Target Version custom field (customfield_10855) with an array of objects containing version IDs:

```python
# In createJiraIssue additional_fields:
additional_fields={
    "customfield_10855": [{"id": "12448830"}]  # Array of objects with id property
}

# In editJiraIssue fields:
fields={
    "customfield_10855": [{"id": "12448830"}]  # Array of objects with id property
}
```

### Epic Name Field (Required for Epics)

When creating Epic issues, include the Epic Name custom field (customfield_10011) with a value matching the Epic's summary:

```python
mcp__plugin_atlassian_atlassian__createJiraIssue(
    cloudId="redhat.atlassian.net",
    projectKey="GCP",
    summary="Multi-cluster monitoring",
    issueTypeName="Epic",
    contentFormat="markdown",
    additional_fields={
        "customfield_10011": "Multi-cluster monitoring",  # Must match summary
        "labels": ["ai-generated-jira"],
    }
)
```

## Parent Linking Fallback Strategy

If issue creation fails due to parent linking errors:

```python
# Step 1: Create issue without parent link
issue = mcp__plugin_atlassian_atlassian__createJiraIssue(
    cloudId="redhat.atlassian.net",
    projectKey="GCP",
    summary="Story title",
    issueTypeName="Story",
    contentFormat="markdown",
    description="Description",
    additional_fields={
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
        # No parent/epic link field
    }
)

# Step 2: Link via update if creation succeeds
if issue:
    mcp__plugin_atlassian_atlassian__editJiraIssue(
        cloudId="redhat.atlassian.net",
        issueIdOrKey=issue["key"],
        fields={
            "customfield_10014": "GCP-456"  # Add Epic Link via update
        }
    )
```

## Common JQL Queries

```jql
# All open stories in a project
project = GCP AND type = Story AND status = Open

# Stories under a specific epic
project = GCP AND "Epic Link" = GCP-100

# AI-generated issues needing review
project = GCP AND labels = "ai-generated-jira" AND status != Done

# Issues created in the last 7 days
project = GCP AND created >= -7d

# Issues assigned to current user
project = GCP AND assignee = currentUser()

# All open epics
project = GCP AND type = Epic AND status != Done ORDER BY created DESC

# Blocker priority issues
project = GCP AND priority = Blocker AND status != Done ORDER BY created DESC

# High priority issues
project = GCP AND priority IN (Blocker, Critical) AND status != Done

# Ready for sprint
project = GCP AND status = "Ready" AND type = Story
```

## Reference

- [Atlassian Jira REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
- [JQL (Jira Query Language) Documentation](https://confluence.atlassian.com/jiracorecloud/advanced-searching-765593716.html)
- [Issue Linking Documentation](https://confluence.atlassian.com/jira/linking-issues-39211382.html)
- [Atlassian MCP Plugin](https://github.com/atlassian/mcp-atlassian)
