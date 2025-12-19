#!/usr/bin/env python3
"""Ingest extracted content into ChromaDB vector database."""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional


def parse_frontmatter(content: str) -> tuple:
    """Parse YAML frontmatter from markdown content.
    
    Returns:
        tuple of (metadata dict, body content)
    """
    if not content.startswith("---"):
        return {}, content
    
    # Find closing ---
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
    """Split text into overlapping chunks.
    
    Args:
        text: Text to split
        chunk_size: Target tokens per chunk (approximated as words * 1.3)
        overlap: Tokens of overlap between chunks
        
    Returns:
        List of text chunks
    """
    # Approximate tokens as words * 1.3
    words = text.split()
    words_per_chunk = int(chunk_size / 1.3)
    words_overlap = int(overlap / 1.3)
    
    if len(words) <= words_per_chunk:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(words):
        end = start + words_per_chunk
        chunk_words = words[start:end]
        
        # Try to end at a sentence boundary
        chunk_text = ' '.join(chunk_words)
        
        chunks.append(chunk_text)
        start = end - words_overlap
    
    return chunks


def ingest_file(
    file_path: Path,
    collection,
    project_name: str,
) -> Dict[str, Any]:
    """Ingest a single file into the vector database.
    
    Args:
        file_path: Path to the extracted content file
        collection: ChromaDB collection
        project_name: Name of the project
        
    Returns:
        dict with ingestion result
    """
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
    source_url = metadata.get("source_url", metadata.get("source_path", str(file_path)))
    source_title = metadata.get("source_title", file_path.stem)
    
    # Generate source ID
    source_id = hashlib.md5(source_url.encode()).hexdigest()[:12]
    
    # Chunk the content
    chunks = chunk_text(body)
    
    if not chunks:
        return {
            "success": False,
            "error": "No content to index",
            "file": str(file_path),
        }
    
    # Prepare documents for ChromaDB
    documents = []
    metadatas = []
    ids = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = f"{source_id}-chunk-{i}"
        
        documents.append(chunk)
        metadatas.append({
            "source_type": source_type,
            "source_url": source_url,
            "source_title": source_title,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "project": project_name,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
        ids.append(chunk_id)
    
    # Add to collection (upsert to handle re-ingestion)
    try:
        collection.upsert(
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
        "chunks_created": len(chunks),
    }


def ingest_project(
    project_name: str,
    source_file: Optional[str] = None,
    all_new: bool = False,
    base_dir: str = ".work/research",
) -> Dict[str, Any]:
    """Ingest content into a project's vector database.
    
    Args:
        project_name: Name of the project
        source_file: Specific file to ingest (optional)
        all_new: Ingest all files in sources directory
        base_dir: Base directory for research projects
        
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
    
    project_path = Path(base_dir) / project_name
    
    if not project_path.exists():
        return {
            "success": False,
            "error": f"Project not found: {project_name}. Create with init_project.py first.",
        }
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(
        path=str(project_path / "vectordb"),
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
            "error": f"Could not load embedding model: {str(e)}. Run: pip install sentence-transformers",
        }
    
    collection = client.get_or_create_collection(
        name=project_name,
        embedding_function=embedding_fn,
        metadata={"description": f"Research project: {project_name}"}
    )
    
    print(f"Collection '{project_name}' has {collection.count()} existing documents", file=sys.stderr)
    
    # Determine files to ingest
    files_to_ingest = []
    
    if source_file:
        source_path = Path(source_file)
        if source_path.exists():
            files_to_ingest.append(source_path)
        else:
            return {
                "success": False,
                "error": f"Source file not found: {source_file}",
            }
    elif all_new:
        sources_dir = project_path / "sources"
        for source_type_dir in sources_dir.iterdir():
            if source_type_dir.is_dir():
                for file_path in source_type_dir.rglob("*.md"):
                    files_to_ingest.append(file_path)
    else:
        return {
            "success": False,
            "error": "Specify --source-file or --all-new",
        }
    
    if not files_to_ingest:
        return {
            "success": False,
            "error": "No files to ingest",
        }
    
    print(f"Ingesting {len(files_to_ingest)} files...", file=sys.stderr)
    
    # Ingest each file
    results = []
    total_chunks = 0
    
    for file_path in files_to_ingest:
        print(f"  Processing: {file_path.name}", file=sys.stderr)
        result = ingest_file(file_path, collection, project_name)
        results.append(result)
        
        if result["success"]:
            total_chunks += result.get("chunks_created", 0)
    
    # Update manifest
    manifest_path = project_path / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    else:
        manifest = {
            "project": project_name,
            "created": datetime.now(timezone.utc).isoformat(),
            "sources": [],
            "stats": {"total_sources": 0, "total_chunks": 0},
        }
    
    # Update sources in manifest
    for result in results:
        if result["success"]:
            source_entry = {
                "id": result["source_id"],
                "type": result["source_type"],
                "title": result["source_title"],
                "file": result["file"],
                "chunks": result["chunks_created"],
                "added": datetime.now(timezone.utc).isoformat(),
                "status": "indexed",
            }
            
            # Update or add
            existing = next((s for s in manifest["sources"] if s["id"] == result["source_id"]), None)
            if existing:
                existing.update(source_entry)
            else:
                manifest["sources"].append(source_entry)
    
    manifest["updated"] = datetime.now(timezone.utc).isoformat()
    manifest["stats"]["total_sources"] = len(manifest["sources"])
    manifest["stats"]["total_chunks"] = collection.count()
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    
    return {
        "success": failed == 0,
        "project": project_name,
        "files_processed": len(results),
        "files_successful": successful,
        "files_failed": failed,
        "chunks_created": total_chunks,
        "total_chunks_in_db": collection.count(),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest content into ChromaDB")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--source-file", help="Specific file to ingest")
    parser.add_argument("--all-new", action="store_true", help="Ingest all files in sources/")
    parser.add_argument("--base-dir", default=".work/research", help="Base directory")
    
    args = parser.parse_args()
    
    result = ingest_project(
        args.project,
        source_file=args.source_file,
        all_new=args.all_new,
        base_dir=args.base_dir,
    )
    
    print(json.dumps(result, indent=2))
    
    # Exit code: 0 = success, 1 = error, 2 = partial success
    if result["success"]:
        sys.exit(0)
    elif result.get("files_successful", 0) > 0:
        sys.exit(2)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()


