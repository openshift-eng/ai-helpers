---
name: Create Jira Epic
description: Implementation guide for creating Jira epics with proper scope and parent linking
---

# Create Jira Epic

This skill provides implementation guidance for creating well-structured Jira epics that organize related stories and tasks into cohesive bodies of work.

## When to Use This Skill

This skill is automatically invoked by the `/jira:create epic` command to guide the epic creation process.

## Prerequisites

- MCP Jira server configured and accessible
- User has permissions to create issues in the target project
- Understanding of the epic scope and related work

**Reference Documentation:**
- [MCP Tools Reference](../../reference/mcp-tools.md) - Custom fields and JQL queries
- [CLI Fallback Reference](../../reference/cli-fallback.md) - jira-cli commands (only if MCP unavailable)

## What is an Epic?

An agile epic is:
- A **body of work** that can be broken down into specific items (stories/tasks)
- Based on the needs/requests of customers or end-users
- An important practice for agile and DevOps teams
- A tool to **manage work** at a higher level than individual stories

### Epic Characteristics

Epics should:
- Be **more narrow** than a market problem or feature
- Be **broader** than a user story
- **Fit inside a time box** (quarter/release)
- Stories within the epic should **fit inside a sprint**
- Include **acceptance criteria** that define when the epic is done

### Epic vs Feature vs Story

| Level | Scope | Duration | Example |
|-------|-------|----------|---------|
| Feature | Strategic objective, market problem | Multiple releases | "Advanced cluster observability" |
| Epic | Specific capability, narrower than feature | One quarter/release | "Multi-cluster metrics aggregation" |
| Story | Single user-facing functionality | One sprint | "As an SRE, I want to view metrics from multiple clusters in one dashboard" |

## Epic Name Field Requirement

**IMPORTANT:** Many Jira configurations require the **epic name** field to be set.

- **Epic Name** = **Summary** (should be identical)
- This is a separate required field in addition to the summary field
- If epic name is missing, epic creation will fail

**MCP Tool Handling:**
- Some projects auto-populate epic name from summary
- Some require explicit epic name field
- Always set epic name = summary to ensure compatibility

## Epic Description Best Practices

### Clear Objective

The epic description should:
- State the overall goal or objective
- Explain the value or benefit
- Identify the target users or stakeholders
- Define the scope (what's included and excluded)

**Good example:**
```
Enable administrators to manage multiple hosted control plane clusters from a single observability dashboard.

This epic delivers unified metrics aggregation, alerting, and visualization across clusters, reducing the operational overhead of managing multiple cluster environments.

Target users: SREs, Platform administrators
```

### Acceptance Criteria for Epics

Epic-level acceptance criteria define when the epic is complete:

**Format:**
```
## Epic Acceptance Criteria

- <High-level outcome 1>
- <High-level outcome 2>
- <High-level outcome 3>
```

**Example:**
```
## Epic Acceptance Criteria

- Administrators can view aggregated metrics from all clusters in a single dashboard
- Alert rules can be configured to fire based on cross-cluster conditions
- Historical metrics are retained for 30 days across all clusters
- Documentation is complete for multi-cluster setup and configuration
```

**Characteristics:**
- Broader than story AC (focus on overall capability, not implementation details)
- Measurable outcomes
- User-observable (not technical implementation)
- Typically 3-6 criteria (if more, consider splitting epic)

### Timeboxing

Include timeframe information:
- Target quarter or release
- Key milestones or dependencies
- Known constraints

**Example:**
```
## Timeline

- Target: Q1 2025 / OpenShift 4.21
- Milestone 1: Metrics collection infrastructure (Sprint 1-2)
- Milestone 2: Dashboard and visualization (Sprint 3-4)
- Milestone 3: Alerting and historical data (Sprint 5-6)
```

### Parent Link to Feature

If the epic belongs to a larger feature:
- Link to parent feature using `--parent` flag
- Explain how this epic contributes to the feature
- Reference feature key in description

**Example:**
```
## Parent Feature

This epic is part of [PROJ-100] "Advanced cluster observability" and specifically addresses the multi-cluster aggregation capability.
```

## Interactive Epic Collection Workflow

When creating an epic, guide the user through:

### 1. Epic Objective

**Prompt:** "What is the main objective or goal of this epic? What capability will it deliver?"

**Helpful questions:**
- What is the overall goal?
- What high-level capability will be delivered?
- Who will benefit from this epic?

**Example response:**
```
Enable SREs to manage and monitor multiple ROSA HCP clusters from a unified observability dashboard, reducing the operational complexity of multi-cluster environments.
```

### 2. Epic Scope

**Prompt:** "What is included in this epic? What is explicitly out of scope?"

**Helpful questions:**
- What functionality is included?
- What related work is NOT part of this epic?
- Where are the boundaries?

**Example response:**
```
In scope:
- Metrics aggregation from multiple clusters
- Unified dashboard for cluster health
- Cross-cluster alerting
- 30-day historical metrics retention

Out of scope:
- Log aggregation (separate epic)
- Cost reporting (different feature)
- Support for non-HCP clusters (future work)
```

### 3. Epic Acceptance Criteria

**Prompt:** "What are the high-level outcomes that define this epic as complete?"

**Guidance:**
- Focus on capabilities, not implementation
- Should be measurable/demonstrable
- Typically 3-6 criteria

**Example response:**
```
- SREs can view aggregated metrics from all managed clusters in one dashboard
- Alert rules can be defined for cross-cluster conditions (e.g., "any cluster CPU >80%")
- Historical metrics available for 30 days
- Configuration documented and tested
```

### 4. Timeframe

**Prompt:** "What is the target timeframe for this epic? (quarter, release, or estimated sprints)"

**Example responses:**
- "Q1 2025"
- "OpenShift 4.21"
- "Estimate 6 sprints"
- "Must complete by March 2025"

### 5. Parent Feature (Optional)

**Prompt:** "Is this epic part of a larger feature? If yes, provide the feature key."

**If yes:**
- Validate parent exists
- Confirm parent is a Feature (not another Epic)
- Link epic to parent

## Field Validation

Before submitting the epic, validate:

### Required Fields
- ✅ Summary is clear and describes the capability
- ✅ Epic name field is set (same as summary)
- ✅ Description includes objective
- ✅ Epic acceptance criteria present
- ✅ Timeframe specified
- ✅ Component is specified (if required by project)
- ✅ Target version is set (if required by project)

### Epic Quality
- ✅ Scope is broader than a story, narrower than a feature
- ✅ Can fit in a quarter/release timeframe
- ✅ Has measurable acceptance criteria
- ✅ Clearly identifies target users/stakeholders
- ✅ Defines what's in scope and out of scope

### Parent Validation (if specified)
- ✅ Parent issue exists
- ✅ Parent is a Feature (not Epic or Story)
- ✅ Epic contributes to parent's objective

### Security
- ✅ No credentials, API keys, or secrets in any field

## MCP Tool Parameters

### Basic Epic Creation

```python
mcp__plugin_atlassian_atlassian__createJiraIssue(
    cloudId="redhat.atlassian.net",
    projectKey="<PROJECT_KEY>",
    summary="<epic summary>",
    issueTypeName="Epic",
    contentFormat="markdown",
    description="""
<Epic objective and description>

## Epic Acceptance Criteria

- <Outcome 1>
- <Outcome 2>
- <Outcome 3>

## Scope

### In Scope
- <What's included>

### Out of Scope
- <What's not included>

## Timeline

Target: <quarter/release>
    """,
    components="<component name>",  # if required
    additional_fields={
        "customfield_epicname": "<epic name>",  # if required, same as summary
        # Add other project-specific fields
    }
)
```

### With Project-Specific Fields (e.g., CNTRLPLANE)

```python
mcp__plugin_atlassian_atlassian__createJiraIssue(
    cloudId="redhat.atlassian.net",
    projectKey="CNTRLPLANE",
    summary="Multi-cluster metrics aggregation for ROSA HCP",
    issueTypeName="Epic",
    contentFormat="markdown",
    description="""
Enable SREs to manage and monitor multiple ROSA HCP clusters from a unified observability dashboard, reducing operational complexity of multi-cluster environments.

## Epic Acceptance Criteria

- SREs can view aggregated metrics from all managed clusters in one dashboard
- Alert rules can be defined for cross-cluster conditions (e.g., "any cluster CPU >80%")
- Historical metrics retained for 30 days across all clusters
- Multi-cluster setup documented and tested with production workloads
- Performance acceptable with 100+ clusters

## Scope

### In Scope
- Metrics aggregation across ROSA HCP clusters
- Unified dashboard for cluster health and performance
- Cross-cluster alerting capabilities
- 30-day historical metrics retention
- Configuration via CLI and API

### Out of Scope
- Log aggregation (separate epic CNTRLPLANE-200)
- Cost reporting (different feature)
- Support for standalone OCP clusters (future consideration)
- Integration with external monitoring systems (post-MVP)

## Timeline

- Target: Q1 2025 / OpenShift 4.21
- Estimated: 6 sprints
- Key milestone: MVP dashboard by end of Sprint 3

## Target Users

- SREs managing multiple ROSA HCP clusters
- Platform administrators
- Operations teams

## Dependencies

- Requires centralized metrics storage infrastructure ([CNTRLPLANE-150])
- Depends on cluster registration API ([CNTRLPLANE-175])
    """,
    components="HyperShift / ROSA",
    additional_fields={
        "customfield_10855": "openshift-4.21",  # target version
        "customfield_epicname": "Multi-cluster metrics aggregation for ROSA HCP",  # epic name
        "labels": ["ai-generated-jira", "observability"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### With Parent Feature Link

When linking an epic to a parent feature via `--parent` flag, use the **Parent Link** custom field (NOT Epic Link, NOT standard `parent` field):

```python
mcp__plugin_atlassian_atlassian__createJiraIssue(
    cloudId="redhat.atlassian.net",
    projectKey="CNTRLPLANE",
    summary="Multi-cluster monitoring dashboard",
    issueTypeName="Epic",
    contentFormat="markdown",
    description="<epic content with scope and AC>",
    components="HyperShift",
    additional_fields={
        "customfield_10011": "Multi-cluster monitoring dashboard",  # Epic Name (required)
        "customfield_10018": "CNTRLPLANE-100",  # Parent Link - links to parent FEATURE (STRING!)
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

**IMPORTANT:**
- Epic→Feature uses **Parent Link** (`customfield_10018`) - value is a STRING
- Story→Epic uses **Epic Link** (`customfield_10014`) - value is a STRING
- The standard `parent` field does NOT work for these relationships

**See:** `/jira:create` command documentation for complete parent linking hierarchy and implementation strategy.

## Jira Description Formatting

Use markdown format (set `contentFormat: "markdown"` on create/edit calls):

### Epic Template Format

```
<Epic objective - what capability will be delivered and why it matters>

## Epic Acceptance Criteria

- <High-level outcome 1>
- <High-level outcome 2>
- <High-level outcome 3>

## Scope

### In Scope
- <Functionality included in this epic>
- <Capabilities to be delivered>

### Out of Scope
- <Related work NOT in this epic>
- <Future considerations>

## Timeline

- Target: <quarter or release>
- Estimated: <sprints>
- Key milestones: <major deliverables>

## Target Users

- <User group 1>
- <User group 2>

## Dependencies (optional)

- [PROJ-XXX] - <dependency description>

## Parent Feature (if applicable)

This epic is part of [PROJ-YYY] "<feature name>" and addresses <how this epic contributes>.
```

## Error Handling

### Epic Name Field Missing

**Scenario:** Epic creation fails due to missing epic name field.

**Action:**
1. Check if project requires epic name field
2. If required, set `customfield_epicname` = summary
3. Retry creation

**Note:** Field ID may vary by Jira instance:
- `customfield_epicname` (common)
- `customfield_10011` (numbered field)
- Check project configuration if standard field names don't work

### Epic Too Large

**Scenario:** Epic seems too large (would take >1 quarter).

**Action:**
1. Suggest splitting into multiple epics
2. Identify natural split points
3. Consider if this should be a Feature instead

**Example:**
```
This epic seems quite large (estimated 12+ sprints). Consider:

Option 1: Split into multiple epics
- Epic 1: Core metrics aggregation (sprints 1-6)
- Epic 2: Advanced dashboards and alerting (sprints 7-12)

Option 2: Create as Feature instead
- This might be better as a Feature with multiple child Epics

Which would you prefer?
```

### Epic Too Small

**Scenario:** Epic could be completed in one sprint.

**Action:**
1. Suggest creating as a Story instead
2. Explain epic should be multi-sprint effort

**Example:**
```
This epic seems small enough to be a single Story (completable in one sprint).

Epics should typically:
- Span multiple sprints (2-8 sprints)
- Contain multiple stories
- Deliver a cohesive capability

Would you like to create this as a Story instead? (yes/no)
```

### Parent Not a Feature

**Scenario:** User specifies parent, but it's not a Feature.

**Action:**
1. Check parent issue type
2. If parent is Epic or Story, inform user
3. Suggest correction

**Example:**
```
Parent issue PROJ-100 is an Epic, but epics should typically link to Features (not other Epics).

Options:
1. Link to the parent Feature instead (if PROJ-100 has a parent)
2. Proceed without parent link
3. Create a Feature first, then link this Epic to it

What would you like to do?
```

### Missing Acceptance Criteria

**Scenario:** User doesn't provide epic acceptance criteria.

**Action:**
1. Explain importance of epic AC
2. Ask probing questions
3. Help construct AC

**Example:**
```
Epic acceptance criteria help define when this epic is complete. Let's add some.

What are the key outcomes that must be achieved?
- What capabilities will exist when this epic is done?
- How will you demonstrate the epic is complete?
- What must work end-to-end?

Example: "Administrators can view aggregated metrics from all clusters"
```

### Security Validation Failure

**Scenario:** Sensitive data detected in epic content.

**Action:**
1. STOP submission
2. Inform user what type of data was detected
3. Ask for redaction

### MCP Tool Error

**Scenario:** MCP tool returns an error when creating the epic.

**Action:**
1. Parse error message
2. Provide user-friendly explanation
3. Suggest corrective action

**Common errors:**
- **"Field 'epic name' is required"** → Set epic name = summary
- **"Invalid parent"** → Verify parent is Feature type
- **"Issue type 'Epic' not available"** → Check if project supports Epics

## Examples

### Example 1: Epic with Parent Feature

**Input:**
```bash
/jira:create epic CNTRLPLANE "Multi-cluster metrics aggregation" --parent CNTRLPLANE-100
```

**Interactive prompts:**
```
What is the main objective of this epic?
> Enable SREs to monitor multiple ROSA HCP clusters from one dashboard

What is included in scope?
> Metrics aggregation, unified dashboard, cross-cluster alerting, 30-day retention

What is out of scope?
> Log aggregation, cost reporting, non-HCP cluster support

Epic acceptance criteria?
> - View aggregated metrics from all clusters
> - Configure cross-cluster alerts
> - 30-day historical retention
> - Complete documentation

Timeframe?
> Q1 2025, estimate 6 sprints
```

**Implementation:**
1. Pre-validate that CNTRLPLANE-100 exists and is a Feature
2. Create epic with Parent Link field:
   ```python
   mcp__plugin_atlassian_atlassian__createJiraIssue(
       cloudId="redhat.atlassian.net",
       ...
       additional_fields={
           "customfield_10011": "Multi-cluster metrics aggregation",  # Epic Name
           "customfield_10018": "CNTRLPLANE-100",  # Parent Link (STRING, not object!)
           "labels": ["ai-generated-jira"],
           "security": {"name": "Red Hat Employee"}
       }
   )
   ```
3. If creation fails, use fallback: create without parent, then update to add parent link

**Result:**
- Epic created with complete description
- Linked to parent feature CNTRLPLANE-100 via Parent Link field (`customfield_10018`)
- All CNTRLPLANE conventions applied

### Example 2: Epic with Auto-Detection

**Input:**
```bash
/jira:create epic CNTRLPLANE "Advanced node pool autoscaling for ARO HCP"
```

**Auto-applied (via cntrlplane skill):**
- Component: HyperShift / ARO (detected from "ARO HCP")
- Target Version: openshift-4.21
- Epic Name: Same as summary
- Labels: ai-generated-jira
- Security: Red Hat Employee

**Interactive prompts:**
- Epic objective and scope
- Acceptance criteria
- Timeframe

**Result:**
- Full epic with ARO component

### Example 3: Standalone Epic (No Parent)

**Input:**
```bash
/jira:create epic MYPROJECT "Improve test coverage for API endpoints"
```

**Result:**
- Epic created without parent
- Standard epic fields applied
- Ready for stories to be linked

## Best Practices Summary

1. **Clear objective:** State what capability will be delivered
2. **Define scope:** Explicitly state what's in and out of scope
3. **Epic AC:** High-level outcomes that define "done"
4. **Right size:** 2-8 sprints, fits in a quarter
5. **Timebox:** Specify target quarter/release
6. **Link to feature:** If part of larger initiative
7. **Target users:** Identify who benefits
8. **Epic name field:** Always set (same as summary)

## Anti-Patterns to Avoid

❌ **Epic is actually a story**
```
"As a user, I want to view a dashboard"
```
✅ Too small, create as Story instead

❌ **Epic is actually a feature**
```
"Complete observability platform redesign" (12 months, 50+ stories)
```
✅ Too large, create as Feature with child Epics

❌ **Vague acceptance criteria**
```
- Epic is done when everything works
```
✅ Be specific: "SREs can view metrics from 100+ clusters with <1s load time"

❌ **Implementation details in AC**
```
- Backend uses PostgreSQL for metrics storage
- API implements gRPC endpoints
```
✅ Focus on outcomes, not implementation

❌ **No scope definition**
```
Description: "Improve monitoring"
```
✅ Define what's included and what's not

## Workflow Summary

1. ✅ Parse command arguments (project, summary, flags)
2. 🔍 Auto-detect component from summary keywords
3. ⚙️ Apply project-specific defaults
4. 💬 Interactively collect epic objective and scope
5. 💬 Interactively collect epic acceptance criteria
6. 💬 Collect timeframe and parent link (if applicable)
7. 🔒 Scan for sensitive data
8. ✅ Validate epic size and quality
9. ✅ Set epic name field = summary
10. 📝 Format description with markdown
11. ✅ Create epic via MCP tool
12. 📤 Return issue key and URL

## See Also

- `/jira:create` - Main command that invokes this skill (includes Issue Hierarchy and Parent Linking documentation)
- `create-feature` skill - For creating parent features
- `create-story` skill - For stories within epics (uses Epic Link field, NOT parent field)
- `cntrlplane` skill - CNTRLPLANE specific conventions
- Agile epic management best practices
