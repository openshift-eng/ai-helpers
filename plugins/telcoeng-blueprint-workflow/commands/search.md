---
description: Search across normalized blueprints for patterns, configurations, and cross-references
argument-hint: <query> [--dir <blueprints-directory>]
---

## Name

telcoeng-blueprint-workflow:search

## Synopsis

```text
/telcoeng-blueprint-workflow:search <query> [--dir <blueprints-directory>]
```

## Description

The `search` command provides a central blueprint index by searching across all normalized blueprint documents for patterns, configurations, and cross-references. It enables queries like "which blueprints reference siteconfigv1?" or "show all BIOS settings across blueprints."

This implements NOW #4 (Central Blueprint Index & Search) from the prioritization matrix. It treats the collection of normalized blueprints as a searchable knowledge base.

### Key Features

- Searches across multiple blueprint files simultaneously
- Supports natural language queries and specific pattern matching
- Returns results with source file, section, and surrounding context
- Cross-references findings across blueprints for comparison
- Identifies commonalities and differences between partner blueprints

## Implementation

### Phase 1: Locate Blueprint Files

1. If `--dir` is provided, search that directory for `.md` files
2. Otherwise, search in default locations:
   - `.work/blueprints/*/blueprint.md` (ingested blueprints)
   - Sibling directories matching `*blueprint*` patterns
3. List all found blueprint files and their partner names
4. If no blueprints found, inform the user and suggest running `ingest` first

### Phase 2: Parse Search Query

Interpret the user's query:

1. **Specific pattern search**: If the query contains a specific term (e.g., "siteconfigv1", "SR-IOV", "SUPPORTEX-12345"), search for exact matches
2. **Section-scoped search**: If the query references a section (e.g., "BIOS settings", "S-BOM versions"), scope the search to that section type
3. **Comparison query**: If the query asks to compare (e.g., "compare networking across blueprints"), collect the relevant section from each blueprint
4. **Natural language**: For general questions, search all content and rank by relevance

### Phase 3: Search and Collect Results

For each blueprint file:

1. Read the file content
2. Search for matches based on the parsed query
3. For each match, extract:
   - Blueprint file path and partner name
   - Section heading where the match was found
   - The matching text with surrounding context (2-3 lines before/after)
   - Line number for reference

### Phase 4: Present Results

Display results grouped by blueprint:

```text
Found X matches across Y blueprints:

## acme-telecom (blueprint.md)
### Software and Configuration > S-BOM
  Line 45: | OpenShift Container Platform | 4.17.3 | 4.17.2 |
  Line 46: | Advanced Cluster Management | 2.11.1 | 2.11.0 |

## samsung (blueprint.md)
### Software and Configuration > S-BOM
  Line 52: | OpenShift Container Platform | 4.16.8 | 4.16.5 |
```

For comparison queries, present a side-by-side or merged view.

## Return Value

- **Match count**: Total matches found
- **Blueprint count**: Number of blueprints searched
- **Results**: Grouped by blueprint with section and context
- **Comparison table** (for comparison queries): Side-by-side view

## Examples

1. **Search for a specific configuration**:
   ```text
   /telcoeng-blueprint-workflow:search "siteconfigv1"
   ```

2. **Compare S-BOM across blueprints**:
   ```text
   /telcoeng-blueprint-workflow:search "compare OCP versions across blueprints"
   ```

3. **Find all BIOS settings**:
   ```text
   /telcoeng-blueprint-workflow:search "BIOS settings" --dir ./blueprints/
   ```

4. **Search for SUPPORTEX tickets**:
   ```text
   /telcoeng-blueprint-workflow:search "SUPPORTEX"
   ```

## Arguments

- `$1` (`<query>`): The search query. Can be a specific term, section name, or natural language question.
- `--dir <blueprints-directory>`: Directory containing blueprint Markdown files to search. Defaults to `.work/blueprints/`.

## Error Handling

- **No blueprints found**: Inform user, suggest running `ingest` to normalize documents first
- **No matches**: Report zero results, suggest alternative search terms
- **Large result set**: Limit to top 20 matches, offer to show more
- **Binary or non-Markdown files**: Skip with a warning
