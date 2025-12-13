# Jira Template Schema

This document defines the YAML schema for Jira issue templates used by the `/jira:create` command.

## Overview

Templates drive the entire issue creation workflow:
- Define required fields and their prompts
- Generate interactive collection workflows
- Provide validation rules
- Specify formatting and defaults

## Template File Structure

```yaml
# Metadata (required)
name: template-name
description: Human-readable description
version: 1.0.0
created: YYYY-MM-DD
author: author-name

# Inheritance (optional)
inherits: path/to/parent.yaml

# Source tracking (optional)
source:
  repository: "https://github.com/..."
  path: "path/to/template.yaml"

# Educational content reference (optional)
documentation:
  guide: "../../docs/issue-types/epic.md"
  description: "Comprehensive guide on epics: what they are, best practices, and anti-patterns"

# Target configuration (optional)
project_key: PROJECTKEY
issue_type: Epic|Story|Task|Bug|Spike|Feature

# Default field values (optional)
defaults:
  priority: Normal
  components:
    - ComponentName
  labels:
    - ai-generated-jira
  target_version: openshift-4.22

# Display format (optional)
display_format:
  - priority
  - summary
  - assignee
  - status

# Description template with Mustache syntax (required)
description_template: |
  {{placeholder_name}}

  **Section Header**

  {{#list_placeholder}}
  * {{.}}
  {{/list_placeholder}}

  {{#optional_section}}
  **Optional Section**
  {{optional_section}}
  {{/optional_section}}

# Placeholder definitions (required)
placeholders:
  - name: placeholder_name
    description: "Prompt text shown to user"
    required: true|false
    type: text|list|multiline
    default: "default value"
    # ... additional metadata

# Jira field mappings (optional)
jira_fields:
  versions:
    source: placeholder_name
    required: true
  components:
    required: true
    prompt_if_missing: true
  customfield_12345:
    source: placeholder_name
    required: false

# Validation rules (optional)
validation:
  summary_max_length: 100
  summary_should_start_with_verb: true
  required_fields:
    - field_name
```

## Placeholder Schema

Each placeholder in the `placeholders` array defines one piece of information to collect from the user.

### Core Fields

#### `name` (required)
- **Type:** string
- **Description:** Internal identifier for the placeholder
- **Used in:** Description template via `{{name}}`
- **Example:** `"user_role"`, `"acceptance_criteria"`

#### `description` (required)
- **Type:** string
- **Description:** Default prompt text shown to user
- **Can be overridden by:** `prompt_text`
- **Example:** `"Who is the user? (e.g., cluster admin, developer)"`

#### `required` (optional)
- **Type:** boolean
- **Default:** `false`
- **Description:** Whether this placeholder must have a value
- **Example:** `true`

#### `type` (optional)
- **Type:** enum
- **Values:** `text`, `list`, `multiline`
- **Default:** `text`
- **Description:** Data type and collection method
  - `text`: Single-line text input
  - `list`: Multiple items, one per line
  - `multiline`: Multi-line text block
- **Example:** `list`

#### `default` (optional)
- **Type:** string | array (for lists)
- **Description:** Default value if user doesn't provide one
- **For lists:** Use empty array `[]` for no default items
- **Example:** `"Normal"`, `[]`

### Interactive Prompting Fields

#### `prompt_text` (optional)
- **Type:** string
- **Description:** Override the description with custom prompt text
- **Use when:** Description is for reference, but prompt needs different wording
- **Example:**
  ```yaml
  description: "List of acceptance criteria (one per line)"
  prompt_text: "What are the key outcomes that define this epic as complete?"
  ```

#### `prompt_type` (optional)
- **Type:** enum
- **Values:** `simple`, `guided`, `suggestion`, `options`
- **Default:** `simple`
- **Description:** How to interactively collect this value
  - `simple`: Just ask with prompt_text/description
  - `guided`: Ask sub-questions to build the value
  - `suggestion`: Generate suggestion, ask for confirmation
  - `options`: Present options to choose from
- **Example:** `suggestion`

#### `prompt_with_suggestion` (optional)
- **Type:** boolean | object
- **Description:** Generate a suggested value for user to confirm
- **When true:** Use `suggestion_template` to describe how to generate
- **Example:**
  ```yaml
  prompt_with_suggestion: true
  suggestion_template: "Generate from summary: extract key nouns/action, max 3-5 words"
  ```

#### `prompt_with_options` (optional)
- **Type:** array of objects
- **Description:** Present options for user to choose from
- **Format:**
  ```yaml
  prompt_with_options:
    - value: "XS"
      description: "Extra Small - About 1 sprint"
    - value: "S"
      description: "Small - About 2 sprints"
  ```

#### `guided_questions` (optional)
- **Type:** array of strings
- **Description:** Sub-questions to ask when `prompt_type: guided`
- **Example:**
  ```yaml
  prompt_type: guided
  guided_questions:
    - "Who is the user or role?"
    - "What do they want to do?"
    - "Why do they want it?"
  assembly_template: "As a {{q1}}, I want to {{q2}}, so that {{q3}}."
  ```

### Validation Fields

#### `validation` (optional)
- **Type:** object
- **Description:** Validation rules for this placeholder
- **Fields:**
  ```yaml
  validation:
    min_length: 10
    max_length: 100
    pattern: "^[A-Z].*"  # Regex pattern
    min_items: 2  # For lists
    max_items: 10  # For lists
    allowed_values: ["Always", "Sometimes", "Rarely"]
  ```

### Help and Examples

#### `help_text` (optional)
- **Type:** string
- **Description:** Extended help shown if user asks "help" or "?"
- **Example:**
  ```yaml
  help_text: |
    Acceptance criteria define when the epic is complete.
    Focus on capabilities, not implementation.
    Should be measurable/demonstrable.
    Typically 3-6 criteria.
  ```

#### `examples` (optional)
- **Type:** array of strings
- **Description:** Example values to show user
- **Example:**
  ```yaml
  examples:
    - "Administrators can view metrics from all clusters"
    - "Alert rules fire based on cross-cluster conditions"
  ```

### Field Mapping Fields

#### `field` (optional)
- **Type:** string
- **Description:** Jira field ID to map this placeholder to
- **Example:** `"customfield_12311141"` (Epic Name)

#### `placeholder_name` (optional)
- **Type:** string
- **Description:** For placeholders that expand to template content
- **Used with:** `placeholder_content`
- **Example:**
  ```yaml
  - name: additional_spikes_link
    placeholder_name: additional_spikes_placeholder
    placeholder_content: "* [Additional Spikes|https://...]"
  ```

## Template Inheritance

Templates can inherit from parent templates using `inherits`:

```yaml
inherits: _base.yaml
```

**Inheritance rules:**
1. Parent is loaded first
2. Child overrides parent fields
3. Arrays are **replaced**, not merged (except `placeholders`)
4. `placeholders` are merged by name (child overrides parent placeholder)
5. `defaults` are merged (child overrides parent defaults)

**Example:**
```yaml
# _base.yaml
defaults:
  priority: Normal
  labels:
    - ai-generated-jira

# child.yaml
inherits: _base.yaml
defaults:
  labels:
    - ai-generated-jira
    - template:child

# Result:
# priority: Normal
# labels: [ai-generated-jira, template:child]
```

## Description Template Syntax

Templates use Mustache syntax:

### Variables
```yaml
{{variable_name}}
```

### Conditional Sections
```yaml
{{#section_name}}
  Content shown if section_name is truthy
{{/section_name}}
```

### Lists
```yaml
{{#list_name}}
  * {{.}}
{{/list_name}}
```

### Inverted Sections
```yaml
{{^section_name}}
  Content shown if section_name is falsy
{{/section_name}}
```

## Complete Example

```yaml
name: common-epic
description: Base epic template with scope and acceptance criteria
version: 1.0.0
created: 2025-01-08
author: openshift-eng

inherits: _base.yaml

issue_type: Epic

defaults:
  labels:
    - ai-generated-jira
    - template:common-epic

description_template: |
  {{objective}}

  **Acceptance Criteria**

  {{#acceptance_criteria}}
  * {{.}}
  {{/acceptance_criteria}}

  **Scope**

  _In Scope_
  {{#in_scope}}
  * {{.}}
  {{/in_scope}}

  _Out of Scope_
  {{#out_of_scope}}
  * {{.}}
  {{/out_of_scope}}

  **Timeline**

  * Target: {{target_release}}
  {{#additional_context}}

  **Additional Context**

  {{additional_context}}
  {{/additional_context}}

placeholders:
  - name: epic_name
    description: "Short identifier for epic (displayed in picker)"
    required: true
    field: customfield_12311141
    prompt_type: suggestion
    prompt_with_suggestion: true
    suggestion_template: "Extract from summary: key nouns/action, max 3-5 words"
    validation:
      max_length: 50
    examples:
      - "Multi-cluster Metrics"
      - "Edge Automatic Scaling"

  - name: objective
    description: "Epic objective"
    required: true
    prompt_text: "What is the main objective or goal of this epic?"
    type: multiline
    help_text: |
      State what capability will be delivered and why.
      Be concise - remove unnecessary adjectives.

  - name: acceptance_criteria
    description: "High-level outcomes that define completion"
    required: true
    type: list
    prompt_text: "What are the key outcomes that define this epic as complete?"
    validation:
      min_items: 2
      max_items: 8
    examples:
      - "Administrators can view metrics from all clusters"
      - "Alert rules fire based on cross-cluster conditions"

  - name: size
    description: "Epic size estimate (XS=1 sprint, S=2, M=3, L=4, XL=5)"
    required: false
    field: customfield_12320852
    prompt_type: options
    prompt_with_options:
      - value: "XS"
        description: "Extra Small - About 1 sprint"
      - value: "S"
        description: "Small - About 2 sprints"
      - value: "M"
        description: "Medium - About 3 sprints"
      - value: "L"
        description: "Large - About 4 sprints"
      - value: "XL"
        description: "Extra Large - About 5 sprints"
    default: "M"

validation:
  summary_max_length: 80
```

## Documentation Reference Field

### `documentation` (optional)

Templates can reference educational content that provides context and guidance:

```yaml
documentation:
  guide: "../../docs/issue-types/epic.md"
  description: "Comprehensive guide on epics: what they are, best practices, and anti-patterns"
  sections:
    - what_is: "What is an Epic?"
    - best_practices: "Epic Best Practices"
    - anti_patterns: "Anti-Patterns to Avoid"
```

**When to use:**
- Link to detailed educational content
- Provide context about the issue type
- Reference best practices and anti-patterns

**How it's used:**
1. **Before prompting**: Show user a link to the guide
   ```
   Creating Epic issue for PROJECT

   📖 For guidance, see: docs/issue-types/epic.md
      "Comprehensive guide on epics: what they are, best practices, and anti-patterns"

   Let's start...
   ```

2. **In help text**: Reference specific sections
   ```
   For more about epic acceptance criteria, see:
   docs/issue-types/epic.md#best_practices
   ```

3. **On errors**: Point to relevant guidance
   ```
   Epic seems too large (>5 sprints). See docs/issue-types/epic.md#anti_patterns
   for guidance on epic sizing.
   ```

## Reference Docs

For educational content about each issue type:
- `docs/issue-types/epic.md` - What is an Epic, best practices, anti-patterns
- `docs/issue-types/story.md` - User story guidelines, acceptance criteria formats
- `docs/issue-types/task.md` - Task vs story distinction, when to use each
- `docs/issue-types/bug.md` - Bug reporting best practices, reproduction steps
- `docs/issue-types/feature.md` - Feature vs epic distinction, strategic planning
- `docs/issue-types/spike.md` - Spike guidelines, research vs implementation
