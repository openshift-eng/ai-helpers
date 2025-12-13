# Story Guide

Guide on Jira User Stories: what they are, how to write them, and best practices.

## What is a User Story?

A user story:
- Describes product functionality from a customer's perspective
- Is a collaboration tool - a reminder to have a conversation
- Shifts focus from writing documentation to talking with stakeholders
- Describes concrete business scenarios in shared language
- Is the right size for planning (completable in one sprint)

### Story vs Task vs Epic

| Type | Purpose | Duration | Example |
|------|---------|----------|---------|
| Epic | Capability requiring multiple stories | 1 quarter | "Multi-cluster metrics aggregation" |
| Story | User-facing functionality | 1 sprint | "As an SRE, I want to view metrics from multiple clusters" |
| Task | Technical work, no direct user value | < 1 sprint | "Refactor metrics collection logic" |

**When to use a Story:**
- Delivers user-observable value
- Can be completed in one sprint
- Has testable acceptance criteria
- Focuses on "who" benefits and "why"

**When to use a Task instead:**
- Technical work with no direct user value
- Refactoring, infrastructure, technical debt
- No specific "user" who benefits

## ⚠️ Summary vs Description: CRITICAL DISTINCTION

**This is the #1 mistake when creating stories.**

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
- ❌ "As a cluster admin, I want to configure ImageTagMirrorSet in HostedCluster CRs so that I can enable tag-based image proxying"
  *Why bad:* Full user story belongs in description, not summary
- ❌ "As a developer, I want to view metrics so that I can debug issues"
  *Why bad:* User story format belongs in description

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

  **Acceptance Criteria**
  - Test that ImageTagMirrorSet can be specified in HostedCluster spec
  - Verify that configuration is applied to guest cluster
  - Test that image pulls use the configured mirrors
```

## User Story Template

### Standard Format

```
As a <User/Who>, I want to <Action/What>, so that <Purpose/Why>.
```

**Components:**

**Who (User/Role):** The person, device, or system that will benefit
- Examples: "cluster admin", "developer", "end user", "monitoring system", "CI pipeline"

**What (Action):** What they can do with the system
- Examples: "configure automatic scaling", "view cluster metrics", "deploy applications"

**Why (Purpose):** Why they want it, the value they gain
- Examples: "to handle traffic spikes", "to identify performance issues", "to reduce deployment time"

### Good Examples

```
As a cluster admin, I want to configure automatic node pool scaling based on CPU utilization,
so that I can handle traffic spikes without manual intervention.
```

```
As a developer, I want to view real-time cluster metrics in the web console,
so that I can quickly identify performance issues before they impact users.
```

```
As an SRE, I want to set up alerting rules for control plane health,
so that I can be notified immediately when issues occur.
```

### Bad Examples (and why)

❌ "Add scaling feature"
- **Why bad:** No user, no value statement, too vague
- **Fix:** "As a cluster admin, I want to enable autoscaling, so that my cluster handles load automatically"

❌ "As a user, I want better performance"
- **Why bad:** Not actionable, no specific action, unclear benefit
- **Fix:** "As a developer, I want API responses under 200ms, so that my application feels responsive"

❌ "Implement autoscaling API"
- **Why bad:** Technical task, not user-facing value
- **Fix:** "As a cluster admin, I want to configure autoscaling policies via API, so that I can automate capacity management"

## The 3 Cs of User Stories

Every user story should have three components:

### 1. Card
The story itself in "As a... I want... So that..." format

### 2. Conversation
Discussion between team and stakeholders about implementation
- Clarifies requirements
- Explores edge cases
- Aligns on approach

### 3. Confirmation
Acceptance criteria that define "done"
- How do we know it works?
- What must be tested?
- What are the boundaries?

## Acceptance Criteria

Acceptance criteria:
- Express conditions that need to be satisfied
- Provide context and details for the team
- Help the team know when they are done
- Provide testing point of view
- Are refined during backlog grooming

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

**When to use:** Clear pass/fail conditions, functional requirements

---

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

**When to use:** User-visible features, UI interactions

---

#### Format 3: Verification-Based
```
- Verify that when <a role> does <some action> they get <this result>
```

**Example:**
```
- Verify that when a cluster admin sets max nodes to 10, the node pool never exceeds 10 nodes
- Verify that when scaling is disabled, node count remains constant regardless of load
```

**When to use:** Role-specific behaviors, permission checks

---

#### Format 4: Given-When-Then (BDD)
```
- Given <a context> when <this event occurs> then <this happens>
```

**Example:**
```
- Given CPU utilization is at 85%, when the scaling policy is active, then a new node is provisioned within 2 minutes
- Given the node pool is at maximum capacity, when scaling is triggered, then an alert is raised
```

**When to use:** Complex scenarios, state-dependent behavior

### How Much Acceptance Criteria is Enough?

You have enough AC when:
- ✅ You have enough to size/estimate the story
- ✅ The testing approach is clear
- ✅ Edge cases are covered
- ✅ Success conditions are specific

You have too much AC when:
- ❌ AC describes implementation details
- ❌ AC is longer than the story itself
- ❌ Team says "we could write the code in less time"

**Good balance:**
- 2-5 acceptance criteria per story (typically)
- Each criterion is testable and specific
- Covers happy path and key edge cases
- Focuses on behavior, not implementation

## Best Practices

### 1. User-Focused
Always describe value from user perspective, not technical implementation.

**Good:** "As an SRE, I want to receive alerts when API latency exceeds 500ms"
**Bad:** "Implement Prometheus alerting rules for API latency metrics"

### 2. Specific Actions
Clear what the user can do.

**Good:** "Configure autoscaling policies via the web console"
**Bad:** "Enable autoscaling"

### 3. Clear Value
Explicit why (benefit to user).

**Good:** "...so that I can handle traffic spikes without manual intervention"
**Bad:** "...so that it works better"

### 4. Testable AC
Specific, observable criteria.

**Good:** "Test that the dashboard loads in under 2 seconds"
**Bad:** "Test that the dashboard is fast"

### 5. Right-Sized
Can complete in one sprint.

**Too big:** Story requires 3 sprints → Split into 3 stories or create as Epic
**Too small:** Story takes 1 hour → Combine with related stories or just do it

### 6. Conversational
Story prompts discussion, not a full specification.

Stories should leave room for conversation. Don't try to capture every detail upfront.

### 7. Independent
Story can be implemented standalone (mostly).

While some dependencies are okay, stories shouldn't form long chains of dependencies.

### 8. Valuable
Delivers user value when complete.

At the end of the sprint, the user should be able to use the new functionality.

## Story Splitting Patterns

When a story is too large, split it using these patterns:

### Pattern 1: By Workflow Steps
**Original:** "As a user, I want to manage my account"

**Split:**
- Story 1: "Create account"
- Story 2: "Edit account details"
- Story 3: "Delete account"

### Pattern 2: By User Roles
**Original:** "As a user, I want to view dashboards"

**Split:**
- Story 1: "As an admin, I want to view all team dashboards"
- Story 2: "As a member, I want to view my personal dashboard"

### Pattern 3: By Business Rules
**Original:** "As a user, I want to apply discounts"

**Split:**
- Story 1: "Apply percentage-based discounts"
- Story 2: "Apply fixed-amount discounts"
- Story 3: "Apply promotional code discounts"

### Pattern 4: By Data Types
**Original:** "As a user, I want to import data"

**Split:**
- Story 1: "Import CSV files"
- Story 2: "Import JSON files"
- Story 3: "Import XML files"

### Pattern 5: By Operations (CRUD)
**Original:** "As a user, I want to manage clusters"

**Split:**
- Story 1: "Create clusters"
- Story 2: "View cluster details"
- Story 3: "Update cluster configuration"
- Story 4: "Delete clusters"

### Pattern 6: By Happy Path vs Edge Cases
**Original:** Large story with many edge cases

**Split:**
- Story 1: Happy path only
- Story 2: Error handling and edge cases

## Anti-Patterns to Avoid

### ❌ Technical Tasks Disguised as Stories

**Example:**
```
As a developer, I want to refactor the database layer
```

**Why bad:** No user value, technical implementation

**Fix:** Use a Task, or reframe with user value:
```
As a developer, I want faster database queries, so that users experience responsive UI
```

---

### ❌ Too Many Stories in One

**Example:**
```
As a user, I want to create, edit, delete, and share documents
```

**Why bad:** Multiple features, can't complete in one sprint

**Fix:** Split into 4 separate stories

---

### ❌ Vague Acceptance Criteria

**Example:**
```
- Test that it works correctly
- Verify good performance
```

**Why bad:** Not specific, not testable

**Fix:** Be specific:
```
- Test that API response time is under 200ms for 95th percentile
- Verify system handles 1000 concurrent users without errors
```

---

### ❌ Implementation Details in AC

**Example:**
```
- Test that the function uses Redis cache
- Verify that the API calls UserService.get() method
```

**Why bad:** Specifies implementation, not behavior

**Fix:** Focus on user-observable behavior:
```
- Test that user profile loads in under 500ms
- Verify that profile data is consistent across sessions
```

---

### ❌ Story is Actually an Epic

**Example:**
```
As an administrator, I want a complete monitoring solution
```

**Why bad:** Too large, needs multiple sprints

**Fix:** Create as Epic with child stories

---

### ❌ No "So That" (No Value)

**Example:**
```
As a user, I want to see a settings page
```

**Why bad:** No clear benefit or value statement

**Fix:** Add the value:
```
As a user, I want to access a settings page, so that I can customize my experience
```

## Story Quality Checklist

Before creating a story, verify:

- ✅ Uses "As a... I want... So that..." format
- ✅ Summary is concise (5-10 words), description has full story
- ✅ Identifies specific user/role
- ✅ Describes user-facing action
- ✅ States clear value/benefit
- ✅ Has 2-5 testable acceptance criteria
- ✅ Can complete in one sprint
- ✅ Delivers user value when done
- ✅ Is independent (mostly) from other stories
- ✅ Prompts conversation, not overly detailed

## Examples

### Example 1: Infrastructure Story

**Summary:** "Enable pod disruption budgets for control plane"

**Description:**
```
As an SRE, I want to configure pod disruption budgets for control plane components,
so that cluster updates don't cause service disruptions.

**Acceptance Criteria**

- Test that PDBs are created for kube-apiserver, etcd, and controller-manager
- Verify that upgrades respect PDB constraints
- Test that emergency updates can override PDB when needed
- Verify that PDB violations are logged and alerted
```

---

### Example 2: UI Story

**Summary:** "Add real-time cluster health indicator to dashboard"

**Description:**
```
As a cluster admin, I want to see a real-time health indicator on my dashboard,
so that I can quickly identify if any clusters need attention.

**Acceptance Criteria**

- Demonstrate that dashboard shows health status for all managed clusters
- Test that status updates within 30 seconds of health change
- Verify that clicking a cluster navigates to its detail page
- Test that color coding matches severity (green/yellow/red)
```

---

### Example 3: API Story

**Summary:** "Support filtering clusters by region in List API"

**Description:**
```
As a developer, I want to filter clusters by region when calling the List API,
so that I can reduce data transfer and improve response time.

**Acceptance Criteria**

- Test that GET /clusters?region=us-east-1 returns only us-east-1 clusters
- Verify that multiple regions can be specified: ?region=us-east-1,eu-west-1
- Test that invalid region names return 400 with clear error message
- Verify that filtering doesn't break pagination
```

## Related

- [Epic Guide](epic.md) - Creating epics that contain stories
- [Task Guide](task.md) - When to use tasks instead of stories
- [Template Reference](../../templates/common/story.yaml) - Story template used by `/jira:create story`
