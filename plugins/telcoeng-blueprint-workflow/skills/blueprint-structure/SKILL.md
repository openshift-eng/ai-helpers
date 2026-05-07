---
name: Blueprint Structure
description: Dynamically reads telcoeng-blueprint-standards to extract the required section hierarchy for partner blueprints
---

# Blueprint Structure

This skill provides the canonical section hierarchy that every Telco Partner Blueprint must follow. It reads the standards document **at runtime** to always reflect the latest requirements.

## When to Use This Skill

Use this skill when:

- Creating a new blueprint scaffold (`ingest` or `generate` commands)
- Validating an existing blueprint's structure (`validate` command)
- Mapping ingested content to the correct sections (`ingest` command)
- Understanding what sections are mandatory vs. optional

## Prerequisites

- The `telcoeng-blueprint-standards` repository must be cloned locally
- See `reference/blueprint-sections.md` for how to locate the standards document

## Implementation Steps

### Step 1: Locate the Standards Document

Search for `telcoeng-blueprint-standards/README.md` in the following order:

1. Sibling directory: `../telcoeng-blueprint-standards/README.md` relative to the current workspace
2. Parent sibling: `../../telcoeng-blueprint-standards/README.md`
3. Broader search: Find any directory named `telcoeng-blueprint-standards` under the user's project directories

If the standards document cannot be found, inform the user and provide the GitLab URL:
`gitlab.cee.redhat.com/telcoeng/telcoeng-blueprint-standards`

### Step 2: Extract Section Hierarchy

Read the standards document and extract all sections under the `# Telco Partner Blueprint` heading. Parse:

1. **Top-level sections** (## headings): These are mandatory blueprint sections
2. **Sub-sections** (### headings): These are required subsections within each top-level section
3. **Bullet points under each section**: These are the required elements/content for that section

Build a structured representation:

```text
Section: <name>
  Required: true/false
  Sub-sections:
    - <sub-section-name>
      Required elements:
        - <element-1>
        - <element-2>
```

### Step 3: Identify Critical Tables

From the standards, identify all tables that must appear in a compliant blueprint:

- S-BOM (Software Bill of Materials)
- Operators and Versions
- Support Exceptions (SUPPORTEX)
- RDS Deviations
- H-BOM (Hardware Bill of Materials)
- Network Attachment Definitions

For each table, extract the required columns from the standards examples.

### Step 4: Extract Persona Requirements

Read the `# Personas and Targeting` section to understand what each persona needs from the blueprint. Map persona requirements to specific sections.

### Step 5: Return Structure Map

Return the complete section hierarchy as a structured map that the calling command can use for:

- **Scaffolding**: Generate empty sections with the correct headings and placeholders
- **Validation**: Check if all required sections exist in a blueprint
- **Mapping**: Match ingested content to the correct section

## Return Value

A structured section hierarchy containing:

- All mandatory section names and their nesting
- Required elements per section
- Required table schemas (column names)
- Persona-to-section mapping

## Error Handling

- **Standards not found**: Inform user, provide clone instructions, fall back to `reference/blueprint-sections.md` as a snapshot
- **Standards format changed**: If the expected headings are not found, warn the user that the standards may have been restructured and suggest reviewing manually
- **Partial read**: If some sections cannot be parsed, return what was found and flag the gaps
