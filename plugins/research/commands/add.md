---
description: Add sources (URLs, YouTube, GitHub repos, local files) to a research project
argument-hint: <project-name> <source-url-or-path> [--single] [--depth N] [--max-pages N]
---

## Name
research:add

## Synopsis
```
/research:add <project-name> <source> [options]
```

## Description

The `research:add` command ingests content from various sources into a research project's vector database. It extracts text content, chunks it semantically, generates embeddings, and stores them in ChromaDB for later querying.

**Supported source types:**
- **Web URLs**: Articles, documentation, blog posts (recursive by default!)
- **YouTube**: Video transcripts (auto-generated captions)
- **GitHub**: Repository code and documentation
- **Local files**: Markdown, text, code files
- **Google Docs**: Publicly shared documents

**Web Crawling Modes:**
| Option | Behavior |
|--------|----------|
| (default) | Recursive - follows all links within same domain |
| `--single` | Only extract the single provided URL |
| `--depth N` | Maximum crawl depth (default: 3) |
| `--max-pages N` | Maximum pages to crawl (default: 50) |

## Implementation

The command delegates to the research-engine skill which handles:

### 1. Project Initialization
- Create project directory at `.work/research/{project-name}/` if it doesn't exist
- Initialize ChromaDB collection for the project
- Create/update `manifest.json` to track sources

### 2. Source Detection & Extraction
For each provided source, detect type and extract content:

#### Web URLs (default - recursive crawling)
```bash
# Default: Recursive crawling (follows links, same domain only)
python3 plugins/research/skills/research-engine/scripts/extract_web.py \
  --url "https://example.com/docs/" \
  --output ".work/research/{project}/sources/web/" \
  --depth 3 \
  --max-pages 50

# Single page only
python3 plugins/research/skills/research-engine/scripts/extract_web.py \
  --url "https://example.com/article" \
  --output ".work/research/{project}/sources/web/" \
  --single
```

#### YouTube Videos
Detected by: `youtube.com`, `youtu.be` in URL
```bash
python3 plugins/research/skills/research-engine/scripts/extract_youtube.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output ".work/research/{project}/sources/youtube/"
```

#### GitHub Repositories
Detected by: `github.com` in URL (not raw files)
```bash
python3 plugins/research/skills/research-engine/scripts/extract_github.py \
  --url "https://github.com/owner/repo" \
  --output ".work/research/{project}/sources/github/"
```

#### Local Files
Detected by: Path starts with `/` or `./` or `~`
```bash
python3 plugins/research/skills/research-engine/scripts/extract_local.py \
  --path "/path/to/file.md" \
  --output ".work/research/{project}/sources/local/"
```

### 3. Chunking & Embedding
After extraction, process content into the vector database:
```bash
python3 plugins/research/skills/research-engine/scripts/ingest.py \
  --project "{project-name}" \
  --source-dir ".work/research/{project}/sources/"
```

### 4. Update Manifest
Track the source in `manifest.json`:
```json
{
  "project": "my-study",
  "created": "2024-12-12T10:00:00Z",
  "sources": [
    {
      "id": "abc123",
      "type": "web",
      "url": "https://example.com/article",
      "title": "Article Title",
      "added": "2024-12-12T10:00:00Z",
      "chunks": 15,
      "status": "indexed"
    }
  ]
}
```

## Arguments
- `$1`: Project name (required) - Identifier for the research project (e.g., `k8s-networking`)
- `$2`: Source URL or path (required) - Source to add

**Options for web URLs:**
- `--single`: Only extract the provided URL, don't follow links
- `--depth N`: Maximum crawl depth for recursive mode (default: 3)
- `--max-pages N`: Maximum pages to extract (default: 50)
- `--allow-external`: Allow following links to external domains

## Return Value
- **Success**: Confirmation message with number of chunks indexed
- **Partial**: Warning if some sources failed with details
- **Failure**: Error message with troubleshooting steps

## Examples

1. **Add documentation site (recursive by default)**:
   ```
   /research:add openshift-study https://docs.openshift.com/container-platform/latest/welcome/index.html
   ```
   This will crawl up to 50 pages within the same domain.

2. **Add a single article only**:
   ```
   /research:add openshift-study https://blog.example.com/article --single
   ```

3. **Crawl deeper with more pages**:
   ```
   /research:add k8s-study https://kubernetes.io/docs/concepts/ --depth 5 --max-pages 100
   ```

4. **Add a YouTube video**:
   ```
   /research:add k8s-basics https://www.youtube.com/watch?v=X48VuDVv0do
   ```

5. **Add a GitHub repository**:
   ```
   /research:add etcd-deep-dive https://github.com/etcd-io/etcd
   ```

6. **Add a local file**:
   ```
   /research:add my-notes ~/Documents/study-notes.md
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `ChromaDB not installed` | Missing dependency | `pip install chromadb sentence-transformers` |
| `yt-dlp not found` | YouTube extraction unavailable | `pip install yt-dlp` |
| `No captions available` | YouTube video lacks subtitles | Try a different video or add transcript manually |
| `Repository too large` | GitHub repo exceeds limits | Clone manually and add as local path |
| `Connection timeout` | Network issue | Check connectivity and retry |

## Prerequisites

1. **Python packages**: `pip install chromadb sentence-transformers trafilatura requests`
2. **yt-dlp**: For YouTube transcripts (`pip install yt-dlp`)
3. **git**: For GitHub repositories

