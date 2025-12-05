---
name: Create Jira Story
description: Implementation guide for creating well-formed Jira user stories with acceptance criteria
---

# Create Jira Story

This skill provides implementation guidance for creating well-structured Jira user stories following agile best practices, including proper user story format and comprehensive acceptance criteria.

## When to Use This Skill

This skill is automatically invoked by the `/jira:create story` command to guide the story creation process.

## Prerequisites

- MCP Jira server configured and accessible
- User has permissions to create issues in the target project
- Understanding of the user story and acceptance criteria to be created

## ⚠️ Summary vs Description: CRITICAL DISTINCTION

**This is the #1 mistake when creating stories. The summary field and description field serve different purposes:**

### Summary Field (Issue Title)
- **SHORT, concise title** (5-10 words maximum)
- Action-oriented, describes WHAT will be done
- **Does NOT contain the full "As a... I want... So that..." format**
- Think of it as a newspaper headline

**Good summary examples:**
- ✅ "Enable ImageTagMirrorSet configuration in HostedCluster CRs"
- ✅ "Add automatic node pool scaling for ROSA HCP"
- ✅ "Implement webhook validation for HostedCluster resources"

**Bad summary examples:**
- ❌ "As a cluster admin, I want to configure ImageTagMirrorSet in HostedCluster CRs so that I can enable tag-based image proxying" (Full user story - belongs in description!)
- ❌ "As a developer, I want to view metrics so that I can debug issues" (User story format - belongs in description!)

### Description Field (Issue Body)
- Contains the **FULL user story format**: "As a... I want... So that..."
- Includes **acceptance criteria**
- Includes **additional context**
- Can be lengthy and detailed

**Correct usage:**
```
Summary: "Enable ImageTagMirrorSet configuration in HostedCluster CRs"

Description:
  As a cluster admin, I want to configure ImageTagMirrorSet in HostedCluster CRs,
  so that I can enable tag-based image proxying for my workloads.

  Acceptance Criteria:
  - Test that ImageTagMirrorSet can be specified...
```

### When Collecting Story Information
1. First collect the full user story (As a... I want... So that...)
2. Then extract/generate a concise summary title from that story
3. Present both to user for confirmation
4. Summary goes in `summary` parameter, full story goes in `description`

## User Story Best Practices

### What is a User Story?

A user story:
- Describes product functionality from a customer's perspective
- Is a collaboration tool - a reminder to have a conversation
- Shifts focus from writing documentation to talking with stakeholders
- Describes concrete business scenarios in shared language
- Is the right size for planning - level of detail based on implementation horizon

### The 3 Cs of User Stories

Every user story should have three components:

1. **Card** - The story itself (As a... I want... So that...)
2. **Conversation** - Discussion between team and stakeholders about implementation
3. **Confirmation** - Acceptance criteria that define "done"

## User Story Template

### Standard Format

```
As a <User/Who>, I want to <Action/What>, so that <Purpose/Why>.
```

**Components:**

- **Who (User/Role):** The person, device, or system that will benefit from or use the output
  - Examples: "cluster admin", "developer", "end user", "monitoring system", "CI pipeline"

- **What (Action):** What they can do with the system
  - Examples: "configure automatic scaling", "view cluster metrics", "deploy applications"

- **Why (Purpose):** Why they want to do the activity, the value they gain
  - Examples: "to handle traffic spikes", "to identify performance issues", "to reduce deployment time"

### Good Examples

```
As a cluster admin, I want to configure automatic node pool scaling based on CPU utilization, so that I can handle traffic spikes without manual intervention.
```

```
As a developer, I want to view real-time cluster metrics in the web console, so that I can quickly identify performance issues before they impact users.
```

```
As an SRE, I want to set up alerting rules for control plane health, so that I can be notified immediately when issues occur.
```

### Bad Examples (and why)

❌ "Add scaling feature"
- **Why bad:** No user, no value statement, too vague

❌ "As a user, I want better performance"
- **Why bad:** Not actionable, no specific action, unclear benefit

❌ "Implement autoscaling API"
- **Why bad:** Technical task, not user-facing value

✅ **Convert to:** "As a cluster admin, I want to configure autoscaling policies via the API, so that I can automate cluster capacity management"

## Acceptance Criteria

Acceptance criteria:
- Express conditions that need to be satisfied for the customer
- Provide context and details for the team
- Help the team know when they are done
- Provide testing point of view
- Are written by Product Owner or dev team members
- Are refined during backlog grooming and iteration planning

### Formats for Acceptance Criteria

Choose the format that best fits the story:

#### Format 1: Test-Based
```
- Test that <criteria>
```

**Example:**
```
- Test that node pools scale up when CPU exceeds 80%
- Test that node pools scale down when CPU drops below 30%
- Test that scaling respects configured min/max node limits
```

#### Format 2: Demonstration-Based
```
- Demonstrate that <this happens>
```

**Example:**
```
- Demonstrate that scaling policies can be configured via CLI
- Demonstrate that scaling events appear in the audit log
- Demonstrate that users receive notifications when scaling occurs
```

#### Format 3: Verification-Based
```
- Verify that when <a role> does <some action> they get <this result>
```

**Example:**
```
- Verify that when a cluster admin sets max nodes to 10, the node pool never exceeds 10 nodes
- Verify that when scaling is disabled, node count remains constant regardless of load
```

#### Format 4: Given-When-Then (BDD)
```
- Given <a context> when <this event occurs> then <this happens>
```

**Example:**
```
- Given CPU utilization is at 85%, when the scaling policy is active, then a new node is provisioned within 2 minutes
- Given the node pool is at maximum capacity, when scaling is triggered, then an alert is raised and no nodes are added
```

### How Much Acceptance Criteria is Enough?

You have enough AC when:
- ✅ You have enough to size/estimate the story
- ✅ The testing approach is clear but not convoluted
- ✅ You've made 2-3 revisions of the criteria
- ✅ The story is independently testable

**If you need more AC:**
- Consider splitting the story into multiple smaller stories
- Each story should be completable in one sprint

**If AC is too detailed:**
- Move implementation details to subtasks or technical design docs
- Keep AC focused on user-observable behavior

## Interactive Story Collection Workflow

When creating a story, guide the user through the process:

### 1. Collect User Story Statement

**Prompt:** "Let's create the user story. I can help you format it properly."

**Ask three questions:**

1. **Who benefits?**
   ```
   Who is the user or role that will benefit from this feature?
   Examples: cluster admin, developer, SRE, end user, system administrator
   ```

2. **What action?**
   ```
   What do they want to be able to do?
   Examples: configure autoscaling, view metrics, set up alerts
   ```

3. **What value/why?**
   ```
   Why do they want this? What value does it provide?
   Examples: to handle traffic spikes, to improve visibility, to reduce downtime
   ```

**Construct the story:**
```
As a <answer1>, I want to <answer2>, so that <answer3>.
```

**Present to user and ask for confirmation:**
```
Here's the user story:

As a cluster admin, I want to configure automatic node pool scaling, so that I can handle traffic spikes without manual intervention.

Does this look correct? (yes/no/modify)
```

### 2. Collect Acceptance Criteria

**Prompt:** "Now let's define the acceptance criteria. These help the team know when the story is complete."

**Approach 1: Guided Questions**

Ask probing questions:
```
1. What are the key behaviors that must work?
2. What are the edge cases or boundaries?
3. How will this be tested?
4. What shouldn't happen?
```

**Approach 2: Template Assistance**

Offer format templates:
```
Which format would you like to use for acceptance criteria?
1. Test that... (test-based)
2. Verify that when... they get... (verification-based)
3. Given... when... then... (BDD)
4. I'll write them in my own format
```

**Approach 3: Free-Form**

```
Please provide the acceptance criteria (one per line, or I can help you structure them):
```

**Validate AC:**
- At least 2-3 criteria provided
- Criteria are specific and testable
- Criteria cover happy path and edge cases
- Criteria are user-observable (not implementation details)

### 3. Collect Additional Context (Optional)

**Prompt:** "Any additional context for the team? (Optional)"

**Helpful additions:**
- Background: Why is this needed now?
- Dependencies: What must exist before this can be done?
- Constraints: Any technical or business constraints?
- Out of scope: What is explicitly not included?
- References: Links to designs, docs, related issues

**Example:**
```
Additional Context:
- This builds on the existing monitoring infrastructure introduced in PROJ-100
- Must integrate with Prometheus metrics
- Out of scope: Custom metrics (will be separate story)
- Design doc: https://docs.example.com/autoscaling-design
```

## Story Sizing and Splitting

### Right-Sized Stories

A well-sized story:
- Can be completed in one sprint (typically 1-2 weeks)
- Can be demonstrated as working software
- Delivers incremental value
- Has clear acceptance criteria

### When to Split Stories

Split a story if:
- It would take more than one sprint
- It has too many acceptance criteria (>7-8)
- It contains multiple distinct features
- It has hard dependencies that could be separate
- Testing becomes too complex

### Splitting Techniques

**By workflow steps:**
```
Original: As a user, I want to manage my account settings
Split:
- As a user, I want to view my account settings
- As a user, I want to update my account settings
- As a user, I want to delete my account
```

**By acceptance criteria:**
```
Original: Complex story with 10 AC
Split:
- Story 1: AC 1-4 (core functionality)
- Story 2: AC 5-7 (edge cases)
- Story 3: AC 8-10 (advanced features)
```

**By platform/component:**
```
Original: Add feature to all platforms
Split:
- Add feature to web interface
- Add feature to CLI
- Add feature to API
```

## Field Validation

Before submitting the story, validate:

### Required Fields
- ✅ Summary is concise title (5-10 words), NOT full user story (see "Summary vs Description" section above)
- ✅ Description contains full user story in "As a... I want... So that..." format
- ✅ Acceptance criteria are present (at least 2)
- ✅ Component is specified (if required by project)
- ✅ Target version is set (if required by project)

### Story Quality
- ✅ Story describes user-facing value (not implementation)
- ✅ Acceptance criteria are testable
- ✅ Acceptance criteria are specific (not vague)
- ✅ Story is sized appropriately (can fit in one sprint)

### Security
- ✅ No credentials, API keys, or secrets in any field
- ✅ No sensitive customer data in examples

## MCP Tool Parameters

### Basic Story Creation

```python
mcp__atlassian__jira_create_issue(
    project_key="<PROJECT_KEY>",
    summary="<concise title>",  # 5-10 words, NOT full user story
    issue_type="Story",
    description="""
As a <user>, I want to <action>, so that <value>.

h2. Acceptance Criteria

* Test that <criteria 1>
* Test that <criteria 2>
* Verify that <criteria 3>

h2. Additional Context

<context if provided>
    """,
    components="<component name>",  # if required
    additional_fields={
        # Add project-specific fields
    }
)
```

### With Project-Specific Fields (e.g., CNTRLPLANE)

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="Enable automatic node pool scaling for ROSA HCP",
    issue_type="Story",
    description="""
As a cluster admin, I want to configure automatic node pool scaling based on CPU utilization, so that I can handle traffic spikes without manual intervention.

h2. Acceptance Criteria

* Test that node pools scale up when average CPU exceeds 80% for 5 minutes
* Test that node pools scale down when average CPU drops below 30% for 10 minutes
* Test that scaling respects configured min/max node limits
* Verify that when scaling is disabled, node count remains constant regardless of load
* Verify that scaling events are logged to the cluster audit trail
* Demonstrate that scaling policies can be configured via rosa CLI

h2. Additional Context

This builds on the existing monitoring infrastructure. Must integrate with Prometheus metrics for CPU utilization data.

Out of scope: Custom metrics-based scaling (will be separate story CNTRLPLANE-457)
    """,
    components="HyperShift / ROSA",
    additional_fields={
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
        # Note: Target version omitted (optional in CNTRLPLANE)
    }
)
```

### With Parent Epic Link

When linking a story to a parent epic via `--parent` flag, use the Epic Link custom field:

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="Add metrics endpoint for cluster health",
    issue_type="Story",
    description="<story description with user story format and AC>",
    components="HyperShift / ROSA",
    additional_fields={
        "customfield_12311140": "CNTRLPLANE-456",  # Epic Link - parent epic key as STRING
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

**Note:** For epic linking, parent field handling, and other project-specific requirements, refer to the appropriate project-specific skill (e.g., CNTRLPLANE, OCPBUGS).

## Jira Description Formatting

Use Jira's native formatting (Wiki markup):

### Story Template Format

```
As a <user>, I want to <action>, so that <value>.

h2. Acceptance Criteria

* Test that <criteria 1>
* Verify that <criteria 2>
* Given <context> when <event> then <outcome>

h2. Additional Context

<optional context>

h3. Dependencies
* [PROJ-123] - Parent epic or related story

h3. Out of Scope
* Feature X (will be separate story)
* Platform Y support (future release)
```

### Formatting Elements

**Headings:**
```
h1. Main Heading
h2. Subheading
h3. Sub-subheading
```

**Lists:**
```
* Bullet item 1
* Bullet item 2
** Nested bullet

# Numbered item 1
# Numbered item 2
```

**Text Formatting:**
```
*bold text*
_italic text_
{{monospace}}
```

**Code Blocks:**
```
{code}
rosa create cluster --autoscaling-min 3 --autoscaling-max 10
{code}
```

**Links:**
```
[Design doc|https://docs.example.com/design]
[PROJ-123]  // Auto-links to Jira issue
```

## Error Handling

### Invalid Story Format

**Scenario:** User provides a story that doesn't follow the template.

**Action:**
1. Identify the issue (missing "Who", "What", or "Why")
2. Explain the user story format
3. Ask questions to extract missing components
4. Reconstruct the story properly

**Example:**
```
The story "Add autoscaling" doesn't follow the user story format.

Let me help you structure it:
- Who will use this feature? (e.g., cluster admin, developer)
- What do they want to do? (e.g., configure autoscaling)
- Why do they want it? (e.g., to handle traffic spikes)
```

### Missing Acceptance Criteria

**Scenario:** User doesn't provide acceptance criteria.

**Action:**
1. Explain importance of AC
2. Offer to help create them
3. Ask probing questions about expected behavior
4. Suggest format that fits the story

**Example:**
```
Acceptance criteria help define when this story is complete. Let's add some.

What are the key behaviors that must work for this story?
For example:
- What actions should users be able to perform?
- What should happen in edge cases?
- How will you know the feature works correctly?
```

### Story Too Large

**Scenario:** Story has too many acceptance criteria or sounds too complex.

**Action:**
1. Suggest the story might be too large for one sprint
2. Identify potential split points
3. Offer to create multiple stories
4. Create parent epic if multiple related stories

**Example:**
```
This story has 12 acceptance criteria, which suggests it might be too large for one sprint.

I can help split this into smaller stories:
1. Core functionality (AC 1-4)
2. Advanced features (AC 5-8)
3. Edge cases and validation (AC 9-12)

Would you like me to create these as separate stories under an epic?
```

### Vague Acceptance Criteria

**Scenario:** AC is too vague or not testable.

**Action:**
1. Identify vague criteria
2. Ask for specifics
3. Suggest more concrete phrasing

**Example:**
```
This acceptance criteria is a bit vague: "Test that it works well"

Can you be more specific? For example:
- What does "works well" mean? (fast response time? handles errors?)
- How would you test this? (what specific behavior would you verify?)

Suggested revision: "Verify that API response time is under 100ms for 95% of requests"
```

### Security Validation Failure

**Scenario:** Sensitive data detected in story content.

**Action:**
1. STOP submission
2. Inform user what type of data was detected
3. Ask for redaction or placeholder values

**Example:**
```
I detected what appears to be API credentials in the acceptance criteria.
Please use placeholder values like "YOUR_API_KEY" instead of real credentials.
```

### MCP Tool Error

**Scenario:** MCP tool returns an error when creating the story.

**Action:**
1. Parse error message
2. Provide user-friendly explanation
3. Suggest corrective action
4. Offer to retry

**Common errors:**
- **"Field 'parent' does not exist"** → Remove parent link or verify epic exists
- **"Invalid issue type"** → Verify project supports "Story" issue type
- **"Component not found"** → List available components, ask user to select

## Examples

### Example 1: Interactive Story Creation

**Input:**
```bash
/jira:create story MYPROJECT "Add user dashboard"
```

**Conversation:**
```
Let's create the user story. I'll ask a few questions:

Who is the user or role that will benefit from this feature?
> End users

What do they want to be able to do?
> View their activity dashboard with recent actions and notifications

Why do they want this? What value does it provide?
> To quickly see what's happened in their account without navigating multiple pages

Great! Here's the user story:

As an end user, I want to view my activity dashboard with recent actions and notifications, so that I can quickly see what's happened in my account without navigating multiple pages.

Does this look correct?
> Yes

Now let's define acceptance criteria. What are the key behaviors that must work?
> 1. Dashboard shows last 10 actions
> 2. Dashboard shows unread notifications
> 3. Dashboard updates in real-time
> 4. Users can filter by action type

Excellent. I'll format these as test-based criteria:

* Test that dashboard displays the last 10 user actions
* Test that dashboard displays all unread notifications
* Test that dashboard updates in real-time when new actions occur
* Verify that users can filter actions by type (login, purchase, settings change)

Any additional context?
> This is part of the Q1 user experience improvements

Perfect! Creating the story now...
```

**Result:**
```
Created: MYPROJECT-123
Title: Add user dashboard
URL: https://jira.example.com/browse/MYPROJECT-123
```

### Example 2: Story with Auto-Detection (CNTRLPLANE)

**Input:**
```bash
/jira:create story CNTRLPLANE "Enable pod disruption budgets for ROSA HCP control plane"
```

**Auto-applied (via cntrlplane skill):**
- Component: HyperShift / ROSA (detected from "ROSA HCP")
- Target Version: openshift-4.21
- Labels: ai-generated-jira
- Security: Red Hat Employee

**Interactive prompts:**
- User story format (Who/What/Why)
- Acceptance criteria

**Result:**
- Full story created with CNTRLPLANE conventions

### Example 3: Story with Parent Epic

**Input:**
```bash
/jira:create story CNTRLPLANE "Add scaling metrics to observability dashboard" --parent CNTRLPLANE-100
```

**Implementation:**
1. Pre-validate that CNTRLPLANE-100 exists and is an Epic
2. Create story with Epic Link field:
   ```python
   additional_fields={
       "customfield_12311140": "CNTRLPLANE-100",  # Epic Link (NOT parent field!)
       "labels": ["ai-generated-jira"],
       "security": {"name": "Red Hat Employee"}
   }
   ```
3. If creation fails, use fallback: create without link, then update to add link

**Result:**
- Story created
- Linked to epic CNTRLPLANE-100 via Epic Link field
- All standard fields applied

**See:** `/jira:create` command documentation for complete parent linking implementation strategy

## Best Practices Summary

1. **User-focused:** Always describe value from user perspective
2. **Specific actions:** Clear what the user can do
3. **Clear value:** Explicit why (benefit to user)
4. **Testable AC:** Specific, observable criteria
5. **Right-sized:** Can complete in one sprint
6. **Conversational:** Story prompts discussion, not full spec
7. **Independent:** Story can be implemented standalone
8. **Valuable:** Delivers user value when complete

## Anti-Patterns to Avoid

❌ **Technical tasks disguised as stories**
```
As a developer, I want to refactor the database layer
```
✅ Use a Task instead, or reframe with user value

❌ **Too many stories in one**
```
As a user, I want to create, edit, delete, and share documents
```
✅ Split into 4 separate stories

❌ **Vague acceptance criteria**
```
- Test that it works correctly
- Verify good performance
```
✅ Be specific: "Response time under 200ms", "Handles 1000 concurrent users"

❌ **Implementation details in AC**
```
- Test that the function uses Redis cache
- Verify that the API calls the UserService.get() method
```
✅ Focus on user-observable behavior, not implementation

## Workflow Summary

1. ✅ Parse command arguments (project, summary, flags)
2. 🔍 Auto-detect component from summary keywords
3. ⚙️ Apply project-specific defaults
4. 💬 Interactively collect user story (Who/What/Why)
5. 💬 Interactively collect acceptance criteria
6. 💬 Optionally collect additional context
7. 🔒 Scan for sensitive data
8. ✅ Validate story quality and completeness
9. 📝 Format description with Jira markup
10. ✅ Create story via MCP tool
11. 📤 Return issue key and URL

## See Also

- `/jira:create` - Main command that invokes this skill (includes Issue Hierarchy and Parent Linking documentation)
- `cntrlplane` skill - CNTRLPLANE specific conventions
- `create-epic` skill - For creating parent epics
- Agile Alliance: User Story resources
- Mike Cohn: User Stories Applied
