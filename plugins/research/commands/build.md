---
description: Build knowledge context from URLs, repos, and files - stores directly in VectorDB
argument-hint: [sources...] [--include-cwd] [--repo URL] [--clear]
---

## Name

research:build

## Synopsis

```
/research:build [sources...] [--include-cwd] [--repo URL] [--clear] [--depth N] [--max-pages N]
```

## Description

The `research:build` command adds sources to the research context, **storing content directly in VectorDB (ChromaDB)** for semantic search. No intermediate files - content goes straight into the vector database.

**Unified Single-Step Process:**
1. Extract content from source
2. Chunk content for embeddings
3. Store directly in ChromaDB with embeddings
4. Track in manifest

**Supported Sources:**
- **Web URLs**: Recursive crawling with prefix restriction
- **YouTube**: Transcript extraction
- **GitHub Repos**: Clone → Index → Delete (saves disk space)
- **Local Files**: Markdown and text files
- **Current Codebase**: Auto-detect project type

**Upsert Behavior:**
- Running build on the same source **updates** existing content (no duplicates)
- New sources are **added** to existing context
- Use `--clear` to start fresh

## Implementation

**CRITICAL: You MUST use the wrapper script, not Python directly.**

The wrapper script handles Python version compatibility (Python 3.14 doesn't work with chromadb).

### Step 1: Locate the Plugin Directory

First, find where the research plugin is installed:

```bash
# Check common locations
PLUGIN_DIR=""
for dir in \
    "$HOME/Documents/pillaimanish/ai-helpers/plugins/research" \
    "$HOME/.claude/plugins/cache/ai-helpers/research/*/"; do
    if [[ -f "$dir/skills/research-engine/scripts/research.sh" ]]; then
        PLUGIN_DIR="$dir"
        break
    fi
done

# If using ai-helpers repo directly
if [[ -z "$PLUGIN_DIR" ]]; then
    PLUGIN_DIR="$(find "$HOME" -path "*/ai-helpers/plugins/research" -type d 2>/dev/null | head -1)"
fi

echo "Plugin found at: $PLUGIN_DIR"
```

### Step 2: Run the Wrapper Script

**ALWAYS use the wrapper script `research.sh`, never call Python directly:**

```bash
# The wrapper script path
RESEARCH_SH="$PLUGIN_DIR/skills/research-engine/scripts/research.sh"

# Make it executable if needed
chmod +x "$RESEARCH_SH"

# Run build command
"$RESEARCH_SH" build [arguments...]
```

### Step 3: Build Examples

**Add a documentation site:**
```bash
"$RESEARCH_SH" build "https://docs.example.com/"
```

**Add multiple sources:**
```bash
"$RESEARCH_SH" build \
    "https://docs.example.com/" \
    "https://youtube.com/watch?v=xyz" \
    --repo "https://github.com/owner/repo" \
    --include-cwd
```

**Clear and rebuild:**
```bash
"$RESEARCH_SH" build --clear "https://new-docs.example.com/"
```

**Add current codebase only:**
```bash
"$RESEARCH_SH" build --include-cwd
```

### Why the Wrapper Script?

The wrapper script (`research.sh`) automatically:
1. **Creates a Python 3.12 virtual environment** - Avoids Python 3.14 compatibility issues with chromadb
2. **Installs all dependencies** - chromadb, sentence-transformers, trafilatura, etc.
3. **Uses the correct Python** - From the venv, not system Python

**DO NOT run Python scripts directly** - they will fail on Python 3.14!

### Arguments

| Argument | Description |
|----------|-------------|
| `sources...` | URLs to process (web, YouTube) |
| `--include-cwd` | Include current working directory as context |
| `--repo URL` | GitHub repo to clone-index-delete (can use multiple times) |
| `--clear` | Clear existing context before adding new sources |
| `--depth N` | Max crawl depth for web (default: 3) |
| `--max-pages N` | Max pages to crawl (default: 50) |

### Storage Location

The VectorDB is stored in the **current working directory**:

```
.work/research/
├── context.db/          # ChromaDB vector database
│   └── chroma.sqlite3   # Embeddings and metadata
├── manifest.json        # Source tracking
└── venv/                # Python 3.12 virtual environment (auto-created)
```

## Return Value

- **Success**: JSON with source count, chunk count, and per-source results
- **Failure**: Error message with specific issue

## Examples

1. **Build context from SPIFFE docs:**
   ```
   /research:build https://spiffe.io/docs/
   ```

2. **Add YouTube video and GitHub repo:**
   ```
   /research:build https://youtube.com/watch?v=VIDEO --repo https://github.com/owner/repo
   ```

3. **Include current codebase:**
   ```
   /research:build --include-cwd
   ```

4. **Clear and rebuild with new sources:**
   ```
   /research:build https://new-docs.com/ --clear
   ```

## Arguments

- $1+: URLs to process (positional, optional)
- `--include-cwd`: Include current working directory
- `--repo URL`: GitHub repository to clone and index
- `--clear`: Clear existing context first
- `--depth N`: Max crawl depth for web (default: 3)
- `--max-pages N`: Max pages per web source (default: 50)
