---
name: OCPBUGS Jira Conventions
description: Jira conventions and bug templates for the OCPBUGS project
---

# OCPBUGS Jira Conventions

This skill provides conventions and requirements for creating bug reports in the OCPBUGS project, which is used by all OpenShift product teams for bug tracking.

## When to Use This Skill

Use this skill when creating bugs in the OCPBUGS project:
- **Project: OCPBUGS** - OpenShift Bugs
- **Issue Type: Bug** - Bug reports only

This skill is automatically invoked by the `/jira:create` command when the project_key is "OCPBUGS" or when issue type is "bug" without a project specified.

## Project Information

### OCPBUGS Project
**Full name:** OpenShift Bugs

**Key:** OCPBUGS

**Used for:** Bugs only

**Used by:** All OpenShift product teams

## Version Requirements

**Note:** Universal requirements (Security Level: Red Hat Employee, Labels: ai-generated-jira) are defined in the `/jira:create` command and automatically applied to all tickets.

### Affects Version/s (`versions`)
**Purpose:** Version where the bug was found

**Common values:** `4.19`, `4.20`, `4.21`, `4.22`, etc.

**Handling:**
- User should specify the version where they encountered the bug
- If not specified, prompt user: "Which version did you encounter this bug in?"
- Multiple versions can be specified if bug affects multiple releases

### Target Version (customfield_10855)
**Purpose:** Version where the fix is targeted

**Common default:** `openshift-4.21` (or current development release)

**Override:** May be different based on:
- Severity (critical bugs may target earlier releases)
- Backport requirements
- Release schedule

**Never set:**
- Fix Version/s (`fixVersions`) - This is managed by the release team

### Version Override Handling

When user specifies a different version:
1. Accept the version as provided
2. Validate version exists via Jira REST API if needed
3. If version doesn't exist, suggest closest match or ask user to confirm

## Component Requirements

**IMPORTANT:** Component requirements are **team-specific**.

Some teams require specific components, while others do not. The OCPBUGS skill does NOT enforce component selection.

**Team-specific component handling:**
- Teams may have their own skills that define required components
- For example, HyperShift team uses `hypershift` skill for component selection
- Other teams may use different components based on their structure

**If component is not specified:**
- Prompt user: "Does this bug require a component? (optional)"
- If yes, ask user to specify component name
- If no, proceed without component

## Bug Description Template

**Note:** Bug template structure and sections are defined in the `create-bug` skill.

**OCPBUGS-specific:**
- All bugs must follow the bug template format
- Version-Release number field may differ from Affects Version (can be more specific)

**Note:** Security validation (credential scanning) is defined in the `/jira:create` command and automatically applied to all tickets.

## MCP Tool Integration

### For OCPBUGS Bugs

```python
mcp__plugin_atlassian_atlassian__createJiraIssue(
    cloudId="redhat.atlassian.net",
    projectKey="OCPBUGS",
    issueTypeName="Bug",
    summary="<bug summary>",
    description="<formatted bug template>",
    contentFormat="markdown",
    additional_fields={
        "components": [{"name": "<component name>"}],  # if required by team
        "versions": [{"name": "4.21"}],           # affects version (user-specified)
        "customfield_10855": "openshift-4.21", # target version (default or user-specified)
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### Field Mapping Reference

| Requirement | MCP Parameter | Value |
|-------------|---------------|-------|
| Cloud ID | `cloudId` | `"redhat.atlassian.net"` |
| Project | `projectKey` | `"OCPBUGS"` |
| Issue Type | `issueTypeName` | `"Bug"` |
| Summary | `summary` | User-provided text |
| Description | `description` | Formatted bug template |
| Content Format | `contentFormat` | `"markdown"` |
| Component | `fields.components` | `[{"name": "<component>"}]` (team-specific, optional) |
| Affects Version | `fields.versions` | `[{"name": "4.21"}]` (user-specified) |
| Target Version | `fields.customfield_10855` | `"openshift-4.21"` (default or user-specified) |
| Labels | `fields.labels` | `["ai-generated-jira"]` (required) |
| Security Level | `fields.security` | `{"name": "Red Hat Employee"}` (required) |

## Interactive Prompts

**Note:** Detailed bug template prompts are defined in the `create-bug` skill.

**OCPBUGS-specific prompts:**
- **Affects Version** (required): "Which version did you encounter this bug in?"
  - Show common versions: 4.19, 4.20, 4.21, 4.22
- **Target Version** (optional): "Which version should this be fixed in? (default: openshift-4.21)"
- **Component** (if required by team): Defer to team-specific skills

## Examples

**Note:** All examples automatically apply universal requirements (Security: Red Hat Employee, Labels: ai-generated-jira) as defined in `/jira:create` command.

### Create Bug with Minimal Info

```bash
/jira:create bug "Control plane pods crash on upgrade from 4.20 to 4.21"
```

**OCPBUGS-specific defaults:**
- Project: OCPBUGS (default for bugs)
- Target Version: openshift-4.21 (default)

**Prompts:** See `create-bug` skill for bug template prompts, plus Affects Version

### Create Bug with Full Details

```bash
/jira:create bug OCPBUGS "API server returns 500 error when creating namespaces" --component "API" --version "4.21"
```

**OCPBUGS-specific defaults:**
- Affects Version: 4.21 (from --version flag)
- Target Version: openshift-4.21 (default)
- Component: API (from --component flag)

**Prompts:** See `create-bug` skill for bug template prompts

## Error Handling

### Invalid Version

**Scenario:** User specifies a version that doesn't exist.

**Action:**
1. Use Jira REST API (`GET /rest/api/3/project/OCPBUGS/versions`) to fetch available versions
2. Suggest closest match: "Version '4.21.5' not found. Did you mean '4.21.0'?"
3. Show available versions: "Available: 4.20.0, 4.21.0, 4.22.0"
4. Wait for confirmation or correction

### Component Required But Missing

**Scenario:** Team requires component, but user didn't specify.

**Action:**
1. If team skill detected required components, show options
2. Otherwise, generic prompt: "Does this bug require a component?"
3. If yes, ask user to specify component name
4. If no, proceed without component

### Sensitive Data Detected

**Scenario:** Credentials or secrets found in bug description or logs.

**Action:**
1. STOP issue creation immediately
2. Inform user: "I detected potential credentials in the bug report."
3. Show general location: "Found in: Additional info section"
4. Do NOT echo the sensitive data back
5. Suggest: "Please sanitize logs and use placeholder values like 'YOUR_API_KEY'"
6. Wait for user to provide sanitized content

### MCP Tool Failure

**Scenario:** MCP tool returns an error.

**Action:**
1. Parse error message for actionable information
2. Common errors:
   - **"Field 'component' is required"** → Prompt for component (team-specific requirement)
   - **"Permission denied"** → User may lack permissions to create bugs in OCPBUGS
   - **"Version not found"** → Use version error handling above
3. Provide clear next steps
4. Offer to retry after corrections

### Wrong Issue Type

**Scenario:** User tries to create a story/task/epic in OCPBUGS.

**Action:**
1. Inform user: "OCPBUGS is for bugs only. Stories/Tasks/Epics should be created in CNTRLPLANE."
2. Suggest: "Would you like to create a bug instead, or change the project to CNTRLPLANE?"
3. Wait for user decision

**Note:** Jira description formatting (Wiki markup) is defined in the `/jira:create` command.

## Team-Specific Extensions

Teams using OCPBUGS may have additional team-specific requirements defined in separate skills:

- **HyperShift team:** Uses `hypershift` skill for component selection (HyperShift / ARO, HyperShift / ROSA, HyperShift)
- **Other teams:** May define their own skills with team-specific components and conventions

Team-specific skills are invoked automatically when team keywords are detected in the summary or when specific components are mentioned.

## Workflow Summary

When `/jira:create bug` is invoked:

1. ✅ **OCPBUGS skill loaded:** Applies project-specific conventions
2. ⚙️ **Apply OCPBUGS defaults:**
   - Project: OCPBUGS (default for bugs)
   - Target version: openshift-4.21 (default)
3. 🔍 **Check for team-specific skills:** If team keywords detected, invoke team skill (e.g., `hypershift`)
4. 💬 **Interactive prompts:**
   - Affects version (required)
   - Bug template sections (see `create-bug` skill)
   - Component (if required by team)

**Note:** Universal requirements (security, labels), security validation, and issue creation handled by `/jira:create` command.

## Best Practices

1. **Version specificity:** Use exact versions (4.21.0) not just major versions (4.21) for Affects Version
2. **Template adherence:** Defer to `create-bug` skill for bug template best practices
3. **Link related issues:** Reference related bugs, PRs, or stories

**Note:** Universal best practices (security, credential sanitization, formatting) are defined in the `/jira:create` command.

## See Also

- `/jira:create` - Main command that invokes this skill
- `cntrlplane` skill - For CNTRLPLANE stories/epics/features/tasks
- Team-specific skills (e.g., `hypershift`) - For team-specific conventions
- `create-bug` skill - General bug report best practices
