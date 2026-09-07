# Common Jira Issue Execution Logic

**Shared across:** `jira:create`, `jira:create-jira-from-file`, and other Jira creation skills

This file documents common patterns for creating Jira issues via MCP tools. Invoking skills should adapt these patterns to their specific workflows (single vs batch, interactive vs automated, etc.).

---

## Universal Defaults

Apply to **ALL** issues regardless of project:

```json
{
  "labels": ["ai-generated-jira"],
  "contentFormat": "markdown"
}
```

**Security Level (conditional, Red Hat-specific default):**

**Note:** This default is optimized for Red Hat's Jira instance. For other organizations:
- Modify `"Red Hat Employee"` to your organization's security level name
- Or remove this block entirely if security levels are not used

```python
# Check if project supports "Red Hat Employee" security level
security_levels = getJiraProjectIssueTypesMetadata(issue.project).get("securityLevels", [])
if any(level["name"] == "Red Hat Employee" for level in security_levels):
    fields["security"] = {"name": "Red Hat Employee"}
# Otherwise omit — not all projects have this security level
```

---

## Project-Specific Conventions

Before creating issues, invoke the `jira:jira-conventions` skill for each distinct project to apply team-specific defaults:

```python
for project_key in {issue.project for issue in issues}:
    try:
        conventions = invoke_skill("jira:jira-conventions", project=project_key)
        if conventions:
            apply_conventions(issues, project_key, conventions)
            # Conventions layer ON TOP of universal defaults
    except SkillNotFoundError:
        pass  # Not installed — skip silently
    except SkillNotApplicableError:
        pass  # Installed but doesn't cover this project
```

**Do NOT hard-code project names** — convention support is discovered at runtime.

---

## Custom Field ID Resolution

Jira custom field IDs vary by project and instance. Resolve them dynamically via `getJiraIssueTypeMetaWithFields`:

```python
type_meta = getJiraIssueTypeMetaWithFields(project=issue.project, issuetype=issue.type)
field_ids = resolve_field_ids(type_meta)
# resolve_field_ids looks up fields by name/schema:
#   "Epic Name" → epic_name_field (e.g., customfield_10011)
#   "Target Version" → target_version_field (e.g., customfield_10855)
# Prefer conventions overrides when jira-conventions returned IDs
```

**Target Version field** (common example):

```python
if issue.version:
    version_id = find_version_id(type_meta, issue.version)
    target_version_field = field_ids.get("target_version")
    if version_id and target_version_field:
        # Format varies by project — delegate to conventions if available
        version_value = apply_version_format(issue.project, version_id)
        fields[target_version_field] = version_value if version_value else [{"id": version_id}]
```

**Epic Name field** (for Epic types):

```python
if issue.type == "Epic" and field_ids.get("epic_name"):
    fields[field_ids["epic_name"]] = issue.summary
```

---

## Parent Linking

Set `parent` field when `parent_key` is present:

```python
if issue.parent_key:
    fields["parent"] = {"key": issue.parent_key}
```

**Pre-existing parents** (e.g., CNTRLPLANE-100 from user input) — validated in Phase 4; set unconditionally when present.

**In-batch parents** — create parent issues first (hierarchy ordering), then rewrite child's `parent_key` to the newly created Jira key before creating the child.

---

## MCP Error Handling Patterns

Create issues with an ordered exception handler chain — specific exceptions before generic fallback:

### Pattern: ParentLinkError Fallback

If parent linking fails during creation, create without parent and link via `editJiraIssue`:

```python
try:
    result = createJiraIssue(
        project=issue.project,
        issuetype=issue.type,
        summary=issue.summary,
        description=description,
        additional_fields=fields,
        contentFormat="markdown"
    )
    created_keys[issue.id] = result["key"]
    successes.append({"key": result["key"], "summary": issue.summary, "url": result["url"]})

except ParentLinkError as e:
    # Create without parent using same contract
    extra = {k: v for k, v in fields.items() 
             if k not in ("project", "issuetype", "summary", "description", "parent")}
    result = createJiraIssue(
        project=issue.project,
        issuetype=issue.type,
        summary=issue.summary,
        description=description,
        additional_fields=extra,
        contentFormat="markdown"
    )
    created_keys[issue.id] = result["key"]
    # Retry parent link via edit
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
```

### Pattern: ComponentNotFoundError Retry

Phase 4 validation should catch invalid components, but if one slips through, retry without the component:

```python
except ComponentNotFoundError as e:
    project_meta = getJiraProjectIssueTypesMetadata(project=issue.project)
    available = [c["name"] for c in project_meta.get("components", [])]
    fields.pop("components", None)
    try:
        result = createJiraIssue(...)  # Same call without component
        successes.append(...)
        warnings.append({
            "key": result["key"],
            "message": f"Created without component '{issue.component}'. Available: {', '.join(available[:5])}"
        })
    except Exception as retry_error:
        failures.append({
            "summary": issue.summary,
            "error": f"Component '{issue.component}' not found; retry failed: {retry_error}"
        })
```

### Pattern: VersionNotFoundError Retry

Similar to component handling:

```python
except VersionNotFoundError as e:
    available = [v["name"] for v in type_meta.get("versions", {}).get("allowedValues", [])]
    if field_ids.get("target_version"):
        fields.pop(field_ids["target_version"], None)
    try:
        result = createJiraIssue(...)  # Same call without version
        successes.append(...)
        warnings.append({
            "key": result["key"],
            "message": f"Created without version '{issue.version}'. Available: {', '.join(available[:5])}"
        })
    except Exception as retry_error:
        failures.append({
            "summary": issue.summary,
            "error": f"Version '{issue.version}' not found; retry failed: {retry_error}"
        })
```

### Pattern: Permission and Validation Errors

These are fatal — no retry:

```python
except PermissionError as e:
    failures.append({
        "summary": issue.summary,
        "error": f"Permission denied: {str(e)}",
        "suggestion": f"Check Jira permissions for project {issue.project}",
        "fatal": True
    })

except FieldValidationError as e:
    failures.append({
        "summary": issue.summary,
        "error": f"Field validation failed: {e.field} — {e.message}",
        "suggestion": "Check field format"
    })
```

### Pattern: Generic Fallback

Catches any unclassified MCP error — MUST be last in the chain:

```python
except Exception as e:
    failures.append({
        "summary": issue.summary,
        "error": str(e),
        "project": issue.project,
        "type": issue.type
    })
```

---

## Batch Processing Notes

For batch creation (create-jira-from-file), track state across issues:

```python
created_jira_keys = {}      # Maps issue.id → result Jira key
jira_key_to_issue_id = {}   # Reverse: result key → issue.id
failed_batch_ids = set()    # issue.id values that failed

# Skip children of failed in-batch parents:
parent_batch_id = jira_key_to_issue_id.get(issue.parent_key)
if parent_batch_id and parent_batch_id in failed_batch_ids:
    failures.append({"summary": issue.summary, "error": f"Parent {issue.parent_key} failed"})
    failed_batch_ids.add(issue.id)
    continue
```

Mark failures immediately in all exception handlers so dependent children are skipped:

```python
except ComponentNotFoundError as e:
    failed_batch_ids.add(issue.id)  # Mark before recording failure
    # ... rest of handler
```

---

## MCP Tools Reference

| Tool | Purpose |
|------|---------|
| `createJiraIssue` | Create issue with project, issuetype, summary, description, additional_fields |
| `editJiraIssue` | Update existing issue (parent linking fallback, field corrections) |
| `getJiraIssue` | Fetch issue metadata (parent validation) |
| `getJiraProjectIssueTypesMetadata` | Discover available types, components, security levels for a project |
| `getJiraIssueTypeMetaWithFields` | Fetch custom field IDs and allowed values for a project/type pair |

---

## Field Format Reference

**Correct MCP field formats:**

```python
{
    "project": {"key": "CNTRLPLANE"},
    "issuetype": {"name": "Story"},
    "summary": "Issue title",
    "description": "Full description (markdown if contentFormat='markdown')",
    "labels": ["label1", "label2"],
    "components": [{"name": "ComponentName"}],
    "priority": {"name": "High"},
    "parent": {"key": "PARENT-123"},
    "security": {"name": "Red Hat Employee"},
    "customfield_10011": "Epic Name value",  # Epic Name
    "customfield_10855": [{"id": "12345"}]   # Target Version (array format)
}
```

**Common mistakes:**

| Wrong | Correct |
|-------|---------|
| `"project": "CNTRLPLANE"` | `"project": {"key": "CNTRLPLANE"}` |
| `"components": "Name"` | `"components": [{"name": "Name"}]` |
| `"customfield_10855": "openshift-4.21"` | `"customfield_10855": [{"id": "VERSION_ID"}]` (or string if project uses that format) |
