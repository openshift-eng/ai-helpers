# Research Plugin

Build and query a unified knowledge context from various sources using semantic vector search.

## Overview

The research plugin creates a **single unified context** that you can incrementally build from:
- 🌐 **Web URLs** - Documentation sites (recursive crawling)
- 📺 **YouTube** - Video transcripts
- 🐙 **GitHub Repos** - Clone → Index → Delete (saves space)
- 📁 **Current Codebase** - Auto-detect your project
- 📄 **Local Files** - Markdown, code, docs

## Commands

| Command | Description |
|---------|-------------|
| `/research:build` | Add sources to your context (incremental) |
| `/research:ask` | Query your knowledge context |
| `/research:context` | List indexed sources and stats |

## Quick Start

```bash
# 1. Add your current codebase to context
/research:build --include-cwd

# 2. Add some documentation
/research:build https://kubernetes.io/docs/concepts/

# 3. Add a YouTube tutorial
/research:build https://www.youtube.com/watch?v=X48VuDVv0do

# 4. Add a GitHub repo (clones, indexes, then deletes clone)
/research:build --repo https://github.com/etcd-io/etcd

# 5. Ask questions!
/research:ask How does etcd handle leader election?
```

## Key Features

### Incremental Building

Each `/research:build` call **appends** to the existing context:

```bash
/research:build https://docs.example.com/   # Adds docs
/research:build https://youtube.com/...      # Adds video (keeps docs)
/research:build --include-cwd                # Adds codebase (keeps all)
```

### GitHub Repo Handling

GitHub repos are handled efficiently:
1. **Clone** - Shallow clone to temp directory
2. **Extract** - Key files (README, docs, API types, controllers)
3. **Index** - Chunk, embed, store in VectorDB
4. **Delete** - Remove clone (only embeddings remain)

```bash
# Index a repo without keeping it on disk
/research:build --repo https://github.com/kubernetes/client-go
```

### Current Codebase Auto-Detection

Automatically detects and indexes your project:

```bash
/research:build --include-cwd
```

Detects:
- Project type (Go operator, Node.js, Python, etc.)
- Dependencies (go.mod, package.json, requirements.txt)
- Key files (README, API types, controllers, configs)

### Build Modes

| Mode | Flag | Behavior |
|------|------|----------|
| **Append** | (default) | Add new sources, keep existing |
| **Clear** | `--clear` | Wipe everything, start fresh |
| **Refresh** | `--refresh` | Re-fetch and update a source |

## Prerequisites

### Automatic Installation (Recommended)

**Dependencies are automatically installed when you first run a command!** No manual setup required.

When you run `/research:build`, the plugin will:
1. Check for missing packages
2. Auto-install them via pip
3. Continue with the operation

### Manual Installation (Optional)

If you prefer to install manually:

```bash
pip install chromadb sentence-transformers trafilatura beautifulsoup4 requests yt-dlp
```

## Storage

**Content goes directly into VectorDB** - no intermediate files:

```
.work/research/
├── context.db/          # ChromaDB vector database (embeddings + metadata)
│   └── chroma.sqlite3   # SQLite database with vectors
└── manifest.json        # Source tracking and stats
```

**What's stored:**
- **Embeddings** - Numerical vectors for semantic search
- **Chunks** - Original text chunks (~500 tokens each)
- **Metadata** - Source URL, title, type, timestamps

## Examples

### Build Context for Learning Kubernetes

```bash
# Add official docs
/research:build https://kubernetes.io/docs/concepts/

# Add a tutorial video
/research:build https://www.youtube.com/watch?v=X48VuDVv0do

# Add the client-go library (index only, delete clone)
/research:build --repo https://github.com/kubernetes/client-go

# Now ask questions!
/research:ask How do I create a pod using client-go?
```

### Build Context for Your Project

```bash
# Index your current codebase
/research:build --include-cwd

# Add related upstream repos
/research:build --repo https://github.com/operator-framework/operator-sdk

# Add relevant docs
/research:build https://sdk.operatorframework.io/docs/

# Ask about your project!
/research:ask How should I implement a validating webhook in my operator?
```

### Manage Context

```bash
# View what's indexed
/research:context

# View with stats
/research:context --stats

# Clear and rebuild
/research:build --clear https://new-docs.example.com/
```

## How It Works

**Building (single unified step):**
1. **Extract** - Content fetched from source (web, YouTube, GitHub, etc.)
2. **Chunk** - Split into ~500 token chunks with overlap
3. **Embed** - Chunks converted to 384-dim vectors (MiniLM-L6-v2)
4. **Store** - Vectors + chunks saved to ChromaDB (no intermediate files!)

**Querying:**
1. **Embed** - Your question converted to vector
2. **Search** - Find top-N similar chunks (semantic search)
3. **Answer** - Claude receives relevant chunks and generates answer

## Tips

- **Start with your codebase** - Always add `--include-cwd` for context-aware answers
- **Add relevant docs** - Documentation helps answer "how to" questions
- **Add reference repos** - Similar projects provide implementation examples
- **Refresh after changes** - Use `--refresh --include-cwd` after code changes
