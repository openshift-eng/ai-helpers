---
name: Research Engine
description: |
  Unified vector-based knowledge context for research and learning.
  Supports web pages, YouTube videos, GitHub repositories, and current codebase.
  Uses ChromaDB for vector storage and sentence-transformers for embeddings.
---

# Research Engine Skill

This skill provides the core functionality for building and querying a unified knowledge context.

## Overview

The research engine:
1. **Extracts** content from various sources (web, YouTube, GitHub, codebase)
2. **Chunks** content into semantic segments (~500 tokens each)
3. **Embeds** chunks using sentence-transformers (all-MiniLM-L6-v2)
4. **Stores** embeddings in a single ChromaDB collection
5. **Queries** using semantic search across all sources

## Key Features

- **Incremental Building**: Each `/research:build` call appends to existing context
- **Upsert Mode**: Existing sources are updated, not duplicated
- **GitHub Efficiency**: Clone → Index → Delete (no disk space wasted)
- **Codebase Auto-Detection**: Understands your project structure

## Prerequisites

### Required Python Packages

```bash
pip install chromadb sentence-transformers trafilatura beautifulsoup4 requests
```

### Optional Tools

```bash
pip install yt-dlp  # For YouTube transcripts
```

## Storage Structure

All data stored in a single location:

```
.work/research/
├── context.db/       # ChromaDB vector database
├── manifest.json     # Source tracking and metadata
└── sources/          # Extracted content cache
    ├── codebase/
    ├── web/
    ├── youtube/
    ├── github/
    └── local/
```

## Implementation Steps

### Step 1: Process Sources

For each source type, run the appropriate extraction script:

#### Current Codebase (`--include-cwd`)
```bash
python3 plugins/research/skills/research-engine/scripts/extract_codebase.py \
  --path "$(pwd)" \
  --output ".work/research/sources/codebase/"
```

Auto-detects project type, dependencies, and key files.

#### Web URLs (Recursive by Default)
```bash
python3 plugins/research/skills/research-engine/scripts/extract_web.py \
  --url "https://docs.example.com/" \
  --output ".work/research/sources/web/" \
  --depth 3 \
  --max-pages 50
```

#### YouTube Videos
```bash
python3 plugins/research/skills/research-engine/scripts/extract_youtube.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output ".work/research/sources/youtube/"
```

#### GitHub Repos (Clone → Index → Delete)
```bash
python3 plugins/research/skills/research-engine/scripts/extract_github_temp.py \
  --url "https://github.com/owner/repo" \
  --output ".work/research/sources/github/"
```

The repo is cloned to a temp directory, indexed, then deleted.

#### Local Files
```bash
python3 plugins/research/skills/research-engine/scripts/extract_local.py \
  --path "/path/to/file.md" \
  --output ".work/research/sources/local/"
```

### Step 2: Ingest to VectorDB

After extraction, ingest to the unified database:

```bash
# Ingest all new sources (upsert mode - updates existing)
python3 plugins/research/skills/research-engine/scripts/ingest.py \
  --source-dir ".work/research/sources/" \
  --mode upsert

# Ingest a specific file
python3 plugins/research/skills/research-engine/scripts/ingest.py \
  --source-file ".work/research/sources/web/kubernetes-io-abc123.md" \
  --mode upsert

# Clear and rebuild
python3 plugins/research/skills/research-engine/scripts/ingest.py \
  --source-dir ".work/research/sources/" \
  --clear
```

### Step 3: Query the Context

```bash
python3 plugins/research/skills/research-engine/scripts/query.py \
  --question "How does the controller handle pod deletion?" \
  --top-k 15
```

Output (JSON):
```json
{
  "success": true,
  "query": "How does the controller handle pod deletion?",
  "total_chunks_searched": 2341,
  "results_returned": 15,
  "sources_matched": 4,
  "sources_summary": [
    {"type": "codebase", "title": "my-operator", "max_relevance": 0.91},
    {"type": "web", "title": "kubernetes.io/docs", "max_relevance": 0.85}
  ],
  "results": [
    {
      "content": "When a pod is deleted, the controller...",
      "source_type": "codebase",
      "source_title": "my-operator",
      "relevance_score": 0.91
    }
  ]
}
```

### Step 4: List Context

```bash
python3 plugins/research/skills/research-engine/scripts/list_context.py
python3 plugins/research/skills/research-engine/scripts/list_context.py --stats
```

## Build Modes

| Mode | Flag | Behavior |
|------|------|----------|
| **Append** | (default) | Add new sources, keep existing |
| **Upsert** | `--mode upsert` | Update existing source if same ID |
| **Clear** | `--clear` | Wipe everything, start fresh |

## Source Detection

The engine auto-detects source types:

| Pattern | Type |
|---------|------|
| `youtube.com/watch`, `youtu.be/` | youtube |
| `github.com/{owner}/{repo}` | github |
| `docs.google.com/document` | gdocs |
| Starts with `/`, `./`, `~` | local |
| `--include-cwd` flag | codebase |
| Everything else | web |

## Error Handling

- **Network errors**: Retry up to 3 times
- **GitHub clone fails**: Report error, continue with other sources
- **YouTube no captions**: Skip video, suggest alternatives
- **Large files**: Skip files > 100KB

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `extract_codebase.py` | Extract current project files |
| `extract_web.py` | Recursive web crawling |
| `extract_youtube.py` | YouTube transcript extraction |
| `extract_github_temp.py` | Clone → Index → Delete repos |
| `extract_local.py` | Local file extraction |
| `ingest.py` | Unified VectorDB ingestion |
| `query.py` | Semantic search queries |
| `list_context.py` | List sources and stats |

## Tips

1. **Start with codebase**: Always add `--include-cwd` for context-aware answers
2. **Add relevant docs**: Documentation helps answer "how to" questions
3. **Use GitHub sparingly**: Each repo adds many chunks
4. **Refresh after changes**: Run `--refresh --include-cwd` after code changes
