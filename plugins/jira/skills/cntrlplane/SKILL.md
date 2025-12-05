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

**Status:** OPTIONAL (many issues in CNTRLPLANE have null target version)

**Recommendation:** **Prompt the user** for target version if needed, rather than assuming a default.

**Prompt:** "Which OpenShift version should this target? (e.g., 4.22, openshift 4.22, OCP 4.22) or press Enter to skip"

### Version Input Normalization

Users may specify versions in various formats. Normalize all inputs to the Jira format `openshift-X.Y`:

| User Input | Normalized Output |
|------------|-------------------|
| `4.21` | `openshift-4.21` |
| `4.22.0` | `openshift-4.22` |
| `openshift 4.23` | `openshift-4.23` |
| `openshift-4.21` | `openshift-4.21` |
| `OCP 4.22` | `openshift-4.22` |
| `ocp 4.21` | `openshift-4.21` |
| `OpenShift 4.23` | `openshift-4.23` |

**Normalization rules:**
1. Convert to lowercase
2. Remove "ocp" or "openshift" prefix (with or without space/hyphen)
3. Extract version number (X.Y or X.Y.Z → X.Y)
4. Prepend "openshift-"

### Setting Target Version in MCP

**If target version is set:**

1. **First, fetch available versions:**
   ```python
   versions = mcp__atlassian__jira_get_project_versions(project_key="CNTRLPLANE")
   ```

2. **Find the version ID** for the normalized version name (e.g., "openshift-4.22")

3. **Use correct MCP format** (array of version objects with ID):
   ```python
   "customfield_12319940": [{"id": "VERSION_ID"}]  # e.g., openshift-4.22
   ```

**IMPORTANT:** Do NOT use string format like `"openshift-4.22"` - this will fail. Must use array with version ID.

**Never set:**
- Fix Version/s (`fixVersions`) - This is managed by the release team

### Version Handling Workflow

When user specifies a version (via `--version` flag or prompt):
1. **Normalize** the input to `openshift-X.Y` format
2. **Fetch** available versions using `mcp__atlassian__jira_get_project_versions`
3. **Find** the matching version ID
4. **If version doesn't exist**, suggest closest match or ask user to confirm
5. **Use array format** with version ID: `[{"id": "VERSION_ID"}]`

## Parent Linking in CNTRLPLANE

**See:** `/jira:create` command documentation for the complete "Issue Hierarchy and Parent Linking" reference, including field mapping, MCP code examples, and fallback strategies.

### Quick Reference for CNTRLPLANE

CNTRLPLANE uses different fields for different parent relationships:

| Creating | Parent Type | Field to Use | Value Format |
|----------|-------------|--------------|--------------|
| Story | Epic | `customfield_12311140` (Epic Link) | `"CNTRLPLANE-123"` (string) |
| Task | Epic | `customfield_12311140` (Epic Link) | `"CNTRLPLANE-123"` (string) |
| Epic | Feature | `customfield_12313140` (Parent Link) | `"CNTRLPLANE-123"` (string) |

**⚠️ CRITICAL:**
- Story/Task → Epic uses **Epic Link** (`customfield_12311140`)
- Epic → Feature uses **Parent Link** (`customfield_12313140`)
- Both fields take STRING values (issue key), NOT objects
- The standard `parent` field does NOT work

### CNTRLPLANE-Specific Field IDs

| Field | Custom Field ID | Format |
|-------|-----------------|--------|
| Epic Link (for stories/tasks) | `customfield_12311140` | String: `"CNTRLPLANE-123"` |
| Parent Link (for epics→features) | `customfield_12313140` | String: `"CNTRLPLANE-123"` |
| Epic Name (required for epics) | `customfield_12311141` | String: same as summary |
| Target Version | `customfield_12319940` | Array: `[{"id": "12448830"}]` |

### Implementation

Follow the implementation strategy documented in `/jira:create` command:
1. **Pre-validate** the parent exists and is the correct type
2. **Attempt creation** with the appropriate parent field
3. **Use fallback** if creation fails (create without link, then update)
4. **Report outcome** to user

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

**Basic story (no epic link):**
```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<concise story title>",  # NOT full user story format
    issue_type="Story",
    description="<formatted description with full user story and AC>",
    components="<component name>",  # if required by team
    additional_fields={
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

**Story linked to epic:**
```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<concise story title>",  # NOT full user story format
    issue_type="Story",
    description="<formatted description with full user story and AC>",
    components="<component name>",  # if required by team
    additional_fields={
        "customfield_12311140": "<epic-key>",  # Epic Link (e.g., "CNTRLPLANE-456")
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### For CNTRLPLANE Epics

**Basic epic (no parent feature):**
```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<concise epic title>",
    issue_type="Epic",
    description="<epic description with scope and AC>",
    components="<component name>",  # if required
    additional_fields={
        "customfield_12311141": "<epic name>",  # required, same as summary
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

**Epic linked to parent feature:**
```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<concise epic title>",
    issue_type="Epic",
    description="<epic description with scope and AC>",
    components="<component name>",  # if required
    additional_fields={
        "customfield_12311141": "<epic name>",  # required, same as summary
        "customfield_12313140": "CNTRLPLANE-123",  # Parent Link - feature key as STRING
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### For CNTRLPLANE Features

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<concise feature title>",
    issue_type="Feature",
    description="<feature description with market problem and success criteria>",
    components="<component name>",  # if required
    additional_fields={
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
        # Target version is optional - omit unless specifically required
    }
)
```

### For CNTRLPLANE Tasks

**Task linked to epic (via Epic Link):**
```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="<task summary>",
    issue_type="Task",
    description="<task description with what/why/AC>",
    components="<component name>",  # if required
    additional_fields={
        "customfield_12311140": "CNTRLPLANE-456",  # Epic Link (if linking to epic)
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

**Note:** If you need to link a task to a parent story, use Epic Link field (`customfield_12311140`) with the story key.

### Field Mapping Reference

| Requirement | MCP Parameter | Value | Required? |
|-------------|---------------|-------|-----------|
| Project | `project_key` | `"CNTRLPLANE"` | Yes |
| Issue Type | `issue_type` | `"Story"`, `"Epic"`, `"Feature"`, `"Task"` | Yes |
| Summary | `summary` | Concise title (5-10 words), NOT full user story | Yes |
| Description | `description` | Formatted template (contains full user story) | Yes |
| Component | `components` | Team-specific component name | Varies by team |
| Target Version | `additional_fields.customfield_12319940` | Array: `[{"id": "12448830"}]` **Recommend omitting** | No |
| Labels | `additional_fields.labels` | `["ai-generated-jira"]` | Yes |
| Security Level | `additional_fields.security` | `{"name": "Red Hat Employee"}` | Yes |
| Epic Link (stories→epics) | `additional_fields.customfield_12311140` | Epic key as string: `"CNTRLPLANE-123"` | No |
| Epic Name (epics only) | `additional_fields.customfield_epicname` | Same as summary | Yes (epics) |
| Parent Link (epics→features) | `additional_fields.parent` | `{"key": "FEATURE-123"}` | No |

## Interactive Prompts

**Note:** Detailed prompts for each issue type are defined in type-specific skills (create-story, create-epic, create-feature, create-task).

**CNTRLPLANE-specific prompts:**
- **Target version** (optional): "Which OpenShift version should this target? (e.g., 4.22, openshift 4.22, OCP 4.22) or press Enter to skip"
- **Component** (if required by team): Defer to team-specific skills
- **Parent link** (for epics/tasks): "Link to parent Feature/Epic?" (optional)

## Examples

**Note:** All examples automatically apply universal requirements (Security: Red Hat Employee, Labels: ai-generated-jira) as defined in `/jira:create` command.

### Create CNTRLPLANE Story

```bash
/jira:create story CNTRLPLANE "Enable pod disruption budgets for control plane"
```

**Prompts:**
- Target version (optional): User prompted, input normalized (e.g., "4.22" → "openshift-4.22")
- See `create-story` skill for story-specific prompts

### Create CNTRLPLANE Epic

```bash
/jira:create epic CNTRLPLANE "Improve cluster lifecycle management"
```

**CNTRLPLANE-specific requirements:**
- Epic Name: Same as summary (required field)

**Prompts:**
- Target version (optional): User prompted, input normalized
- See `create-epic` skill for epic-specific prompts

### Create CNTRLPLANE Feature

```bash
/jira:create feature CNTRLPLANE "Advanced observability capabilities"
```

**Prompts:**
- Target version (optional): User prompted, input normalized
- See `create-feature` skill for feature-specific prompts

### Create CNTRLPLANE Task

```bash
/jira:create task CNTRLPLANE "Refactor cluster controller reconciliation logic"
```

**Prompts:**
- Target version (optional): User prompted, input normalized
- See `create-task` skill for task-specific prompts

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
2. ⚙️ **Apply CNTRLPLANE requirements:**
   - Epic name field (for epics)
3. 🔍 **Check for team-specific skills:** If team keywords detected, invoke team skill (e.g., `hypershift`)
4. 💬 **Interactive prompts:** Collect missing information:
   - Target version (optional): Prompt user, normalize input (e.g., "4.22" → "openshift-4.22")
   - See type-specific skills for additional prompts

**Note:** Universal requirements (security, labels), security validation, and issue creation handled by `/jira:create` command.

## Best Practices

1. **Version input:** Always normalize user version input (e.g., "4.22", "OCP 4.22" → "openshift-4.22")
2. **Template adherence:** Defer to type-specific skills for templates (create-story, create-epic, etc.)
3. **Link hierarchy:** Link epics to features, tasks to stories/epics using `--parent` flag
4. **Descriptive summaries:** Use clear, searchable issue summaries
5. **Component selection:** Defer to team-specific skills when applicable (e.g., HyperShift)

**Note:** Universal best practices (security, labels, formatting, credential scanning) are defined in the `/jira:create` command.

## See Also

- `/jira:create` - Main command that invokes this skill (includes Issue Hierarchy and Parent Linking documentation)
- `ocpbugs` skill - For OCPBUGS bugs
- Team-specific skills (e.g., `hypershift`) - For team-specific conventions
- Type-specific skills (create-story, create-epic, create-feature, create-task) - For issue type best practices
