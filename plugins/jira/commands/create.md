---
description: Create Jira issues (story, epic, feature, task, bug, feature-request) with proper formatting
argument-hint: <type> [project-key] <summary> [--component <name>] [--version <version>] [--parent <key>] [--template <name>] [--overrides <path>] [--priority <value>] [--security-level <value>]
---

## Name
jira:create

## Synopsis
```bash
/jira:create <type> [project-key] <summary> [--component <name>] [--version <version>] [--parent <key>] [--template <name>] [--overrides <path>] [--priority <value>] [--security-level <value>]
```

## Description
The `jira:create` command creates Jira issues following best practices and team-specific conventions. It supports creating stories, epics, features, tasks, bugs, and feature requests with intelligent defaults, interactive prompts, and validation.

This command is particularly useful for:
- Creating well-formed user stories with acceptance criteria
- Organizing epics and features with proper hierarchy
- Submitting bugs with complete reproduction steps
- Capturing customer-driven feature requests with business justification
- Maintaining consistency across team Jira practices

## Key Features

- **Multi-Type Support** - Create stories, epics, features, tasks, bugs, or feature requests from a single command
- **Smart Defaults** - Automatically applies project-specific conventions (e.g., CNTRLPLANE, OCPBUGS, RFE)
- **Interactive Guidance** - Prompts for missing information with helpful templates
- **Context Detection** - Analyzes summary text to suggest components (ARO, ROSA, HyperShift)
- **Security Validation** - Scans for credentials and secrets before submission
- **Template Support** - Provides user story templates, bug report templates, feature request workflows, acceptance criteria formats

## Issue Hierarchy and Parent Linking

Jira issues form a hierarchy. Understanding this hierarchy is critical for proper parent linking:

```text
Feature (Strategic objective, market problem)
    │
    └── Epic (Body of work, fits in a quarter)
            │
            ├── Story (User-facing functionality, fits in a sprint)
            │
            └── Task (Technical work, fits in a sprint)
```

### Parent Linking Field Reference

**CRITICAL:** Different relationships use different Jira fields. Using the wrong field will cause creation to fail.

| Relationship | Field | MCP Parameter | Value Format |
|--------------|-------|---------------|--------------|
| **Epic → Feature** | Parent Link (custom field) | `additional_fields.customfield_12313140` | `"PROJ-123"` (string) |
| **Story → Epic** | Epic Link (custom field) | `additional_fields.customfield_12311140` | `"PROJ-123"` (string) |
| **Task → Epic** | Epic Link (custom field) | `additional_fields.customfield_12311140` | `"PROJ-123"` (string) |
| **Task → Story** | Epic Link (custom field) | `additional_fields.customfield_12311140` | `"PROJ-123"` (string) |

**Why the difference?**
- The Parent Link field (`customfield_12313140`) is used for Epic→Feature relationships in CNTRLPLANE
- The Epic Link field (`customfield_12311140`) is used for Story/Task→Epic relationships
- Both are custom fields specific to how Red Hat Jira handles hierarchy
- The standard `parent` field does NOT work for these relationships

### MCP Code Examples for Parent Linking

#### Linking a Story to an Epic

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="Add metrics endpoint for cluster health",
    issue_type="Story",
    description="<story description>",
    components="HyperShift / ROSA",
    additional_fields={
        "customfield_12311140": "CNTRLPLANE-456",  # Epic Link - links to parent epic
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}  # Set according to template or global default (Phase 5)
    }
)
```text

#### Linking an Epic to a Feature

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="Multi-cluster metrics aggregation",
    issue_type="Epic",
    description="<epic description>",
    components="HyperShift",
    additional_fields={
        "customfield_12311141": "Multi-cluster metrics aggregation",  # Epic Name (same as summary)
        "customfield_12313140": "CNTRLPLANE-100",  # Parent Link - links to parent feature (STRING, not object!)
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}  # Set according to template or global default (Phase 5)
    }
)
```text

#### Linking a Task to an Epic

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="Refactor metrics collection pipeline",
    issue_type="Task",
    description="<task description>",
    additional_fields={
        "customfield_12311140": "CNTRLPLANE-456",  # Epic Link - links to parent epic
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}  # Set according to template or global default (Phase 5)
    }
)
```

### Parent Linking Implementation Strategy

When the `--parent` flag is provided, follow this strategy:

#### Step 1: Pre-Validation (Required)

Before creating the issue, validate the parent:

```python
# Fetch parent issue to verify it exists and is correct type
parent_issue = mcp__atlassian__jira_get_issue(issue_key="<parent-key>")

# Verify parent type matches expected hierarchy:
# - If creating Story/Task with --parent, parent should be Epic
# - If creating Epic with --parent, parent should be Feature
```text

**Validation rules:**
| Creating | Parent Should Be | If Wrong Type |
|----------|------------------|---------------|
| Story | Epic | Warn user, ask to confirm or correct |
| Task | Epic or Story | Warn user, ask to confirm or correct |
| Epic | Feature | Warn user, ask to confirm or correct |

**If parent not found:**
```
Parent issue CNTRLPLANE-999 not found.

Options:
1. Proceed without parent link
2. Specify different parent
3. Cancel creation

What would you like to do?
```

#### Step 2: Attempt Creation with Parent Link

Include the appropriate parent field based on issue type:

- **Story/Task → Epic:** Use `customfield_12311140` (Epic Link)
- **Epic → Feature:** Use `customfield_12313140` (Parent Link)

#### Step 3: Fallback Strategy (If Creation Fails)

If creation fails with an error related to parent linking:

1. **Detect linking error:** Error message contains "epic", "parent", "link", or "customfield"

2. **Create without parent link:**
   ```python
   issue = mcp__atlassian__jira_create_issue(
       # ... same parameters but WITHOUT the parent/epic link field
   )
   ```text

3. **Link via update:**
   ```python
   # For Story/Task → Epic:
   mcp__atlassian__jira_update_issue(
       issue_key=issue["key"],
       fields={},
       additional_fields={"customfield_12311140": "<epic-key>"}
   )

   # For Epic → Feature:
   mcp__atlassian__jira_update_issue(
       issue_key=issue["key"],
       fields={},
       additional_fields={"customfield_12313140": "<feature-key>"}
   )
   ```text

4. **Report outcome:**
   ```
   Created: CNTRLPLANE-789
   Linked to parent: CNTRLPLANE-456 ✓
   Title: <issue title>
   URL: https://issues.redhat.com/browse/CNTRLPLANE-789
   ```text

#### Step 4: If Fallback Also Fails

If the update to add parent link also fails:
```
Created: CNTRLPLANE-789
⚠️  Automatic parent linking failed. Please link manually in Jira.
URL: https://issues.redhat.com/browse/CNTRLPLANE-789
```

### Common Parent Linking Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Field 'parent' does not exist` | Using standard `parent` field | Use `customfield_12313140` (Parent Link) or `customfield_12311140` (Epic Link) |
| `customfield_12311140 is not valid` | Epic Link field issue | Use fallback: create then update |
| `customfield_12313140 is not valid` | Parent Link field issue | Use fallback: create then update |
| `Parent issue not found` | Invalid parent key | Verify parent exists first |
| `Cannot link to issue of type X` | Wrong parent type | Verify hierarchy (Story→Epic, Epic→Feature) |

## Implementation

The `jira:create` command runs in multiple phases:

### 🔌 Phase 0: MCP Server Verification (FIRST-TIME SETUP)

**CRITICAL: This phase runs BEFORE any Jira operations.**

This phase ensures the Atlassian MCP server is configured and working before attempting any Jira operations.

#### Step 1: Check MCP Server Availability

Attempt to list available MCP tools to verify the Atlassian MCP server is connected:

```python
# Try to detect if atlassian MCP tools are available
try:
    # Attempt to use a basic MCP tool (e.g., list projects)
    # This will fail if MCP server isn't configured
    mcp_tools_available = True
except:
    mcp_tools_available = False
```

#### Step 2: Check Setup Status Flag

Read `~/.claude/jira-config.json` to check if setup has been completed:

```json
{
  "mcp_setup_complete": true
}
```

**Decision tree:**

| MCP Available | Flag Set | Action |
|---------------|----------|--------|
| ✅ Yes | ❌ No | Set flag to `true`, proceed |
| ✅ Yes | ✅ Yes | Proceed (already configured) |
| ❌ No | ❌ No | **Start guided setup** |
| ❌ No | ✅ Yes | **Reset flag**, start guided setup |

#### Step 3: Guided Setup (If MCP Not Available)

If MCP tools are not available AND flag is not set (first time):

**Display to user:**
```text
The Jira plugin requires the Atlassian MCP server to be configured.

Would you like to set it up now? This is a one-time setup.

Options:
1. Yes - Walk me through setup now
2. Later - Skip for now (will ask again next session)
3. Disable - I've already configured it manually (don't ask again)

Your choice (1/2/3):
```

**User selects "1 - Yes":**
- Display link to setup guide: `plugins/jira/docs/MCP_SETUP.md`
- Guide user through MCP setup interactively (token, environment variable, mcp.json)
- Set `mcp_setup_complete: true` **before** requesting restart
- Request Claude Code restart
- After restart, user can retry the command

**User selects "2 - Later":**
- Do NOT set the flag (will ask again next session)
- Inform user they can run `/jira:create` again when ready
- Provide link to setup guide for reference
- Cancel current operation

**User selects "3 - Disable":**
- Set `mcp_setup_complete: true` (won't ask again)
- Inform user that MCP tools are required for the command to work
- Suggest they check their MCP configuration
- Cancel current operation

#### Step 4: MCP Server Reconnection (If Flag Set But Unavailable)

If MCP tools are NOT available but `mcp_setup_complete: true`:

**This means the server was configured before but is now unavailable.**

**Display to user:**
```bash
⚠️ The Atlassian MCP server appears to be disconnected.

This could mean:
- The mcp.json configuration is incorrect
- Claude Code was not restarted after configuration
- JIRA_PERSONAL_TOKEN environment variable not set
- Podman/Docker not available or not running

Troubleshooting:
1. Verify mcp.json exists and is valid:
   cat ~/.claude/mcp.json | jq .

2. Check JIRA_PERSONAL_TOKEN environment variable:
   echo $JIRA_PERSONAL_TOKEN

3. Verify podman/docker is available:
   podman --version  # or docker --version

4. Restart Claude Code to reload configuration

See plugins/jira/docs/MCP_SETUP.md for detailed troubleshooting.

Would you like to:
1. Try again (after fixing the issue)
2. Reset setup and reconfigure from scratch
3. Cancel

Your choice (1/2/3):
```

**User selects "1 - Try again":**
- Retry MCP availability check
- If successful: Proceed with command
- If failed: Display same troubleshooting again

**User selects "2 - Reset setup":**
- Set `mcp_setup_complete: false`
- Restart from Step 3 (guided setup)

**User selects "3 - Cancel":**
- Cancel current operation
- User can retry when ready

#### Step 5: Proceed to Template Loading

Once MCP server is verified and available:
- Flag is set to `true`
- MCP tools are confirmed working
- Proceed to Phase 1 (Template Discovery)

**Interactive Setup Workflow:**

When user selects "1 - Yes" for guided setup, walk them through the following steps from [MCP_SETUP.md](../docs/MCP_SETUP.md):

1. **Get Jira Personal Access Token** - Guide to token creation page, wait for confirmation
2. **Set Environment Variable** - Show export command for ~/.bashrc or ~/.zshrc, wait for confirmation
3. **Configure mcp.json** - Display configuration template, explain customization, wait for confirmation
4. **Restart Claude Code** - Explain restart requirement, provide retry instructions

**For detailed setup instructions and examples**, see [docs/MCP_SETUP.md](../docs/MCP_SETUP.md).

### 🎨 Phase 1: Template Discovery and Loading (IF APPLICABLE)

**CRITICAL: This phase runs BEFORE loading implementation skills.**

#### Step 1: Check for Template Specification

Check if user specified `--template <name>` flag:
- If specified: Load that template
- If NOT specified: Auto-detect template based on project + issue type

#### Step 2: Auto-Detect Template (if --template not provided)

Search for templates in priority order:
1. **User templates**: `~/.jira-templates/<project>-<type>.yaml` or `.jira-templates/user/<project>-<type>.yaml`
2. **Project templates**: `plugins/jira/templates/<project>/<type>.yaml`
3. **Common templates**: `plugins/jira/templates/common/<type>.yaml`

**Example auto-detection:**
```text
Command: /jira:create epic <PROJECT> "My Epic"

Search order:
1. ~/.jira-templates/<project>-epic.yaml
2. plugins/jira/templates/<project>/epic.yaml
3. plugins/jira/templates/common/epic.yaml  ✓ FOUND
```

#### Step 3: Load Template Defaults

If template found, extract and store ALL defaults:
- `defaults.priority`
- `defaults.components`
- `defaults.labels`
- `defaults.security_level` (or absence of security field)
- `defaults.target_version`
- Any other custom fields defined in `defaults`

**CRITICAL: Template defaults take precedence over hardcoded values in later phases.**

#### Step 4: Note Template Inheritance

Templates may inherit from `_base.yaml`. Merge defaults in order:
1. Start with `_base.yaml` defaults
2. Override with template-specific defaults
3. User flags override both

**Example:**
```yaml
# _base.yaml
defaults:
  priority: Normal
  labels:
    - ai-generated-jira

# common/epic.yaml (inherits _base.yaml)
defaults:
  labels:
    - ai-generated-jira
    - template:common-epic

# Final merged defaults:
priority: Normal
labels: [ai-generated-jira, template:common-epic]
# Note: No security field = public/no security level
```text

#### Step 5: Store Template Context

Save template information for use in later phases:
- Template name
- Template path
- Template defaults (merged with inheritance)
- Template placeholders
- Template description_template

This context will be used in:
- Phase 5 (Apply Smart Defaults) - use template security/priority/components
- Phase 6 (Interactive Prompts) - use template placeholders
- Phase 9 (Create Issue) - add template attribution label

#### Step 6: Inform User of Template Selection (REQUIRED)

**CRITICAL: Always inform the user which template is being used or that no template was found.**

If template was found:
```
Using template: <template-name>
Location: <template-path>
Description: <template-description>

Template defaults:
- Priority: <priority>
- Labels: <labels>
- Security Level: <security_level or "Not set (will use global default)">
- Components: <components or "None">
```text

If no template was found:
```
No template found for <project>-<type>.
Using type-specific guidance from jira:create-<type> skill.
```

**This ensures transparency about what defaults are being applied and from where.**

### 🎯 Phase 2: Load Implementation Guidance

**NOTE: If a template was loaded in Phase 1, skills provide supplementary guidance but template defaults take precedence.**

Invoke the unified `jira:create-issue` skill using the Skill tool:

**All issue types** → Invoke `jira:create-issue` skill
  - Loads appropriate template based on project + issue type
  - Displays educational guide reference (if template has documentation field)
  - Generates interactive prompts dynamically from template placeholder metadata
  - Applies validation rules defined in template
  - Creates issue via MCP with all collected information

The skill handles all issue types (story, epic, feature, task, bug, spike, feature-request) using a template-driven approach. Each type references its own educational guide for best practices.

### 🏢 Phase 3: Apply Project-Specific Conventions

Invoke project-specific and team-specific skills using the Skill tool as needed:

**Project-specific skills:**
- **CNTRLPLANE:** Invoke `cntrlplane` skill for CNTRLPLANE stories/epics/features/tasks
- **OCPBUGS:** Invoke `ocpbugs` skill for OCPBUGS bugs
- **Other projects:** Use only type-specific skills for best practices

**Team-specific skills:**
- Detected based on keywords in summary/description or component
- Apply team-specific conventions (component selection, custom fields, workflows)
- Layer on top of project-specific conventions
- Example: HyperShift team → invoke `hypershift` skill

**General projects** use only the unified `create-issue` skill for best practices.

### 📝 Phase 4: Parse Arguments & Detect Context

Parse command arguments:
- **Required:** `type`, `summary`
- **Optional:** `project_key` (may have project-specific defaults)
- **Optional flags:** `--component`, `--version`, `--parent`, `--team`, `--template`

**Apply project defaults if project_key not provided:**
- If `type` is `bug` and `project_key` is missing → default to `OCPBUGS`
- If `type` is `feature` and `project_key` is missing → default to `OCPSTRAT`
- If `type` is `feature-request` and `project_key` is missing → default to `RFE`
- If `type` is `story`, `epic`, or `task` and `project_key` is missing → error (project required)

Example:
```python
if not project_key:
    if issue_type == "bug":
        project_key = "OCPBUGS"
    elif issue_type == "feature":
        project_key = "OCPSTRAT"
    elif issue_type == "feature-request":
        project_key = "RFE"
    else:
        # Error: project required for stories/epics/tasks
        raise ValueError(f"Project key is required for {issue_type}")
```

Analyze summary text for context clues:
- Extract keywords that may indicate team, component, or platform
- Pass context to project-specific and team-specific skills for interpretation
- Skills handle keyword detection and component/field suggestions

### ⚙️ Phase 5: Apply Smart Defaults

#### Security Level Determination - Priority Chain

Security level is determined using the following priority (highest to lowest):

| Priority | Source | When Applied |
|----------|--------|--------------|
| 1. User flag | `--security-level <value>` | When user explicitly provides flag |
| 2. Template default | `defaults.security_level` in template | When template loaded in Phase 1 |
| 3. Global default | `default_security_level` in jira-config.json | Fallback if no template/flag |

**Confirmation prompt shown when:**
- Final security level ≠ global default
- AND `skip_security_confirmation = false` in config

**Example scenarios:**

*Scenario 1: User flag overrides all*
- Global default: "Red Hat Employee"
- Template specifies: (none - public)
- User provides: `--security-level "Public"`
- **Result:** Public (flag wins, no confirmation needed - matches intent)

*Scenario 2: Template overrides global default*
- Global default: "Red Hat Employee"
- Template specifies: "Public"
- User provides: (none)
- **Result:** Public (template wins, confirmation prompt shown)

---

**STEP 1: Check/Prompt for Global Security Default (ALWAYS FIRST)**

Check if `~/.claude/jira-config.json` exists and has `default_security_level` set.

If NOT set, prompt user:
```text
No global security default is set. This will be used for all JIRA issues unless overridden.

Common options:
1. Red Hat Employee (internal issues)
2. Public (no security level)
3. Custom (specify your own)

Select default security level (1-3):
```

Save selection to `~/.claude/jira-config.json`:
```json
{
  "default_security_level": "Red Hat Employee",  // or null for public
  "skip_security_confirmation": false  // prompt for confirmation when security differs
}
```

**STEP 2: Determine Final Security Level**

Apply in priority order (highest to lowest):
1. **User-specified override** - `--security-level` flag
2. **Template value** - If template specifies security_level in defaults (loaded in Phase 1)
   - **If template has no security field**: Final value = null (Public)
   - **If template specifies security_level**: Final value = template's security_level
   - Templates loaded in Phase 1 take precedence over global defaults
3. **Global default** - From `~/.claude/jira-config.json` (set in Step 1)

**STEP 3: Confirm if Final Value Differs from Global Default**

If final security level ≠ global default AND `skip_security_confirmation` is false:

Display confirmation prompt:
```text
⚠️  Security level will be set to: <final value>
    (Your default is: <global default>)

Reason: <why it's different - e.g., "Template override" or "User flag">

Proceed with this security level? (yes/no/always)
```

- **yes**: Continue with issue creation
- **no**: Cancel issue creation
- **always**: Continue and set `skip_security_confirmation: true` in config

This happens when:
- User provides `--security-level` flag
- Template overrides with different security level

**Universal requirements (MUST be applied to ALL tickets):**
- **Labels:** ai-generated-jira (required)

**Project defaults:**
- May include default project for certain issue types
- Version defaults (if applicable)
- Additional labels (for tracking or automation)

**Team defaults:**
- Component selection (based on keywords or prompts)
- Custom field values
- Workflow-specific requirements

**Template defaults:**
- Templates may specify security level (takes priority over global default)
- Templates may specify priority, components, labels, etc.

**General projects:**
- Use type-specific skills for issue structure
- Prompt for required fields as needed

### 💬 Phase 6: Interactive Prompts (Hybrid Approach)

**CRITICAL: Writing Guidelines for All Long-Form Fields**

When collecting or generating descriptions, objectives, acceptance criteria, or any long-form text:

1. **Be concise**: Remove unnecessary adjectives and adverbs
2. **Be direct**: State facts, not opinions or emphasis
3. **Be specific**: Use concrete nouns and verbs
4. **Avoid filler words**: "really", "very", "easily", "simply", "just", "actually", "comprehensive", "powerful", "beautiful", "significant"

**Example (Good - concise, direct):**
```text
Manage clusters from a single dashboard. Provides metrics, alerting, and visualization.
```

**Example (Bad - wordy, with unnecessary modifiers):**
```text
Enable administrators to easily manage clusters from a single, unified dashboard. Provides comprehensive metrics, powerful alerting, and beautiful visualization.
```

**CRITICAL: Jira Formatting Standards**

For complete formatting guidelines (heading standards, MCP vs Direct API), see the [Jira Formatting section in the plugin README](../README.md#jira-formatting).

**For All Issue Types: Priority Prompt**

Prompt behavior depends on flags and template defaults:

**When to prompt:**
- `--priority` flag provided → Skip prompt entirely, use flag value
- `--priority` flag NOT provided → Prompt user for priority

**Default priority (when user accepts default):**
1. Template `defaults.priority` if specified (takes precedence)
2. "Normal" (fallback if template has no default)

**Prompt:** "What is the priority for this issue?"

**Common values:**
- Blocker, Urgent, Critical, Must Have, High
- Major, Should Have
- **Normal** (fallback default)
- Medium, Minor, Low, Could Have
- Trivial, Optional

**Example scenarios:**

*Scenario 1: Template has priority default*
- Template specifies: `defaults.priority: "High"`
- User accepts default at prompt
- **Result:** "High" (template default used)

*Scenario 2: User provides flag*
- Command: `--priority "Blocker"`
- **Result:** "Blocker" (flag used, no prompt shown)

*Scenario 3: No template default, no flag*
- Template has no priority default
- User accepts default at prompt
- **Result:** "Normal" (fallback default)

Prompt for missing required information based on issue type:

**For Stories:**
- Offer user story template: "As a... I want... So that..."
- Collect acceptance criteria (suggest formats)
- Confirm auto-detected component

**For Epics:**
- Collect epic objective and scope
- Collect epic acceptance criteria
- **Prompt for Size** (XS/S/M/L/XL based on estimated sprints, default: M)
- Collect timeline/target release
- Set epic name field (same as summary)
- Optional parent feature link (via `--parent` or prompt)
- **Prompt for additional context** (optional, default empty - omit section if empty)

**For Features:**
- Collect market problem description
- Collect strategic value and business impact
- Collect success criteria (adoption, usage, outcomes, business)
- Identify component epics (3-8 major work streams)
- Collect timeline and milestones

**For Tasks:**
- Collect task description (what needs to be done)
- Collect motivation/context (why it's needed)
- Optionally collect acceptance criteria
- Optionally collect technical details (files, approach)

**For Bugs:**
- Use bug template (interactive fill-in):
  - Description of problem
  - Version-Release number
  - How reproducible (Always | Sometimes | Rarely)
  - Steps to Reproduce (numbered list)
  - Actual results (include error messages)
  - Expected results (correct behavior)
  - Additional info (logs, screenshots)

**For Feature Requests:**
- Use 4-question workflow:
  1. Proposed title of feature request
  2. Nature and description (current limitations, desired behavior, use case)
  3. Business requirements (customer impact, regulatory drivers, justification)
  4. Affected packages and components (teams, operators, component mapping)

### ✅ Phase 7: Summary Validation

Before security validation, validate the summary format to catch common mistakes:

**Check for anti-patterns:**
1. Summary starts with "As a" (user story format belongs in description)
2. Summary contains "I want" or "so that" (belongs in description)
3. Summary exceeds 100 characters (likely too long, may be full user story)

**Action if anti-pattern detected:**
1. Detect that user put full user story in summary field
2. Extract the key action/feature from the summary
3. Generate a concise alternative (5-10 words)
4. Prompt user for confirmation:
   ```text
   The summary looks like a full user story. Summaries should be concise titles.

   Current: "As a cluster admin, I want to configure ImageTagMirrorSet in HostedCluster CRs so that I can enable tag-based image proxying"

   Suggested: "Enable ImageTagMirrorSet configuration in HostedCluster CRs"

   Use the suggested summary? (yes/no/edit)
   ```

5. If user says yes, use suggested summary
6. If user says edit, prompt for their preferred summary
7. If user says no, use their original summary (but warn it may be truncated in Jira)

**Note:** This validation should happen BEFORE creating the issue, to avoid having to update the summary afterward.

### 🔒 Phase 8: Security Validation

Scan all content (summary, description, comments) for sensitive data:

**Prohibited content:**
- Credentials (usernames/passwords, API tokens)
- Cloud keys (AWS access keys, GCP service accounts, Azure credentials)
- Kubeconfigs (cluster credentials, service account tokens)
- SSH keys (private keys, authorized_keys)
- Certificates (PEM files, private keys)
- URLs with embedded credentials (e.g., `https://user:pass@example.com`)

**Action if detected:**
- STOP issue creation immediately
- Inform user what type of data was detected (without exposing it)
- Ask user to redact sensitive information
- Provide guidance on safe alternatives (placeholder values)

### ✅ Phase 9: Create Issue via MCP

Use the `mcp__atlassian__jira_create_issue` MCP tool with collected parameters.

**Build additional_fields:**

**Required fields (MUST be included):**
- `labels`: `["ai-generated-jira"]` (may be combined with additional labels)

**Security level (determined in Phase 4, applied here):**
- Final value determined by priority: user override > template > global default
- If final value differs from global default, warn user:
  ```text
  ⚠️  Security level: <final value> (differs from your default: <global default>)
  ```

**Project-specific and team-specific fields:**
- Custom field mappings
- Version fields
- Additional labels
- Parent links
- Component names
- Any other project/team-specific requirements

The MCP tool parameters come from the combined guidance of type-specific, project-specific, and team-specific skills, with universal requirements always applied.

**Note:** Project-specific skills (e.g., CNTRLPLANE) may implement fallback strategies for handling creation failures (such as epic linking). Refer to the project-specific skill documentation for these strategies.

### 📤 Phase 10: Return Result

Display to user:
- **Issue Key** (e.g., PROJECT-1234)
- **Issue URL** (direct link to created issue)
- **Summary of applied defaults** (any fields auto-populated by skills)

**Example output:**
```text
Created: PROJECT-1234
Title: <issue summary>
URL: <issue URL>

Applied defaults:
- <Field>: <Value>
- <Field>: <Value>
(varies by project/team)
```text

## Usage Examples

1. **Create a story with minimal info**:
   ```bash
   /jira:create story MYPROJECT "Add user dashboard"
   ```text
   → Prompts for user story format, acceptance criteria, and any required fields

2. **Create a story with options**:
   ```bash
   /jira:create story MYPROJECT "Add search functionality" --component "Frontend" --version "2.5.0"
   ```text
   → Uses provided component and version, prompts only for description and AC

3. **Create an epic with parent feature**:
   ```bash
   /jira:create epic MYPROJECT "Mobile application redesign" --parent MYPROJECT-100
   ```text
   → Links epic to parent feature, prompts for epic details

4. **Create a bug**:
   ```bash
   /jira:create bug MYPROJECT "Login button doesn't work on mobile"
   ```text
   → Prompts for bug template fields (description, steps, actual/expected results)

5. **Create a bug with component**:
   ```bash
   /jira:create bug MYPROJECT "API returns 500 error" --component "Backend"
   ```text
   → Uses specified component, prompts for bug details

6. **Create a task under a story**:
   ```bash
   /jira:create task MYPROJECT "Update API documentation" --parent MYPROJECT-456
   ```text
   → Links task to parent story, prompts for task description

7. **Create a feature**:
   ```bash
   /jira:create feature MYPROJECT "Advanced search capabilities"
   ```text
   → Prompts for market problem, strategic value, success criteria, epic breakdown

8. **Create a feature request**:
   ```bash
   /jira:create feature-request RFE "Support custom SSL certificates for ROSA HCP"
   ```text
   → Prompts for nature/description, business requirements, affected components (4-question workflow)

9. **Create with project-specific conventions** (examples vary by project):
   ```bash
   /jira:create story SPECIALPROJECT "New capability"
   ```
   → Applies SPECIALPROJECT-specific skills and conventions automatically

## Arguments

- **$1 – type** *(required)*
  Issue type to create.
  **Options:** `story` | `epic` | `feature` | `task` | `bug` | `feature-request`

- **$2 – project-key** *(optional for bugs, features, and feature-requests)*
  JIRA project key (e.g., `CNTRLPLANE`, `OCPBUGS`, `OCPSTRAT`, `RFE`, `MYPROJECT`).
  **Default for bugs:** `OCPBUGS`
  **Default for features:** `OCPSTRAT`
  **Default for feature-requests:** `RFE`
  **Required for:** stories, epics, tasks

- **$3 – summary** *(required)*
  Issue title/summary text.
  Use quotes for multi-word summaries: `"Enable automatic scaling"`

- **--component** *(optional)*
  Component name (e.g., `"HyperShift / ROSA"`, `"Networking"`, `"API"`).
  Auto-detected from summary context if not provided (for CNTRLPLANE/OCPBUGS).

- **--version** *(optional)*
  Target version. User input is normalized to Jira format `openshift-X.Y`.

  **Accepted input formats (examples):**
  | User Input | Normalized |
  |------------|------------|
  | `4.21` | `openshift-4.21` |
  | `4.22.0` | `openshift-4.22` |
  | `openshift 4.23` | `openshift-4.23` |
  | `OCP 4.21` | `openshift-4.21` |
  | `ocp 4.22` | `openshift-4.22` |

  **Behavior:** If not provided via flag, user is prompted (optional field).

  **Normalization rules:**
  1. Convert to lowercase
  2. Remove "ocp" or "openshift" prefix (with space or hyphen)
  3. Extract version number (X.Y or X.Y.Z → X.Y)
  4. Prepend "openshift-"

  **Edge cases:**
  | Input | Handling |
  |-------|----------|
  | `openshift-4.21` | Pass through (already normalized) |
  | `v4.21` | Normalize → `openshift-4.21` (strip `v` prefix) |
  | `version 4.21` | Normalize → `openshift-4.21` (strip `version` prefix) |
  | `4` | Prompt for clarification: "Did you mean 4.0, 4.x, or a specific minor version?" |
  | `4.x` | Prompt for clarification: "Which minor version? (e.g., 4.21, 4.22)" |
  | Invalid format | Warn and re-prompt: "Version must be in format X.Y (e.g., 4.21)" |

- **--parent** *(optional)*
  Parent issue key for linking (e.g., `CNTRLPLANE-123`).
  **Valid for:**
  - Epics: Link to parent Feature
  - Tasks: Link to parent Story or Epic
  - Stories: Link to parent Epic (less common)

- **--template** *(optional)*
  Template name to use for issue creation (e.g., `team-story`, `user/my-bug-template`).

  **Template sources:**
  - Published templates: `ocpedge-spike`, `ocpbugs-bug`, `common-story`
  - User templates: `user/my-template`

  **Behavior:**
  - Loads template defaults (priority, components, labels, etc.)
  - Uses template description format with placeholders
  - Prompts for template-specific placeholders
  - Adds `template:<name>` label automatically
  - **Validates template issue type matches command** (warns if mismatch)

  **Template validation:**
  If the template's `issue_type` doesn't match the command type (e.g., `bug` template for `story` command):
  ```text
  ⚠️  WARNING: Template mismatch detected!

  Command issue type: Story
  Template issue type: Bug (from ocpbugs-bug.yaml)

  This may result in incorrect field mappings and validation errors.

  Do you want to proceed anyway? (y/N)
  ```
  - **y** - Proceed with mismatched template (may cause errors)
  - **N** - Abort and allow template correction

  **Examples:**
  ```bash
  /jira:create story <PROJECT> "Add feature" --template <team>-story
  /jira:create bug "Fix crash" --template user/debug-bug

  # This will warn about mismatch:
  /jira:create bug --template <team>-spike
  ```

  **See also:** `/jira:template list` to view available templates

- **--overrides** *(optional)*
  Path to overrides file to apply team or project conventions on top of the base template.

  **Use case:**
  Apply team-specific conventions when creating issues in any project.

  **Supported formats:**
  - Project-relative path: `ocpedge/overrides.yaml`, `cntrlplane/overrides.yaml`
  - User-specific path: `~/.jira-overrides/my-team.yaml`
  - Explicit skip: `none` (disable overrides even if auto-detected)

  **Behavior:**
  - Loads specified overrides file
  - Merges override fields on top of selected template
  - Overrides can include: component requirements, display formats, labels, etc.
  - Field-level `applies_to` patterns control which templates get which overrides

  **Examples:**
  ```bash
  # Use project-relative overrides
  /jira:create bug OCPBUGS "API server crash" --overrides ocpedge/overrides.yaml

  # Use user-specific overrides
  /jira:create story <PROJECT> "New feature" --overrides ~/.jira-overrides/my-team.yaml

  # Explicitly skip overrides
  /jira:create epic OCPEDGE "Major work" --overrides none
  ```

  **Auto-detection:**
  If `--overrides` is not specified:
  - **Project match**: If creating in OCPEDGE and `ocpedge/overrides.yaml` exists → use it automatically
  - **No match**: Prompt user to select overrides:
  ```text
  Creating bug in OCPBUGS project.
  Apply overrides file?
  1. None (use default template)
  2. ocpedge/overrides.yaml (OCPEDGE team conventions)
  3. cntrlplane/overrides.yaml (CNTRLPLANE team conventions)
  4. Other (specify path)

  Select (1-4):
  ```

  **See also:** [Project Overrides](../templates/README.md#project-overrides) for override file format

## Return Value

- **Issue Key**: The created Jira issue identifier (e.g., `CNTRLPLANE-1234`)
- **Issue URL**: Direct link to the created issue
- **Summary**: Confirmation of applied defaults and field values

## Configuration

### Project-Specific Skills

The command automatically detects and applies project-specific conventions:

- **CNTRLPLANE:** Uses `cntrlplane` skill for CNTRLPLANE stories/epics/features/tasks
- **OCPBUGS:** Uses `ocpbugs` skill for OCPBUGS bugs
- **Other projects:** Uses general best practices from type-specific skills

To add conventions for your project, create a skill at:
```text
plugins/jira/skills/your-project-name/SKILL.md
```

Then update the command implementation to invoke your skill when the project is detected.

### Environment Variables

The command respects MCP Jira server configuration:
- **JIRA_PROJECTS_FILTER:** Filter which projects are accessible
- **JIRA_SERVER_URL:** Jira instance URL
- **JIRA_AUTH:** Authentication credentials

## Error Handling

### Invalid Issue Type

**Scenario:** User specifies invalid type.

**Action:**
```text
Invalid issue type "stroy". Valid types: story, epic, feature, task, bug

Did you mean "story"?
```

### Missing Project Key

**Scenario:** Project key required but not provided.

**Action:**
```text
Project key is required for stories/tasks/epics/features.

Usage: /jira:create story PROJECT-KEY "summary"

Example: /jira:create story CNTRLPLANE "Enable autoscaling"
```

### Component Required But Not Provided

**Scenario:** Project requires component, cannot auto-detect, user didn't specify.

**Action:**
```text
Component is required for CNTRLPLANE issues. Which component?
1. HyperShift / ARO - for ARO HCP (Azure) issues
2. HyperShift / ROSA - for ROSA HCP (AWS) issues
3. HyperShift - for platform-agnostic issues

Select a component (1-3):
```

### Parent Issue Not Found

**Scenario:** User specifies `--parent` but issue doesn't exist.

**Action:**
```text
Parent issue CNTRLPLANE-999 not found.

Options:
1. Proceed without parent link
2. Specify different parent
3. Cancel creation

What would you like to do?
```

### Security Validation Failure

**Scenario:** Credentials or secrets detected.

**Action:**
```text
I detected what appears to be an API token in the description.

Please review and redact before proceeding. Use placeholder values like:
- YOUR_API_KEY
- <redacted>
- ********

Would you like to edit the description?
```

### MCP Tool Error

**Scenario:** MCP tool returns an error.

**Action:**
1. Parse error message
2. Translate to user-friendly explanation
3. Suggest corrective action
4. Offer to retry

**Common errors:**
- **"Field 'component' is required"** → Prompt for component
- **"Version not found"** → Fetch available versions, suggest closest match
- **"Permission denied"** → User may lack permissions, suggest contacting admin
- **"Issue type not available"** → Project may not support this issue type

### Epic Link Creation Failure

**Scenario:** Story/task creation fails when including epic link field.

**Action:**
Refer to project-specific skills for epic linking fallback strategies:
- **CNTRLPLANE:** See CNTRLPLANE skill "Epic Linking Implementation Strategy" section
- **Other projects:** Consult project-specific skill documentation

**General pattern:**
1. Detect error related to linking (error contains "epic", "parent", "link", or "customfield")
2. Check project-specific skill for recommended fallback approach
3. Typically: Create without link, then link via update
4. Inform user of outcome
5. **Last stand fallback:** If all strategies fail (including update-after-create), retry with absolute minimal fields:
   - Remove ALL custom fields (epic link, target version, etc.)
   - Keep only: project_key, summary, issue_type, description, assignee, components
   - Log to console what was stripped out
   - If this succeeds, inform user which fields need manual configuration in Jira

### Field Format Error

**Scenario:** Field provided in wrong format (e.g., Target Version as string instead of array).

**Common field format errors:**

1. **Target Version format**
   - ❌ Wrong: `"customfield_12319940": "openshift-4.21"`
   - ✅ Correct: `"customfield_12319940": [{"id": "12448830"}]`
   - **Action:** Fetch version ID using `mcp__atlassian__jira_get_project_versions`, convert to correct format

2. **Epic Link format**
   - ❌ Wrong: `"parent": {"key": "EPIC-123"}` (for stories)
   - ✅ Correct: `"customfield_12311140": "EPIC-123"` (string, not object)
   - **Action:** Convert to correct format and retry

3. **Component format**
   - ❌ Wrong: `"components": "ComponentName"`
   - ✅ Correct: `"components": ["ComponentName"]` (array) or just `"ComponentName"` (MCP accepts both)
   - **Action:** Ensure consistent format

**Detection:**
- Parse error message for field names
- Check skill documentation for correct format
- Automatically convert and retry when possible

## Best Practices

1. **Use descriptive summaries:** Include relevant keywords for context and auto-detection
2. **Provide flags when known:** Use `--component` and `--version` to skip prompts
3. **Link related work:** Use `--parent` to maintain hierarchy
4. **Review before submit:** Check the formatted content before confirming creation
5. **Follow templates:** Use the provided templates for consistency
6. **Sanitize content:** Remove credentials before including logs or screenshots

## Anti-Patterns to Avoid

❌ **Wrong issue type**
```text
/jira:create story MYPROJECT "Refactor database layer"
```
✅ This is technical work, use `task` instead

❌ **Vague summaries**
```text
/jira:create bug "Something is broken"
```
✅ Be specific: "API server returns 500 error when creating namespaces"

❌ **Missing context**
```text
/jira:create epic MYPROJECT "Improve things"
```
✅ Be descriptive: "Mobile application redesign"

❌ **Including credentials**
```text
Steps to reproduce:
1. Export API_KEY=sk_live_abc123xyz
```
✅ Use placeholders: "Export API_KEY=YOUR_API_KEY"

## See Also

- `jira:solve` - Analyze and solve Jira issues
- `jira:grooming` - Generate grooming meeting agendas
- `jira:status-rollup` - Create status rollup reports
- `jira:generate-test-plan` - Generate test plans for PRs

## Skills Reference

The following skills are automatically invoked by this command:

**Unified creation skill:**
- **create-issue** - Template-driven workflow for all issue types (story, epic, feature, task, bug, spike, feature-request)
  - Loads appropriate template based on project + issue type
  - Displays educational guide reference
  - Generates interactive prompts from template metadata
  - Applies validation rules from template
  - See `plugins/jira/skills/create-issue/SKILL.md` for details

**Educational guides:**
- `plugins/jira/docs/issue-types/epic.md` - Epic best practices
- `plugins/jira/docs/issue-types/story.md` - User story guide
- `plugins/jira/docs/issue-types/task.md` - Task guide
- `plugins/jira/docs/issue-types/bug.md` - Bug report guide
- `plugins/jira/docs/issue-types/spike.md` - Spike guide
- `plugins/jira/docs/issue-types/feature.md` - Feature guide

**Project-specific skills:**
- **cntrlplane** - CNTRLPLANE project conventions (stories, epics, features, tasks)
- **ocpbugs** - OCPBUGS project conventions (bugs only)

**Team-specific skills:**
- **hypershift** - HyperShift team conventions (component selection for ARO/ROSA/HyperShift)

To view skill details:
```bash
cat plugins/jira/skills/create-issue/SKILL.md
cat plugins/jira/docs/issue-types/epic.md
cat plugins/jira/skills/cntrlplane/SKILL.md
cat plugins/jira/skills/ocpbugs/SKILL.md
cat plugins/jira/skills/hypershift/SKILL.md
```
