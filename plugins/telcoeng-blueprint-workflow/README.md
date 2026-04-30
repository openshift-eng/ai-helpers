# Telco Blueprint Workflow Plugin

End-to-end blueprint lifecycle management for Telco Engineering partner blueprints, aligned with `telcoeng-blueprint-standards`.

## Features

- **Document Ingestion** - Convert partner blueprints from Word/PDF/Google Docs into normalized Markdown matching the standards section hierarchy
- **Compliance Validation** - Score blueprints (0-100) against `telcoeng-blueprint-standards` with section-by-section compliance reports
- **Content Generation** - Generate standards-compliant S-BOM tables, networking sections, deviation lists, and full blueprint scaffolds
- **Blueprint Search** - Search across normalized blueprints for patterns, configurations, and cross-references
- **Automated Fix Proposals** - Generate concrete fix proposals as diffs for non-compliant sections, with optional auto-apply
- **JIRA Integration** - Create and update ECOPS tickets for compliance findings and deviations
- **Cluster Validation** - Validate live clusters against Telco RDS profiles via kube-compare-mcp

## Prerequisites

- Claude Code installed
- `telcoeng-blueprint-standards` repository accessible (sibling directory or discoverable path)
- Optional: `pandoc` or `pip install markitdown` for Word/PDF conversion
- Optional: kube-compare-mcp server configured for cluster-level validation
- Optional: Jira MCP server configured for ECOPS ticket integration

## Installation

Ensure you have the ai-helpers marketplace enabled, via [the instructions here](https://github.com/openshift-eng/ai-helpers#readme).

```bash
/plugin install telcoeng-blueprint-workflow@ai-helpers
```

## Available Commands

### `/telcoeng-blueprint-workflow:ingest` - Document Ingestion & Normalization

Convert partner blueprints from Word, PDF, or Google Docs into normalized Markdown aligned with `telcoeng-blueprint-standards`.

```bash
# Convert a Word document
/telcoeng-blueprint-workflow:ingest ~/Documents/partner-blueprint.docx --partner acme-telecom

# Normalize an existing Markdown file
/telcoeng-blueprint-workflow:ingest ./existing-blueprint.md --partner softbank
```

See [commands/ingest.md](commands/ingest.md) for full documentation.

---

### `/telcoeng-blueprint-workflow:validate` - Compliance Checking & Validation

Score a blueprint against `telcoeng-blueprint-standards` (0-100) with a section-by-section compliance report.

```bash
# Basic validation
/telcoeng-blueprint-workflow:validate .work/blueprints/acme-telecom/blueprint.md

# Validation with cluster check
/telcoeng-blueprint-workflow:validate ./blueprint.md --cluster ~/.kube/config --partner samsung

# Validation with JIRA ticket creation
/telcoeng-blueprint-workflow:validate ./blueprint.md --partner softbank --jira
```

See [commands/validate.md](commands/validate.md) for full documentation.

---

### `/telcoeng-blueprint-workflow:generate` - Content Generation

Generate standards-compliant paragraphs, tables, and sections for Telco Partner Blueprints.

```bash
# Generate S-BOM table
/telcoeng-blueprint-workflow:generate sbom --partner acme-telecom --ocp-version 4.17

# Generate full blueprint scaffold
/telcoeng-blueprint-workflow:generate all --partner samsung --ocp-version 4.16

# Generate and insert into existing blueprint
/telcoeng-blueprint-workflow:generate deviations --blueprint .work/blueprints/softbank/blueprint.md
```

Supported section types: `metadata`, `intro`, `sbom`, `operators`, `support-exceptions`, `deviations`, `hbom`, `node-config`, `networking`, `operations`, `certification`, `all`.

See [commands/generate.md](commands/generate.md) for full documentation.

---

### `/telcoeng-blueprint-workflow:search` - Blueprint Index & Search

Search across normalized blueprints for patterns, configurations, and cross-references.

```bash
# Search for a specific configuration
/telcoeng-blueprint-workflow:search "siteconfigv1"

# Compare S-BOM across blueprints
/telcoeng-blueprint-workflow:search "compare OCP versions across blueprints"

# Search with custom directory
/telcoeng-blueprint-workflow:search "BIOS settings" --dir ./blueprints/
```

See [commands/search.md](commands/search.md) for full documentation.

---

### `/telcoeng-blueprint-workflow:fix` - Automated Fix Proposals

Compare non-compliant blueprints against standards and propose concrete fixes as diffs.

```bash
# Interactive fix session
/telcoeng-blueprint-workflow:fix .work/blueprints/acme-telecom/blueprint.md --partner acme-telecom

# Auto-apply all fixes
/telcoeng-blueprint-workflow:fix ./blueprint.md --partner samsung --auto

# Fix with JIRA tracking
/telcoeng-blueprint-workflow:fix ./blueprint.md --partner softbank --jira
```

See [commands/fix.md](commands/fix.md) for full documentation.

---

## Typical Workflow

```text
1. Ingest    Partner sends Word doc  -->  /telcoeng-blueprint-workflow:ingest
2. Validate  Check compliance        -->  /telcoeng-blueprint-workflow:validate
3. Fix       Apply automated fixes   -->  /telcoeng-blueprint-workflow:fix
4. Generate  Fill remaining gaps     -->  /telcoeng-blueprint-workflow:generate
5. Search    Cross-reference others  -->  /telcoeng-blueprint-workflow:search
6. Validate  Final compliance check  -->  /telcoeng-blueprint-workflow:validate
```

## Standards Resilience

This plugin reads `telcoeng-blueprint-standards` dynamically at runtime. When standards change:

- Section hierarchy updates automatically on next command run
- Compliance rubric weights can be adjusted in `reference/compliance-rubric.md`
- No hardcoded section names or compliance rules in commands or skills

## Reference Files

| File | Purpose |
|------|---------|
| [reference/blueprint-sections.md](reference/blueprint-sections.md) | Standards section hierarchy (pointer to canonical source) |
| [reference/mcp-tools.md](reference/mcp-tools.md) | kube-compare-mcp and JIRA MCP tool signatures |
| [reference/compliance-rubric.md](reference/compliance-rubric.md) | Scoring criteria and weights (configurable) |

## Contributing

Contributions welcome! Please submit pull requests to the [ai-helpers repository](https://github.com/openshift-eng/ai-helpers).

## License

Apache-2.0
