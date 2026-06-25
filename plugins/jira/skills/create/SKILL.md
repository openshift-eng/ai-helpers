---
name: create
description: Create Jira issues — story, bug, epic, feature, task, or feature-request — with CNTRLPLANE, OCPBUGS, GCP, HyperShift, ARO, ROSA conventions and type-specific templates
---

# Create Jira Issue

```bash
/jira:create <type> [project-key] <summary> [--component <name>] [--version <version>] [--parent <key>]
```

Creates Jira issues following best practices and team-specific conventions. Supports stories, epics, features, tasks, bugs, and feature requests with intelligent defaults, interactive prompts, and validation.

## Type-Specific Guidance

Load the reference file matching the issue type for templates, interactive workflows, and best practices:

| Type | Reference | Key Content |
|---|---|---|
| **story** | [Story guide](../../reference/create-story.md) | User story format, acceptance criteria, summary vs description |
| **bug** | [Bug guide](../../reference/create-bug.md) | Bug template, steps to reproduce, reproducibility |
| **epic** | [Epic guide](../../reference/create-epic.md) | Epic Name field, scope/timeline, parent Feature linking |
| **feature** | [Feature guide](../../reference/create-feature.md) | Market problem, strategic value, success criteria |
| **task** | [Task guide](../../reference/create-task.md) | Task vs story distinction, action-verb summaries |
| **feature-request** | [Feature Request guide](../../reference/create-feature-request.md) | RFE project, 4-question workflow, business requirements |

Also load [Markdown for Jira](../../reference/markdown-for-jira.md) for description formatting.

## Arguments

- **type** *(required)* — `story` | `epic` | `feature` | `task` | `bug` | `feature-request`
- **project-key** *(optional for bugs and feature-requests)* — e.g., `CNTRLPLANE`, `OCPBUGS`, `RFE`. Default for bugs: `OCPBUGS`. Default for feature-requests: `RFE`.
- **summary** *(required)* — Issue title. Use quotes for multi-word: `"Enable automatic scaling"`
- **--component** *(optional)* — Component name. Auto-detected from summary for known projects.
- **--version** *(optional)* — Target version. Normalized to `openshift-X.Y` per project conventions.
- **--parent** *(optional)* — Parent issue key for linking (e.g., `CNTRLPLANE-123`).

## Implementation Phases

### Phase 1: Load Guidance

1. Load the type-specific reference file from the table above
2. Invoke the `jira:jira-conventions` skill when the project key, component, or summary keywords match a known project or team

### Phase 2: Parse Arguments & Detect Context

Parse required and optional arguments. Analyze summary text for context clues (team, component, platform keywords).

### Phase 3: Apply Smart Defaults

**Universal requirements (ALL tickets):**

```
"labels": ["ai-generated-jira"]
"security": {"name": "Red Hat Employee"}
contentFormat: "markdown"
```

Project and team defaults (version, component, labels) come from the `jira-conventions` skill.

### Phase 4: Interactive Prompts

Follow the type-specific reference file's interactive workflow to collect missing information (story format, bug template sections, epic scope, etc.).

### Phase 5: Summary Validation

Check for anti-patterns before creation:

1. Summary starts with "As a" or contains "I want" / "so that" → belongs in description
2. Summary exceeds 100 characters → likely too long

If detected:
```plaintext
The summary looks like a full user story. Summaries should be concise titles.

Current: "As a cluster admin, I want to configure ImageTagMirrorSet in HostedCluster CRs so that I can enable tag-based image proxying"

Suggested: "Enable ImageTagMirrorSet configuration in HostedCluster CRs"

Use the suggested summary? (yes/no/edit)
```

### Phase 6: Security Validation

Scan all content (summary, description) for sensitive data:

- Credentials, API tokens, cloud keys (AWS, GCP, Azure)
- Kubeconfigs, SSH keys, certificates, PEM files
- URLs with embedded credentials

If detected: STOP creation, inform user of the type found (without echoing it), suggest placeholder values.

### Phase 7: Create Issue via MCP

Use `createJiraIssue` with collected parameters. Include universal fields and any project/team-specific fields.

### Phase 8: Return Result

```plaintext
Created: PROJECT-1234
Title: <issue summary>
URL: <issue URL>

Applied defaults:
- <Field>: <Value>
```

## Custom Fields (redhat.atlassian.net)

| Field | ID | Type | Usage |
|---|---|---|---|
| Epic Link | `customfield_10014` | String | Links Story/Task/Bug → parent Epic |
| Parent Link | `customfield_10018` | String | Links Epic → parent Feature |
| Epic Name | `customfield_10011` | String | Required for Epics; must match summary |
| Target Version | `customfield_10855` | Array | Format: `[{"id": "VERSION_ID"}]` — fetch via `getJiraIssueTypeMetaWithFields`. Some projects use string format; project conventions take precedence |

## Issue Hierarchy and Parent Linking

```plaintext
Feature → Epic → Story/Task
```

### Field Reference

| Relationship | Field | Value Format |
|---|---|---|
| Story → Epic | `customfield_10014` (Epic Link) | `"PROJ-123"` (string) |
| Task → Epic | `customfield_10014` (Epic Link) | `"PROJ-123"` (string) |
| Task → Story | `customfield_10014` (Epic Link) | `"PROJ-123"` (string) |
| Bug → Epic | `customfield_10014` (Epic Link) | `"PROJ-123"` (string) |
| Epic → Feature | `customfield_10018` (Parent Link) | `"PROJ-123"` (string) |

The standard `parent` field does NOT work for these relationships.

### Pre-Validation (when `--parent` is provided)

Fetch the parent via `getJiraIssue` to verify it exists and its type matches the hierarchy:

| Creating | Parent Should Be | If Wrong Type |
|----------|------------------|---------------|
| Story | Epic | Warn user, ask to confirm or correct |
| Task | Epic or Story | Warn user, ask to confirm or correct |
| Epic | Feature | Warn user, ask to confirm or correct |

If parent not found, offer options: proceed without parent, specify different parent, or cancel.

### Parent Linking Fallback

Some projects require creating without the parent link and updating separately — project conventions take precedence over this generic fallback.

If creation fails with a 4xx error referencing `customfield_10014` or `customfield_10018`:

1. **Duplicate guard:** Search for an issue with the same summary in the target project — the original call may have partially succeeded
2. **Retry** WITHOUT the parent/epic link field
3. **Link via update:** Call `editJiraIssue` (with `contentFormat: "markdown"`) to set the link field
4. **Report outcome:** If the update also fails, inform the user and suggest manual linking
5. **Last stand fallback:** If all strategies fail, retry with absolute minimal fields (project, summary, type, description only). Inform user which fields need manual configuration.

### Common Parent Linking Errors

| Error Message | Cause | Solution |
|---|---|---|
| `Field 'parent' does not exist` | Using standard `parent` field | Use `customfield_10018` or `customfield_10014` |
| `customfield_10014 is not valid` | Epic Link field issue | Use fallback: create then update |
| `customfield_10018 is not valid` | Parent Link field issue | Use fallback: create then update |
| `Parent issue not found` | Invalid parent key | Verify parent exists first |
| `Cannot link to issue of type X` | Wrong parent type | Verify hierarchy |

## Error Handling

### Invalid Issue Type

```plaintext
Invalid issue type "stroy". Valid types: story, epic, feature, task, bug, feature-request

Did you mean "story"?
```

### Missing Project Key

```plaintext
Project key is required for stories/tasks/epics/features.

Usage: /jira:create story PROJECT-KEY "summary"
```

### Field Format Errors

| Field | Wrong | Correct |
|---|---|---|
| Target Version | `"customfield_10855": "openshift-4.21"` | `"customfield_10855": [{"id": "12448830"}]` |
| Epic Link | `"parent": {"key": "EPIC-123"}` | `"customfield_10014": "EPIC-123"` (string) |
| Component | `"components": "Name"` | `"components": ["Name"]` (array) |

### MCP Tool Errors

- **"Field 'component' is required"** → Prompt for component
- **"Version not found"** → Fetch available versions, suggest closest match
- **"Permission denied"** → User may lack permissions
- **"Issue type not available"** → Project may not support this type

## Usage Examples

```bash
/jira:create story CNTRLPLANE "Add user dashboard"
/jira:create story CNTRLPLANE "Add search" --component "Frontend" --version "4.22"
/jira:create epic CNTRLPLANE "Mobile redesign" --parent CNTRLPLANE-100
/jira:create bug "API returns 500 error" --component "Backend"
/jira:create task CNTRLPLANE "Update API docs" --parent CNTRLPLANE-456
/jira:create feature CNTRLPLANE "Advanced search capabilities"
/jira:create feature-request RFE "Support custom SSL certificates for ROSA HCP"
```

## Configuration

### Project and Team Conventions

The `jira-conventions` skill automatically detects and applies conventions:

- **CNTRLPLANE:** version normalization, parent linking fields
- **OCPBUGS:** bug-specific version fields
- **GCP:** team templates, sizing guide, priority scheme
- **HyperShift:** component selection (ARO/ROSA/HyperShift)

To add conventions for your project, create a reference file at `plugins/jira/reference/your-project.md` and add a routing entry to `plugins/jira/skills/jira-conventions/SKILL.md`.

## Best Practices

1. Use descriptive summaries with relevant keywords for auto-detection
2. Provide `--component` and `--version` flags when known to skip prompts
3. Use `--parent` to maintain issue hierarchy
4. Sanitize content — remove credentials before including logs

## Anti-Patterns

- **Wrong type:** `/jira:create story "Refactor database"` → technical work, use `task`
- **Vague summary:** `/jira:create bug "Something is broken"` → be specific
- **Credentials in content:** Use placeholders like `YOUR_API_KEY`
