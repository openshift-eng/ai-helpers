#!/usr/bin/env python3
"""Ingest extracted content into unified ChromaDB vector database."""

import subprocess
import sys

# Auto-install missing dependencies
def ensure_deps():
    required = [("chromadb", "chromadb"), ("sentence_transformers", "sentence-transformers")]
    missing = []
    for imp, pip in required:
        try:
            __import__(imp)
        except ImportError:
            missing.append(pip)
    if missing:
        print(f"📦 Installing: {', '.join(missing)}", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet"] + missing)
        print("✅ Dependencies installed!", file=sys.stderr)

ensure_deps()

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional


# Unified storage location
RESEARCH_DIR = ".work/research"
VECTORDB_DIR = f"{RESEARCH_DIR}/context.db"
MANIFEST_FILE = f"{RESEARCH_DIR}/manifest.json"


def parse_frontmatter(content: str) -> tuple:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content
    
    end_match = re.search(r'\n---\n', content[3:])
    if not end_match:
        return {}, content
    
    frontmatter_end = end_match.end() + 3
    frontmatter_text = content[4:end_match.start() + 3]
    body = content[frontmatter_end:]
    
    # Parse simple YAML
    metadata = {}
    for line in frontmatter_text.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            metadata[key] = value
    
    return metadata, body


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    words_per_chunk = int(chunk_size / 1.3)
    words_overlap = int(overlap / 1.3)
    
    if len(words) <= words_per_chunk:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(words):
        end = start + words_per_chunk
        chunk_words = words[start:end]
        chunk_text = ' '.join(chunk_words)
        if chunk_text.strip():
            chunks.append(chunk_text)
        start = end - words_overlap
    
    return chunks


def load_manifest() -> dict:
    """Load or create manifest."""
    manifest_path = Path(MANIFEST_FILE)
    
    if manifest_path.exists():
        with open(manifest_path, "r") as f:
            return json.load(f)
    
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "updated": datetime.now(timezone.utc).isoformat(),
        "sources": [],
        "stats": {"total_sources": 0, "total_chunks": 0},
    }


def save_manifest(manifest: dict):
    """Save manifest."""
    manifest_path = Path(MANIFEST_FILE)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest["updated"] = datetime.now(timezone.utc).isoformat()
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def ingest_file(
    file_path: Path,
    collection,
    mode: str = "upsert",
) -> Dict[str, Any]:
    """Ingest a single file into the vector database."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not read file: {str(e)}",
            "file": str(file_path),
        }
    
    # Parse frontmatter
    metadata, body = parse_frontmatter(content)
    
    source_type = metadata.get("source_type", "unknown")
    source_id = metadata.get("source_id", hashlib.md5(str(file_path).encode()).hexdigest()[:12])
    source_url = metadata.get("source_url", metadata.get("source_path", str(file_path)))
    source_title = metadata.get("source_title", metadata.get("project_name", file_path.stem))
    
    # For upsert mode, delete existing chunks for this source first
    if mode == "upsert":
        try:
            # Get existing IDs for this source
            existing = collection.get(where={"source_id": source_id})
            if existing and existing["ids"]:
                collection.delete(ids=existing["ids"])
                print(f"    Removed {len(existing['ids'])} existing chunks", file=sys.stderr)
        except Exception:
            pass  # Collection might be empty or source doesn't exist
    
    # Chunk the content
    chunks = chunk_text(body)
    
    if not chunks:
        return {
            "success": False,
            "error": "No content to index",
            "file": str(file_path),
        }
    
    # Prepare documents
    documents = []
    metadatas = []
    ids = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = f"{source_id}-chunk-{i}"
        
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
        ids.append(chunk_id)
    
    # Add to collection
    try:
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"ChromaDB error: {str(e)}",
            "file": str(file_path),
        }
    
    return {
        "success": True,
        "file": str(file_path),
        "source_id": source_id,
        "source_type": source_type,
        "source_title": source_title,
        "source_url": source_url,
        "chunks_created": len(chunks),
    }


def ingest_sources(
    source_dir: str = None,
    source_file: str = None,
    mode: str = "upsert",
    clear: bool = False,
) -> Dict[str, Any]:
    """Ingest content into the unified vector database.
    
    Args:
        source_dir: Directory containing source files
        source_file: Specific file to ingest
        mode: 'upsert' (default) or 'add'
        clear: Clear all existing content first
        
    Returns:
        dict with ingestion result
    """
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        return {
            "success": False,
            "error": "chromadb not installed. Run: pip install chromadb sentence-transformers",
        }
    
    # Create research directory
    Path(RESEARCH_DIR).mkdir(parents=True, exist_ok=True)
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(
        path=VECTORDB_DIR,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # Get embedding function
    try:
        from chromadb.utils import embedding_functions
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not load embedding model: {str(e)}",
        }
    
    # Clear if requested
    if clear:
        try:
            client.delete_collection("research_context")
            print("Cleared existing context", file=sys.stderr)
        except:
            pass
    
    # Get or create collection
    collection = client.get_or_create_collection(
        name="research_context",
        embedding_function=embedding_fn,
        metadata={"description": "Unified research context"}
    )
    
    print(f"Collection has {collection.count()} existing chunks", file=sys.stderr)
    
    # Determine files to ingest
    files_to_ingest = []
    
    if source_file:
        source_path = Path(source_file)
        if source_path.exists():
            files_to_ingest.append(source_path)
        else:
            return {"success": False, "error": f"File not found: {source_file}"}
    
    elif source_dir:
        source_path = Path(source_dir)
        if source_path.exists():
            for file_path in source_path.rglob("*.md"):
                files_to_ingest.append(file_path)
        else:
            return {"success": False, "error": f"Directory not found: {source_dir}"}
    
    else:
        return {"success": False, "error": "Specify --source-dir or --source-file"}
    
    if not files_to_ingest:
        return {"success": False, "error": "No files to ingest"}
    
    print(f"Ingesting {len(files_to_ingest)} files...", file=sys.stderr)
    
    # Load manifest
    manifest = load_manifest()
    
    # Ingest each file
    results = []
    total_chunks = 0
    
    for file_path in files_to_ingest:
        print(f"  Processing: {file_path.name}", file=sys.stderr)
        result = ingest_file(file_path, collection, mode)
        results.append(result)
        
        if result["success"]:
            total_chunks += result.get("chunks_created", 0)
            
            # Update manifest
            source_entry = {
                "id": result["source_id"],
                "type": result["source_type"],
                "title": result["source_title"],
                "url": result.get("source_url", ""),
                "chunks": result["chunks_created"],
                "added": datetime.now(timezone.utc).isoformat(),
            }
            
            # Update or add to manifest
            existing_idx = next((i for i, s in enumerate(manifest["sources"]) if s["id"] == result["source_id"]), None)
            if existing_idx is not None:
                manifest["sources"][existing_idx] = source_entry
            else:
                manifest["sources"].append(source_entry)
    
    # Update manifest stats
    manifest["stats"]["total_sources"] = len(manifest["sources"])
    manifest["stats"]["total_chunks"] = collection.count()
    save_manifest(manifest)
    
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    
    return {
        "success": failed == 0,
        "files_processed": len(results),
        "files_successful": successful,
        "files_failed": failed,
        "chunks_created": total_chunks,
        "total_chunks_in_db": collection.count(),
        "total_sources": len(manifest["sources"]),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest content into unified VectorDB")
    parser.add_argument("--source-dir", help="Directory containing source files")
    parser.add_argument("--source-file", help="Specific file to ingest")
    parser.add_argument("--mode", choices=["upsert", "add"], default="upsert", help="Ingestion mode")
    parser.add_argument("--clear", action="store_true", help="Clear existing context first")
    
    args = parser.parse_args()
    
    result = ingest_sources(
        source_dir=args.source_dir,
        source_file=args.source_file,
        mode=args.mode,
        clear=args.clear,
    )
    
    print(json.dumps(result, indent=2))
    
    if result["success"]:
        sys.exit(0)
    elif result.get("files_successful", 0) > 0:
        sys.exit(2)  # Partial success
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
