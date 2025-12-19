---
name: Research Engine
description: |
  Vector-based knowledge base engine for ingesting and querying content from various sources.
  Supports web pages, YouTube videos, GitHub repositories, and local files.
  Uses ChromaDB for vector storage and sentence-transformers for embeddings.
---

# Research Engine Skill

This skill provides the core functionality for the research plugin, handling content extraction, chunking, embedding, storage, and semantic search.

## Overview

The research engine:
1. **Extracts** content from various source types (web, YouTube, GitHub, local files)
2. **Chunks** content into semantic segments (~500 tokens each)
3. **Embeds** chunks using sentence-transformers (all-MiniLM-L6-v2)
4. **Stores** embeddings in ChromaDB for fast similarity search
5. **Queries** the database using semantic search to find relevant content

## Prerequisites

### Required Python Packages

```bash
pip install chromadb sentence-transformers trafilatura beautifulsoup4 requests
```

### Optional Tools

- **yt-dlp**: For YouTube transcript extraction
  ```bash
  pip install yt-dlp
  ```

- **git**: For GitHub repository cloning

### Verify Installation

```bash
python3 -c "import chromadb; import sentence_transformers; print('✅ Dependencies installed')"
```

## Directory Structure

```
.work/research/{project-name}/
├── manifest.json           # Source tracking
├── sources/                # Extracted raw content
│   ├── web/
│   │   └── {domain}-{hash}.md
│   ├── youtube/
│   │   └── {video-id}.md
│   ├── github/
│   │   └── {repo-name}/
│   │       ├── _manifest.json
│   │       └── *.md (extracted files)
│   └── local/
│       └── {filename}.md
└── vectordb/               # ChromaDB storage
    └── chroma.sqlite3
```

## Implementation Steps

### Step 1: Initialize Project

Create project directory and ChromaDB collection:

```bash
python3 plugins/research/skills/research-engine/scripts/init_project.py \
  --project "my-project"
```

This creates:
- `.work/research/my-project/` directory structure
- Empty `manifest.json`
- ChromaDB collection named `my-project`

### Step 2: Extract Content

#### Web Pages (Recursive by Default)
```bash
# Default: Recursive crawling within same domain
python3 plugins/research/skills/research-engine/scripts/extract_web.py \
  --url "https://docs.example.com/guide/" \
  --output ".work/research/my-project/sources/web/"

# With custom depth and page limits
python3 plugins/research/skills/research-engine/scripts/extract_web.py \
  --url "https://docs.example.com/guide/" \
  --output ".work/research/my-project/sources/web/" \
  --depth 5 \
  --max-pages 100

# Single page only (no crawling)
python3 plugins/research/skills/research-engine/scripts/extract_web.py \
  --url "https://example.com/article" \
  --output ".work/research/my-project/sources/web/" \
  --single

# Allow external domains
python3 plugins/research/skills/research-engine/scripts/extract_web.py \
  --url "https://example.com/links" \
  --output ".work/research/my-project/sources/web/" \
  --allow-external
```

Uses `trafilatura` for clean article extraction and `beautifulsoup4` for link discovery.

**Crawling Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--single` | false | Only extract the provided URL |
| `--depth N` | 3 | Maximum crawl depth |
| `--max-pages N` | 50 | Maximum pages to extract |
| `--allow-external` | false | Follow links to other domains |

#### YouTube Videos
```bash
python3 plugins/research/skills/research-engine/scripts/extract_youtube.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output ".work/research/my-project/sources/youtube/"
```

Uses `yt-dlp` to download auto-generated captions.

#### GitHub Repositories
```bash
python3 plugins/research/skills/research-engine/scripts/extract_github.py \
  --url "https://github.com/owner/repo" \
  --output ".work/research/my-project/sources/github/" \
  --max-files 100
```

Clones repo (shallow) and extracts README, docs, and key source files.

#### Local Files
```bash
python3 plugins/research/skills/research-engine/scripts/extract_local.py \
  --path "/path/to/file.md" \
  --output ".work/research/my-project/sources/local/"
```

### Step 3: Ingest into Vector Database

```bash
python3 plugins/research/skills/research-engine/scripts/ingest.py \
  --project "my-project" \
  --source-file ".work/research/my-project/sources/web/example-com-abc123.md"
```

Or ingest all new sources:
```bash
python3 plugins/research/skills/research-engine/scripts/ingest.py \
  --project "my-project" \
  --all-new
```

The ingestion process:
1. Reads extracted content files
2. Splits into chunks (~500 tokens, with overlap)
3. Generates embeddings using sentence-transformers
4. Stores in ChromaDB with metadata

### Step 4: Query the Database

```bash
python3 plugins/research/skills/research-engine/scripts/query.py \
  --project "my-project" \
  --question "How does X work?" \
  --top-k 10
```

Output (JSON):
```json
{
  "query": "How does X work?",
  "project": "my-project",
  "results": [
    {
      "content": "X works by...",
      "source_url": "https://example.com/article",
      "source_title": "Understanding X",
      "source_type": "web",
      "chunk_index": 5,
      "relevance_score": 0.89
    }
  ],
  "total_chunks_searched": 847
}
```

### Step 5: List Sources

```bash
python3 plugins/research/skills/research-engine/scripts/list_sources.py \
  --project "my-project"
```

Output (JSON):
```json
{
  "project": "my-project",
  "created": "2024-12-12T10:00:00Z",
  "total_sources": 12,
  "total_chunks": 847,
  "sources": [
    {
      "id": "web-abc123",
      "type": "web",
      "url": "https://example.com/article",
      "title": "Article Title",
      "added": "2024-12-12T10:00:00Z",
      "chunks": 45,
      "status": "indexed"
    }
  ]
}
```

## Source Type Detection

The engine auto-detects source types:

| Pattern | Type |
|---------|------|
| `youtube.com/watch`, `youtu.be/` | youtube |
| `github.com/{owner}/{repo}` (not raw/blob) | github |
| `docs.google.com/document` | gdocs |
| Starts with `/`, `./`, `~`, or is local path | local |
| Everything else | web |

## Chunking Strategy

Content is chunked using these rules:
- **Target size**: ~500 tokens (roughly 375 words)
- **Overlap**: 50 tokens between chunks for context continuity
- **Boundaries**: Prefer splitting at paragraph/section boundaries
- **Metadata**: Each chunk preserves source URL, title, and position

## Embedding Model

Uses `all-MiniLM-L6-v2` from sentence-transformers:
- **Size**: ~90MB (downloaded on first use)
- **Dimensions**: 384
- **Speed**: Fast, runs on CPU
- **Quality**: Good balance of speed and accuracy

## Error Handling

### Network Errors
- Retry up to 3 times with exponential backoff
- Log failures and continue with other sources
- Mark failed sources in manifest

### Extraction Errors
- Log parsing failures with source URL
- Skip problematic files, continue with others
- Provide user-friendly error messages

### ChromaDB Errors
- Validate collection exists before operations
- Handle duplicate document IDs gracefully
- Provide recovery suggestions

## Performance Tips

1. **Batch ingestion**: Add multiple sources at once for efficiency
2. **GitHub limits**: Use `--max-files` to limit large repos
3. **First run**: Initial embedding model download (~90MB) takes time
4. **Query tuning**: Adjust `--top-k` based on result quality

## Maintenance

### Refresh Sources
Re-extract and re-ingest a source:
```bash
python3 plugins/research/skills/research-engine/scripts/ingest.py \
  --project "my-project" \
  --source-id "web-abc123" \
  --refresh
```

### Delete Source
```bash
python3 plugins/research/skills/research-engine/scripts/manage.py \
  --project "my-project" \
  --delete-source "web-abc123"
```

### Delete Project
```bash
rm -rf .work/research/my-project/
```

## Integration Notes

- All scripts output JSON to stdout for easy parsing
- Diagnostic/progress messages go to stderr
- Exit codes: 0 = success, 1 = error, 2 = partial success
- Scripts are idempotent - safe to re-run

