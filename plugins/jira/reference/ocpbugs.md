# OCPBUGS Jira Conventions

Conventions and requirements for creating bug reports in the OCPBUGS project, used by all OpenShift product teams for bug tracking.

## Project Information

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
2. Fetch available versions from the project via `getJiraIssueTypeMetaWithFields` if needed
3. If version doesn't exist, suggest closest match or ask user to confirm

## Component Requirements

**IMPORTANT:** Component requirements are **team-specific**.

Some teams require specific components, while others do not. The OCPBUGS conventions do NOT enforce component selection.

**Team-specific component handling:**
- Teams may have their own conventions that define required components
- For example, HyperShift team uses specific components (see [hypershift.md](hypershift.md))
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

**Note:** Always include `contentFormat: "markdown"` when calling `createJiraIssue` or `editJiraIssue` so descriptions are interpreted as Markdown.

### For OCPBUGS Bugs

Use `createJiraIssue` with `contentFormat: "markdown"`, project key `OCPBUGS`, and issue type `Bug`. Set the following fields via `additional_fields`:

- `versions`: affects version, e.g. `[{"name": "4.21"}]` (user-specified)
- `customfield_10855`: target version, e.g. `"openshift-4.21"` (default or user-specified)
- `labels`: `["ai-generated-jira"]`
- `security`: `{"name": "Red Hat Employee"}`

Set `components` if required by the team.

## Interactive Prompts

**Note:** Detailed bug template prompts are defined in the `create-bug` skill.

**OCPBUGS-specific prompts:**
- **Affects Version** (required): "Which version did you encounter this bug in?"
  - Show common versions: 4.19, 4.20, 4.21, 4.22
- **Target Version** (optional): "Which version should this be fixed in? (default: openshift-4.21)"
- **Component** (if required by team): Defer to team-specific conventions

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
1. Fetch available versions from the project
2. Suggest closest match: "Version '4.21.5' not found. Did you mean '4.21.0'?"
3. Show available versions: "Available: 4.20.0, 4.21.0, 4.22.0"
4. Wait for confirmation or correction

### Component Required But Missing

**Scenario:** Team requires component, but user didn't specify.

**Action:**
1. If team conventions require specific components, show options
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

**Note:** Jira descriptions use Markdown (`contentFormat: "markdown"`). Formatting conventions are defined in the `/jira:create` command.

## Team-Specific Extensions

Teams using OCPBUGS may have additional team-specific requirements:

- **HyperShift team:** See [hypershift.md](hypershift.md) for component selection (HyperShift / ARO, HyperShift / ROSA, HyperShift)
- **Other teams:** May define their own conventions with team-specific components

Team-specific conventions are invoked automatically when team keywords are detected in the summary or when specific components are mentioned.
