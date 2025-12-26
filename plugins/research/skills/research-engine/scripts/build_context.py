#!/usr/bin/env python3
"""
Unified context builder: Extract content and store directly in VectorDB.
Combines extraction + ingestion into a single step.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


# ============================================================================
# Dependency Management
# ============================================================================

def ensure_dependencies():
    """Check and install required dependencies."""
    required = [
        ("chromadb", "chromadb"),
        ("sentence_transformers", "sentence-transformers"),
        ("trafilatura", "trafilatura"),
        ("bs4", "beautifulsoup4"),
        ("requests", "requests"),
    ]
    
    missing = []
    for import_name, pip_name in required:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    
    if missing:
        print(f"📦 Installing: {', '.join(missing)}", file=sys.stderr)
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
                check=True, timeout=300
            )
            print(f"✅ Installed: {', '.join(missing)}", file=sys.stderr)
        except Exception as e:
            print(f"❌ Install failed: {e}", file=sys.stderr)
            print(f"   Run: pip install {' '.join(missing)}", file=sys.stderr)
            sys.exit(1)


# Auto-install on import
ensure_dependencies()


# ============================================================================
# Storage Configuration
# ============================================================================

RESEARCH_DIR = ".work/research"
VECTORDB_DIR = f"{RESEARCH_DIR}/context.db"
MANIFEST_FILE = f"{RESEARCH_DIR}/manifest.json"


# ============================================================================
# VectorDB Management
# ============================================================================

def get_collection():
    """Get or create the ChromaDB collection."""
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    
    Path(RESEARCH_DIR).mkdir(parents=True, exist_ok=True)
    
    client = chromadb.PersistentClient(
        path=VECTORDB_DIR,
        settings=Settings(anonymized_telemetry=False)
    )
    
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    return client.get_or_create_collection(
        name="research_context",
        embedding_function=embedding_fn,
        metadata={"description": "Unified research context"}
    )


def chunk_text(text: str, chunk_size: int = 500) -> list:
    """Split text into chunks."""
    words = text.split()
    words_per_chunk = int(chunk_size / 1.3)
    
    if len(words) <= words_per_chunk:
        return [text] if text.strip() else []
    
    chunks = []
    overlap = int(50 / 1.3)
    start = 0
    
    while start < len(words):
        end = start + words_per_chunk
        chunk = ' '.join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
    
    return chunks


def ingest_content(
    collection,
    content: str,
    source_id: str,
    source_type: str,
    source_url: str,
    source_title: str,
) -> int:
    """Ingest content directly into VectorDB. Returns chunk count."""
    
    # Delete existing chunks for this source (upsert)
    try:
        existing = collection.get(where={"source_id": source_id})
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except:
        pass
    
    # Chunk content
    chunks = chunk_text(content)
    if not chunks:
        return 0
    
    # Prepare documents
    documents = []
    metadatas = []
    ids = []
    
    for i, chunk in enumerate(chunks):
        documents.append(chunk)
        metadatas.append({
            "source_type": source_type,
            "source_id": source_id,
            "source_url": source_url,
            "source_title": source_title,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
        ids.append(f"{source_id}-chunk-{i}")
    
    # Add to collection
    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    
    return len(chunks)


# ============================================================================
# Manifest Management
# ============================================================================

def load_manifest() -> dict:
    """Load or create manifest."""
    path = Path(MANIFEST_FILE)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "sources": [],
        "stats": {"total_sources": 0, "total_chunks": 0},
    }


def save_manifest(manifest: dict, collection):
    """Save manifest with updated stats."""
    path = Path(MANIFEST_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest["updated"] = datetime.now(timezone.utc).isoformat()
    manifest["stats"]["total_sources"] = len(manifest["sources"])
    manifest["stats"]["total_chunks"] = collection.count()
    
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


def update_manifest_source(manifest: dict, source_info: dict):
    """Add or update source in manifest."""
    existing_idx = next(
        (i for i, s in enumerate(manifest["sources"]) if s["id"] == source_info["id"]),
        None
    )
    if existing_idx is not None:
        manifest["sources"][existing_idx] = source_info
    else:
        manifest["sources"].append(source_info)


# ============================================================================
# Source Extractors
# ============================================================================

def detect_source_type(source: str) -> str:
    """Detect source type from URL or path."""
    source_lower = source.lower()
    
    if source.startswith("--"):
        return "flag"
    
    if "youtube.com" in source_lower or "youtu.be" in source_lower:
        return "youtube"
    
    if "github.com" in source_lower and "/blob/" not in source_lower:
        # Check if it looks like a repo URL (has owner/repo pattern)
        if re.match(r'https?://github\.com/[^/]+/[^/]+', source):
            return "github"
    
    if source.startswith(("/", "./", "~", "../")) or os.path.exists(source):
        return "local"
    
    if source.startswith("http"):
        return "web"
    
    return "unknown"


def extract_web(url: str, collection, manifest: dict, max_pages: int = 50, max_depth: int = 3) -> dict:
    """Extract web content and store directly in VectorDB."""
    import trafilatura
    from trafilatura.settings import use_config
    import requests
    from bs4 import BeautifulSoup
    from collections import deque
    from urllib.parse import urljoin, urlparse, urldefrag
    
    config = use_config()
    config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")
    
    def normalize_url(u):
        u, _ = urldefrag(u)
        return u.rstrip('/').lower()
    
    def get_prefix(u):
        parsed = urlparse(u)
        path = parsed.path.rstrip('/') + '/'
        return f"{parsed.scheme}://{parsed.netloc}{path}".lower()
    
    start_prefix = get_prefix(url)
    visited = set()
    queue = deque([(url, 0)])
    
    total_chunks = 0
    pages_extracted = 0
    
    print(f"🌐 Crawling: {url}", file=sys.stderr)
    print(f"   Prefix: {start_prefix}*", file=sys.stderr)
    
    while queue and pages_extracted < max_pages:
        current_url, depth = queue.popleft()
        normalized = normalize_url(current_url)
        
        if normalized in visited:
            continue
        visited.add(normalized)
        
        # Skip non-page URLs
        if any(current_url.lower().endswith(ext) for ext in ['.pdf', '.zip', '.png', '.jpg', '.css', '.js']):
            continue
        
        print(f"   [{pages_extracted+1}/{max_pages}] {current_url[:70]}...", file=sys.stderr)
        
        try:
            headers = {"User-Agent": "Mozilla/5.0 (ResearchBot/1.0)"}
            resp = requests.get(current_url, headers=headers, timeout=30)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            continue
        
        # Extract content
        content = trafilatura.extract(html, include_tables=True, output_format="markdown", config=config)
        if not content or len(content) < 100:
            continue
        
        # Get title
        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata and metadata.title else urlparse(current_url).path.split('/')[-1]
        
        # Generate source ID
        url_hash = hashlib.md5(current_url.encode()).hexdigest()[:10]
        source_id = f"web-{url_hash}"
        
        # Store directly in VectorDB
        chunks = ingest_content(collection, content, source_id, "web", current_url, title)
        total_chunks += chunks
        pages_extracted += 1
        
        # Update manifest
        update_manifest_source(manifest, {
            "id": source_id,
            "type": "web",
            "title": title,
            "url": current_url,
            "chunks": chunks,
            "added": datetime.now(timezone.utc).isoformat(),
        })
        
        # Find links for recursive crawling
        if depth < max_depth:
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a', href=True):
                link = urljoin(current_url, a['href'])
                link_normalized = normalize_url(link)
                
                # Only follow links under same prefix
                if link_normalized.startswith(start_prefix.rstrip('/')) and link_normalized not in visited:
                    queue.append((link, depth + 1))
        
        import time
        time.sleep(0.3)
    
    print(f"   ✅ {pages_extracted} pages → {total_chunks} chunks", file=sys.stderr)
    
    return {"pages": pages_extracted, "chunks": total_chunks}


def extract_youtube(url: str, collection, manifest: dict) -> dict:
    """Extract YouTube transcript and store in VectorDB."""
    import shutil
    import tempfile
    
    # Ensure yt-dlp is available
    if not shutil.which("yt-dlp"):
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "yt-dlp"], check=True)
        except:
            return {"error": "Could not install yt-dlp"}
    
    # Extract video ID
    match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    if not match:
        return {"error": "Invalid YouTube URL"}
    
    video_id = match.group(1)
    print(f"📺 YouTube: {video_id}", file=sys.stderr)
    
    # Download subtitles
    with tempfile.TemporaryDirectory() as temp_dir:
        cmd = ["yt-dlp", "--skip-download", "--write-auto-sub", "--sub-lang", "en",
               "--sub-format", "vtt", "-o", f"{temp_dir}/%(id)s.%(ext)s", url]
        
        try:
            subprocess.run(cmd, capture_output=True, timeout=120)
        except:
            return {"error": "Failed to get transcript"}
        
        # Find VTT file
        vtt_file = None
        for f in Path(temp_dir).glob("*.vtt"):
            vtt_file = f
            break
        
        if not vtt_file:
            return {"error": "No captions available"}
        
        # Parse VTT
        with open(vtt_file, "r") as f:
            vtt_content = f.read()
        
        # Extract text from VTT
        lines = []
        seen = set()
        for line in vtt_content.split('\n'):
            if line.startswith('WEBVTT') or '-->' in line or re.match(r'^\d{2}:\d{2}', line):
                continue
            cleaned = re.sub(r'<[^>]+>', '', line).strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                lines.append(cleaned)
        
        transcript = ' '.join(lines)
    
    # Get video title
    try:
        info_cmd = ["yt-dlp", "--dump-json", "--no-download", url]
        result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(result.stdout)
        title = info.get("title", f"YouTube Video {video_id}")
    except:
        title = f"YouTube Video {video_id}"
    
    # Store in VectorDB
    source_id = f"youtube-{video_id}"
    content = f"# {title}\n\n{transcript}"
    chunks = ingest_content(collection, content, source_id, "youtube", url, title)
    
    # Update manifest
    update_manifest_source(manifest, {
        "id": source_id,
        "type": "youtube",
        "title": title,
        "url": url,
        "chunks": chunks,
        "added": datetime.now(timezone.utc).isoformat(),
    })
    
    print(f"   ✅ {title[:50]}... → {chunks} chunks", file=sys.stderr)
    
    return {"title": title, "chunks": chunks}


def extract_github(url: str, collection, manifest: dict, max_files: int = 75) -> dict:
    """Extract GitHub repo and store in VectorDB (clone → index → delete)."""
    
    # Parse URL
    match = re.search(r'github\.com/([^/]+)/([^/\?#]+)', url)
    if not match:
        return {"error": "Invalid GitHub URL"}
    
    owner, repo = match.groups()
    repo = repo.rstrip('.git')
    
    print(f"🐙 GitHub: {owner}/{repo}", file=sys.stderr)
    
    # Clone to temp dir
    temp_dir = tempfile.mkdtemp(prefix=f"research-{repo}-")
    clone_path = Path(temp_dir) / repo
    
    try:
        # Shallow clone
        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", f"https://github.com/{owner}/{repo}.git", str(clone_path)],
            check=True, timeout=180
        )
        
        # Find key files
        include_ext = {".md", ".go", ".py", ".js", ".ts", ".yaml", ".yml", ".json"}
        skip_dirs = {".git", "node_modules", "vendor", "__pycache__", "test", "tests"}
        
        files = []
        for f in clone_path.rglob("*"):
            if f.is_file() and f.suffix.lower() in include_ext:
                if not any(d in f.parts for d in skip_dirs):
                    files.append(f)
        
        # Sort by importance (README first, then by path)
        def priority(f):
            name = f.name.lower()
            if name.startswith("readme"): return 0
            if "api/" in str(f) or "_types.go" in name: return 1
            if "doc" in str(f).lower(): return 2
            return 10
        
        files.sort(key=priority)
        files = files[:max_files]
        
        # Extract and combine content
        all_content = [f"# GitHub: {owner}/{repo}\n\n"]
        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                if len(content) < 10 or len(content) > 100000:
                    continue
                relative = f.relative_to(clone_path)
                ext = f.suffix.lstrip('.') or 'text'
                all_content.append(f"\n## File: {relative}\n\n```{ext}\n{content}\n```\n")
            except:
                continue
        
        combined = ''.join(all_content)
        
        # Store in VectorDB
        source_id = f"github-{owner}-{repo}"
        chunks = ingest_content(collection, combined, source_id, "github", url, f"{owner}/{repo}")
        
        # Update manifest
        update_manifest_source(manifest, {
            "id": source_id,
            "type": "github",
            "title": f"{owner}/{repo}",
            "url": url,
            "files": len(files),
            "chunks": chunks,
            "added": datetime.now(timezone.utc).isoformat(),
        })
        
        print(f"   ✅ {len(files)} files → {chunks} chunks", file=sys.stderr)
        
        return {"files": len(files), "chunks": chunks}
        
    finally:
        # Always delete the clone
        shutil.rmtree(temp_dir, ignore_errors=True)


def extract_codebase(path: str, collection, manifest: dict) -> dict:
    """Extract current codebase and store in VectorDB."""
    
    project_path = Path(path).expanduser().resolve()
    print(f"📁 Codebase: {project_path.name}", file=sys.stderr)
    
    # Detect project type
    project_type = "unknown"
    if (project_path / "go.mod").exists():
        project_type = "go"
    elif (project_path / "package.json").exists():
        project_type = "nodejs"
    elif (project_path / "requirements.txt").exists():
        project_type = "python"
    
    # Find key files
    include_ext = {".md", ".go", ".py", ".js", ".ts", ".yaml", ".yml", ".json", ".sh"}
    skip_dirs = {".git", "node_modules", "vendor", "__pycache__", ".work", "dist", "build"}
    
    files = []
    for f in project_path.rglob("*"):
        if f.is_file() and f.suffix.lower() in include_ext:
            if not any(d in f.parts for d in skip_dirs):
                files.append(f)
    
    # Sort by priority
    def priority(f):
        name = f.name.lower()
        if name.startswith("readme"): return 0
        if "api/" in str(f) or "_types.go" in name: return 1
        if "controller" in str(f).lower(): return 2
        return 10
    
    files.sort(key=priority)
    files = files[:100]
    
    # Combine content
    all_content = [f"# Codebase: {project_path.name}\n\nType: {project_type}\n\n"]
    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            if len(content) < 10 or len(content) > 50000:
                continue
            relative = f.relative_to(project_path)
            ext = f.suffix.lstrip('.') or 'text'
            all_content.append(f"\n## {relative}\n\n```{ext}\n{content}\n```\n")
        except:
            continue
    
    combined = ''.join(all_content)
    
    # Store in VectorDB
    source_id = f"codebase-{hashlib.md5(str(project_path).encode()).hexdigest()[:8]}"
    chunks = ingest_content(collection, combined, source_id, "codebase", str(project_path), project_path.name)
    
    # Update manifest
    update_manifest_source(manifest, {
        "id": source_id,
        "type": "codebase",
        "title": project_path.name,
        "url": str(project_path),
        "project_type": project_type,
        "files": len(files),
        "chunks": chunks,
        "added": datetime.now(timezone.utc).isoformat(),
    })
    
    print(f"   ✅ {len(files)} files → {chunks} chunks", file=sys.stderr)
    
    return {"files": len(files), "chunks": chunks, "type": project_type}


# ============================================================================
# Main
# ============================================================================

def build_context(
    sources: list,
    include_cwd: bool = False,
    repos: list = None,
    clear: bool = False,
    max_pages: int = 50,
    max_depth: int = 3,
) -> dict:
    """Build context from sources, storing directly in VectorDB."""
    
    print("", file=sys.stderr)
    print("🔨 Building research context...", file=sys.stderr)
    print("", file=sys.stderr)
    
    # Get collection
    collection = get_collection()
    
    # Clear if requested
    if clear:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=VECTORDB_DIR)
            client.delete_collection("research_context")
            collection = get_collection()
            print("🗑️  Cleared existing context", file=sys.stderr)
        except:
            pass
    
    # Load manifest
    manifest = load_manifest()
    
    results = []
    
    # Process codebase if requested
    if include_cwd:
        result = extract_codebase(".", collection, manifest)
        results.append({"type": "codebase", **result})
    
    # Process GitHub repos
    if repos:
        for repo_url in repos:
            result = extract_github(repo_url, collection, manifest)
            results.append({"type": "github", "url": repo_url, **result})
    
    # Process other sources
    for source in sources:
        source_type = detect_source_type(source)
        
        if source_type == "web":
            result = extract_web(source, collection, manifest, max_pages, max_depth)
            results.append({"type": "web", "url": source, **result})
        
        elif source_type == "youtube":
            result = extract_youtube(source, collection, manifest)
            results.append({"type": "youtube", "url": source, **result})
        
        elif source_type == "local":
            # TODO: Add local file support
            print(f"⚠️  Local files not yet supported: {source}", file=sys.stderr)
    
    # Save manifest
    save_manifest(manifest, collection)
    
    # Summary
    total_chunks = collection.count()
    total_sources = len(manifest["sources"])
    
    print("", file=sys.stderr)
    print("═" * 60, file=sys.stderr)
    print(f"✅ Context built: {total_sources} sources, {total_chunks} chunks", file=sys.stderr)
    print("═" * 60, file=sys.stderr)
    
    return {
        "success": True,
        "total_sources": total_sources,
        "total_chunks": total_chunks,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Build research context (extract + store in VectorDB)")
    parser.add_argument("sources", nargs="*", help="URLs to add")
    parser.add_argument("--include-cwd", action="store_true", help="Include current codebase")
    parser.add_argument("--repo", action="append", dest="repos", help="GitHub repo to clone and index")
    parser.add_argument("--clear", action="store_true", help="Clear existing context first")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages for web crawling")
    parser.add_argument("--depth", type=int, default=3, help="Max crawl depth")
    
    args = parser.parse_args()
    
    if not args.sources and not args.include_cwd and not args.repos:
        parser.print_help()
        print("\nError: No sources specified. Use URLs, --include-cwd, or --repo", file=sys.stderr)
        sys.exit(1)
    
    result = build_context(
        sources=args.sources,
        include_cwd=args.include_cwd,
        repos=args.repos,
        clear=args.clear,
        max_pages=args.max_pages,
        max_depth=args.depth,
    )
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

