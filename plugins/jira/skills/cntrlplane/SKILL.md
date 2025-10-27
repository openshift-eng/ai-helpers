---
name: CNTRLPLANE Jira Conventions
description: Jira conventions for the CNTRLPLANE project used by OpenShift teams
---

# CNTRLPLANE Jira Conventions

This skill provides conventions and requirements for creating Jira issues in the CNTRLPLANE project, which is used by various OpenShift teams for feature development, epics, stories, and tasks.

## When to Use This Skill

Use this skill when creating Jira items in the CNTRLPLANE project:
- **Project: CNTRLPLANE** - Features, Epics, Stories, Tasks for OpenShift teams
- **Issue Types: Story, Epic, Feature, Task**

This skill is automatically invoked by the `/jira:create` command when the project_key is "CNTRLPLANE".

## Project Information

### CNTRLPLANE Project
**Full name:** Red Hat OpenShift Control Planes

**Key:** CNTRLPLANE

**Used for:** Features, Epics, Stories, Tasks, Spikes

**Used by:** Multiple OpenShift teams (HyperShift, Cluster Infrastructure, Networking, Storage, etc.)

## Version Requirements

**Note:** Universal requirements (Security Level: Red Hat Employee, Labels: ai-generated-jira) are defined in the `/jira:create` command and automatically applied to all tickets.

### Target Version (customfield_12319940)
**Purpose:** Target release version for the feature/story/task

**Common default:** `openshift-4.21` (current development release)

**Override:** Teams may specify different versions based on their roadmap:
- `openshift-4.20` (maintenance release)
- `openshift-4.22` (future release)
- `openshift-4.23` (future release)
- Or team-specific version schemes

**Never set:**
- Fix Version/s (`fixVersions`) - This is managed by the release team

### Version Override Handling

When user specifies a different version:
1. Accept the version as provided
2. Validate version exists using MCP tool `jira_get_project_versions` if needed
3. If version doesn't exist, suggest closest match or ask user to confirm

## Component Requirements

**IMPORTANT:** Component requirements are **team-specific**.

Some teams require specific components, while others do not. The CNTRLPLANE skill does NOT enforce component selection.

**Team-specific component handling:**
- Teams may have their own skills that define required components
- For example, HyperShift team uses `hypershift` skill for component selection
- Other teams may use different components based on their structure

**If component is not specified:**
- Prompt user: "Does this issue require a component? (optional)"
- If yes, ask user to specify component name
- If no, proceed without component

## Issue Type Requirements

**Note:** Issue type templates and best practices are defined in type-specific skills (create-story, create-epic, create-feature, create-task).

### Stories
- Must include acceptance criteria
- May link to parent Epic (use `--parent` flag)

### Epics
- **Epic Name field required:** `customfield_epicname` must be set (same value as summary)
- May link to parent Feature (use `--parent` flag)

### Features
- Should include market problem and success criteria (see `create-feature` skill)

### Tasks
- May link to parent Story or Epic (use `--parent` flag)

**Note:** Security validation (credential scanning) is defined in the `/jira:create` command and automatically applied to all tickets.

## MCP Tool Integration

### For CNTRLPLANE Stories

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<story summary>",
    issue_type="Story",
    description="<formatted description with AC>",
    components="<component name>",  # if required by team
    additional_fields={
        "customfield_12319940": "openshift-4.21",  # target version (default)
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### For CNTRLPLANE Epics

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<epic summary>",
    issue_type="Epic",
    description="<epic description with scope and AC>",
    components="<component name>",  # if required
    additional_fields={
        "customfield_12319940": "openshift-4.21",
        "customfield_epicname": "<epic name>",  # required, same as summary
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"},
        "parent": {"key": "CNTRLPLANE-123"}  # if --parent specified
    }
)
```

### For CNTRLPLANE Features

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<feature summary>",
    issue_type="Feature",
    description="<feature description with market problem and success criteria>",
    components="<component name>",  # if required
    additional_fields={
        "customfield_12319940": "openshift-4.21",
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### For CNTRLPLANE Tasks

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<task summary>",
    issue_type="Task",
    description="<task description with what/why/AC>",
    components="<component name>",  # if required
    additional_fields={
        "customfield_12319940": "openshift-4.21",
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"},
        "parent": {"key": "CNTRLPLANE-456"}  # if --parent specified
    }
)
```

### Field Mapping Reference

| Requirement | MCP Parameter | Value |
|-------------|---------------|-------|
| Project | `project_key` | `"CNTRLPLANE"` |
| Issue Type | `issue_type` | `"Story"`, `"Epic"`, `"Feature"`, `"Task"` |
| Summary | `summary` | User-provided text |
| Description | `description` | Formatted template content |
| Component | `components` | Team-specific (optional) |
| Target Version | `additional_fields.customfield_12319940` | `"openshift-4.21"` (default) |
| Labels | `additional_fields.labels` | `["ai-generated-jira"]` (required) |
| Security Level | `additional_fields.security` | `{"name": "Red Hat Employee"}` (required) |
| Parent Link | `additional_fields.parent` | `{"key": "PARENT-123"}` |
| Epic Name | `additional_fields.customfield_epicname` | Same as summary (epics only) |

## Interactive Prompts

**Note:** Detailed prompts for each issue type are defined in type-specific skills (create-story, create-epic, create-feature, create-task).

**CNTRLPLANE-specific prompts:**
- **Target version** (optional): "Which version should this target? (default: openshift-4.21)"
- **Component** (if required by team): Defer to team-specific skills
- **Parent link** (for epics/tasks): "Link to parent Feature/Epic?" (optional)

## Examples

**Note:** All examples automatically apply universal requirements (Security: Red Hat Employee, Labels: ai-generated-jira) as defined in `/jira:create` command.

### Create CNTRLPLANE Story

```bash
/jira:create story CNTRLPLANE "Enable pod disruption budgets for control plane"
```

**CNTRLPLANE-specific defaults:**
- Target Version: openshift-4.21

**Prompts:** See `create-story` skill for story-specific prompts

### Create CNTRLPLANE Epic

```bash
/jira:create epic CNTRLPLANE "Improve cluster lifecycle management"
```

**CNTRLPLANE-specific defaults:**
- Target Version: openshift-4.21
- Epic Name: Same as summary (required field)

**Prompts:** See `create-epic` skill for epic-specific prompts

### Create CNTRLPLANE Feature

```bash
/jira:create feature CNTRLPLANE "Advanced observability capabilities"
```

**CNTRLPLANE-specific defaults:**
- Target Version: openshift-4.21

**Prompts:** See `create-feature` skill for feature-specific prompts

### Create CNTRLPLANE Task

```bash
/jira:create task CNTRLPLANE "Refactor cluster controller reconciliation logic"
```

**CNTRLPLANE-specific defaults:**
- Target Version: openshift-4.21

**Prompts:** See `create-task` skill for task-specific prompts

## Error Handling

### Invalid Version

**Scenario:** User specifies a version that doesn't exist.

**Action:**
1. Use `mcp__atlassian__jira_get_project_versions` to fetch available versions
2. Suggest closest match: "Version 'openshift-4.21.5' not found. Did you mean 'openshift-4.21.0'?"
3. Show available versions: "Available: openshift-4.20.0, openshift-4.21.0, openshift-4.22.0"
4. Wait for confirmation or correction

### Component Required But Missing

**Scenario:** Team requires component, but user didn't specify.

**Action:**
1. If team skill detected required components, show options
2. Otherwise, generic prompt: "Does this issue require a component?"
3. If yes, ask user to specify component name
4. If no, proceed without component

### Sensitive Data Detected

**Scenario:** Credentials or secrets found in description.

**Action:**
1. STOP issue creation immediately
2. Inform user: "I detected potential credentials in the description."
3. Show general location: "Found in: Technical details section"
4. Do NOT echo the sensitive data back
5. Suggest: "Please use placeholder values like 'YOUR_API_KEY'"
6. Wait for user to provide sanitized content

### Parent Issue Not Found

**Scenario:** User specifies `--parent CNTRLPLANE-999` but issue doesn't exist.

**Action:**
1. Attempt to fetch parent issue using `mcp__atlassian__jira_get_issue`
2. If not found: "Parent issue CNTRLPLANE-999 not found. Would you like to proceed without a parent?"
3. Offer options:
   - Proceed without parent
   - Specify different parent
   - Cancel creation

### MCP Tool Failure

**Scenario:** MCP tool returns an error.

**Action:**
1. Parse error message for actionable information
2. Common errors:
   - **"Field 'component' is required"** → Prompt for component (team-specific requirement)
   - **"Permission denied"** → User may lack permissions
   - **"Version not found"** → Use version error handling above
   - **"Issue type not available"** → Project may not support this issue type
3. Provide clear next steps
4. Offer to retry after corrections

### Wrong Issue Type

**Scenario:** User tries to create a bug in CNTRLPLANE.

**Action:**
1. Inform user: "Bugs should be created in OCPBUGS. CNTRLPLANE is for stories/epics/features/tasks."
2. Suggest: "Would you like to create this as a story in CNTRLPLANE, or as a bug in OCPBUGS?"
3. Wait for user decision

**Note:** Jira description formatting (Wiki markup) is defined in the `/jira:create` command.

## Team-Specific Extensions

Teams using CNTRLPLANE may have additional team-specific requirements defined in separate skills:

- **HyperShift team:** Uses `hypershift` skill for component selection (HyperShift / ARO, HyperShift / ROSA, HyperShift)
- **Other teams:** May define their own skills with team-specific components and conventions

Team-specific skills are invoked automatically when team keywords are detected in the summary or when specific components are mentioned.

## Workflow Summary

When `/jira:create` is invoked for CNTRLPLANE:

1. ✅ **CNTRLPLANE skill loaded:** Applies project-specific conventions
2. ⚙️ **Apply CNTRLPLANE defaults:**
   - Target version: openshift-4.21 (default)
   - Epic name field (for epics)
3. 🔍 **Check for team-specific skills:** If team keywords detected, invoke team skill (e.g., `hypershift`)
4. 💬 **Interactive prompts:** Collect missing information (see type-specific skills for details)

**Note:** Universal requirements (security, labels), security validation, and issue creation handled by `/jira:create` command.

## Best Practices

1. **Version consistency:** Use common defaults (openshift-4.21) unless team specifies otherwise
2. **Template adherence:** Defer to type-specific skills for templates (create-story, create-epic, etc.)
3. **Link hierarchy:** Link epics to features, tasks to stories/epics using `--parent` flag
4. **Descriptive summaries:** Use clear, searchable issue summaries
5. **Component selection:** Defer to team-specific skills when applicable (e.g., HyperShift)

**Note:** Universal best practices (security, labels, formatting, credential scanning) are defined in the `/jira:create` command.

## See Also

- `/jira:create` - Main command that invokes this skill
- `ocpbugs` skill - For OCPBUGS bugs
- Team-specific skills (e.g., `hypershift`) - For team-specific conventions
- Type-specific skills (create-story, create-epic, create-feature, create-task) - For issue type best practices
