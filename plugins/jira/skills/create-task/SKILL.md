---
name: Create Jira Task
description: Implementation guide for creating Jira tasks for technical and operational work
---

# Create Jira Task

This skill provides implementation guidance for creating Jira tasks, which are used for technical or operational work that doesn't necessarily deliver direct user-facing value.

## When to Use This Skill

This skill is automatically invoked by the `/jira:create task` command to guide the task creation process.

## Prerequisites

- MCP Jira server configured and accessible
- User has permissions to create issues in the target project
- Understanding of the technical work to be performed

## Tasks vs Stories

### When to Use a Task

Use a **Task** when the work is:
- **Technical/operational** - Infrastructure, refactoring, configuration
- **Not user-facing** - No direct end-user functionality
- **Internal improvement** - Code quality, performance, maintenance
- **Enabler work** - Supports future stories but isn't user-visible

**Examples of tasks:**
- "Update scaling documentation"
- "Refactor authentication utility package"
- "Configure CI pipeline for integration tests"
- "Upgrade dependency X to version Y"
- "Investigate performance regression in component Z"

### When to Use a Story Instead

Use a **Story** when the work:
- Delivers user-facing functionality
- Can be expressed as "As a... I want... so that..."
- Has business value to end users
- Is part of a user workflow

**If in doubt:** Ask "Would an end user notice or care about this change?"
- **Yes** → Story
- **No** → Task

## Task Best Practices

### Clear Summary

The summary should:
- Be concise (one sentence)
- Use action verbs (Update, Refactor, Configure, Investigate, Fix)
- Identify what is being changed
- Optionally include "why" if not obvious

**Good examples:**
- "Update autoscaling documentation for 4.21 release"
- "Refactor scaling controller to reduce code duplication"
- "Configure Prometheus alerts for control plane memory usage"
- "Investigate intermittent timeout in etcd health checks"

**Bad examples:**
- "Do some work on docs" (too vague)
- "Technical debt" (not specific)
- "Various improvements" (not actionable)

### Detailed Description

The description should include:

1. **What needs to be done** - Clear statement of the work
2. **Why it's needed** - Context or motivation
3. **Acceptance criteria** (optional but recommended) - How to know it's done
4. **Technical details** (if helpful) - Specific files, commands, approaches

**Example:**
```
Update the autoscaling documentation to reflect changes in the 4.21 release.

Why: The autoscaling API changed in 4.21 with new fields and behavior. Documentation currently reflects 4.20 and will confuse users.

Acceptance Criteria:
- All autoscaling examples updated to use 4.21 API
- New fields documented with descriptions and examples
- Deprecated fields marked as deprecated
- Documentation builds without warnings

Files to update:
- docs/content/how-to/autoscaling.md
- docs/content/reference/api.md
```

## Task Description Template

Use this structure for consistency:

```
<What needs to be done>

h2. Why

<Context, motivation, or reason this is needed>

h2. Acceptance Criteria

* <Criterion 1>
* <Criterion 2>
* <Criterion 3>

h2. Technical Details (optional)

* Files to modify: <list>
* Dependencies: <related issues or work>
* Approach: <suggested implementation approach>
```

## Interactive Task Collection Workflow

When creating a task, collect necessary information:

### 1. Task Description

**Prompt:** "What work needs to be done? Be specific about what you'll change or update."

**Helpful questions:**
- What component or area is being worked on?
- What specific changes will be made?
- What's the end state after this task is complete?

**Example response:**
```
Refactor the scaling controller to extract common validation logic into a shared utility package. Currently, validation code is duplicated across three controller files.
```

### 2. Motivation/Context

**Prompt:** "Why is this task needed? What problem does it solve?"

**Helpful questions:**
- What prompted this work?
- What will improve after this is done?
- Is this addressing a specific issue or enabling future work?

**Example response:**
```
Code duplication makes maintenance difficult. When validation logic changes, we have to update it in three places, which is error-prone. Consolidating into a shared utility will make the code easier to maintain and reduce bugs.
```

### 3. Acceptance Criteria (Optional but Recommended)

**Prompt:** "How will you know this task is complete? (Optional: skip if obvious)"

**For technical tasks, AC might include:**
- Tests passing
- Documentation updated
- Code review completed
- Specific functionality working

**Example response:**
```
- Validation logic extracted to support/validation package
- All three controllers updated to use shared validation
- Existing tests pass
- New unit tests added for validation utility
- Code review approved
```

### 4. Parent Link (Optional)

**Prompt:** "Is this task part of a larger story or epic? (Optional)"

**If yes:**
- Collect parent issue key
- Verify parent exists
- Link task to parent

### 5. Additional Technical Details (Optional)

**Prompt:** "Any technical details to include? (files to change, dependencies, approach)"

**Example response:**
```
Files to modify:
- hypershift/operator/controllers/nodepool/autoscaling.go
- hypershift/operator/controllers/hostedcluster/autoscaling.go
- hypershift/operator/controllers/manifests/autoscaling.go
- hypershift/support/validation/autoscaling.go (new)

Dependencies:
- Must complete after PROJ-100 (validation refactor epic)

Approach:
- Extract common validation functions to support/validation
- Add comprehensive unit tests for new package
- Update controllers to import and use new package
- Remove duplicated code
```

## Field Validation

Before submitting the task, validate:

### Required Fields
- ✅ Summary is clear and specific
- ✅ Description explains what needs to be done
- ✅ Description includes why (motivation)
- ✅ Component is specified (if required by project)
- ✅ Target version is set (if required by project)

### Task Quality
- ✅ Summary uses action verb (Update, Refactor, Configure, etc.)
- ✅ Work is technical/operational (not user-facing functionality)
- ✅ Description is detailed enough for someone else to understand
- ✅ Acceptance criteria present (if work is non-trivial)
- ✅ Task is sized appropriately (can complete in reasonable time)

### Security
- ✅ No credentials, API keys, or secrets in any field
- ✅ No sensitive technical details that shouldn't be public

## MCP Tool Parameters

### Basic Task Creation

```python
mcp__atlassian__jira_create_issue(
    project_key="<PROJECT_KEY>",
    summary="<task summary>",
    issue_type="Task",
    description="""
<What needs to be done>

h2. Why

<Context and motivation>

h2. Acceptance Criteria

* <Criterion 1>
* <Criterion 2>

h2. Technical Details

<Optional technical details>
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
    summary="Update autoscaling documentation for 4.21 release",
    issue_type="Task",
    description="""
Update the autoscaling documentation to reflect API changes in the 4.21 release.

h2. Why

The autoscaling API changed in 4.21 with new fields (maxNodeGracePeriod, scaleDownDelay) and modified behavior. Current documentation reflects 4.20 API and will confuse users upgrading to 4.21.

h2. Acceptance Criteria

* All autoscaling examples updated to use 4.21 API syntax
* New fields (maxNodeGracePeriod, scaleDownDelay) documented with descriptions and examples
* Deprecated fields marked as deprecated with migration guidance
* Documentation builds successfully without warnings or broken links
* Changes reviewed by docs team

h2. Technical Details

Files to update:
* docs/content/how-to/cluster-autoscaling.md
* docs/content/reference/api/nodepool.md
* docs/content/tutorials/autoscaling-rosa.md

Reference: API changes introduced in PR #1234
    """,
    components="HyperShift",
    additional_fields={
        "customfield_12319940": "openshift-4.21",  # target version
        "labels": ["ai-generated-jira", "documentation"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### With Parent Link

```python
mcp__atlassian__jira_create_issue(
    project_key="MYPROJECT",
    summary="Add unit tests for scaling validation",
    issue_type="Task",
    description="<task content>",
    additional_fields={
        "parent": {"key": "MYPROJECT-100"}  # link to story or epic
    }
)
```

## Jira Description Formatting

Use Jira's native formatting (Wiki markup):

### Task Template Format

```
<Brief description of what needs to be done>

h2. Why

<Context, motivation, or problem this solves>

h2. Acceptance Criteria

* <Criterion 1>
* <Criterion 2>
* <Criterion 3>

h2. Technical Details

h3. Files to Modify
* {{path/to/file1.go}}
* {{path/to/file2.go}}

h3. Dependencies
* Must complete after [PROJ-100]
* Requires library X version Y

h3. Approach
<Suggested implementation approach or technical notes>

h2. Additional Context

<Optional: Links to designs, related issues, background>
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

# Numbered item 1
# Numbered item 2
```

**Code/Paths:**
```
{{path/to/file.go}}
{{package.function()}}

{code}
make test
make build
{code}
```

**Links:**
```
[Design doc|https://docs.example.com/design]
[PROJ-123]  // Auto-links to Jira issue
```

## Error Handling

### Task vs Story Confusion

**Scenario:** User tries to create a task for user-facing functionality.

**Action:**
1. Detect user-facing language in summary/description
2. Ask if this should be a story instead
3. Explain the difference
4. Offer to create as story if appropriate

**Example:**
```
This sounds like it might deliver user-facing functionality. The summary mentions "users can configure autoscaling".

Should this be a Story instead of a Task?
- Story: For user-facing features (visible to end users)
- Task: For internal/technical work (not visible to end users)

Would you like me to create this as a Story? (yes/no)
```

### Missing Context

**Scenario:** User provides minimal description without context.

**Action:**
1. Ask for more details
2. Prompt for "why" if missing
3. Suggest adding acceptance criteria if non-trivial

**Example:**
```
The description "Update docs" is a bit brief. Can you provide more detail?

- Which documentation needs updating?
- Why does it need updating? (new features, corrections, clarifications?)
- What specific changes should be made?
```

### Parent Not Found

**Scenario:** User specifies `--parent` but issue doesn't exist.

**Action:**
1. Attempt to fetch parent issue
2. If not found, inform user
3. Offer options: proceed without parent, specify different parent, cancel

**Example:**
```
Parent issue PROJ-999 not found.

Options:
1. Proceed without parent link
2. Specify different parent
3. Cancel task creation

What would you like to do?
```

### Security Validation Failure

**Scenario:** Sensitive data detected in task content.

**Action:**
1. STOP submission
2. Inform user what type of data was detected
3. Ask for redaction

**Example:**
```
I detected what appears to be an API key in the technical details section.
Please use placeholder values like "YOUR_API_KEY" instead of real credentials.
```

### MCP Tool Error

**Scenario:** MCP tool returns an error when creating the task.

**Action:**
1. Parse error message
2. Provide user-friendly explanation
3. Suggest corrective action

**Common errors:**
- **"Field 'component' is required"** → Prompt for component
- **"Invalid parent"** → Verify parent issue exists and is correct type
- **"Permission denied"** → User may lack project permissions

## Examples

### Example 1: Documentation Task

**Input:**
```bash
/jira:create task CNTRLPLANE "Update autoscaling documentation for 4.21 release"
```

**Interactive prompts:**
```
What work needs to be done?
> Update the autoscaling documentation to include new fields added in 4.21

Why is this task needed?
> API changed in 4.21, docs need updating to match

How will you know this is complete?
> All examples work with 4.21, new fields documented, no build warnings

Any technical details?
> Files: docs/content/how-to/autoscaling.md, docs/content/reference/api.md
```

**Result:**
- Task created with complete description
- Target version: 4.21
- Component: HyperShift (or auto-detected)

### Example 2: Refactoring Task

**Input:**
```bash
/jira:create task MYPROJECT "Refactor validation logic to reduce duplication"
```

**Interactive prompts:**
```
What work needs to be done?
> Extract common validation code from three controller files into shared utility

Why is this needed?
> Code duplication makes maintenance difficult and error-prone

Acceptance criteria?
> - Validation extracted to support/validation package
> - All controllers use shared validation
> - Tests pass
> - New unit tests for validation utility

Any technical details?
> Files to modify:
> - controllers/nodepool/autoscaling.go
> - controllers/hostedcluster/autoscaling.go
> - controllers/manifests/autoscaling.go
> New file: support/validation/autoscaling.go
```

**Result:**
- Task with detailed technical plan
- Clear acceptance criteria
- Ready for implementation

### Example 3: Task with Parent

**Input:**
```bash
/jira:create task CNTRLPLANE "Add integration tests for node autoscaling" --parent CNTRLPLANE-100
```

**Auto-applied:**
- Linked to parent story CNTRLPLANE-100
- Inherits component from parent (if applicable)
- CNTRLPLANE conventions applied

**Result:**
- Task created under parent story
- All fields properly set

### Example 4: Investigation Task

**Input:**
```bash
/jira:create task CNTRLPLANE "Investigate intermittent timeouts in etcd health checks"
```

**Description pattern for investigation tasks:**
```
Investigate intermittent timeout errors occurring in etcd health checks on ROSA HCP clusters.

h2. Why

Users report clusters occasionally showing unhealthy status despite normal operation. Logs show intermittent timeout errors from etcd health checks.

h2. Acceptance Criteria

* Root cause identified and documented
* Recommendation provided (fix, workaround, or "no action needed")
* Findings shared with team in investigation summary

h2. Technical Details

Error pattern:
{code}
etcd health check failed: context deadline exceeded (timeout: 2s)
{code}

Frequency: ~5% of health checks
Affected clusters: ROSA HCP in us-east-1
Logs to review: control-plane-operator, etcd-operator

Related issues: OCPBUGS-1234 (similar symptoms)
```

**Result:**
- Investigation task with clear scope
- Defined outcome (root cause + recommendation)
- Context for debugging

## Best Practices Summary

1. **Specific summaries:** Use action verbs, identify what's changing
2. **Explain why:** Always include motivation/context
3. **Add AC:** Even for tasks, AC helps define "done"
4. **Technical details:** Include file paths, commands, approaches when helpful
5. **Right size:** Task should be completable in reasonable time (days, not weeks)
6. **Link to parent:** If task supports a story/epic, link it
7. **Not a story:** If it's user-facing, create a story instead

## Anti-Patterns to Avoid

❌ **Vague summaries**
```
"Update stuff"
"Fix things"
```
✅ Be specific: "Update autoscaling documentation for 4.21 API changes"

❌ **User-facing work as tasks**
```
"Add user dashboard feature"
```
✅ Should be a Story if it delivers user value

❌ **Too large**
```
"Refactor entire codebase"
"Update all documentation"
```
✅ Break into smaller, focused tasks

❌ **No context**
```
Summary: "Update docs"
Description: <empty>
```
✅ Always explain why and what specifically

## Workflow Summary

1. ✅ Parse command arguments (project, summary, flags)
2. 🔍 Auto-detect component from summary keywords
3. ⚙️ Apply project-specific defaults
4. 💬 Interactively collect task description and context
5. 💬 Interactively collect acceptance criteria (optional)
6. 💬 Optionally collect technical details
7. 🔒 Scan for sensitive data
8. ✅ Validate task is appropriate (not a story)
9. 📝 Format description with Jira markup
10. ✅ Create task via MCP tool
11. 📤 Return issue key and URL

## See Also

- `/jira:create` - Main command that invokes this skill
- `create-story` skill - For user-facing functionality
- `cntrlplane` skill - CNTRLPLANE specific conventions
- Agile task management best practices
