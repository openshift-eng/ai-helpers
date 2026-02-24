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
- [Components](#components)
- [MCP Tool Integration](#mcp-tool-integration)
  - [For GCP HCP Stories in GCP Project](#for-gcp-hcp-stories-in-gcp-project)
  - [For GCP HCP Epics in GCP Project](#for-gcp-hcp-epics-in-gcp-project)
- [Epic Linking Best Practices](#epic-linking-best-practices)
- [GCP HCP Team Standards](#gcp-hcp-team-standards)
  - [JIRA Templates](#jira-templates)
    - [Story Template](#story-template)
      - [Story Sizing Guide](#story-sizing-guide)
    - [Epic Template](#epic-template)
    - [Feature Template](#feature-template)
  - [Definition of Done](#definition-of-done)
    - [Story DoD](#story-dod)
    - [Spike DoD](#spike-dod)
    - [Bug DoD](#bug-dod)
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
| **Story Points** | `customfield_12310243` | Optional story point estimate | `3.0` |

## Components

The GCP project uses these components for organizing work:

| Component | Usage |
|-----------|-------|
| `hypershift-operator-gcp` | HyperShift operator, control plane components |
| `gcp-hcp-automation` | Terraform, ArgoCD, infrastructure automation |
| `gcp-api-gateway` | API gateway work |
| `Retrospective action items` | Team retrospective tracking |

**Usage:**
- Components are **optional** - only specify if the work clearly fits a component
- Use the direct `components` parameter (NOT in `additional_fields`)
- If work doesn't fit any existing component, leave empty - do not request new components

## MCP Tool Integration

### For GCP HCP Stories in GCP Project

```python
mcp__atlassian__jira_create_issue(
    project_key="GCP",
    summary="<story summary>",
    issue_type="Story",
    description="<formatted story description>",
    components="<component name>",  # Optional - see Components section
    additional_fields={
        "customfield_12311140": "GCP-456",  # Epic Link - parent epic
        "customfield_12310243": 3.0,        # Story Points - OMIT unless user confirms
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

**Story Points guidance**: Before creating a story, ask the user if they want to assign story points: "Would you like to assign story points to this story? I can walk you through the sizing guide." Reference the [Story Sizing Guide](#story-sizing-guide) to guide the conversation. If yes, set `customfield_12310243` as a float (e.g. `3.0`). If no, omit the field entirely.

### For GCP HCP Epics in GCP Project

```python
mcp__atlassian__jira_create_issue(
    project_key="GCP",
    summary="<epic summary>",
    issue_type="Epic",
    description="<formatted epic description>",
    components="<component name>",  # Optional - see Components section
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

The GCP HCP team maintains standardized templates and definitions to ensure consistent, high-quality JIRA tickets. **All GCP project issues MUST conform to these standards.**

### JIRA Templates

When creating GCP project issues, follow the appropriate template structure below. The full template content is embedded here for reference; source URLs are provided for each template.

---

### Story Template

Source: [jira-story-template.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-story-template.md)

Required structure for all Stories:

#### User Story

**As a** [platform user/developer/operations team/end user]
**I want** [goal/desire],
**so that** [benefit/reason].

_[Optional placeholder for another user story if this deliverable serves multiple users]_

#### Context / Background

[Current state, problem being solved, relevant history, links to related tickets/incidents]

#### Requirements

[Functional and non-functional requirements (performance, scalability, reliability, SLOs, compliance)]

#### Technical Approach

[Proposed solution, technologies/tools, major steps, alternatives considered]

#### Dependencies

[Blocking items: other teams/stories, external vendors, infrastructure/access needs, required approvals]

#### Additional Context

[Any relevant background, links, screenshots, or technical notes]

#### Story Sizing Guide

Use this guide to estimate the size of a story during refinement. Story sizes reflect complexity, risk, and effort combined. Story points use the Fibonacci sequence (0, 1, 2, 3, 5, 8, 13) to reflect increasing uncertainty as size grows. Stories should typically be **1-5 points**. Stories sized at 8+ should be split into smaller stories.

##### Pointing Criteria

| Points | Description |
|--------|-------------|
| **0** | Rarely used. Trivial task with stakeholder value but less risk/complexity than a 1-pointer. Example: Update a README link. |
| **1** | The smallest issue possible, everything scales from here. Can be a one-line change in code, a tedious but extremely simple task, etc. Basically, no risk, very low effort, very low complexity. |
| **2** | Simple, well-understood change. Low risk, low complexity but slightly more effort than a 1. Some investigation into how to accomplish the task may be necessary. |
| **3** | Doesn't have to be complex, but it is usually time consuming. The work should be fairly straightforward. There can be some minor risks. |
| **5** | Requires investigation, design, discussions, collaboration. Can be time consuming or complex. Risks involved. |
| **8** | Big task. Requires investigation, design, discussions, collaboration. Solution is challenging. Risks expected. Design doc required. **Consider splitting into smaller stories.** |
| **13** | Ideally, this shouldn't be used. If you ever see an issue that is this big, **it must be split into smaller stories**. |

##### Story Point Examples (GCP HCP Context)

**1 Point Examples**:
- Add a new environment variable to an existing operator deployment
- Update GKE node pool version in terraform config
- Fix a typo in HyperShift API field documentation
- Add a simple validation check to an existing function

**2 Point Examples**:
- Implement a new Prometheus metric for hosted control plane CPU usage
- Add retry logic to GCP API client with exponential backoff
- Create a simple e2e test for GKE cluster creation
- Update RBAC rules to allow service account access to a new resource type

**3 Point Examples**:
- Implement health checks for all management cluster components
- Add automated cleanup of orphaned GCP resources after cluster deletion
- Refactor logging configuration to use structured logging library
- Implement GCP service account impersonation for a specific workload

**5 Point Examples**:
- Design and implement a new controller to manage GCP firewall rules for hosted clusters
- Add support for customer-managed encryption keys (CMEK) to a storage component
- Implement automated backup and restore for management cluster state
- Migrate an existing operator from in-cluster to out-of-cluster deployment pattern

**8 Point Examples** (Should be split):
- Implement full observability stack (metrics, logging, tracing) for hosted control planes
- Add support for VPC-native GKE clusters with IP aliasing and network policies
- Migrate entire CI/CD pipeline from one platform to another

##### When to Split Stories

Split a story if any of these apply:

**By scope**:
- More than 5 acceptance criteria
- Touches more than 3 components or repositories
- Contains both investigation (spike) AND implementation work
- Has internal sequencing (step 1 must complete before step 2 begins)

**By layer**:
- API changes + controller implementation + CLI updates → 3 stories
- Backend logic + frontend UI + documentation → 3 stories

**By workflow step**:
- Create + Read + Update + Delete operations → 4 stories (or start with Create + Read)

**By component**:
- Changes needed in multiple operators → 1 story per operator
- Changes needed across multiple GCP services → 1 story per service

**By risk**:
- Separate proof-of-concept spike from production implementation
- Separate migration work (risky) from new feature work (lower risk)

##### Splitting Strategies

When splitting a large story, consider these approaches:

1. **Vertical slices**: Each story delivers end-to-end value for a subset of functionality
   - "As a user, I can create a cluster with default settings" → Story 1
   - "As a user, I can create a cluster with custom network settings" → Story 2

2. **Technical layers**: Split by component or layer (use sparingly, prefer vertical slices)
   - API design and implementation → Story 1
   - Controller implementation → Story 2
   - CLI integration → Story 3

3. **Spike + Implementation**: Separate research from execution
   - "Investigate options for GCP Workload Identity Federation" → Spike
   - "Implement WIF for HyperShift operator" → Story

4. **Incremental delivery**: Build complexity over multiple stories
   - "Implement basic health check endpoint" → Story 1
   - "Add detailed health metrics to endpoint" → Story 2
   - "Add automated alerting based on health metrics" → Story 3

#### Acceptance Criteria

- [ ] [Specific testable outcome 1]
- [ ] [Specific testable outcome 2]
- [ ] [Specific testable outcome 3]

---

### Epic Template

Source: [jira-epic-template.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-epic-template.md)

Required structure for all Epics. Epics represent a cohesive chunk of work within a Feature that can typically be completed in 1-2 sprints and decomposes into multiple Stories.

**Hierarchy**: Feature → **Epic** → Story

#### Title

[Action Verb] + [Specific Capability or Component]

**Examples**:
- "Establish e2e test suite for Hypershift on GKE in Prow"
- "Audit and set resource requests/limits for all Management Cluster components"
- "Cloud Network Config Controller: GCP Workload Identity Federation"

#### Use Case / Context

[Brief description of why this Epic is needed, what problem it solves, or what capability it enables]

#### Current State

[Describe the current state, limitations, or gaps that this Epic addresses]

**Optional**: Include technical details about current implementation, blockers, or constraints

#### Desired State / Goal

[Describe what will be true when this Epic is complete]

#### Scope

**This Epic covers**:
- [Component or capability 1]
- [Component or capability 2]
- [Component or capability 3]

**Out of Scope** (if applicable):
- [What's NOT included to avoid confusion]

#### Technical Details (Optional)

[Include relevant technical information such as:
- Architecture changes needed
- Technologies or tools to use
- Integration points
- Configuration requirements
- Standards or patterns to follow]

#### Dependencies

- [ ] [Blocking Epic or Story from another team]
- [ ] [External dependency or approval needed]
- [ ] [Infrastructure or access requirement]

#### Story Breakdown Checklist

- [ ] Stories created for all work identified in scope
- [ ] Each Story follows the Story Template above
- [ ] Story sequencing/priorities established
- [ ] Dependencies between Stories identified

#### Acceptance Criteria

- [ ] [Specific, measurable outcome 1]
- [ ] [Specific, measurable outcome 2]
- [ ] [Specific, measurable outcome 3]

#### Metadata

**Feature**: [Parent Feature, if applicable]
**Assignee**: [DRI for this Epic]
**Priority**: [P0/P1/P2/P3]
**Sprint Target**: [Target sprint(s) or quarter]
**Size Estimate**: Small / Medium / Large

---

### Feature Template

Source: [jira-feature-template.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-feature-template.md)

Required structure for all Features. Features represent high-level capabilities that span multiple sprints and decompose into multiple Epics and Stories. Used during milestone and quarterly planning.

#### Title

[Action Verb] + [Capability]

**Example**: "Implement Distributed Tracing for GCP HCP Services"

#### Context

[Why this Feature is needed and how it supports overall goals (e.g., Q1 milestone, Zero Operator principles, customer requirements)]

#### Scope

**What's Included**:
- [Main capability/component 1]
- [Main capability/component 2]
- [Main capability/component 3]

**What's NOT Included**:
- [Out of scope item 1 to avoid confusion]
- [Out of scope item 2]

#### Technical Approach (Optional)

[High-level approach if decided, key technologies/patterns to use, or note "TBD during Epic breakdown"]

#### Dependencies

- [Other Features that must complete first]
- [External teams or services (e.g., CLM team, Hypershift upstream, App-SRE)]
- [Infrastructure or access requirements]
- [Required approvals or decisions]

#### Acceptance Criteria

- [ ] [Specific, measurable outcome 1]
- [ ] [Specific, measurable outcome 2]
- [ ] [Specific, measurable outcome 3]

#### Metadata

**Epic(s)**: [To be created during breakdown]
**Priority**: [Set during prioritization]
**Demo Critical**: Yes/No
**Size Estimate**: Small / Medium / Large
**DRI**: [Directly Responsible Individual]

---

### Definition of Done

Source: [definition-of-done.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/definition-of-done.md)

When generating issue descriptions for GCP project, ensure acceptance criteria align with the relevant Definition of Done below.

#### Story DoD

In addition to meeting the requirements and any acceptance criteria from the Jira ticket, the developer must be able to check off the following activities for the story to be considered "done":

1. Story satisfies all acceptance criteria
2. Test automation complete, where applicable:
   1. Unit test coverage at >= 85% and passing
   2. Integration tests added and passing
   3. e2e test added and passing
3. PR for code changes has been merged
4. AI-Assisted Development: Human-in-the-Loop Guidelines are followed (e.g. commit message conventions)
5. PR for relevant architecture and design doc changes has been merged
6. Deployment to stage (once we have a stage platform)
7. Story is demo-able for end of sprint

#### Spike DoD

1. Spike findings are documented
2. Decision is made and documented in the relevant design decision/architecture docs
3. Resulting backlog items are created

#### Bug DoD

1. Test Added
   - Automated test included that verifies the fix
   - If not feasible, document why in the PR
2. Root Cause Documented
   - PR description explains what caused the bug
3. All Tests Pass
   - New and existing tests pass
   - No regressions introduced
4. Code Review Approved
   - At least one approval received
5. Ticket Closed
   - Link to merged PR added to bug ticket

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
Story Points: 3.0
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
