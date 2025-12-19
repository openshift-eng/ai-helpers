# Research Plugin

Build and query a personal knowledge base from various sources using semantic vector search.

## Overview

The research plugin allows you to:
- **Ingest** content from URLs, YouTube videos, GitHub repositories, and local files
- **Store** content in a local vector database (ChromaDB) with semantic embeddings
- **Query** your knowledge base with natural language questions
- **Get accurate answers** based on the indexed content, not hallucinations

## Commands

| Command | Description |
|---------|-------------|
| `/research:add` | Add sources (URLs, YouTube, GitHub, docs) to a project |
| `/research:query` | Ask questions about the indexed content |
| `/research:list` | List all sources in a project |

## Prerequisites

### Required Tools

1. **Python 3.9+**
   ```bash
   python3 --version
   ```

2. **yt-dlp** (for YouTube transcripts)
   ```bash
   # Install
   pip install yt-dlp
   # Or on Fedora/RHEL
   sudo dnf install yt-dlp
   ```

3. **git** (for GitHub repos)
   ```bash
   git --version
   ```

### Python Dependencies

Install the required Python packages:

```bash
pip install chromadb sentence-transformers trafilatura beautifulsoup4 requests
```

## Quick Start

### 1. Create a new research project and add sources

```
/research:add my-k8s-study https://kubernetes.io/docs/concepts/overview/
```

### 2. Add more sources

```
/research:add my-k8s-study https://www.youtube.com/watch?v=X48VuDVv0do
/research:add my-k8s-study https://github.com/kubernetes/kubernetes
```

### 3. Query your knowledge base

```
/research:query my-k8s-study How do pods communicate with each other?
```

### 4. List all sources

```
/research:list my-k8s-study
```

## Supported Source Types

| Source Type | Example | Extraction Method |
|-------------|---------|-------------------|
| Web URLs | `https://docs.example.com/guide` | **Recursive crawling** (follows links within same domain) |
| YouTube | `https://youtube.com/watch?v=...` | yt-dlp (auto-generated captions) |
| GitHub Repos | `https://github.com/owner/repo` | git clone + file traversal |
| Local Files | `/path/to/document.md` | Direct file read |
| Google Docs | `https://docs.google.com/...` | Export as text (public docs) |

### Web Crawling Options

By default, web URLs are crawled recursively (follows all links within the same domain):

| Option | Default | Description |
|--------|---------|-------------|
| (none) | recursive | Follows links within same domain |
| `--single` | - | Only extract the single provided URL |
| `--depth N` | 3 | Maximum crawl depth |
| `--max-pages N` | 50 | Maximum pages to extract |
| `--allow-external` | - | Follow links to external domains |

**Examples:**
```bash
# Crawl entire docs site (up to 50 pages, depth 3)
/research:add my-study https://kubernetes.io/docs/concepts/

# Single article only
/research:add my-study https://blog.example.com/post --single

# Deep crawl with more pages
/research:add my-study https://docs.example.com/ --depth 5 --max-pages 100
```

## Storage Location

All research projects are stored in:
```
.work/research/{project-name}/
├── manifest.json      # Source tracking and metadata
├── sources/           # Raw extracted content
│   ├── web/
│   ├── youtube/
│   ├── github/
│   └── local/
└── vectordb/          # ChromaDB database
    └── chroma.sqlite3
```

## How It Works

1. **Content Extraction**: Each source type has a specialized extractor
2. **Chunking**: Content is split into semantic chunks (~500 tokens each)
3. **Embedding**: Chunks are converted to vectors using sentence-transformers
4. **Storage**: Vectors are stored in ChromaDB for fast similarity search
5. **Query**: Your question is embedded and matched against stored chunks
6. **Answer**: Claude receives the most relevant chunks and generates an accurate answer

## Tips

- **Be specific with project names**: Use descriptive names like `openshift-networking` instead of `study1`
- **Add diverse sources**: Mix documentation, videos, and code for comprehensive coverage
- **Refresh periodically**: Use `/research:add` with the same URL to update content
- **Query naturally**: Ask questions as you would ask a colleague

## Limitations

- YouTube requires auto-generated captions (most videos have them)
- Google Docs must be publicly accessible or shared with "anyone with link"
- Very large repositories may take time to ingest
- Embedding model runs locally (first run downloads ~90MB model)

