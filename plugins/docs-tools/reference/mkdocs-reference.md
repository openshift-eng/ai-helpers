# Material for MkDocs Markdown reference

Detailed guidance for writing documentation as Material for MkDocs Markdown pages. Use these conventions when the workflow specifies `--mkdocs` output format.

## Table of contents

- [Page types](#page-types)
- [Page structure](#page-structure)
- [Writing conventions](#writing-conventions)
- [Navigation fragment](#navigation-fragment)
- [Quality checklist](#quality-checklist)

## Page types

MkDocs pages follow the same CONCEPT / PROCEDURE / REFERENCE taxonomy as AsciiDoc modular docs. The page type is implicit from the content — no `:_mod-docs-content-type:` attribute is needed.

| Type | Purpose | Title format |
|------|---------|--------------|
| Concept | Explain what something is | Noun phrase |
| Procedure | Step-by-step instructions | Imperative phrase (verb) |
| Reference | Lookup data (tables, lists) | Noun phrase |

There are no assembly files in MkDocs output. Navigation structure is defined in `mkdocs-nav.yml` instead.

---

## Page structure

Every MkDocs page must have YAML frontmatter and a single `# h1` title:

```markdown
---
title: Scale applications automatically
description: Configure horizontal pod autoscaling to adjust resources based on workload demands.
---

# Scale applications automatically

You can configure automatic scaling to adjust resources based on workload demands.
Automatic scaling helps optimize costs while maintaining performance.
```

### Frontmatter fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Page title, matches the `# h1` heading |
| `description` | Yes | 1-2 sentence summary for search metadata and SEO |

### Heading hierarchy

- Start with `# h1` (one per page, matches the `title` frontmatter)
- Use `## h2` for major sections, `### h3` for subsections
- Never skip heading levels (e.g., `#` to `###`)

### Short descriptions

The first paragraph after the `# h1` heading serves as the short description. Write 2-3 sentences explaining what and why, focusing on user benefits.

---

## Writing conventions

### Code blocks

Use fenced code blocks with language identifiers and optional titles:

````markdown
```terminal title="Create a new project"
$ oc new-project <project_name>
```

```yaml title="Pod manifest"
apiVersion: v1
kind: ConfigMap
metadata:
  name: example
```

```json title="API response"
{
  "key": "value"
}
```
````

Common language identifiers: `terminal`, `bash`, `yaml`, `json`, `python`, `go`, `java`, `xml`, `toml`, `ini`, `sql`.

### User-replaced values

Mark values users must replace using angle brackets:

```markdown
In the following command, replace `<project_name>` with the name of your project:

```terminal
$ oc new-project <project_name>
```
```

For multiple replaceable values, use a definition list or bulleted list after the code block:

```markdown
Where:

- `<project_name>` is the name of your project.
- `<namespace>` is the target namespace.
```

### Admonitions

Use Material for MkDocs admonition syntax. Indent content with 4 spaces:

```markdown
!!! note
    Additional helpful information.

!!! important
    Information users must not overlook.

!!! warning
    Information about potential data loss or security issues.

!!! tip
    Helpful suggestion for a better workflow.

!!! example
    Concrete example illustrating a concept.
```

Collapsible admonitions use `???` instead of `!!!`:

```markdown
??? note "Click to expand"
    This content is hidden by default.
```

### Content tabs

Use content tabs for platform-specific or alternative instructions:

```markdown
=== "Linux"

    ```terminal
    $ sudo dnf install package-name
    ```

=== "macOS"

    ```terminal
    $ brew install package-name
    ```

=== "Windows"

    ```terminal
    > choco install package-name
    ```
```

### Internal links

Use relative paths to other `.md` files:

```markdown
For more information, see [Autoscaling configuration options](configuration-options.md).
```

For section anchors within a page:

```markdown
See [Code blocks](#code-blocks) for syntax details.
```

For cross-page section links:

```markdown
See [Prerequisites](installing-operator.md#prerequisites) for setup requirements.
```

### Tables

Use standard Markdown table syntax:

```markdown
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `replicas` | integer | `1` | Number of pod replicas |
| `timeout` | string | `30s` | Request timeout duration |
```

### Prerequisites section

Use a `## Prerequisites` heading with a bulleted list:

```markdown
## Prerequisites

- JDK 11 or later is installed.
- You are logged in to the console.
- A running Kubernetes cluster.
```

### Procedure section

Use a `## Procedure` heading with a numbered list:

```markdown
## Procedure

1. Install the package:

    ```terminal
    $ sudo dnf install package-name
    ```

2. Configure the settings:

    ```terminal
    $ vi /etc/package/config.yaml
    ```

3. Start the service:

    ```terminal
    $ sudo systemctl start package-name
    ```
```

### Verification section

Use a `## Verification` heading:

```markdown
## Verification

* Run the following command to verify the installation:

    ```terminal
    $ package-name --version
    ```

    Expected output:

    ```
    package-name v1.2.3
    ```
```

### Product names

Use the full product name directly in the text. MkDocs Markdown does not support AsciiDoc-style attribute substitution.

---

## Navigation fragment

Generate a `mkdocs-nav.yml` file with the suggested navigation structure for the pages:

```yaml
nav:
  - Overview: docs/understanding-feature.md
  - Getting started:
    - Install the operator: docs/installing-operator.md
    - Configure the feature: docs/configuring-feature.md
  - Reference:
    - Configuration options: docs/configuration-parameters.md
```

### Navigation guidelines

- Group related pages under descriptive section headings
- Order pages by user workflow (overview → setup → usage → reference)
- Use sentence case for section headings
- Page titles in the nav should match the `title` frontmatter

---

## Quality checklist

Before completing an MkDocs page, verify:

- [ ] YAML frontmatter present with `title` and `description`
- [ ] Title is outcome-focused and follows page type convention
- [ ] Heading hierarchy starts at `# h1`, no skipped levels
- [ ] Ventilated prose used (one sentence per line)
- [ ] Code blocks use fenced syntax with language identifier
- [ ] Admonitions use Material for MkDocs syntax (`!!! type`)
- [ ] Internal links use relative paths to other `.md` files
- [ ] `mkdocs-nav.yml` generated with suggested navigation tree
- [ ] `lint-with-vale` run and all ERROR-level issues fixed
