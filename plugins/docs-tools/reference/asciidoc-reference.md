# AsciiDoc modular documentation reference

Detailed guidance for Red Hat modular documentation module types, structure, templates, and rules.

## Table of contents

- [Concept modules](#concept-modules)
- [Procedure modules](#procedure-modules)
- [Reference modules](#reference-modules)
- [Assembly files](#assembly-files)
- [Text snippets](#text-snippets)
- [Common violations](#common-violations)

## Module types overview

| Type | Purpose | Title format |
|------|---------|--------------|
| Concept | Explain what something is | Noun phrase |
| Procedure | Step-by-step instructions | Imperative phrase (verb) |
| Reference | Lookup data (tables, lists) | Noun phrase |
| Assembly | Combine modules into user story | Imperative if includes procedures |

### Critical rules

- Modules should NOT contain other modules — only text snippets
- All CONCEPT, PROCEDURE, and REFERENCE module anchor IDs must include `_{context}`
- Assembly anchor IDs do NOT include `_{context}`
- All module and assembly titles must use H1 heading (`= My heading`)

---

## Concept modules

A concept module gives users descriptions and explanations needed to understand and use a product.

### Template

```asciidoc
:_mod-docs-content-type: CONCEPT
[id="REPLACE_ME_WITH_ID_{context}"]
= REPLACE_ME_WITH_TITLE
//In the title of concept modules, include nouns or noun phrases that are used in the body text. This helps readers and search engines find the information quickly. Do not start the title of concept modules with a verb.

[role="_abstract"]
//Write a short introductory paragraph that provides an overview of the module. The text that immediately follows the `[role="_abstract"]` tag is used for search metadata.
```

### Required parts

1. **Title**: H1 heading (`= Title`) with noun phrase
2. **Anchor ID**: With context variable `[id="concept-name_{context}"]`
3. **Introduction**: Single, concise paragraph answering:
   - What is the concept?
   - Why should the user care?
4. **Body**: Explanation using paragraphs, lists, tables, examples, diagrams

### Optional parts

- Additional resources section
- Subheadings (if content cannot be split into separate modules)

### Concept body

**Allowed elements**:
- Paragraphs
- Lists
- Tables
- Examples
- Graphics or diagrams (to speed up understanding)

**Actions in concept modules**:
- **Generally avoid** instructions to perform actions (those belong in procedure modules)
- **Exception**: Simple actions that are highly dependent on context and have no place in any procedure module
- **If including actions**: Ensure the heading remains a noun phrase, NOT an imperative

### Subheadings in concept modules

If a concept module is large and complex:

1. **First try**: Split into multiple standalone concept modules
2. **If that is not possible**: Use subheadings to structure content

**Subheading options**:
- **Discrete subheading** (excluded from TOC): `[discrete]` followed by `== Subheading`
- **Standard subheading** (included in TOC): `[#anchor-id_{context}]` followed by `== Subheading`

Subheadings are allowed in concept and reference modules, but NOT in procedure modules.

### Finding concepts to document

- Look at **nouns** in related procedure modules and assemblies
- Explain only things that are **visible to users**
- Even if a concept is interesting, it probably does not require explanation if it is not visible to users

### Types of conceptual information

- **Principle**: Fundamental truth or rule
- **Concept**: Abstract idea or general notion
- **Structure**: Organization or arrangement
- **Process**: Series of actions or steps
- **Fact**: Verified piece of information

---

## Procedure modules

Procedure modules explain how to do something. They contain numbered, step-by-step instructions to help users accomplish a single task.

### Template

```asciidoc
:_mod-docs-content-type: PROCEDURE
[id="REPLACE_ME_WITH_ID_{context}"]
= REPLACE_ME_WITH_TITLE

[role="_abstract"]
//Short introductory paragraph that provides an overview of the module. The text that immediately follows the abstract tag is used for search metadata.

.Prerequisites

* List procedure prerequisites one per bullet

.Procedure
//Start each step with an active verb. Use an unnumbered bullet (*) if the procedure includes only one step.

.Verification
//Provide the user with verification methods for the procedure, such as expected output or commands that confirm success or failure.
```

### Required parts

1. **Title**: H1 heading with **imperative phrase** ("Configure...", "Install...", "Deploy...")
2. **Anchor ID**: With context variable `[id="procedure-name_{context}"]`
3. **Introduction**: Short paragraph providing context
4. **Procedure section**: One or more numbered steps

### Optional parts (in this order only)

1. `.Limitations` - Bulleted list of limitations (not used often)
2. `.Prerequisites` - Bulleted list of conditions
3. `.Verification` - Steps to verify success
4. `.Troubleshooting` - Keep short; consider separate module
5. `.Next steps` - **Links only, NOT instructions**
6. `.Additional resources` - Links to related material

**Critical rule**: Do NOT change or embellish these subheading names. Do NOT create additional subheadings unless absolutely necessary.

### Procedure introduction

A short paragraph that provides context and overview.

**Should include**:
- What the module will help the user do
- Why it will be beneficial to the user
- Key words for search engine optimization

**Key questions to answer**:
- Why perform this procedure?
- Where do you perform this procedure?
- Special considerations specific to the procedure

### Limitations section

- Use bulleted list
- Use plural heading "Limitations" even if only one limitation exists
- Not used often

### Prerequisites section

Conditions that must be satisfied before the user starts the procedure.

- Use bulleted list
- Use plural heading "Prerequisites" even if only one prerequisite exists
- Can be full sentences or sentence fragments (must be parallel)
- Focus on relevant prerequisites users might not be aware of
- Do NOT list obvious prerequisites

**Best practice**: If a prerequisite applies to all procedures in a user story, list it in the assembly file instead.

**Good** (conditions):
- "JDK 11 or later is installed."
- "You are logged in to the console."
- "A running Kubernetes cluster."

**Bad** (instructions):
- "Install JDK 11" - this is a step, not a prerequisite
- "You should have JDK 11" - "should" is unnecessary

### Procedure section

- Each step describes one action
- Written in imperative form (e.g., "Do this action")
- Use numbered list for multiple steps
- Use unnumbered bullet for single-step procedures

**Important note**: Not all numbered lists are procedures. You can also use numbered lists for non-procedural sequences (e.g., process flow of system actions).

### Verification section

Steps to verify that the procedure provided the intended outcome.

**Can include**:
- Example of expected command output
- Pop-up window the user should see when successful
- Actions to complete (e.g., entering a command) to determine success or failure

### Troubleshooting section

- Keep this section short
- Not used often
- Consider whether the information might be better as:
  - A separate troubleshooting procedure
  - Part of a reference module with other troubleshooting sections

### Next steps section

Links to resources with instructions that might be useful after completing this procedure.

**Critical warning**: Do NOT use "Next steps" to provide a second list of instructions. It is for links only.

### Additional resources section

Links to closely related material:
- Other documentation resources
- Instructional videos
- Labs

**Best practice**:
- Focus on relevant resources that might interest the user
- Do NOT list resources just for completeness
- If a resource applies to all modules in a user story, list it in the assembly file instead

### No subheadings in procedures

You cannot use custom subheadings in procedure modules. Only use the allowed optional sections listed above.

---

## Reference modules

Reference modules provide data that users might want to look up, but do not need to remember.

### Template

```asciidoc
:_mod-docs-content-type: REFERENCE
[id="REPLACE_ME_WITH_ID_{context}"]
= REPLACE_ME_WITH_TITLE
//In the title of a reference module, include nouns that are used in the body text. For example, "Keyboard shortcuts for ___" or "Command options for ___." This helps readers and search engines find the information quickly.

[role="_abstract"]
//Short introductory paragraph that provides an overview of the module. The text that immediately follows the abstract tag is used for search metadata.

.Labeled list
Term 1:: Definition
Term 2:: Definition

.TABLE_TITLE
[cols="1,2", options="header"]
|===
|Column 1
|Column 2

|Value 1
|Value 2
|===
```

### Common examples

- List of commands users can use with an application
- Table of configuration files with definitions and usage examples
- List of default settings for a product
- API parameters and options
- Environment variables

### Required parts

1. **Title**: H1 heading (`= Title`) with noun phrase
2. **Anchor ID**: With context variable `[id="reference-name_{context}"]`
3. **Introduction**: Single, concise paragraph
4. **Body**: Reference data in structured format (tables, lists)

### Optional parts

- Additional resources section
- Subheadings (if content cannot be split)

### Reference introduction

A single, concise paragraph that provides a short overview of the module.

**Purpose**: Enables users to quickly determine whether the reference is useful without reading the entire module.

### Reference body

A very strict structure, often in the form of a list or table.

**Key principle**: A well-organized reference module enables users to scan it quickly to find the details they want.

**Organization options**:
- Logical order (e.g., alphabetically)
- Table format
- Labeled lists
- Unordered lists

**For large volumes of similar data**:
- Use a consistent structure
- Document each logical unit as one reference module
- Think of man pages: different information but consistent titles and formats

### Subheadings in reference modules

If a reference module is large and complex:

1. **First try**: Split into multiple standalone reference modules
2. **If that is not possible**: Use subheadings to structure content

**Subheading options**:
- **Discrete subheading** (excluded from TOC): `[discrete]` followed by `== Subheading`
- **Standard subheading** (included in TOC): `[#anchor-id_{context}]` followed by `== Subheading`

### Lists vs. tables

- Tables are better for multi-dimensional data
- Lists are easier to scan for simple key-value pairs
- Tables provide better structure for complex relationships

---

## Assembly files

An assembly is a collection of modules that describes how to accomplish a user story.

### Template

```asciidoc
:_mod-docs-content-type: ASSEMBLY
include::_attributes/attributes.adoc[]
:context: assembly-name
[id="assembly-file-name"]
= Assembly title
//Add any required context or attributes

[role="_abstract"]
//Short introductory paragraph that provides an overview of the assembly.

include::modules/concept-module.adoc[leveloffset=+1]

include::modules/procedure-module.adoc[leveloffset=+1]

include::modules/reference-module.adoc[leveloffset=+1]
```

### Required parts

1. **Title**: Imperative form if includes procedures, noun phrase otherwise
2. **Anchor ID**: With context variable `[id="assembly-name"]` — **Do not use _{context} in assembly IDs**
3. **Context variable**: Set before module includes
4. **Introduction**: Explains what user accomplishes
5. **Modules**: One or more included modules

### Optional parts

- Prerequisites (before modules)
- Next steps (after modules)
- Additional resources (after modules)

### Assembly title guidelines

- **With procedure modules**: Use imperative form (e.g., "Encrypt block devices using LUKS")
- **Without procedure modules**: Use noun phrase (e.g., "Red Hat Process Automation Manager API reference")

### Assembly introduction

The introduction explains what the user accomplishes by working through the assembled modules.

**Technique**: Reword the user story to write the assembly introduction.

**Example transformation**:
- **User story**: "As an administrator, I want to provide external identity, authentication and authorization services for my Atomic Host, so that users from external identity sources can access the Atomic Host."
- **Assembly introduction**: "As a system administrator, you can use SSSD in a container to provide external identity, authentication, and authorization services for the Atomic Host system. This enables users from external identity sources to authenticate to the Atomic Host."

### Prerequisites section

- Conditions that must be satisfied before starting the assembly
- Applicable to all modules in the assembly
- Use second-level heading syntax (`==`) for table of contents display

### Including modules

Use the AsciiDoc `include` directive with `leveloffset` attribute:

```asciidoc
:context: my-assembly-name

include::modules/con-my-concept.adoc[leveloffset=+1]
include::modules/proc-my-procedure.adoc[leveloffset=+1]
include::modules/ref-my-reference.adoc[leveloffset=+1]
```

### Next steps and Additional resources

- Optional sections at the end of the assembly
- If using both, list **Next steps** first, then **Additional resources**
- Focus on relevant resources that might interest the user
- Do NOT list resources just for completeness

**Warning**: If the last module in the assembly also has Next steps or Additional resources, check the rendered HTML and consider rewriting or reorganizing.

---

## Text snippets

A text snippet is a section of text stored in an AsciiDoc file that is reused in multiple modules or assemblies.

### Template

```asciidoc
:_mod-docs-content-type: SNIPPET
//Snippets are reusable content fragments that can be included in multiple modules.
//Snippets do not have an id or title - they are included inline within other content.

//Add reusable content here that will be included in other modules.
```

### Key requirements

- A text snippet is NOT a module
- Cannot include structural elements (anchor ID, H1 heading)
- Prefix file name with `snip-` or `snip_`, OR add `:_mod-docs-content-type: SNIPPET`

### Examples of snippets

- One or more paragraphs of text
- A step or series of steps in a procedure
- A table or list
- A note (e.g., technology preview disclaimer)

### Usage

```asciidoc
include::snippets/snip-beta-note.adoc[]
```

---

## Writing conventions

### Short descriptions (abstracts)

Every module must have a short description using the `[role="_abstract"]` tag:

```asciidoc
[role="_abstract"]
You can configure automatic scaling to adjust resources based on workload demands.
Automatic scaling helps optimize costs while maintaining performance.
This feature is available in version 4.10 and later.
```

### Code blocks

Always specify the source language:

```asciidoc
[source,terminal]
----
$ user command with dollar sign prompt
----

[source,terminal]
----
# root command with hash prompt
----

[source,yaml]
----
apiVersion: v1
kind: ConfigMap
----

[source,json]
----
{
  "key": "value"
}
----
```

**Do NOT use callouts** — AsciiDoc callouts are not supported in DITA and should not be used in new content. Instead, use one of these approaches to explain commands, options, or user-replaced values:

**Option 1: Simple sentence** (for single values):
```asciidoc
In the following command, replace `<project_name>` with the name of your project:

[source,terminal]
----
$ oc new-project <project_name>
----
```

**Option 2: Definition list** (for multiple options/parameters):
```asciidoc
[source,yaml]
----
apiVersion: v1
kind: Pod
metadata:
  name: <my_pod>
----
+
--
Where:

`apiVersion`:: Specifies the API version.
`kind`:: Specifies the resource type.
`<my_pod>`:: Specifies the name of the pod.
--
```

**Option 3: Bulleted list** (for explaining YAML structure):
```asciidoc
[source,yaml]
----
apiVersion: v1
kind: Pod
metadata:
  name: example
----

* `apiVersion` specifies the API version.
* `kind` specifies the resource type.
* `metadata.name` specifies the name of the pod.
```

See the Red Hat supplementary style guide: https://redhat-documentation.github.io/supplementary-style-guide/#explain-commands-variables-in-code-blocks

### User-replaced values

Mark values users must replace:

```asciidoc
Replace `<username>` with your actual username:

[source,terminal]
----
$ ssh <username>@server.example.com
----
```

### Admonitions

Use sparingly and appropriately:

```asciidoc
[NOTE]
====
Additional helpful information.
====

[IMPORTANT]
====
Information users must not overlook.
====

[WARNING]
====
Information about potential data loss or security issues.
====
```

### Product attributes

Always use attributes from `_attributes/attributes.adoc`. Read the attributes file first to understand available attributes.

```asciidoc
{product-name} version {product-version} provides...
```

---

## Additional template rules

### Assembly IDs

Do not use `_{context}` suffix in the Anchor ID for ASSEMBLY files. Use a simple descriptive ID: `[id="deploying-the-application"]`.

### Assembly attributes

Always include the repository's attributes file immediately after the content type declaration. Use a simple path (e.g., `_attributes/attributes.adoc`) that works via the symlinks set up in the drafts folder.

### No parent-context constructions

Since topics in this documentation are not reused across multiple assemblies, do NOT include parent-context preservation patterns (`ifdef::context[:parent-context: {context}]` etc.).

---

## Symlink setup for drafts

Before writing assemblies, create symlinks in the drafts folder to the repository's shared directories. This ensures include paths work identically in drafts and when files are moved to the repo.

When creating a new drafts folder for a JIRA ticket, set up symlinks to the repository's:
- **Attributes folder** (e.g., `_attributes/`, `attributes/`)
- **Snippets folder** (if it exists)
- **Assemblies folder** (if it exists and you need to reference existing assemblies)

**Example setup:**
```bash
# Create the drafts folder
mkdir -p artifacts/drafts/<jira-id>/modules

# Create symlinks to repo directories (adjust paths based on actual repo structure)
cd artifacts/drafts/<jira-id>
ln -s ../../../_attributes _attributes      # or whatever the attributes folder is called
ln -s ../../../snippets snippets            # if snippets folder exists
ln -s ../../../assemblies assemblies        # if assemblies folder exists
```

**Finding the correct paths:**
1. Look for attributes file: `find . -name "attributes*.adoc" -type f | head -5`
2. Look for snippets: `find . -type d -name "snippets" | head -5`
3. Look for assemblies: `find . -type d -name "assemblies" | head -5`

With symlinks in place, assemblies can use simple include paths like:
```asciidoc
include::_attributes/attributes.adoc[]
include::modules/my-module.adoc[leveloffset=+1]
include::snippets/common-prereqs.adoc[]
```

These paths work in the drafts folder (via symlinks) and continue working when files are moved to the repository root.

---

## Quality checklist

Before completing an AsciiDoc module, verify:

- [ ] Module type attribute set (`:_mod-docs-content-type:`)
- [ ] Anchor ID includes `_{context}` for modules, NOT for assemblies
- [ ] Short description with `[role="_abstract"]` present
- [ ] Title is outcome-focused and follows module type convention
- [ ] Ventilated prose used (one sentence per line)
- [ ] Symlinks created in drafts folder to repo's `_attributes/`, `snippets/`, `assemblies/`
- [ ] Assemblies include `_attributes/attributes.adoc[]` after content type
- [ ] No parent-context constructions (`ifdef::context[:parent-context:]` patterns prohibited)
- [ ] Code blocks specify source language
- [ ] No callouts in code blocks
- [ ] Product names use attributes
- [ ] `lint-with-vale` run and all ERROR-level issues fixed

---

## Common violations

| Issue | Wrong | Correct |
|-------|-------|---------|
| Missing context | `[id="my-assembly"]` | `[id="my-module_{context}"]` |
| Procedure title | `= Database Configuration` | `= Configure the database` |
| Custom subheading in procedure | `== Additional setup` | Use allowed sections only |
| Instructions in Next steps | Numbered steps | Links only |
| Module contains module | `include::` of module | Only snippets in modules |
| Missing leveloffset | `include::mod.adoc[]` | `include::mod.adoc[leveloffset=+1]` |
| Prerequisite as step | `* Install JDK 11` | `* JDK 11 is installed.` |
| Deep assembly nesting | Many levels of nested assemblies | Link to assemblies instead |
| Writers defining user stories | Writer creates user story | Product management defines user stories |
