---
name: GCP HCP Jira Conventions
description: GCP HCP team-specific Jira requirements for creating issues in the GCP project (Hypershift on GKE)
---

# GCP HCP Jira Conventions

This skill provides GCP HCP (Hypershift on GKE) team-specific conventions for creating Jira issues in the GCP project.

## Table of Contents

- [When to Use This Skill](#when-to-use-this-skill)
- [Project Information](#project-information)
- [Custom Fields](#custom-fields)
- [MCP Tool Integration](#mcp-tool-integration)
  - [For GCP HCP Stories in GCP Project](#for-gcp-hcp-stories-in-gcp-project)
  - [For GCP HCP Epics in GCP Project](#for-gcp-hcp-epics-in-gcp-project)
- [Epic Linking Best Practices](#epic-linking-best-practices)
- [GCP HCP Team Standards](#gcp-hcp-team-standards)
  - [JIRA Templates](#jira-templates)
  - [Definition of Done](#definition-of-done)
- [Examples](#examples)
  - [Example 1: GCP HCP Story](#example-1-gcp-hcp-story)
  - [Example 2: GCP HCP Epic](#example-2-gcp-hcp-epic)
- [See Also](#see-also)

## When to Use This Skill

This skill is automatically invoked when:
- Summary or description contains GCP HCP keywords: "GCP HCP", "Hypershift on GKE", "GKE hosted control plane"
- Project key is "GCP"
- User explicitly requests GCP HCP conventions

## Project Information

| Field | Value |
|-------|-------|
| **Project Key** | GCP |
| **Project Name** | GCP Hosted Control Planes (Hypershift on GKE) |
| **Issue Types** | Story, Epic, Task, Bug, Feature Request |

## Custom Fields

GCP project uses the same instance-wide custom fields as other Red Hat Jira projects:

| Field | Custom Field ID | Usage | Example |
|-------|-----------------|-------|---------|
| **Epic Name** | `customfield_12311141` | Required when creating Epics | `"Multi-cluster metrics aggregation"` |
| **Epic Link** | `customfield_12311140` | Link Story/Task → Epic | `"GCP-456"` |
| **Parent Link** | `customfield_12313140` | Link Epic → Feature | `"GCP-100"` |

## MCP Tool Integration

### For GCP HCP Stories in GCP Project

```python
mcp__atlassian__jira_create_issue(
    project_key="GCP",
    summary="<story summary>",
    issue_type="Story",
    description="<formatted story description>",
    additional_fields={
        "customfield_12311140": "GCP-456",  # Epic Link - parent epic
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### For GCP HCP Epics in GCP Project

```python
mcp__atlassian__jira_create_issue(
    project_key="GCP",
    summary="<epic summary>",
    issue_type="Epic",
    description="<formatted epic description>",
    additional_fields={
        "customfield_12311141": "Multi-cluster metrics aggregation",  # Epic Name (required, same as summary)
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
    # NOTE: Do NOT include parent link (customfield_12313140) here.
    # Add parent link in a separate update call per "Epic Linking Best Practices" section.
)
```

## Epic Linking Best Practices

**When creating an Epic with a parent Feature:**

1. Create Epic first WITHOUT parent link
2. Link to Feature in a separate update call

**Example:**
```python
# Step 1: Create Epic
epic = mcp__atlassian__jira_create_issue(
    project_key="GCP",
    issue_type="Epic",
    summary="Multi-cluster monitoring",
    additional_fields={
        "customfield_12311141": "Multi-cluster monitoring",  # Epic Name
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)

# Step 2: Link to Feature
mcp__atlassian__jira_update_issue(
    issue_key=epic["key"],
    fields={},
    additional_fields={
        "customfield_12313140": "GCP-100"  # Parent Link (Feature key)
    }
)
```

## GCP HCP Team Standards

The GCP HCP team maintains standardized templates and definitions to ensure consistent, high-quality JIRA tickets. **All GCP project issues MUST conform to these standards:**

### JIRA Templates

When creating GCP project issues, follow the appropriate template structure:

- **[Story Template](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-story-template.md)** - Required structure for all Stories
  - Includes: User Story, Context/Background, Requirements, Technical Approach, Dependencies, Acceptance Criteria
  - Ensures clear work requirements and reduces implementation ambiguity

- **[Epic Template](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-epic-template.md)** - Required structure for all Epics
  - Includes: Title format, Use Case/Context, Current State, Desired State/Goal, Scope, Technical Details, Dependencies, Story Breakdown Checklist, Acceptance Criteria, Metadata
  - Represents cohesive chunks of work completable in 1-2 sprints

- **[Feature Template](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-feature-template.md)** - Required structure for all Features
  - Includes: Title format, Context, Scope (What's Included/Not Included), Technical Approach, Dependencies, Acceptance Criteria, Metadata
  - Used during milestone and quarterly planning

### Definition of Done

- **[Definition of Done](https://github.com/openshift-online/gcp-hcp/blob/main/docs/definition-of-done.md)** - Completion criteria checklist
  - **Stories**: Test coverage ≥85%, PR merged, demo-able, architecture docs updated
  - **Spikes**: Findings documented, decision made, backlog items created
  - **Bugs**: Test added, root cause documented, no regressions

When generating issue descriptions for GCP project, incorporate the relevant template structure and ensure acceptance criteria align with the Definition of Done.

## Examples

### Example 1: GCP HCP Story

```
Summary: Enable automated backups for GKE hosted control planes

Description:
As a cluster administrator, I want to enable automated backups for my GKE-hosted control planes, so that I can quickly recover from data loss or corruption.

Acceptance Criteria:
- Test that backups can be scheduled daily at a configurable time
- Test that backup retention policy is enforced (30 days default)
- Test that backups can be restored to the same or different GCP project
- Test that backup operations do not interrupt cluster operations

Project: GCP
Issue Type: Story
Component: (optional)
Parent: GCP-456 (Epic)
Labels: ai-generated-jira
```

### Example 2: GCP HCP Epic

```
Summary: Multi-cluster monitoring and observability

Description:
Implement comprehensive monitoring and observability for GCP-hosted control planes across multiple GKE clusters, enabling operators to detect and respond to issues proactively.

h2. Scope

* Metrics collection from control plane pods
* Central metrics aggregation and storage
* Dashboards for monitoring cluster health
* Alerting framework for critical metrics
* Log aggregation and analysis

h2. Acceptance Criteria

- Test that metrics are collected from all control plane pods
- Test that metrics are available within 30 seconds of generation
- Test that dashboards accurately reflect cluster state
- Test that alerts fire within 2 minutes of anomaly detection

Project: GCP
Issue Type: Epic
Parent: GCP-100 (Feature)
Labels: ai-generated-jira
```

## See Also

- `/jira:create` command - Main Jira issue creation command
- `cntrlplane` skill - CNTRLPLANE project conventions (similar structure)
- `hypershift` skill - HyperShift team conventions (on AWS/Azure)
