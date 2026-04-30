---
description: Generate standards-compliant paragraphs, tables, and sections for Telco Partner Blueprints
argument-hint: <section-type> [--partner <name>] [--blueprint <path>] [--ocp-version <version>]
---

## Name

telcoeng-blueprint-workflow:generate

## Synopsis

```text
/telcoeng-blueprint-workflow:generate <section-type> [--partner <name>] [--blueprint <path>] [--ocp-version <version>]
```

## Description

The `generate` command produces standards-compliant text snippets for common blueprint sections. It reads the current standards to ensure generated content matches the required format, then interactively collects partner-specific data to produce ready-to-use content.

This implements WOW #3 (Recommended Paragraph & Content Generation) from the prioritization matrix. It eliminates manual authoring of repetitive sections like S-BOM tables, deviation lists, and boilerplate text.

### Key Features

- Generates content for any standard blueprint section
- Reads standards dynamically — format adapts when standards change
- Collects partner-specific inputs interactively
- Produces ready-to-use Markdown with TODO markers for missing data
- Can insert generated content directly into an existing blueprint

## Implementation

### Phase 1: Load Content Templates

1. Invoke the `content-generation` skill using the Skill tool to load templates and format patterns
2. Invoke the `blueprint-structure` skill using the Skill tool to understand the target section's requirements

### Phase 2: Identify Target Section

Parse the `<section-type>` argument. Supported values:

| Section Type | What It Generates |
|-------------|-------------------|
| `metadata` | Title, version history table, NDA notice, contacts table |
| `intro` | Purpose statement, workload description, deployment scenarios |
| `sbom` | Software Bill of Materials table with version columns |
| `operators` | Operators table with version, channel, and role |
| `support-exceptions` | Support Exceptions table with SUPPORTEX IDs |
| `deviations` | RDS deviations list with explanations and impact |
| `hbom` | Hardware Bill of Materials table |
| `node-config` | Node types, labels, taints, resource partitioning |
| `networking` | Network overview, CNI config, secondary networks, NAD table |
| `operations` | LCM, backup/restore, observability, security, user management |
| `certification` | CNF certification, hardware certification links |
| `all` | Full blueprint scaffold with all sections |

If the section type is not recognized, display the table above and prompt for selection.

### Phase 3: Read Current Standards

Read the corresponding section from `telcoeng-blueprint-standards/README.md` to extract:

1. The exact heading hierarchy and format expected
2. Example content and table structures from the standards
3. Required disclaimers or boilerplate text

### Phase 4: Collect Partner-Specific Inputs

Interactively prompt the user for required data based on the section type:

- For `sbom`: OCP version, partner product name/version, operators in use
- For `hbom`: Server models, CPU, memory, storage, NICs
- For `deviations`: RDS baseline, known deviations with rationale
- For `networking`: Primary CNI, secondary network types, NAD count
- For `metadata`: Partner name, document version, contacts
- For `all`: Partner name, product, OCP version, deployment type (minimum required)

Use the `--ocp-version` and `--partner` flags to pre-fill known values.

### Phase 5: Generate Content

Produce Markdown content that:

1. Follows the exact format from the current standards
2. Uses specific values where the user provided data
3. Marks gaps with `<!-- TODO: description of what is needed -->` comments
4. Includes appropriate links (Red Hat docs, SUPPORTEX tickets, RDS references)
5. Uses standard Telco Engineering terminology

### Phase 6: Present and Insert

1. Display the generated content to the user for review
2. If `--blueprint <path>` is provided:
   - Locate the target section in the existing blueprint
   - Show a diff preview of what will change
   - Ask for confirmation before inserting
   - Insert or replace the section content
3. If no blueprint path is provided:
   - Display the content for the user to copy
   - Suggest saving to `.work/blueprints/<partner-name>/generated/<section-type>.md`

## Return Value

- **Generated content**: Markdown text for the requested section
- **Completeness**: Complete / Partial / Template-only (based on how much data was provided)
- **TODO count**: Number of items still needing user input
- **Insertion status**: Whether content was inserted into an existing blueprint

## Examples

1. **Generate S-BOM table**:
   ```text
   /telcoeng-blueprint-workflow:generate sbom --partner acme-telecom --ocp-version 4.17
   ```
   Output: A complete S-BOM table pre-filled with OCP 4.17 components, with TODO markers for partner-specific software.

2. **Generate full blueprint scaffold**:
   ```text
   /telcoeng-blueprint-workflow:generate all --partner samsung --ocp-version 4.16
   ```
   Output: Complete blueprint structure with all mandatory sections, pre-filled boilerplate, and TODO markers for partner data.

3. **Generate and insert deviations into existing blueprint**:
   ```text
   /telcoeng-blueprint-workflow:generate deviations --blueprint .work/blueprints/softbank/blueprint.md
   ```
   Output: Generates an RDS deviations section and inserts it into the existing blueprint at the correct location.

4. **Generate networking section**:
   ```text
   /telcoeng-blueprint-workflow:generate networking --partner acme-telecom
   ```

## Arguments

- `$1` (`<section-type>`): The type of section to generate. See the table in Phase 2 for supported values. Use `all` for a full scaffold.
- `--partner <name>`: Partner name used in generated content and file paths.
- `--blueprint <path>`: Path to an existing blueprint to insert generated content into. Optional.
- `--ocp-version <version>`: OpenShift version (e.g., 4.17) to pre-fill in generated tables. Optional.

## Error Handling

- **Unknown section type**: Display supported types table and prompt for selection
- **Blueprint path not found**: Generate content to stdout instead of inserting
- **Standards not found**: Fall back to `reference/blueprint-sections.md` for format reference
- **Insufficient input**: Generate template with TODO markers rather than refusing
- **Existing section conflict**: When inserting into a blueprint, warn if the section already has content and ask whether to replace or append
