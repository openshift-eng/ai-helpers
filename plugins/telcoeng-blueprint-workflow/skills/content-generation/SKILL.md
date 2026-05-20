---
name: Content Generation
description: Generates standards-compliant text snippets, tables, and sections for Telco Partner Blueprints
---

# Content Generation

This skill generates standards-compliant content for common blueprint sections. It produces recommended paragraphs, table templates, and section text that conform to `telcoeng-blueprint-standards`.

## When to Use This Skill

Use this skill when:

- The `generate` command needs to produce content for a specific blueprint section
- The `fix` command needs to generate replacement text for non-compliant sections
- A user needs a template for a specific table (S-BOM, H-BOM, Support Exceptions, etc.)
- Drafting deprecation notices, best-practice guidance, or operator update text

## Prerequisites

- The `blueprint-structure` skill should be invoked first to understand the target section's requirements
- The user should provide partner-specific details (partner name, product, OCP version, deployment type)
- Read `reference/blueprint-sections.md` for the section hierarchy

## Implementation Steps

### Step 1: Identify Target Section

Determine which section(s) to generate content for by first parsing `telcoeng-blueprint-standards/README.md` headings and section rules to derive the canonical section taxonomy at runtime. Do not rely on a fixed list — the standards document is authoritative.

Common section types include (illustrative, not exhaustive): Document Metadata, S-BOM, H-BOM, Operators, Support Exceptions, RDS Deviations, Networking, Node Configuration, Operations and Management, and Certification. Always check the current standards for the complete and up-to-date list.

### Step 2: Collect Required Inputs

For each section type, prompt the user for the minimum required information:

**For S-BOM**:
- OpenShift version (e.g., 4.17)
- Partner product name and version
- Key operators in use

**For H-BOM**:
- Server model(s)
- CPU type and count
- Memory per node
- Storage configuration
- NIC models and speeds

**For Networking**:
- Primary CNI (typically OVNKubernetes)
- Secondary network types (SR-IOV, MACVLAN)
- Number of network attachment definitions

**For RDS Deviations**:
- Which RDS the blueprint aligns with
- Known deviations from the partner's architecture

### Step 3: Read Standards Examples

Read the corresponding section from `telcoeng-blueprint-standards/README.md` to extract:

1. The exact format expected (headings, bullet structure, table layout)
2. Example content provided in the standards (e.g., sample SUPPORTEX table, sample deviations list)
3. Required disclaimers or boilerplate text (NDA notice, audience statements)

### Step 4: Generate Content

Produce content that:

1. **Follows the exact format** from the standards (heading levels, table columns, list structure)
2. **Uses specific values** — never generate "TBD" or placeholder text where the user provided real data
3. **Includes TODO markers** only for information the user did not provide, formatted as `<!-- TODO: <what is needed> -->`
4. **References appropriate links** — Red Hat docs, SUPPORTEX tickets, RDS documentation
5. **Matches the standards' tone** — technical, precise, using standard terminology (CNF, DU, CU, RAN, RDS)

### Step 5: Present for Review

Show the generated content to the user before insertion. Highlight:

- Sections that are complete (all data provided)
- Sections with TODO markers (data still needed)
- Any assumptions made about the partner's architecture

## Content Templates

### S-BOM Table Template

```markdown
### Software Bill of Materials (S-BOM)

| Component | Version | Minimum Patch Level |
|-----------|---------|---------------------|
| Red Hat OpenShift Container Platform | 4.X.Y | 4.X.Y |
| Red Hat Advanced Cluster Management | 2.X.Y | 2.X.Y |
| <!-- TODO: Add partner software components --> | | |
```

### Support Exceptions Table Template

```markdown
### Support Exceptions

This design relies on the following support exceptions:

| Support Exception ID | Required for | Status/Comments |
|----------------------|--------------|-----------------|
| [SUPPORTEX-XXXXX](https://issues.redhat.com/browse/SUPPORTEX-XXXXX) | [Partner Product] deviations vs OCP 4.X RAN RDS | Approved |
```

### H-BOM Table Template

```markdown
### Hardware Bill of Materials (H-BOM)

| Component | Specification |
|-----------|---------------|
| Server Model | <!-- TODO: Server model --> |
| CPU | <!-- TODO: CPU model and count --> |
| Memory | <!-- TODO: Memory per node --> |
| Storage | <!-- TODO: Storage type and capacity --> |
| NIC | <!-- TODO: NIC model and speed --> |
```

### RDS Deviations Template

When generating a deviations section, read the blueprint content to pre-populate known deviations. Each deviation must follow this structure:

```markdown
### Deviations from Red Hat Telco 5G OCP 4.X Reference Design Specification

This solution deviates from the [Telco-5G-RAN 4.X Reference Design Specification](https://docs.openshift.com/container-platform/latest/scalability_and_performance/telco_ref_design_specs/ran/telco-ran-ref-design-spec.html) in the following ways:

* **[Deviation category]**: [Specific description of what differs]
  * RDS expectation: [What the RDS specifies]
  * Blueprint configuration: [What this blueprint does instead]
  * Rationale: [Why this deviation is necessary]
  * Impact: [Effect on platform resources, support scope, or stability]
  * Tracked via: [SUPPORTEX-XXXXX](https://issues.redhat.com/browse/SUPPORTEX-XXXXX)
```

Load deviation detection patterns at runtime from the `deviation-tracking` skill (invoke it via the Skill tool) and from the current RDS reference configurations in `telcoeng-blueprint-standards`. The examples below are illustrative only — always defer to the loaded patterns, as RDS baselines change across OCP versions:

- **RAN-DU examples**: Non-x86 architecture, non-RT kernel, GPU acceleration, custom kernel parameters
- **Core examples**: Custom SCC capabilities, additional kernel modules, ODF internal mode, service mesh
- **Hub examples**: Converged Hub with ODF on masters, Tech Preview operators, partner components
- **Shared examples**: Additional cluster capabilities, etcd encryption, non-standard logging

For multi-profile blueprints (e.g., Hub + Core), tag each deviation with its applicable profile. A configuration that is baseline for one profile may be a deviation for another (e.g., non-RT kernel is baseline for Core but a deviation for RAN-DU).

When generating, scan the blueprint for detected patterns and pre-fill the deviations section with findings. Mark each with `<!-- TODO: Confirm rationale and file SUPPORTEX ticket -->` if the rationale is not clear from context.

## Return Value

- Generated Markdown content for the requested section(s)
- List of TODO markers requiring user input
- Confidence level (Complete / Partial / Template-only)

## Error Handling

- **Insufficient input**: Generate a template with TODO markers rather than refusing
- **Unknown section type**: Refer to the standards document and attempt to generate based on the section's requirements
- **Conflicting information**: Flag the conflict and ask the user to resolve before generating
