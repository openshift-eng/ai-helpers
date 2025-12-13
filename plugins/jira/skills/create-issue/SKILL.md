---
name: Create Jira Issue (Template-Driven)
description: Unified skill for creating all Jira issue types using template-driven workflows
---

# Create Jira Issue - Template-Driven Workflow

This skill provides a unified, template-driven workflow for creating all Jira issue types (Epic, Story, Task, Bug, Spike, Feature, Feature Request).

## When to Use This Skill

This skill is automatically invoked by the `/jira:create` command for all issue types.

## How It Works

1. **Template Selection**: Automatically selects the appropriate template based on project + issue type
2. **Dynamic Prompting**: Generates interactive prompts from template placeholder metadata
3. **Validation**: Applies validation rules defined in the template
4. **Issue Creation**: Creates the issue via MCP with all collected information

## Template-Driven Approach

Instead of hardcoding workflows for each issue type, this skill:
- Reads the template YAML file
- Extracts placeholder definitions
- Generates prompts dynamically from metadata
- Validates input based on template rules
- Formats the description using the template

**Benefits:**
- Single source of truth (templates)
- Consistent behavior across all issue types
- New issue types work automatically
- Template changes immediately reflected

## Workflow Overview

```
1. Parse command arguments (project, type, summary, flags)
2. Load template (project-specific → common fallback)
3. Show educational guide reference (if template has documentation field)
4. Scan and describe template to user
5. Apply template defaults
6. Prompt for priority (all issue types)
7. Interactive placeholder collection (template-driven)
8. Validate summary format
9. Security validation
10. Create issue via MCP
11. Return result
```

## Educational Content Integration

Templates can reference educational documentation:

```yaml
documentation:
  guide: "../../docs/issue-types/epic.md"
  description: "Comprehensive guide on epics: what they are, best practices, and anti-patterns"
```

**At workflow start**, display the guide reference:
```
Creating Epic issue for OCPEDGE

📖 For guidance, see: docs/issue-types/epic.md
   "Comprehensive guide on epics: what they are, best practices, and anti-patterns"

Using template: common-epic (common/epic.yaml)

Let's start...
```

**During prompting**, reference specific sections in help text:
```
What are the key outcomes that define this epic as complete?

[?] For help: Epic acceptance criteria are high-level outcomes...
    See docs/issue-types/epic.md#acceptance-criteria for examples.
```

**On validation errors**, point to relevant guidance:
```
⚠️  Epic seems too large (estimated >5 sprints).
    Consider splitting into multiple epics or creating as a Feature.
    See docs/issue-types/epic.md#sizing for guidance.
```

## Interactive Collection Process

For each placeholder in the template:

### 1. Determine Prompt Type

Based on placeholder metadata:
- `prompt_type: suggestion` → Generate suggestion, ask for confirmation
- `prompt_type: options` → Present options to choose from
- `prompt_type: guided` → Ask sub-questions, assemble answer
- `prompt_type: simple` (default) → Direct prompt

### 2. Get Prompt Text

Priority order:
1. `prompt_text` (if specified)
2. `description` (fallback)

### 3. Show Help if Available

If `help_text` is defined and user types "?" or "help":
- Display the help text
- Show examples if available
- Re-prompt for value

### 4. Collect Value

Based on `type`:
- `text`: Single line input
- `multiline`: Multi-line text block
- `list`: Multiple items, one per line

### 5. Validate Input

Apply validation rules from `validation`:
- `required`: Must have value
- `min_length` / `max_length`: Length constraints
- `min_items` / `max_items`: List size constraints
- `pattern`: Regex validation
- `allowed_values`: Enum validation

### 6. Use Default if Applicable

If user provides no value and `default` is specified:
- Use the default value
- Skip if not required

## Prompt Type Examples

### Simple Prompt

```yaml
placeholders:
  - name: task_description
    description: "What work needs to be done?"
    required: true
    type: text
```

**Execution:**
```
What work needs to be done?
> [user types answer]
```

### Suggestion Prompt

```yaml
placeholders:
  - name: epic_name
    prompt_type: suggestion
    prompt_with_suggestion: true
    suggestion_template: "Generate from summary: extract key nouns/action, max 3-5 words"
```

**Execution:**
```
Epic Name:
  Summary: "Enable graceful API server responses during planned maintenance"
  Suggested: "API Server Graceful Responses"

Use this epic name? (yes/no/custom)
> [user responds]
```

### Options Prompt

```yaml
placeholders:
  - name: size
    prompt_type: options
    prompt_text: "What is the estimated size?"
    prompt_with_options:
      - value: "S"
        description: "Small - About 2 sprints"
      - value: "M"
        description: "Medium - About 3 sprints"
```

**Execution:**
```
What is the estimated size?
1. S - Small - About 2 sprints
2. M - Medium - About 3 sprints
3. L - Large - About 4 sprints

Select option (1-3):
> [user selects]
```

### Guided Prompt

```yaml
placeholders:
  - name: user_story
    prompt_type: guided
    guided_questions:
      - "Who is the user?"
      - "What do they want to do?"
      - "Why do they want it?"
    assembly_template: "As a {{q1}}, I want to {{q2}}, so that {{q3}}."
```

**Execution:**
```
Let's build the user story together.

Who is the user?
> cluster admin

What do they want to do?
> configure automatic node pool scaling

Why do they want it?
> to handle traffic spikes without manual intervention

User story:
  As a cluster admin, I want to configure automatic node pool scaling,
  so that I can handle traffic spikes without manual intervention.

Does this look correct? (yes/no/modify)
> [user confirms]
```

## Priority Prompting

**Always prompt for priority** (applies to all issue types):

```
What is the priority for this issue?

Common values:
  - Blocker, Urgent, Critical, Must Have, High
  - Major, Should Have
  - Normal (default)
  - Medium, Minor, Low, Could Have
  - Trivial, Optional

Priority: [Normal]
> [user enters or accepts default]
```

## Validation

### Template-Based Validation

Apply rules from `validation` block:

```yaml
validation:
  summary_max_length: 80
  summary_should_start_with_verb: true
  required_fields:
    - field_name
```

### Placeholder-Level Validation

Apply rules from placeholder's `validation`:

```yaml
placeholders:
  - name: acceptance_criteria
    type: list
    validation:
      min_items: 2
      max_items: 8
```

### Universal Validation

Always validate:
- Required placeholders have values
- Summary is not empty
- No sensitive data (credentials, keys, tokens)

## Description Formatting

### MCP vs Direct API

**CRITICAL:** Formatting differs based on tool used.

**When using MCP tools** (`mcp__atlassian__jira_create_issue`):
- Section headers: `**Header**` (double asterisks)
- MCP converts Markdown to Jira Wiki markup

**When using Jira REST API directly**:
- Section headers: `*Header*` (single asterisks)
- API requires native Jira Wiki markup

**For all methods:**
- Sub-headers: `_Sub-header_` (underscores)
- Bullet lists: `* Item` (single asterisk)

### Template Rendering

1. Load description_template from template
2. Populate with collected placeholder values
3. Use Mustache rendering:
   - `{{name}}` → Insert value
   - `{{#list}}...{{/list}}` → Iterate list
   - `{{#optional}}...{{/optional}}` → Show if truthy

## MCP Tool Parameters

### Basic Issue Creation

```python
mcp__atlassian__jira_create_issue(
    project_key="<PROJECT>",
    summary="<summary>",
    issue_type="<Epic|Story|Task|Bug|Spike|Feature>",
    description="<rendered template>",
    priority="<priority>",
    components="<component>",  # if specified
    additional_fields={
        "labels": ["ai-generated-jira", "template:<template-name>"],
        # Custom fields from template
        "customfield_12311141": "<epic_name>",  # if Epic
        "customfield_12320852": "<size>",  # if Epic with size
        # Parent linking if --parent flag
        "customfield_12313140": "<parent-key>",  # Epic → Feature
        "customfield_12311140": "<epic-key>",  # Story/Task → Epic
    }
)
```

### Field Mapping

Use `field` attribute from placeholder:

```yaml
placeholders:
  - name: epic_name
    field: customfield_12311141
```

Maps to:
```python
additional_fields["customfield_12311141"] = values["epic_name"]
```

## Error Handling

### Template Not Found

```
Could not find template for <project> <issue_type>.

Searched:
  1. ~/.jira-templates/<project>-<type>.yaml
  2. plugins/jira/templates/<project>/<type>.yaml
  3. plugins/jira/templates/common/<type>.yaml

Would you like to:
  1. Use a different template (specify path)
  2. Create issue without template
  3. Cancel
```

### Invalid Placeholder Value

```
Invalid value for '<placeholder_name>':
  Error: Must be at least 2 items (got 1)

Please provide at least 2 <placeholder_description>:
> [retry]
```

### Required Field Missing

```
Required field '<placeholder_name>' has no value.

<description>

[Shows help_text if available]
[Shows examples if available]

> [prompt again]
```

### MCP Tool Error

```
Failed to create issue:
  Error: <mcp error message>

Suggested action: <based on error>
```

## Educational Content

For detailed guidance on each issue type, see:
- [Epic Best Practices](../../docs/issue-types/epic.md)
- [Story Best Practices](../../docs/issue-types/story.md)
- [Task Best Practices](../../docs/issue-types/task.md)
- [Bug Best Practices](../../docs/issue-types/bug.md)
- [Feature Best Practices](../../docs/issue-types/feature.md)
- [Spike Best Practices](../../docs/issue-types/spike.md)

## Implementation Notes

### Template Loading

```python
def load_template(project_key, issue_type):
    """Load template with inheritance."""
    search_paths = [
        f"~/.jira-templates/{project_key.lower()}-{issue_type.lower()}.yaml",
        f"plugins/jira/templates/{project_key.lower()}/{issue_type.lower()}.yaml",
        f"plugins/jira/templates/common/{issue_type.lower()}.yaml"
    ]

    for path in search_paths:
        if exists(path):
            template = load_yaml(path)
            if template.get('inherits'):
                parent = load_template_by_path(template['inherits'])
                template = merge_templates(parent, template)
            return template

    raise TemplateNotFoundError(f"No template found for {project_key} {issue_type}")
```

### Dynamic Prompting

```python
def collect_placeholder(placeholder, context):
    """Collect value for a placeholder based on its metadata."""
    prompt_type = placeholder.get('prompt_type', 'simple')

    if prompt_type == 'suggestion':
        return collect_with_suggestion(placeholder, context)
    elif prompt_type == 'options':
        return collect_with_options(placeholder)
    elif prompt_type == 'guided':
        return collect_with_guided_questions(placeholder)
    else:  # simple
        return collect_simple(placeholder)
```

### Validation

```python
def validate_placeholder(name, value, placeholder):
    """Validate placeholder value against rules."""
    validation = placeholder.get('validation', {})

    # Required check
    if placeholder.get('required') and not value:
        raise ValidationError(f"Required field '{name}' has no value")

    # Length checks (for text)
    if 'min_length' in validation:
        if len(value) < validation['min_length']:
            raise ValidationError(f"Must be at least {validation['min_length']} characters")

    # Item count checks (for lists)
    if 'min_items' in validation:
        if len(value) < validation['min_items']:
            raise ValidationError(f"Must have at least {validation['min_items']} items")

    # Pattern matching
    if 'pattern' in validation:
        if not re.match(validation['pattern'], value):
            raise ValidationError(f"Does not match required pattern")

    # Allowed values
    if 'allowed_values' in validation:
        if value not in validation['allowed_values']:
            raise ValidationError(f"Must be one of: {', '.join(validation['allowed_values'])}")
```

## See Also

- [Template Schema](../../templates/SCHEMA.md)
- [/jira:create Command](../../commands/create.md)
- [Template Management](../template-management/SKILL.md)
