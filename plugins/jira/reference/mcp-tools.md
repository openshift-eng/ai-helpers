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
  - [Parent Field (all hierarchy levels)](#parent-field-all-hierarchy-levels)
  - [Target Version Field](#target-version-field)
  - [Creating Epics](#creating-epics)
- [Parent Linking Fallback Strategy](#parent-linking-fallback-strategy)
- [Common JQL Queries](#common-jql-queries)
- [Reference](#reference)

## Issue Operations

### Create Issue

**Tool:** `mcp__rh-jira__jira_create_issue`

```python
mcp__rh-jira__jira_create_issue(
    project_key="PROJECT",           # Required: Project key (e.g., "CNTRLPLANE", "GCP", "OCPBUGS")
    summary="Issue title",            # Required: Issue summary/title
    issue_type="Story",               # Required: Type (Story, Epic, Task, Bug, Feature) — "Feature Request" is RFE project only
    description="Issue description",  # Optional: Full description in Markdown (wiki markup also accepted)
    components="Component Name",      # Optional: Single component name or list
    additional_fields={               # Optional: Additional fields
        "labels": ["label1", "label2"],
        "security": {"name": "Red Hat Employee"},
        "parent": {"key": "EPIC-OR-FEATURE-KEY"},  # Parent for any level: Story→Epic, Epic→Feature
        "customfield_10855": [{"id": "VERSION_ID"}],  # Target Version (array of objects with id)
    }
)
```

**Returns:** Issue object with `key` and `id` fields

**Example - Create Story with Epic Link:**

```python
issue = mcp__rh-jira__jira_create_issue(
    project_key="GCP",
    summary="Enable Pod Disruption Budgets for control plane",
    issue_type="Story",
    description="As a cluster administrator, I want to enable Pod Disruption Budgets for the control plane, so that I can prevent accidental disruptions.\n\n## Acceptance Criteria\n\n* Test that PDB is configured for all control plane pods\n* Test that pods are protected from voluntary disruptions",
    components="HyperShift / ROSA",
    additional_fields={
        "parent": {"key": "GCP-456"},  # Link to parent Epic
        "priority": {"name": "Major"},  # Set priority level
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
print(f"Created: {issue['key']}")  # Output: Created: GCP-789
```

### Get Issue

**Tool:** `mcp__rh-jira__jira_get_issue`

```python
mcp__rh-jira__jira_get_issue(
    issue_key="PROJ-123"  # Required: Issue key (e.g., "GCP-456")
)
```

**Returns:** Issue object with default fields (summary, status, priority, assignee, reporter, labels, description, created, updated). Use `fields="*all"` to include all custom fields.

**Example:**

```python
issue = mcp__rh-jira__jira_get_issue(issue_key="GCP-456")
print(issue["summary"])        # Get issue summary
print(issue["status"]["name"]) # Get status
```

### Search Issues

**Tool:** `mcp__rh-jira__jira_search`

```python
mcp__rh-jira__jira_search(
    jql="project = GCP AND type = Story",  # Required: JQL query
    fields="summary,status,assignee",      # Optional: Comma-separated fields to return
    start_at=0,                            # Optional: Pagination offset (0-based)
    limit=50                               # Optional: Max results (1-50)
)
```

**Returns:** Dict with `issues` list — `{"total": N, "start_at": N, "issues": [...]}`

**Common JQL Queries:**

```jql
# All issues in a project
project = GCP

# Issues by type
project = GCP AND type = Story
project = GCP AND type = Epic

# Issues by status
project = GCP AND status = "In Progress"
project = GCP AND status = "To Do"

# Issues by assignee
project = GCP AND assignee = currentUser()

# Issues by label
project = GCP AND labels = "ai-generated-jira"

# Issues by parent epic
project = GCP AND parent = GCP-100

# Combinations
project = GCP AND type = Story AND parent = GCP-100 AND status != Done
```

### Update Issue

**Tool:** `mcp__rh-jira__jira_update_issue`

```python
mcp__rh-jira__jira_update_issue(
    issue_key="PROJ-123",             # Required: Issue key
    fields={                           # Optional: Standard fields to update
        "summary": "New summary",
        "description": "New description",
        "parent": {"key": "EPIC-456"},  # Update parent (standard field → goes in fields)
    },
    additional_fields={               # Optional: Custom fields to update
        "labels": ["new-label"],
        "customfield_10855": [{"id": "VERSION_ID"}],  # Update Target Version
    }
)
```

**Example - Link Epic to Feature:**

```python
mcp__rh-jira__jira_update_issue(
    issue_key="GCP-100",
    fields={"parent": {"key": "GCP-50"}},  # Link Epic to parent Feature
    additional_fields={}
)
```

### Add Comment

**Tool:** `mcp__rh-jira__jira_add_comment`

```python
mcp__rh-jira__jira_add_comment(
    issue_key="PROJ-123",             # Required: Issue key
    comment="Comment text"            # Required: Comment content (Markdown supported)
)
```

**Example:**

```python
mcp__rh-jira__jira_add_comment(
    issue_key="GCP-456",
    comment="Implementation complete. Ready for testing.\n\nSee linked PR for code changes."
)
```

## Linking Operations

### Create Issue Link

**Tool:** `mcp__rh-jira__jira_create_issue_link`

```python
mcp__rh-jira__jira_create_issue_link(
    inward_issue_key="PROJ-123",       # Required: inward issue key
    outward_issue_key="PROJ-456",      # Required: outward issue key
    link_type="Related"                # Required: link type NAME (see table below)
)
```

**Common Link Types** (`link_type` = type name; inward/outward is the direction):

| `link_type` value | inward | outward |
|-------------------|--------|---------|
| `Related` | is related to | relates to |
| `Blocks` | is blocked by | blocks |
| `Cloners` | is cloned by | clones |
| `Duplicate` | is duplicated by | duplicates |
| `Depend` | is depended on by | depends on |
| `Causality` | is caused by | causes |
| `Incorporates` | is incorporated by | incorporates |

**Example:**

```python
mcp__rh-jira__jira_create_issue_link(
    inward_issue_key="GCP-456",   # inward = "is blocked by"
    outward_issue_key="GCP-789",  # outward = "blocks"
    link_type="Blocks"  # GCP-456 is blocked by GCP-789
)
```

### Get Link Types

**Tool:** `mcp__rh-jira__jira_get_link_types`

```python
mcp__rh-jira__jira_get_link_types()
```

**Returns:** List of link type objects `{"id": "10000", "name": "Blocks", "inward": "...", "outward": "..."}` — note: `id` here is a **string** (unlike transition IDs which are integers)


## Issue Transitions

### Get Transitions

**Tool:** `mcp__rh-jira__jira_get_transitions`

```python
mcp__rh-jira__jira_get_transitions(
    issue_key="PROJ-123"  # Required: Issue key
)
```

**Returns:** List of available transitions for the issue

**Example:**

```python
# Note: trans['id'] is an integer; convert to str when passing to jira_transition_issue
# Transition names/IDs are project-specific:
#   CNTRLPLANE Story: To Do(11), In Progress(21), Code Review(31), Review(41), Closed(51)
#   OCPBUGS Bug:      New(11),   ASSIGNED(21),    POST(31), ON_QA(41), Closed(81)
transitions = mcp__rh-jira__jira_get_transitions(issue_key="GCP-456")
for trans in transitions:
    print(f"{trans['name']}: {trans['id']}")
```

### Transition Issue

**Tool:** `mcp__rh-jira__jira_transition_issue`

```python
mcp__rh-jira__jira_transition_issue(
    issue_key="PROJ-123",              # Required: Issue key
    transition_id="11",                # Required: Transition ID (get from jira_get_transitions)
    fields={}                          # Optional: Fields to update during transition
)
```

**Example:**

```python
# First get available transitions
transitions = mcp__rh-jira__jira_get_transitions(issue_key="GCP-456")
target_name = "In Progress"  # varies by project: "ASSIGNED" for OCPBUGS, "In Progress" for CNTRLPLANE
transition = next((t for t in transitions if t["name"] == target_name), None)
if transition:
    in_progress_id = str(transition["id"])

# Then transition the issue
mcp__rh-jira__jira_transition_issue(
    issue_key="GCP-456",
    transition_id=in_progress_id  # str, e.g. "21"
)
```

## Custom Fields for redhat.atlassian.net

The Red Hat Jira instance (redhat.atlassian.net) uses the following custom fields for issue hierarchy and versions:

| Field Name | Custom Field ID | Type | Usage | Example |
|-----------|-----------------|------|-------|---------|
| **Parent** | `parent` | Object | Link any issue to its parent — works for ALL levels: Story→Epic, Epic→Feature (including cross-project) | `{"key": "GCP-456"}` |
| **Target Version** | `customfield_10855` | Array of Objects | Set target release version | `[{"id": "VERSION_ID"}]` |

> **Note:** `customfield_10018` (JPO Parent Link) exists as a field but is **not populated** in redhat.atlassian.net — the standard `parent` field handles all hierarchy levels including Epic→Feature.

> **Note:** The old `issues.redhat.com` fields `customfield_12311140` (Epic Link), `customfield_12311141` (Epic Name), `customfield_12313140` (Parent Link), and `customfield_12319940` (Target Version) are no longer valid. On Atlassian Cloud, Epic Name is not a separate field — the Epic's `summary` serves as its name.

### Field Format Notes

**Parent (`parent`):**
- Type: Object
- Format: Object with `key` property
- Usage: Link ANY issue to its parent — covers ALL hierarchy levels (Story→Epic, Epic→Feature, cross-project)
- Example: `"parent": {"key": "GCP-456"}`
- Note: `customfield_10018` (JPO Parent Link) is NOT used in redhat.atlassian.net

**Target Version (`customfield_10855`):**
- Type: Array of Objects
- Format: Array with objects containing `id` OR `name` — both accepted
- Usage: Set the target release version
- Value: Fetch versions via `mcp__rh-jira__jira_get_project_versions`
- Example by ID: `"customfield_10855": [{"id": "79148"}]`
- Example by name: `"customfield_10855": [{"name": "openshift-4.22"}]` or `[{"name": "4.22"}]` (OCPBUGS)
- Note: Must be array format, not string

## Field Format Requirements

### Parent Field (all hierarchy levels)

Use the standard `parent` field for ALL hierarchy links — Story→Epic, Epic→Feature, including cross-project:

```python
# In jira_create_issue — parent goes in additional_fields
additional_fields={
    "parent": {"key": "GCP-456"}  # Epic key (Story→Epic)
}
additional_fields={
    "parent": {"key": "GCP-100"}  # Feature key (Epic→Feature, cross-project ok)
}

# In jira_update_issue — parent goes in fields (standard field)
fields={
    "parent": {"key": "GCP-456"}
}
```

### Target Version Field

Use the Target Version custom field (`customfield_10855`) with an array containing either `id` or `name`:

```python
# By version ID (preferred — use jira_get_project_versions to look up ID)
additional_fields={
    "customfield_10855": [{"id": "79148"}]  # e.g. openshift-4.22 in CNTRLPLANE
}

# By version name (simpler, but ensure exact name match)
additional_fields={
    "customfield_10855": [{"name": "openshift-4.22"}]  # CNTRLPLANE format
}
additional_fields={
    "customfield_10855": [{"name": "4.22"}]  # OCPBUGS format (no openshift- prefix)
}
```

### Creating Epics

In Jira Cloud, Epic Name is no longer a separate required custom field — the `summary` field serves as the Epic name:

```python
mcp__rh-jira__jira_create_issue(
    project_key="GCP",
    summary="Multi-cluster monitoring",
    issue_type="Epic",
    additional_fields={
        "labels": ["ai-generated-jira"],
    }
)
```

## Parent Linking Fallback Strategy

If issue creation fails due to parent linking errors:

```python
# Step 1: Create issue without parent link
issue = mcp__rh-jira__jira_create_issue(
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
    mcp__rh-jira__jira_update_issue(
        issue_key=issue["key"],
        fields={"parent": {"key": "GCP-456"}},  # Add parent Epic via update
        additional_fields={}
    )
```

## Common JQL Queries

```jql
# All open stories in a project
project = GCP AND type = Story AND status != Done

# Stories under a specific epic
project = GCP AND parent = GCP-100

# AI-generated issues needing review
project = GCP AND labels = "ai-generated-jira" AND status != Done

# Issues created in the last 7 days
project = GCP AND created >= -7d

# Issues assigned to current user
project = GCP AND assignee = currentUser()

# All open epics
project = GCP AND type = Epic AND status != Done ORDER BY created DESC

# Critical priority issues
project = GCP AND priority = Critical AND status != Done ORDER BY created DESC

# High priority issues
project = GCP AND priority IN (Critical, Major) AND status != Done

# Open stories
project = GCP AND status != Done AND type = Story ORDER BY priority ASC
```

## Reference

- [Atlassian Jira REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
- [JQL (Jira Query Language) Documentation](https://confluence.atlassian.com/jiracorecloud/advanced-searching-765593716.html)
- [Issue Linking Documentation](https://support.atlassian.com/jira-software-cloud/docs/link-issues/)
