---
name: go-mod-dependency-paths
description: Parse go mod graph output to enumerate paths from the root module to a vulnerable dependency for CVE impact reports
---

# Go Module Dependency Paths

Deterministic helper for **Method 2** of dependency tree analysis: given `go mod graph` output, list every module path from the project root to a target module (typically the CVE-affected module).

## When to Use This Skill

Use when analyzing a Go codebase for CVE impact and you need:

- All dependency chains from the main module to a vulnerable module coordinate
- ASCII tree formatting suitable for `dependency-tree.txt` / report sections
- Consistent output (run the script; do not re-type or paraphrase the algorithm in chat)

## Prerequisites

- `go mod graph` has already been written to a file (e.g. `mod-graph.txt`)
- Python 3.9+ available as `python3`
- Target module string from the CVE profile (full `path@version` or path prefix matching the graph nodes)

## Script

**Repository path (relative to ai-helpers root):**

`plugins/compliance/skills/go-mod-dependency-paths/parse_mod_graph_paths.py`

## Usage

```bash
python3 plugins/compliance/skills/go-mod-dependency-paths/parse_mod_graph_paths.py \
  .work/compliance/analyze-cve/${CVE_ID}/mod-graph.txt \
  "golang.org/x/net@v0.0.0-20211015210444"
```

Optional: limit search depth (default 20):

```bash
python3 plugins/compliance/skills/go-mod-dependency-paths/parse_mod_graph_paths.py \
  .work/compliance/analyze-cve/${CVE_ID}/mod-graph.txt \
  "golang.org/x/net@v0.0.0-20211015210444" \
  --max-depth 30
```

Save stdout to the analysis workdir:

```bash
python3 plugins/compliance/skills/go-mod-dependency-paths/parse_mod_graph_paths.py \
  .work/compliance/analyze-cve/${CVE_ID}/mod-graph.txt \
  "<vulnerable-module>" \
  | tee .work/compliance/analyze-cve/${CVE_ID}/dependency-tree.txt
```

## Behavior

1. Parses `mod-graph.txt` as directed edges (`dependent dependency` per line).
2. Treats the **first line’s left-hand module** as the graph root (same convention as `go mod graph`).
3. Enumerates paths where the current module equals the target or starts with the target’s module path prefix (before `@`).
4. On failure, prints up to ten similar module strings from the graph to help fix typos or version mismatches.
5. Exits with status **1** if no path is found.

## Integration

Invoked from `/compliance:analyze-cve` **Phase 2** after `go mod graph` is captured. The parent command should not inline this logic; always run this script for path enumeration.
