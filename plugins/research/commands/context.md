---
description: View indexed sources and context statistics
argument-hint: [--stats]
---

## Name
research:context

## Synopsis
```
/research:context [--stats]
```

## Description

The `research:context` command displays all sources indexed in your knowledge context, including metadata, chunk counts, and optional statistics.

## Implementation

**CRITICAL: You MUST use the wrapper script, not Python directly.**

### Step 1: Locate the Plugin Directory

```bash
# Find the research plugin
PLUGIN_DIR=""
for dir in \
    "$HOME/Documents/pillaimanish/ai-helpers/plugins/research" \
    "$HOME/.claude/plugins/cache/ai-helpers/research/*/"; do
    if [[ -f "$dir/skills/research-engine/scripts/research.sh" ]]; then
        PLUGIN_DIR="$dir"
        break
    fi
done
RESEARCH_SH="$PLUGIN_DIR/skills/research-engine/scripts/research.sh"
```

### Step 2: Read Manifest and Query DB

**Use the wrapper script:**
```bash
"$RESEARCH_SH" context [--stats]
```

### 2. Display Results

**Default view:**
```
📚 Research Context
═══════════════════════════════════════════════════════════════

Total: 12 sources, 2,341 chunks
Last updated: 2024-12-24 10:30:00

Sources:
────────────────────────────────────────────────────────────────
Type  Source                                      Chunks  Added
────────────────────────────────────────────────────────────────
📁    Current codebase (my-operator)              268     2h ago
🌐    kubernetes.io/docs/concepts/                423     2h ago
🌐    etcd.io/docs/                               312     1h ago
📺    YouTube: Kubernetes Tutorial                156     1h ago
🐙    github.com/etcd-io/etcd (indexed)           847     30m ago
📄    ~/notes/k8s-notes.md                        23      15m ago

Legend: 📁 codebase | 🌐 web | 📺 youtube | 🐙 github | 📄 local
```

**With --stats:**
```
📊 Context Statistics
═══════════════════════════════════════════════════════════════

Overview:
  Total sources: 12
  Total chunks: 2,341
  Vector dimensions: 384
  Embedding model: all-MiniLM-L6-v2
  Database size: 45.2 MB

By Source Type:
  📁 Codebase:  1 source,   268 chunks (11%)
  🌐 Web:       2 sources,  735 chunks (31%)
  📺 YouTube:   1 source,   156 chunks (7%)
  🐙 GitHub:    1 source,   847 chunks (36%)
  📄 Local:     1 source,    23 chunks (1%)

Top Sources by Chunks:
  1. github.com/etcd-io/etcd      847 chunks
  2. kubernetes.io/docs/          423 chunks
  3. etcd.io/docs/                312 chunks
```

## Arguments

- `--stats`: Show detailed statistics (chunk distribution, sizes, etc.)

## Return Value

Formatted table of sources with metadata.

## Examples

1. **List all sources:**
   ```
   /research:context
   ```

2. **Show statistics:**
   ```
   /research:context --stats
   ```

## Tips

- Run after `/research:build` to verify sources were added
- Use `--stats` to check if context is getting too large
- Sources are listed in order of when they were added

