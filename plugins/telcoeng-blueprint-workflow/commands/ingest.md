---
description: Convert partner blueprints from Word/PDF/Google Docs into normalized Markdown aligned with telcoeng-blueprint-standards
argument-hint: <file-path> [--partner <name>] [--format word|pdf|markdown|gdocs]
---

## Name

telcoeng-blueprint-workflow:ingest

## Synopsis

```text
/telcoeng-blueprint-workflow:ingest <file-path> [--partner <name>] [--format word|pdf|markdown|gdocs]
```

## Description

The `ingest` command converts a partner blueprint document from Word, PDF, or Google Docs format into normalized Markdown that aligns with the `telcoeng-blueprint-standards` section hierarchy.

This is the foundation layer of the blueprint workflow (WOW #1 from the prioritization matrix). All downstream commands (`validate`, `generate`, `fix`) operate on normalized Markdown, making ingestion the required first step for non-Markdown blueprints.

### Key Features

- Auto-detects input format based on file extension
- Converts to raw Markdown using available tools (pandoc, MarkItDown, DocLing)
- Maps extracted content to the standards-compliant section structure
- Normalizes tables (S-BOM, H-BOM, deviation tables) into consistent Markdown format
- Reports unmapped content that could not be placed into standard sections
- Preserves original content — nothing is deleted, only reorganized

## Implementation

### Phase 1: Validate Input and Detect Format

1. Check that the file exists at the provided path
2. Detect format from extension (`.docx`, `.doc`, `.pdf`, `.md`) or from the `--format` flag
3. If the file is already Markdown, skip to Phase 3
4. Determine the partner name from `--partner` flag, file name, or prompt the user

### Phase 2: Convert to Raw Markdown

Based on available tools, convert the document:

**Priority order for conversion tools:**

1. **pandoc** (most reliable for Word): `pandoc -f docx -t markdown --wrap=none <file>`
2. **MarkItDown** (Microsoft, good for mixed formats): Python library, install with `pip install markitdown`
3. **DocLing** (IBM Research, good for PDFs): Python library for document understanding

Run the conversion and capture the raw Markdown output. If the first tool fails, try the next in priority order.

**Post-conversion cleanup** (required for all tools):

Remove pandoc and conversion artifacts that break Markdown rendering:
- `{.underline}` — remove entirely
- `{.mark}` — remove entirely
- `{width="..." height="..."}` — remove image dimension attributes
- `\[text\]` — unescape square brackets to `[text]`
- `\'` — unescape apostrophes to `'`
- Escaped pipes in tables — unescape `\|` to `|` within table cells
- Grid tables — convert to standard pipe tables
- Any remaining `{.*}` attribute patterns — remove curly-brace annotations not caught above

**Image and diagram handling**:

Pandoc converts embedded Word images to `![](media/imageN.ext)` references. These files exist only in the pandoc media extraction directory, not in the output Markdown. For each image reference:
1. If the image file was extracted alongside the Markdown, copy it to `.work/blueprints/<partner-name>/media/`
2. If the image file is not available, replace the reference with a descriptive comment: `<!-- DIAGRAM: [description based on surrounding context] — source: original document -->`
3. Never leave bare `![](media/imageN.ext)` references that point to nonexistent files

**For Google Docs:**
1. If a URL is provided, inform the user to export as `.docx` first
2. If a downloaded `.docx` is provided, proceed with Word conversion

### Phase 3: Load Standards Structure

Invoke the `blueprint-structure` skill using the Skill tool to:

1. Locate and read the current `telcoeng-blueprint-standards/README.md`
2. Extract the required section hierarchy
3. Get the list of mandatory sections and their expected content

### Phase 4: Map Content to Standards Sections

Analyze the raw Markdown and map content to the standards-compliant sections:

1. **Heading matching**: Match existing headings in the document to standards section names (fuzzy match — case-insensitive, synonym support)
2. **Content classification**: For content under non-standard headings, classify by content type:
   - Tables with version columns → Software and Configuration (S-BOM)
   - Tables with hardware specs → Hardware and Node Configuration (H-BOM)
   - Network diagrams or VLAN references → Networking
   - Upgrade procedures → Operations and Management > LCM
   - SUPPORTEX references → Software and Configuration > Support Exceptions
3. **Unmapped content**: Content that cannot be classified goes into an "Unmapped Content" appendix

### Phase 5: Normalize Tables

For each recognized table type, normalize to the standards format:

- **S-BOM**: Ensure columns are Component | Version | Minimum Patch Level
- **H-BOM**: Ensure columns are Component | Specification
- **Support Exceptions**: Ensure columns are Support Exception ID | Required for | Status/Comments
- **Operators**: Ensure columns are Operator | Version | Channel | Role
- **NADs**: Ensure columns are NAD Name | Type | Parameters

Preserve all original data — only restructure column order and headers.

### Phase 6: Generate Output

1. Assemble the normalized blueprint with all sections in the standards-prescribed order
2. Insert `<!-- TODO: This section needs content -->` markers for empty mandatory sections
3. Save to `.work/blueprints/<partner-name>/blueprint.md`
4. Generate a summary report listing:
   - Sections successfully mapped (with content)
   - Sections empty (need content)
   - Unmapped content (needs manual placement)
   - Tables normalized (with before/after column mapping)

### Phase 7: Present Results

Display to the user:
1. The output file path
2. The mapping summary (how many sections mapped vs. empty)
3. Any unmapped content that needs manual review
4. Suggested next steps: run `validate` to check compliance, or `generate` to fill empty sections

## Return Value

- **Output file path**: `.work/blueprints/<partner-name>/blueprint.md`
- **Mapping summary**: Sections mapped / empty / unmapped counts
- **Unmapped content list**: Items that could not be automatically placed
- **Conversion tool used**: Which tool performed the conversion

## Examples

1. **Convert a Word document**:
   ```text
   /telcoeng-blueprint-workflow:ingest ~/Documents/partner-blueprint.docx --partner acme-telecom
   ```
   Output:
   ```text
   Ingested: partner-blueprint.docx → .work/blueprints/acme-telecom/blueprint.md
   Sections mapped: 5/7 | Empty: 2 | Unmapped content: 3 blocks
   Next: Run /telcoeng-blueprint-workflow:validate .work/blueprints/acme-telecom/blueprint.md
   ```

2. **Convert a PDF**:
   ```text
   /telcoeng-blueprint-workflow:ingest ./samsung-vbsc-blueprint.pdf --partner samsung
   ```

3. **Normalize an existing Markdown file**:
   ```text
   /telcoeng-blueprint-workflow:ingest ./existing-blueprint.md --partner softbank
   ```
   Skips conversion, goes directly to section mapping and normalization.

## Arguments

- `$1` (`<file-path>`): Path to the blueprint document to ingest. Supports `.docx`, `.doc`, `.pdf`, `.md` extensions.
- `--partner <name>`: Partner name for output directory naming. If omitted, derived from file name or prompted interactively.
- `--format <type>`: Override format detection. Values: `word`, `pdf`, `markdown`, `gdocs`.

## Error Handling

- **File not found**: Display error with the provided path and suggest checking the path
- **No conversion tool available**: List which tools are needed and provide installation commands (`pip install markitdown`, `brew install pandoc`)
- **Conversion failure**: Show the error from the conversion tool, suggest trying a different format or tool
- **Empty document**: Warn that the document appears empty, suggest checking the file
- **Standards not found**: Fall back to `reference/blueprint-sections.md` for section hierarchy
