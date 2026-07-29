---
name: create-jira-from-file
description: >
  Create Jira issues from a markdown file (single or batch). Use whenever the user
  asks to create Jira from a file, create tickets/issues from markdown, batch-create
  Jira issues from a planning doc, or run /jira:create-jira-from-file. Project-agnostic —
  extracts Project, Type, Component, Version, Parent, Priority, and Labels from the file.
argument-hint: "<path-to-markdown-file>"
effort: medium
---

# Create Jira from Markdown

Project-agnostic skill that creates one or more Jira issues from a markdown file. Extracts ALL metadata from the markdown file itself — makes no assumptions about projects, components, or versions.

**Examples:** [`../../examples/create-jira-from-file-single-story.md`](../../examples/create-jira-from-file-single-story.md), [`../../examples/create-jira-from-file-batch.md`](../../examples/create-jira-from-file-batch.md)

## Model notes (optional)

When the host allows choosing models, prefer a lighter model for ingest/plan/summarize and a stronger model for parse, validate, and execute. Most sessions run on a single model — treat the table as guidance only, not a hard requirement.

| Phase | Prefer | Why |
|-------|--------|-----|
| 1. Ingest | lighter | File I/O and pattern detection |
| 2. Parse | stronger | Markdown structure extraction |
| 3. Plan | lighter | Table formatting |
| 4. Validate | stronger | Credential scanning |
| 5. Execute | stronger | API orchestration |
| 6. Summarize | lighter | Result reporting |

---

## Prerequisites

Before starting:
1. Atlassian MCP server must be authenticated (`/mcp` → Atlassian → check status)
2. User must provide a markdown file path (via `$ARGUMENTS` or message)
3. User must have Jira create permissions for the target project(s)
4. The markdown file must be readable and contain required metadata

If MCP server is not authenticated, instruct the user to run `/mcp` and authenticate before proceeding.

---

## Phase 1: Ingest & Mode Detection

**Task Complexity:** Low (file I/O and pattern matching)

### Read the Markdown File

```markdown
1. Read file from $ARGUMENTS (first argument is the file path)
2. Verify file is readable and exists
3. Check file is markdown (.md) or text format
4. Do NOT process binary files or executables
```

### Detect Mode

Determine if this is single-issue mode or batch mode:

**Batch Mode Indicators:**
- File contains multiple H2 headers with type prefixes (two equivalent formats are supported):
  - Colon format: `## Story: <summary>`, `## Bug: <summary>`, `## Task: <summary>`, `## Epic: <summary>`, `## Feature: <summary>`, `## Initiative: <summary>`, `## Sub-task: <summary>`
  - Bracket format: `## [Story] <summary>`, `## [Bug] <summary>`, `## [Task] <summary>`, `## [Epic] <summary>`, `## [Feature] <summary>`, `## [Initiative] <summary>`, `## [Sub-task] <summary>`

**OR:**
- File contains multiple issue-boundary headings separated by horizontal rules (`---`) — see rule 3 below (a lone `---` is not enough)

**Single Issue Mode:**
- Everything else (one H1, no type-prefixed H2s, or simple structure)

**Detection Logic (checked in order):**

1. **Type-prefixed H2 headers:** Count headers matching `^## (Story|Bug|Task|Epic|Feature|Initiative|Sub-task)[:\[]`
   - If count >= 2: BATCH MODE

2. **Plain H2 headers:** Count H2 headers that are NOT known content-section names
   - Known content sections (not issue boundaries): Description, Overview, Acceptance Criteria, AC, Steps to Reproduce, Repro Steps, Expected Behavior, Actual Behavior, Environment, Technical Notes, Implementation Notes, Testing Notes, Context, Dependencies, Notes, Background, Definition of Done, Reminder, User Story
   - If count of non-content H2s >= 2 AND no type prefixes: BATCH MODE
   - A single issue with only content-section H2s (e.g., `## Acceptance Criteria`, `## Context`) is NOT batch

3. **Separator-based (strict):** Strip YAML front matter (`---` block at the very start of the file) first
   - Count remaining horizontal rules (`---` alone on a line)
   - Count issue-boundary titles in remaining content: H1 headers **or** non-content H2 headers (same exclusion list as rule 2)
   - BATCH MODE only if **both** are true:
     - separators >= 1 **and** issue-boundary titles >= 2
   - A single-issue doc with one thematic `---` break must stay SINGLE ISSUE MODE

Otherwise: SINGLE ISSUE MODE

### Output

Inform user which mode was detected and proceed to Phase 2.

---

## Phase 2: Parse & Extract

**Goal:** Parse markdown input and extract structured metadata, summaries, and content sections for each issue. Auto-detect issue types and handle both single-issue and batch modes.

---

### Metadata Extraction

Extract inline metadata from **bold key:** patterns anywhere in the markdown:

- **Project:** → `project` (REQUIRED; if missing, prompt user: "Which project should this issue be created in?" — do not fail immediately)
- **Type:** → `type` (Story, Task, Bug, Epic, Feature, Initiative, Sub-task; optional, can be auto-detected)
- **Component:** → `component` (optional)
- **Version:** → `version` (optional)
- **Parent:** → `parent_key` (epic/story key like PROJ-123; optional)
- **Priority:** → `priority` (optional)
- **Labels:** → `labels` (comma-separated; optional)

**Rules:**
- Case-insensitive matching for keys (e.g., **project:**, **PROJECT:**, **Project:** all match)
- Values are trimmed strings after the colon
- **Labels:** can be comma/space-separated; normalize to array
- If multiple instances of same key exist, last one wins
- Remove metadata lines from content sections after extraction

---

### Summary Extraction

**Single mode:** Extract from first H1 (`# Summary text`)
- Use full H1 text as summary
- If no H1 exists, try fallbacks in order: (1) first non-empty sentence, (2) filename without extension
- If all fallbacks fail, prompt user: "No title found. Enter a summary for this issue:"

**Batch mode:** Extract from H2 headers with type prefixes
- Pattern: `## [Type] Summary text` or `## Summary text`
- Examples: `## [Story] User login`, `## Add dashboard widget`
- Strip type prefix if present (handled in Type Auto-Detection)
- Use remaining text as summary

**Validation:**
- Summary must be non-empty after trimming
- Warn if summary exceeds 255 characters (Jira limit)

---

### Content Section Extraction

Map H2/H3 headings to Jira fields based on common patterns:

**Standard mappings:**
- `Description` / `Overview` → `description`
- `Acceptance Criteria` / `AC` → `acceptance_criteria`
- `Steps to Reproduce` / `Repro Steps` → `steps_to_reproduce`
- `Expected Behavior` / `Expected` → `expected_behavior`
- `Actual Behavior` / `Actual` → `actual_behavior`
- `Environment` → `environment`
- `Technical Notes` / `Implementation Notes` → `technical_notes`
- `Testing Notes` → `testing_notes`

**User story patterns:**
- `As a ... I want ... So that ...` → extract to `user_story` field
- `Story` / `User Story` heading → `user_story`

**Extraction rules:**
- Collect all content under heading until next same-level or higher heading
- Preserve markdown formatting (lists, code blocks, etc.)
- If multiple sections map to same field, concatenate with double newline
- Sections not matching known patterns → append to `description` with heading as bold prefix

---

### Type Auto-Detection

If **Type:** not explicitly provided, detect from content patterns:

**Story indicators:**
- H2/H3 heading contains "User Story", "Story", "Acceptance Criteria"
- Content contains "As a ... I want ... So that ..." pattern
- Default type if batch mode H2 starts with `[Story]`

**Bug indicators:**
- Contains sections: "Steps to Reproduce", "Expected Behavior", "Actual Behavior"
- H2/H3 headings: "Repro Steps", "Environment", "Error", "Bug"
- Default type if batch mode H2 starts with `[Bug]`

**Task indicators:**
- No story or bug patterns detected
- Contains: "TODO", "Implementation", "Technical Notes"

**Epic indicators:**
- Explicitly set via **Type:** or batch prefix `[Epic]` / `Epic:`
- Cannot be auto-detected from content

**Feature indicators:**
- Explicitly set via **Type:** or batch prefix `[Feature]` / `Feature:`
- Cannot be auto-detected from content

**Initiative indicators:**
- Explicitly set via **Type:** or batch prefix `[Initiative]` / `Initiative:`
- Cannot be auto-detected from content

**Sub-task indicators:**
- Explicit `**Type:** Sub-task` in metadata
- Batch mode H2 prefix `[Sub-task]` / `Sub-task:`
- Cannot be auto-detected from content — a `**Parent:**` field alone does NOT imply Sub-task (Stories, Tasks, and Epics can also have parents)

**Fallback:** Leave type as `null` — Phase 4 validation will detect the missing type and prompt the user to specify it interactively

---

### Batch Mode Splitting

**Detection:** Input contains multiple H2 headers OR `---` separators

**Splitting strategies:**

1. **Type-prefixed H2 headers** (colon or bracket format):
   ```markdown
   ## Story: First issue      # colon format
   Content...

   ## [Bug] Second issue      # bracket format
   Content...
   ```
   Split on `## <Type>:` or `## [<Type>]` patterns

2. **Plain H2 headers:**
   ```markdown
   ## First issue summary
   Content...
   
   ## Second issue summary
   Content...
   ```
   Split on each `##` at start of line

3. **Separator-based:**
   ```markdown
   # First issue
   Content...
   
   ---
   
   # Second issue
   Content...
   ```
   Split on `---` (three or more dashes on own line)

**Batch processing:**
- Each section inherits metadata from top-level **Key:** declarations
- Section-local **Key:** overrides inherited values
- Parse and extract each section independently
- Return array of issue objects with metadata + content

**Validation:**
- Each batch entry must have summary (H1 or H2)
- Each batch entry must have **Project:** (inherited or local)
- Warn if batch contains mixed projects

---

### Output Format

Return structured data for Phase 3:

```json
{
  "mode": "single | batch",
  "issues": [
    {
      "id": 0,
      "project": "PROJ",
      "type": "Story",
      "summary": "Issue summary",
      "component": "ComponentName",
      "version": "v1.2.3",
      "parent_key": "PROJ-123",
      "priority": "High",
      "labels": ["label1", "label2"],
      "description": "Full description text...",
      "acceptance_criteria": "AC text...",
      "user_story": "As a... I want... So that...",
      "expected_behavior": "Expected outcome...",
      "actual_behavior": "Actual outcome...",
      "environment": "Environment details...",
      "technical_notes": "Implementation details...",
      "testing_notes": "Testing details..."
    }
  ]
}
```

**Critical:** Never assume or infer project codes, component names, or version strings. Only use explicitly provided values. If required fields are missing, prompt the user interactively rather than failing immediately.

`id` is assigned during parsing as a zero-based sequential integer matching the issue's position in the `issues` array. It is used as the stable key for all creation-state tracking maps (`created_jira_keys`, `jira_key_to_issue_id`, `failed_batch_ids`) throughout Phase 5.

---

## Phase 3: Plan & Review

**Task Complexity:** Low-Medium (formatting and presentation)

### Present Extracted Issues

**For Batch Mode:**

```text
Extracted Issues from Markdown:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| # | Type  | Project | Summary                  | Component | Version | Parent |
|---|-------|---------|--------------------------|-----------|---------|--------|
| 1 | Story | PROJ-A  | Add user dashboard       | Frontend  | 2.5     | -      |
| 2 | Bug   | PROJ-B  | API returns 500 error    | Backend   | 3.1     | -      |
| 3 | Task  | PROJ-A  | Update API docs          | Docs      | 2.5     | PROJ-A-100 |

Total: 3 issues
Projects: PROJ-A (2), PROJ-B (1)
Types: Story (1), Bug (1), Task (1)
```

For each issue, show:
- Type, Project, Summary
- Component (or "none" if not specified)
- Version (or "none" if not specified)
- Parent (or "none" if not specified)
- Priority, custom labels (if specified)
- First 100 characters of description

**For Single Issue Mode:**

```text
Extracted Issue:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Type:        Story
Project:     MYPROJECT
Summary:     Enable automatic scaling
Component:   Infrastructure (from markdown)
Version:     2.5 (from markdown)
Parent:      none

Description Preview:
────────────────────────────────────────────
As a cluster admin, I want to configure autoscaling...

## Acceptance Criteria
- [ ] Scales up when CPU > 80%
[... 100 chars total ...]

Metadata:
────────────────────────────────────────────
- Project: MYPROJECT (from **Project:** field)
- Type: Story (auto-detected from user story format)
- Component: Infrastructure (from **Component:** field)
- Version: 2.5 (from **Version:** field)

Applied Universal Defaults:
────────────────────────────────────────────
- Labels: ["ai-generated-jira"]
- Security: Red Hat Employee (if supported by project, omitted otherwise)
- Content Format: Markdown
```

### User Options

Present options to user:

```text
What would you like to do?

1. View full details for issue #<N>
2. Edit issue #<N> (change fields)
3. Skip issue #<N> (don't create)
4. Create all issues (proceed to validation)
5. Cancel (abort)
```

**Interactive Flow:**
- If user selects "View details": Show full description and all metadata for selected issue
- If user selects "Edit": Prompt for which fields to change, update in memory
- If user selects "Skip": Mark issue to skip, remove from creation list
- If user selects "Create all": Proceed to Phase 4 (Validation)
- If user selects "Cancel": Abort skill execution

---

## Phase 4: Validate

**Load and follow:** [`phase4-validate.md`](phase4-validate.md) in this skill directory.

Do not skip this phase. After validation completes (all checks pass, or user accepts partial success for non-security failures), proceed to Phase 5.

---

## Phase 5: Execute

This phase creates Jira issues in the correct order with proper defaults and error handling.

### Execution Order

Create issues in **hierarchy order** to ensure parent issues exist before children:

1. **Level 3:** Outcomes (if any)
2. **Level 2:** Features, Initiatives (if any)
3. **Level 1:** Epics
4. **Level 0:** Stories, Tasks, Bugs
5. **Level -1:** Sub-tasks

Within each level, maintain the document order from the markdown file.

### Universal Defaults

Apply to **ALL** issues regardless of project:

```json
{
  "labels": ["ai-generated-jira"],
  "contentFormat": "markdown"
}
```

**Security Level (conditional):** Applied per-issue during execution — see the "Creating Issues via MCP" section. Security is checked per `issue.project` (not pre-loop) to avoid referencing `project_key` before it is defined.

These fields are non-negotiable and set automatically without prompting.

### Project-Specific Defaults (Optional)

**Before creating issues**, attempt to invoke the `jira:jira-conventions` skill for each distinct project. The skill decides whether conventions apply — this skill does not hard-code any project or component names:

```python
# Discover conventions dynamically — no hard-coded allowlists
for project_key in {issue.project for issue in issues}:
    try:
        conventions = invoke_skill("jira:jira-conventions", project=project_key)
        if conventions:
            # Apply returned defaults for all issues in this project
            apply_conventions(issues, project_key, conventions)
            # Layered ON TOP of universal defaults, never replacing them
    except SkillNotFoundError:
        pass  # jira:jira-conventions not installed — skip silently
    except SkillNotApplicableError:
        pass  # Skill is installed but doesn't cover this project — skip
```

**Do NOT hard-code project names or component names** in this skill. Convention support is discovered at runtime by delegating to `jira:jira-conventions`.

**Project-specific defaults are layered ON TOP of universal defaults**, never replacing them.

### Creating Issues via MCP

For each issue in execution order:

```python
# Assemble full description from all extracted sections
description_parts = []
if issue.description:
    description_parts.append(issue.description)
if issue.user_story:
    description_parts.append(f"## User Story\n{issue.user_story}")
if issue.acceptance_criteria:
    description_parts.append(f"## Acceptance Criteria\n{issue.acceptance_criteria}")
if issue.steps_to_reproduce:
    description_parts.append(f"## Steps to Reproduce\n{issue.steps_to_reproduce}")
if issue.expected_behavior:
    description_parts.append(f"## Expected Behavior\n{issue.expected_behavior}")
if issue.actual_behavior:
    description_parts.append(f"## Actual Behavior\n{issue.actual_behavior}")
if issue.environment:
    description_parts.append(f"## Environment\n{issue.environment}")
if issue.technical_notes:
    description_parts.append(f"## Technical Notes\n{issue.technical_notes}")
if issue.testing_notes:
    description_parts.append(f"## Testing Notes\n{issue.testing_notes}")
full_description = "\n\n".join(description_parts)

# Prepare fields
fields = {
    "project": {"key": issue.project},
    "issuetype": {"name": issue.type},
    "summary": issue.summary,
    "description": full_description,
    "labels": list(set(issue.labels or []) | {"ai-generated-jira"}),  # Merge with user labels
}

# Add security level if available for the project
security_levels = getJiraProjectIssueTypesMetadata(issue.project).get("securityLevels", [])
if any(level["name"] == "Red Hat Employee" for level in security_levels):
    fields["security"] = {"name": "Red Hat Employee"}

# Add optional fields
if issue.component:
    fields["components"] = [{"name": issue.component}]

if issue.priority:
    fields["priority"] = {"name": issue.priority}

# Resolve field IDs from issue-type metadata (project-agnostic — do NOT hard-code customfield IDs)
type_meta = getJiraIssueTypeMetaWithFields(project=issue.project, issuetype=issue.type)
field_ids = resolve_field_ids(type_meta)  # maps logical names → customfield_* when present
# resolve_field_ids looks up fields by name/schema, e.g.:
#   "Epic Name" / epic name schema → epic_name_field
#   "Target Version" / version picker custom fields → target_version_field
# Prefer conventions overrides when jira-conventions returned field IDs for this project.

if issue.version:
    version_id = find_version_id(type_meta, issue.version)
    target_version_field = field_ids.get("target_version")
    if version_id and target_version_field:
        # Value format varies by project — delegate to jira-conventions if installed,
        # otherwise default to array form; plain string is used by some projects
        # and must be set by the conventions layer.
        version_value = apply_version_format(issue.project, version_id)  # from conventions
        fields[target_version_field] = version_value if version_value else [{"id": version_id}]
    elif issue.version and not target_version_field:
        warnings.append({
            "summary": issue.summary,
            "message": f"Version '{issue.version}' requested but no Target Version field found for {issue.project}/{issue.type}; omitting"
        })

# Parent: always set when present. Pre-existing keys were validated in Phase 4;
# in-batch parents are resolved earlier (see Parent Resolution below) into real Jira keys.
if issue.parent_key:
    fields["parent"] = {"key": issue.parent_key}

# Epic Name — only when the project/type exposes that field
if issue.type == "Epic" and field_ids.get("epic_name"):
    fields[field_ids["epic_name"]] = issue.summary

# Create via MCP — ordered handler chain: specific exceptions before generic fallback
try:
    result = createJiraIssue(
        project=issue.project,
        issuetype=issue.type,
        summary=issue.summary,
        description=full_description,
        additional_fields=fields,
        contentFormat="markdown"
    )
    created_jira_keys[issue.id] = result["key"]
    jira_key_to_issue_id[result["key"]] = issue.id
    successes.append({
        "key": result["key"],
        "summary": issue.summary,
        "url": result["url"]
    })

except ParentLinkError as e:
    # Create without parent using same named-parameter contract as primary call
    extra = {k: v for k, v in fields.items() if k not in ("project", "issuetype", "summary", "description", "parent")}
    result = createJiraIssue(
        project=issue.project,
        issuetype=issue.type,
        summary=issue.summary,
        description=full_description,
        additional_fields=extra,
        contentFormat="markdown"
    )
    created_jira_keys[issue.id] = result["key"]
    jira_key_to_issue_id[result["key"]] = issue.id
    try:
        editJiraIssue(
            issue_key=result["key"],
            update_fields={"parent": {"key": issue.parent_key}},
            contentFormat="markdown"
        )
    except Exception as link_error:
        warnings.append({
            "key": result["key"],
            "message": f"Created but failed to link parent {issue.parent_key}: {link_error}"
        })

except ComponentNotFoundError as e:
    # Phase 4 should have caught this; if it still happens, retry without component
    project_meta = getJiraProjectIssueTypesMetadata(project=issue.project)
    available = [c["name"] for c in project_meta.get("components", [])]
    fields.pop("components", None)
    try:
        result = createJiraIssue(
            project=issue.project,
            issuetype=issue.type,
            summary=issue.summary,
            description=full_description,
            additional_fields={k: v for k, v in fields.items() if k not in ("project", "issuetype", "summary", "description")},
            contentFormat="markdown"
        )
        created_jira_keys[issue.id] = result["key"]
        jira_key_to_issue_id[result["key"]] = issue.id
        successes.append({"key": result["key"], "summary": issue.summary, "url": result["url"]})
        warnings.append({
            "key": result["key"],
            "message": f"Created without component '{issue.component}' (not found). Available: {', '.join(available[:5])}"
        })
    except Exception as retry_error:
        failed_batch_ids.add(issue.id)
        failures.append({
            "summary": issue.summary,
            "error": f"Component '{issue.component}' not found; retry without component also failed: {retry_error}",
            "suggestion": f"Available: {', '.join(available[:5])}",
            "project": issue.project,
            "type": issue.type
        })

except VersionNotFoundError as e:
    # Phase 4 should have caught this; if it still happens, retry without version
    available = [v["name"] for v in type_meta.get("versions", {}).get("allowedValues", [])]
    if field_ids.get("target_version"):
        fields.pop(field_ids["target_version"], None)
    try:
        result = createJiraIssue(
            project=issue.project,
            issuetype=issue.type,
            summary=issue.summary,
            description=full_description,
            additional_fields={k: v for k, v in fields.items() if k not in ("project", "issuetype", "summary", "description")},
            contentFormat="markdown"
        )
        created_jira_keys[issue.id] = result["key"]
        jira_key_to_issue_id[result["key"]] = issue.id
        successes.append({"key": result["key"], "summary": issue.summary, "url": result["url"]})
        warnings.append({
            "key": result["key"],
            "message": f"Created without version '{issue.version}' (not found). Available: {', '.join(available[:5])}"
        })
    except Exception as retry_error:
        failed_batch_ids.add(issue.id)
        failures.append({
            "summary": issue.summary,
            "error": f"Version '{issue.version}' not found; retry without version also failed: {retry_error}",
            "suggestion": f"Available: {', '.join(available[:5])}",
            "project": issue.project,
            "type": issue.type
        })

except PermissionError as e:
    failed_batch_ids.add(issue.id)  # mark failed so children are skipped
    failures.append({
        "summary": issue.summary,
        "error": f"Permission denied: {str(e)}",
        "suggestion": f"Check Jira permissions for project {issue.project}",
        "fatal": True,
        "project": issue.project,
        "type": issue.type
    })

except FieldValidationError as e:
    failed_batch_ids.add(issue.id)  # mark failed so children are skipped
    failures.append({
        "summary": issue.summary,
        "error": f"Field validation failed: {e.field} — {e.message}",
        "suggestion": "Check field format in markdown",
        "project": issue.project,
        "type": issue.type
    })

except Exception as e:
    # Generic fallback — catches any unclassified MCP error
    failed_batch_ids.add(issue.id)
    failures.append({
        "summary": issue.summary,
        "error": str(e),
        "project": issue.project,
        "type": issue.type
    })
```

### Parent Linking Notes

`issue.parent_key` must be a real Jira issue key at create time:

1. **Pre-existing parents** (e.g. `CNTRLPLANE-100` in markdown) — validated in Phase 4; set `fields["parent"]` unconditionally when `parent_key` is present.
2. **In-batch parents** — create parents first (hierarchy order). After a parent succeeds, if any child referenced that batch issue (by parse `id` or summary), rewrite the child's `parent_key` to the new Jira key from `created_jira_keys` before creating the child.
3. Use `created_jira_keys` / `jira_key_to_issue_id` / `failed_batch_ids` only for in-batch failure skipping — **never** as a gate for whether to set `parent` on pre-existing keys.

**Do not** require `parent_key in created_jira_keys` (or a nonexistent `created_issues` map) before linking — that silently drops valid pre-existing parents.

### Batch Mode Partial Failures

Track successes and failures separately, including tracking failed parent issues:

```python
results = {
    "successes": [],  # [{key, summary, url}]
    "failures": [],   # [{summary, error, suggestion, project, type}]
    "warnings": []    # [{key, message}]
}

failed_batch_ids = set()    # issue.id values for batch issues that failed
created_jira_keys = {}      # Maps issue.id -> result Jira key (e.g., "PROJ-789")
jira_key_to_issue_id = {}   # Reverse map: result Jira key -> issue.id (for child lookup)

# Continue execution even if some issues fail
for issue in sorted_issues:
    # Skip if this issue's parent was a batch-created issue that failed.
    # Pre-existing parents (Jira keys from outside this batch) cannot fail here.
    parent_batch_id = jira_key_to_issue_id.get(issue.parent_key)
    if parent_batch_id and parent_batch_id in failed_batch_ids:
        results["failures"].append({
            "summary": issue.summary,
            "error": f"Parent {issue.parent_key} failed to create",
            "project": issue.project,
            "type": issue.type
        })
        failed_batch_ids.add(issue.id)
        continue
    
    try:
        result = createJiraIssue(...)
        created_jira_keys[issue.id] = result["key"]
        jira_key_to_issue_id[result["key"]] = issue.id
        results["successes"].append({
            "key": result["key"],
            "summary": issue.summary,
            "url": result["url"]
        })
    except Exception as e:
        # Track this issue as failed — use issue.id (result may not exist)
        failed_batch_ids.add(issue.id)
        results["failures"].append({
            "summary": issue.summary,
            "error": str(e),
            "project": issue.project,
            "type": issue.type
        })
        # CONTINUE to next issue

# Report at end
return results
```

**Output format:**

```text
Created 7 of 10 issues:

✅ SUCCESSES (7):
  CNTRLPLANE-100: Enable autoscaling
  CNTRLPLANE-101: Add metrics dashboard
  ...

❌ FAILURES (3):
  "API rate limiting" - Component 'Backend' not found in PLATFORM
    Suggestion: Available components: Frontend, Infrastructure, CLI
    
  "Database optimization" - Version '4.25' not found
    Suggestion: Available versions: openshift-4.21, openshift-4.22, openshift-4.23

⚠️  WARNINGS (1):
  CNTRLPLANE-100: Created but failed to link parent CNTRLPLANE-99

Next steps:
- Fix failed issues and retry
- Review warnings and manually link parents if needed
```

### Return to Command

Pass structured results back to the calling command for user reporting:

```python
return {
    "successes": results["successes"],
    "failures": results["failures"],
    "warnings": results["warnings"],
    "total_attempted": len(issues),
    "total_created": len(results["successes"])
}
```

---

## Phase 6: Summarize

**Task Complexity:** Low (simple reporting)

### Generate Results Report

**For Single Issue Mode:**

```text
✓ Created Jira Issue
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issue Key:  MYPROJECT-456
Title:      Enable automatic scaling
URL:        https://your-jira.atlassian.net/browse/MYPROJECT-456

Metadata Applied:
- Project: MYPROJECT
- Type: Story
- Component: Infrastructure
- Version: 2.5

Universal Defaults:
- Labels: ai-generated-jira
- Security: Red Hat Employee (applied — project supports this security level)
  (omitted if project does not support this security level)
```

**For Batch Mode (All Successful):**

```text
✓ Created 3 Jira Issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Key        | Type  | Summary                  | URL                                    |
|------------|-------|--------------------------|----------------------------------------|
| PROJ-A-789 | Story | Add user dashboard       | https://jira.atlassian.net/browse/...  |
| PROJ-B-101 | Bug   | API returns 500 error    | https://jira.atlassian.net/browse/...  |
| PROJ-A-790 | Task  | Update API docs          | https://jira.atlassian.net/browse/...  |

Summary:
- 3 issues created successfully
- Projects: PROJ-A (2), PROJ-B (1)
- Types: Story (1), Bug (1), Task (1)
```

**For Batch Mode (Partial Failures):**

```text
⚠ Created 2/3 Jira Issues (1 failed)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Successful:

| Key        | Type  | Summary                  | Status    |
|------------|-------|--------------------------|-----------|
| PROJ-A-789 | Story | Add user dashboard       | ✓ Created |
| PROJ-A-790 | Task  | Update API docs          | ✓ Created |

Failed:

| # | Type | Project | Summary               | Error                   |
|---|------|---------|-----------------------|-------------------------|
| 2 | Bug  | PROJ-B  | API returns 500 error | Permission denied       |

Summary:
- 2 issues created successfully
- 1 issue failed (permission denied for PROJ-B)
- Successfully created: PROJ-A (2)
```

### Reminder

```text
Reminder: If you granted write permissions during this session,
revoke them via /permissions (remove editJiraIssue allowance).
```

---

## Markdown Format Reference

### Required Metadata Fields

```markdown
**Project:** <project-key>      # REQUIRED - Jira project key
**Type:** <issue-type>          # Recommended; auto-detected from content if omitted
```

Valid types: `Story`, `Bug`, `Task`, `Epic`, `Feature`, `Initiative`, `Sub-task`

### Optional Metadata Fields

```markdown
**Component:** <component-name>
**Version:** <version-string>
**Parent:** <parent-issue-key>        # e.g., PROJ-123
**Priority:** <priority-name>         # e.g., High, Critical
**Labels:** <label1>, <label2>        # comma-separated
```

### Single Issue Example

```markdown
# Enable autoscaling for clusters

**Project:** PLATFORM
**Type:** Story
**Component:** Infrastructure
**Version:** 2.5

As a cluster admin, I want to configure autoscaling, so that I can handle traffic spikes.

## Acceptance Criteria
- [ ] Node pools scale up when CPU > 80%
- [ ] Node pools scale down when CPU < 30%
- [ ] Scaling respects min/max limits

## Context
Current state: Admins manually scale node pools.

## Dependencies
- PLATFORM-100 — Monitoring infrastructure must be deployed
```

### Batch Mode Example

```markdown
# Sprint 42 Planning

## Story: Add user dashboard
**Project:** FRONTEND
**Type:** Story
**Component:** Console
**Version:** 1.5

As a developer, I want a dashboard to monitor applications.

### Acceptance Criteria
- [ ] Shows running pods
- [ ] Shows resource usage

---

## Bug: API returns 500 error
**Project:** BACKEND
**Type:** Bug
**Component:** API Gateway
**Priority:** High

Description: API crashes on special characters.

Steps to Reproduce:
1. Create resource with special chars
2. Observe 500 error

Expected: Should return 400 with validation error

---

## Task: Update API documentation
**Project:** FRONTEND
**Type:** Task
**Parent:** FRONTEND-456

Update docs for new endpoints.

### Definition of Done
- [ ] Swagger spec updated
- [ ] Examples added
```

---

## MCP Tools Used

| Tool | Phase | Purpose |
|------|-------|---------|
| `createJiraIssue` | Execute | Create each Jira issue |
| `editJiraIssue` | Execute | Fallback for parent linking if create fails |
| `getJiraIssue` | Validate | Verify parent exists and hierarchy level matches |
| `getJiraIssueTypeMetaWithFields` | Validate/Execute | Fetch components, versions, custom fields for project |
| `getJiraProjectIssueTypesMetadata` | Validate | Discover available issue types and hierarchy levels |

---

## Edge Cases and Handling

### 1. Missing Project Metadata

**Scenario:** Markdown has no `**Project:**` field

**Handling:**
```markdown
1. Prompt user: "Which project should this issue be created in?"
2. Wait for user input
3. Use provided project key
4. Do NOT assume or default to any project
```

### 2. Missing Type Metadata

**Scenario:** Markdown has no `**Type:**` field and auto-detection fails

**Handling:**
```markdown
1. Attempt auto-detection from content patterns (see Phase 2)
2. If auto-detection is ambiguous or fails:
   - Prompt user: "What type of issue? (Story, Bug, Task, Epic, Feature, Initiative, Sub-task)"
   - Wait for user input
3. Do NOT default to any type
```

### 3. Component Not Valid for Project

**Scenario:** User specifies `**Component:** XYZ` but XYZ doesn't exist in project

**Handling:**
```markdown
1. createJiraIssue fails with "Component not found" error
2. Fetch available components via getJiraIssueTypeMetaWithFields
3. Show user: "Component 'XYZ' not found in PROJECT. Available components: [list]"
4. Ask: "Select a component from the list, or proceed without component?"
5. Retry creation with selected component or omit component field
```

### 4. Version Format Mismatch

**Scenario:** User provides version string "2.5", but project requires version ID

**Handling:**
```markdown
1. createJiraIssue fails with "Version not found" error
2. Fetch available versions via getJiraIssueTypeMetaWithFields
3. Attempt fuzzy match (e.g., "2.5" → find version with name containing "2.5")
4. If match found, use version ID
5. If no match, show available versions to user and ask which to use
6. Retry creation with correct version format
```

### 5. Invalid Parent Hierarchy

**Scenario:** User specifies Story with Feature or Initiative as parent (should be Epic)

**Handling:**
```markdown
1. In Phase 4 validation, fetch parent via getJiraIssue
2. Extract parent's issuetype.hierarchyLevel (Feature/Initiative = level 2)
3. Extract child's hierarchyLevel (Story = level 0)
4. Detect mismatch: Story (level 0) needs Epic (level 1) parent, not Feature/Initiative (level 2)
5. Warn user: "Story cannot have Feature or Initiative as parent. Expected Epic (level 1)."
6. Offer options:
   a) Proceed without parent
   b) Provide different parent key
   c) Cancel creation
7. User decides; proceed accordingly
```

### 6. Unstructured Markdown

**Scenario:** File is prose with no sections, no metadata

**Handling:**
```markdown
1. No **Project:** found → prompt user: "Which project?"
2. No **Type:** found, no auto-detection match → prompt user: "What type?"
3. Summary extraction uses Phase 2 fallback order: first H1 → first sentence → filename without extension → prompt user
4. Entire file content becomes description
5. Proceed with interactive prompts for all missing required fields
```

### 7. Mixed Projects in Batch Mode

**Scenario:** File has issues for PROJ-A, PROJ-B, PROJ-C

**Handling:**
```markdown
1. Parse all issues independently
2. Apply universal defaults to all (labels: ai-generated-jira, content format: markdown)
3. Apply security level per project if supported (check each project independently)
4. Optionally invoke jira-conventions for each distinct project
5. Group by project in review phase: "PROJ-A (2 issues), PROJ-B (1), PROJ-C (1)"
6. Create each issue with its own project's metadata
7. Report results grouped by project
```

---

## Integration with Existing Skills (Optional)

### jira-conventions Skill

**Purpose:** Apply project-specific defaults and transformations

**How to check if available:**
```markdown
Attempt to invoke: "Load and apply jira-conventions for project {PROJECT_KEY}"
If skill not found or invocation fails, skip this step
```

**What to extract (if available):**
- Custom field IDs and default values
- Component requirements
- Version format (string vs array vs custom field)
- Additional project-specific labels
- Template validation rules

**What NOT to do:**
- Do NOT require this skill to exist
- Do NOT hard-code project names
- If skill unavailable, use only universal defaults

### Type-Specific Templates

**Purpose:** Validate content structure

**Templates (if they exist):**
- Story → `../../reference/create-story.md`
- Bug → `../../reference/create-bug.md`
- Epic → `../../reference/create-epic.md`
- Task → `../../reference/create-task.md`
- Feature → `../../reference/create-feature.md`
- Initiative → `../../reference/create-initiative.md`

There is no dedicated Sub-task reference file; use Task guidance plus parent-link rules from Phase 4/5.

**What to extract:**
- Expected section names
- Description format recommendations
- Validation rules (e.g., "Stories should have Acceptance Criteria")

**What NOT to do:**
- Do NOT require templates to exist
- Do NOT enforce strict compliance (warn only)

### Markdown Formatting Guide

**Reference:** `../../reference/markdown-for-jira.md` (if exists)

**Key points:**
- Use `contentFormat: "markdown"` for all MCP calls
- Checkboxes `- [ ]` render as actionable checkboxes in Jira
- Code blocks render as Jira code blocks
- Issue keys auto-link

---

## Best Practices

1. **Be explicit with metadata:** Always include `**Project:**` and `**Type:**` in markdown
2. **Use descriptive summaries:** Avoid vague titles like "Fix issue" or "Update thing"
3. **Sanitize sensitive data:** Never include credentials, API keys, or secrets
4. **Structure content:** Use H2/H3 headings for sections (Acceptance Criteria, Context, etc.)
5. **Batch mode separator:** Use `---` between issues if not using type-prefixed H2s
6. **Parent linking:** Verify parent exists and is correct type before specifying
7. **Component names:** Check project's components before including `**Component:**`

---

## Anti-Patterns to Avoid

❌ **Don't put user story in summary:**
```markdown
# As a developer, I want to add a dashboard so that I can monitor apps
```
✅ **Do this instead:**
```markdown
# Add developer dashboard

As a developer, I want a dashboard to monitor applications, so that...
```

❌ **Don't include secrets:**
```markdown
API Key: AKIA... (redacted AWS key)
```
✅ **Use placeholders:**
```markdown
API Key: YOUR_API_KEY
```

❌ **Don't omit required metadata:**
```markdown
# Add feature

This is a story about adding a feature.
```
✅ **Include Project and Type:**
```markdown
# Add feature

**Project:** MYPROJECT
**Type:** Story

As a user, I want...
```

---

**Last Updated:** 2026-07-23
