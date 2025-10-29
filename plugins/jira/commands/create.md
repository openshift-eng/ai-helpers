---
description: Create Jira issues (story, epic, feature, task, bug) with proper formatting
argument-hint: <type> [project-key] <summary> [--component <name>] [--version <version>] [--parent <key>]
---

## Name
jira:create

## Synopsis
```
/jira:create <type> [project-key] <summary> [options]
```

## Description
The `jira:create` command creates Jira issues following best practices and team-specific conventions. It supports creating stories, epics, features, tasks, and bugs with intelligent defaults, interactive prompts, and validation.

This command is particularly useful for:
- Creating well-formed user stories with acceptance criteria
- Organizing epics and features with proper hierarchy
- Submitting bugs with complete reproduction steps
- Maintaining consistency across team Jira practices

## Key Features

- **Multi-Type Support** - Create stories, epics, features, tasks, or bugs from a single command
- **Smart Defaults** - Automatically applies project-specific conventions (e.g., CNTRLPLANE, OCPBUGS)
- **Interactive Guidance** - Prompts for missing information with helpful templates
- **Context Detection** - Analyzes summary text to suggest components (ARO, ROSA, HyperShift)
- **Security Validation** - Scans for credentials and secrets before submission
- **Template Support** - Provides user story templates, bug report templates, acceptance criteria formats

## Implementation

The `jira:create` command runs in multiple phases:

### 🎯 Phase 1: Load Implementation Guidance

Invoke the appropriate skill based on issue type using the Skill tool:

- **Type: `story`** → Invoke `jira:create-story` skill
  - Loads user story template guidance
  - Provides acceptance criteria formats
  - Offers story quality validation

- **Type: `epic`** → Invoke `jira:create-epic` skill
  - Loads epic structure guidance
  - Provides epic name field handling
  - Offers parent feature linking workflow

- **Type: `feature`** → Invoke `jira:create-feature` skill
  - Loads strategic planning guidance
  - Provides market problem framework
  - Offers success criteria templates

- **Type: `task`** → Invoke `jira:create-task` skill
  - Loads technical task guidance
  - Provides task vs story differentiation
  - Offers acceptance criteria for technical work

- **Type: `bug`** → Invoke `jira:create-bug` skill
  - Loads bug report template
  - Provides structured reproduction steps
  - Offers severity and reproducibility guidance

### 🏢 Phase 2: Apply Project-Specific Conventions

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

**General projects** use only the type-specific skills (create-story, create-bug, etc.) for best practices.

### 📝 Phase 3: Parse Arguments & Detect Context

Parse command arguments:
- **Required:** `type`, `summary`
- **Optional:** `project_key` (may have project-specific defaults)
- **Optional flags:** `--component`, `--version`, `--parent`

Analyze summary text for context clues:
- Extract keywords that may indicate team, component, or platform
- Pass context to project-specific and team-specific skills for interpretation
- Skills handle keyword detection and component/field suggestions

### ⚙️ Phase 4: Apply Smart Defaults

**Universal requirements (MUST be applied to ALL tickets):**
- **Security level:** Red Hat Employee (required)
- **Labels:** ai-generated-jira (required)

**Project defaults:**
- May include default project for certain issue types
- Version defaults (if applicable)
- Additional labels (for tracking or automation)

**Team defaults:**
- Component selection (based on keywords or prompts)
- Custom field values
- Workflow-specific requirements

**General projects:**
- Use type-specific skills for issue structure
- Prompt for required fields as needed

### 💬 Phase 5: Interactive Prompts (Hybrid Approach)

Prompt for missing required information based on issue type:

**For Stories:**
- Offer user story template: "As a... I want... So that..."
- Collect acceptance criteria (suggest formats)
- Confirm auto-detected component

**For Epics:**
- Collect epic objective and scope
- Collect epic acceptance criteria
- Collect timeline/target release
- Set epic name field (same as summary)
- Optional parent feature link (via `--parent` or prompt)

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

### 🔒 Phase 6: Security Validation

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

### ✅ Phase 7: Create Issue via MCP

Use the `mcp__atlassian__jira_create_issue` MCP tool with collected parameters.

**Build additional_fields:**

**Required fields (MUST be included):**
- `security`: `{"name": "Red Hat Employee"}`
- `labels`: `["ai-generated-jira"]` (may be combined with additional labels)

**Project-specific and team-specific fields:**
- Custom field mappings
- Version fields
- Additional labels
- Parent links
- Component names
- Any other project/team-specific requirements

The MCP tool parameters come from the combined guidance of type-specific, project-specific, and team-specific skills, with universal requirements always applied.

### 📤 Phase 8: Return Result

Display to user:
- **Issue Key** (e.g., PROJECT-1234)
- **Issue URL** (direct link to created issue)
- **Summary of applied defaults** (any fields auto-populated by skills)

**Example output:**
```
Created: PROJECT-1234
Title: <issue summary>
URL: <issue URL>

Applied defaults:
- <Field>: <Value>
- <Field>: <Value>
(varies by project/team)
```

## Usage Examples

1. **Create a story with minimal info**:
   ```
   /jira:create story MYPROJECT "Add user dashboard"
   ```
   → Prompts for user story format, acceptance criteria, and any required fields

2. **Create a story with options**:
   ```
   /jira:create story MYPROJECT "Add search functionality" --component "Frontend" --version "2.5.0"
   ```
   → Uses provided component and version, prompts only for description and AC

3. **Create an epic with parent feature**:
   ```
   /jira:create epic MYPROJECT "Mobile application redesign" --parent MYPROJECT-100
   ```
   → Links epic to parent feature, prompts for epic details

4. **Create a bug**:
   ```
   /jira:create bug MYPROJECT "Login button doesn't work on mobile"
   ```
   → Prompts for bug template fields (description, steps, actual/expected results)

5. **Create a bug with component**:
   ```
   /jira:create bug MYPROJECT "API returns 500 error" --component "Backend"
   ```
   → Uses specified component, prompts for bug details

6. **Create a task under a story**:
   ```
   /jira:create task MYPROJECT "Update API documentation" --parent MYPROJECT-456
   ```
   → Links task to parent story, prompts for task description

7. **Create a feature**:
   ```
   /jira:create feature MYPROJECT "Advanced search capabilities"
   ```
   → Prompts for market problem, strategic value, success criteria, epic breakdown

8. **Create with project-specific conventions** (examples vary by project):
   ```
   /jira:create story SPECIALPROJECT "New capability"
   ```
   → Applies SPECIALPROJECT-specific skills and conventions automatically

## Arguments

- **$1 – type** *(required)*
  Issue type to create.
  **Options:** `story` | `epic` | `feature` | `task` | `bug`

- **$2 – project-key** *(optional for bugs)*
  JIRA project key (e.g., `CNTRLPLANE`, `OCPBUGS`, `MYPROJECT`).
  **Default for bugs:** `OCPBUGS`
  **Required for:** stories, epics, features, tasks

- **$3 – summary** *(required)*
  Issue title/summary text.
  Use quotes for multi-word summaries: `"Enable automatic scaling"`

- **--component** *(optional)*
  Component name (e.g., `"HyperShift / ROSA"`, `"Networking"`, `"API"`).
  Auto-detected from summary context if not provided (for CNTRLPLANE/OCPBUGS).

- **--version** *(optional)*
  Target version (e.g., `"4.21"`, `"4.22"`, `"2.5.0"`).
  **Default varies by project:**
  - CNTRLPLANE/OCPBUGS: `openshift-4.21`
  - Other projects: Prompt or use project default

- **--parent** *(optional)*
  Parent issue key for linking (e.g., `CNTRLPLANE-123`).
  **Valid for:**
  - Epics: Link to parent Feature
  - Tasks: Link to parent Story or Epic
  - Stories: Link to parent Epic (less common)

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
```
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
```
Invalid issue type "stroy". Valid types: story, epic, feature, task, bug

Did you mean "story"?
```

### Missing Project Key

**Scenario:** Project key required but not provided.

**Action:**
```
Project key is required for stories/tasks/epics/features.

Usage: /jira:create story PROJECT-KEY "summary"

Example: /jira:create story CNTRLPLANE "Enable autoscaling"
```

### Component Required But Not Provided

**Scenario:** Project requires component, cannot auto-detect, user didn't specify.

**Action:**
```
Component is required for CNTRLPLANE issues. Which component?
1. HyperShift / ARO - for ARO HCP (Azure) issues
2. HyperShift / ROSA - for ROSA HCP (AWS) issues
3. HyperShift - for platform-agnostic issues

Select a component (1-3):
```

### Parent Issue Not Found

**Scenario:** User specifies `--parent` but issue doesn't exist.

**Action:**
```
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
```
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

## Best Practices

1. **Use descriptive summaries:** Include relevant keywords for context and auto-detection
2. **Provide flags when known:** Use `--component` and `--version` to skip prompts
3. **Link related work:** Use `--parent` to maintain hierarchy
4. **Review before submit:** Check the formatted content before confirming creation
5. **Follow templates:** Use the provided templates for consistency
6. **Sanitize content:** Remove credentials before including logs or screenshots

## Anti-Patterns to Avoid

❌ **Wrong issue type**
```
/jira:create story MYPROJECT "Refactor database layer"
```
✅ This is technical work, use `task` instead

❌ **Vague summaries**
```
/jira:create bug "Something is broken"
```
✅ Be specific: "API server returns 500 error when creating namespaces"

❌ **Missing context**
```
/jira:create epic MYPROJECT "Improve things"
```
✅ Be descriptive: "Mobile application redesign"

❌ **Including credentials**
```
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

**Type-specific skills:**
- **create-story** - User story creation guidance
- **create-epic** - Epic creation and structure
- **create-feature** - Feature planning and strategy
- **create-task** - Technical task creation
- **create-bug** - Bug report templates

**Project-specific skills:**
- **cntrlplane** - CNTRLPLANE project conventions (stories, epics, features, tasks)
- **ocpbugs** - OCPBUGS project conventions (bugs only)

**Team-specific skills:**
- **hypershift** - HyperShift team conventions (component selection for ARO/ROSA/HyperShift)

To view skill details:
```bash
ls plugins/jira/skills/
cat plugins/jira/skills/create-story/SKILL.md
cat plugins/jira/skills/cntrlplane/SKILL.md
cat plugins/jira/skills/ocpbugs/SKILL.md
cat plugins/jira/skills/hypershift/SKILL.md
```
