---
name: MCP Tools Reference
description: MCP tool signatures and custom field documentation for Jira
---

# MCP Tools Reference

This guide documents the MCP (Model Context Protocol) tools available for automating Jira operations, including tool signatures, parameters, and custom field definitions for the Red Hat Jira instance (redhat.atlassian.net).

## Table of Contents

- [Issue Operations](#issue-operations)
  - [Create Issue](#create-issue)
  - [Get Issue](#get-issue)
  - [Search Issues](#search-issues)
  - [Update Issue](#update-issue)
  - [Add Comment](#add-comment)
- [Linking Operations](#linking-operations)
  - [Create Issue Link](#create-issue-link)
  - [Get Link Types](#get-link-types)
- [Issue Transitions](#issue-transitions)
  - [Get Transitions](#get-transitions)
  - [Transition Issue](#transition-issue)
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

## Issue Operations

### Create Issue

**Tool:** `mcp__atlassian__jira_create_issue`

```python
mcp__atlassian__jira_create_issue(
    project_key="PROJECT",           # Required: Project key (e.g., "CNTRLPLANE", "GCP", "OCPBUGS")
    summary="Issue title",            # Required: Issue summary/title
    issue_type="Story",               # Required: Type (Story, Epic, Task, Bug, Feature, Feature Request)
    description="Issue description",  # Optional: Full description with wiki markup
    components="Component Name",      # Optional: Single component name or list
    additional_fields={               # Optional: Additional fields
        "labels": ["label1", "label2"],
        "security": {"name": "Red Hat Employee"},
        "customfield_10014": "EPIC-123",  # Epic Link for Stories/Tasks
        "customfield_10011": "Epic Name",  # Epic Name for Epics
        "customfield_10018": "FEATURE-50", # Parent Link for Epics
        "customfield_10855": [{"id": "12448830"}],  # Target Version (array of objects with id)
    }
)
```

**Returns:** Issue object with `key` and `id` fields

**Example - Create Story with Epic Link:**

```python
issue = mcp__atlassian__jira_create_issue(
    project_key="GCP",
    summary="Enable Pod Disruption Budgets for control plane",
    issue_type="Story",
    description="As a cluster administrator, I want to enable Pod Disruption Budgets for the control plane, so that I can prevent accidental disruptions.\n\nh2. Acceptance Criteria\n\n* Test that PDB is configured for all control plane pods\n* Test that pods are protected from voluntary disruptions",
    components="HyperShift / ROSA",
    additional_fields={
        "customfield_10014": "GCP-456",  # Link to parent Epic
        "priority": {"name": "Major"},  # Set priority level
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
print(f"Created: {issue['key']}")  # Output: Created: GCP-789
```

### Get Issue

**Tool:** `mcp__atlassian__jira_get_issue`

```python
mcp__atlassian__jira_get_issue(
    issue_key="PROJ-123"  # Required: Issue key (e.g., "GCP-456")
)
```

**Returns:** Complete issue object with all fields

**Example:**

```python
issue = mcp__atlassian__jira_get_issue(issue_key="GCP-456")
print(issue["fields"]["summary"])  # Get issue summary
print(issue["fields"]["status"]["name"])  # Get status
```

### Search Issues

**Tool:** `mcp__atlassian__jira_search_issues`

```python
mcp__atlassian__jira_search_issues(
    jql="project = GCP AND type = Story",  # Required: JQL query
    start_at=0,           # Optional: Pagination offset
    max_results=50        # Optional: Number of results to return
)
```

**Returns:** List of issue objects matching the query

**Common JQL Queries:**

```jql
# All issues in a project
project = GCP

# Issues by type
project = GCP AND type = Story
project = GCP AND type = Epic

# Issues by status
project = GCP AND status = "In Progress"
project = GCP AND status = Open

# Issues by assignee
project = GCP AND assignee = currentUser()

# Issues by label
project = GCP AND labels = "ai-generated-jira"

# Issues by parent epic
project = GCP AND "Epic Link" = GCP-100

# Combinations
project = GCP AND type = Story AND "Epic Link" = GCP-100 AND status = Open
```

### Update Issue

**Tool:** `mcp__atlassian__jira_update_issue`

```python
mcp__atlassian__jira_update_issue(
    issue_key="PROJ-123",             # Required: Issue key
    fields={                           # Optional: Standard fields to update
        "summary": "New summary",
        "description": "New description"
    },
    additional_fields={               # Optional: Custom fields to update
        "customfield_10014": "EPIC-456",  # Update Epic Link
        "labels": ["new-label"],
        "customfield_10855": [{"id": "12448830"}],  # Update Target Version
    }
)
```

**Example - Link Epic to Feature:**

```python
mcp__atlassian__jira_update_issue(
    issue_key="GCP-100",
    fields={},
    additional_fields={
        "customfield_10018": "GCP-50"  # Parent Link (Feature key)
    }
)
```

### Add Comment

**Tool:** `mcp__atlassian__jira_add_issue_comment`

```python
mcp__atlassian__jira_add_issue_comment(
    issue_key="PROJ-123",             # Required: Issue key
    comment_body="Comment text"        # Required: Comment content (wiki markup supported)
)
```

**Example:**

```python
mcp__atlassian__jira_add_issue_comment(
    issue_key="GCP-456",
    comment_body="Implementation complete. Ready for testing.\n\nSee linked PR for code changes."
)
```

## Linking Operations

### Create Issue Link

**Tool:** `mcp__atlassian__jira_create_issue_link`

```python
mcp__atlassian__jira_create_issue_link(
    inward_issue_key="PROJ-123",       # Required: First issue
    outward_issue_key="PROJ-456",      # Required: Second issue
    link_type="relates to"              # Required: Link type (see below)
)
```

**Common Link Types:**

- `relates to` - Generic relationship
- `is blocked by` - Blocked by another issue
- `blocks` - Blocks another issue
- `is cloned by` - Cloned by another issue
- `clones` - Clones another issue
- `is duplicated by` - Duplicated by another issue
- `duplicates` - Duplicates another issue
- `depends on` - Depends on another issue
- `is depended on by` - Depended on by another issue

**Example:**

```python
mcp__atlassian__jira_create_issue_link(
    inward_issue_key="GCP-456",
    outward_issue_key="GCP-789",
    link_type="is blocked by"  # GCP-456 is blocked by GCP-789
)
```

### Get Link Types

**Tool:** `mcp__atlassian__jira_get_link_types`

```python
mcp__atlassian__jira_get_link_types()
```

**Returns:** List of available link types

## Issue Transitions

### Get Transitions

**Tool:** `mcp__atlassian__jira_get_issue_transitions`

```python
mcp__atlassian__jira_get_issue_transitions(
    issue_key="PROJ-123"  # Required: Issue key
)
```

**Returns:** List of available transitions for the issue

**Example:**

```python
transitions = mcp__atlassian__jira_get_issue_transitions(issue_key="GCP-456")
for trans in transitions:
    print(f"{trans['name']}: {trans['id']}")  # e.g., "In Progress: 11", "Done: 21"
```

### Transition Issue

**Tool:** `mcp__atlassian__jira_transition_issue`

```python
mcp__atlassian__jira_transition_issue(
    issue_key="PROJ-123",              # Required: Issue key
    transition_id="11",                # Required: Transition ID (get from get_issue_transitions)
    fields={}                          # Optional: Fields to update during transition
)
```

**Example:**

```python
# First get available transitions
transitions = mcp__atlassian__jira_get_issue_transitions(issue_key="GCP-456")
in_progress_id = next(t["id"] for t in transitions if t["name"] == "In Progress")

# Then transition the issue
mcp__atlassian__jira_transition_issue(
    issue_key="GCP-456",
    transition_id=in_progress_id
)
```

## Custom Fields for redhat.atlassian.net

The Red Hat Jira instance (redhat.atlassian.net) uses the following custom fields for issue hierarchy and versions:

| Field Name | Custom Field ID | Type | Usage | Example |
|-----------|-----------------|------|-------|---------|
| **Epic Name** | `customfield_10011` | String | Required when creating Epics (must match summary) | `"Multi-cluster monitoring"` |
| **Epic Link** | `customfield_10014` | String | Link Story/Task → Epic | `"GCP-456"` |
| **Parent Link** | `customfield_10018` | String | Link Epic → Feature | `"GCP-100"` |
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
additional_fields={
    "customfield_10014": "GCP-456"  # Epic Link - string format with issue key
}
```

### Parent Link Field

Use the Parent Link custom field (customfield_10018) to link Epics to parent Features. The field accepts a string value containing the Feature's issue key:

```python
additional_fields={
    "customfield_10018": "GCP-100"  # Parent Link - string format with issue key
}
```

### Target Version Field

Use the Target Version custom field (customfield_10855) with an array of objects containing version IDs:

```python
additional_fields={
    "customfield_10855": [{"id": "12448830"}]  # Array of objects with id property
}
```

### Epic Name Field (Required for Epics)

When creating Epic issues, include the Epic Name custom field (customfield_10011) with a value matching the Epic's summary:

```python
mcp__atlassian__jira_create_issue(
    project_key="GCP",
    summary="Multi-cluster monitoring",
    issue_type="Epic",
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
issue = mcp__atlassian__jira_create_issue(
    project_key="GCP",
    summary="Story title",
    issue_type="Story",
    description="Description",
    additional_fields={
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
        # No parent/epic link field
    }
)

# Step 2: Link via update if creation succeeds
if issue:
    mcp__atlassian__jira_update_issue(
        issue_key=issue["key"],
        fields={},
        additional_fields={
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
