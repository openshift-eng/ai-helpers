#!/usr/bin/env python3
"""List sources and statistics for the unified research context."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


# Unified storage location
RESEARCH_DIR = ".work/research"
VECTORDB_DIR = f"{RESEARCH_DIR}/context.db"
MANIFEST_FILE = f"{RESEARCH_DIR}/manifest.json"


def get_relative_time(iso_timestamp: str) -> str:
    """Convert ISO timestamp to relative time."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo)
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"
    except:
        return "unknown"


def list_context(show_stats: bool = False) -> Dict[str, Any]:
    """List all sources in the research context.
    
    Args:
        show_stats: Include detailed statistics
        
    Returns:
        dict with context information
    """
    manifest_path = Path(MANIFEST_FILE)
    vectordb_path = Path(VECTORDB_DIR)
    
    if not manifest_path.exists():
        return {
            "success": True,
            "empty": True,
            "message": "No research context found. Create one with /research:build",
            "sources": [],
        }
    
    # Load manifest
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not read manifest: {str(e)}",
        }
    
    sources = manifest.get("sources", [])
    
    # Get ChromaDB stats if available
    db_chunks = 0
    db_size_mb = 0
    
    if vectordb_path.exists():
        try:
            import chromadb
            from chromadb.config import Settings
            
            client = chromadb.PersistentClient(
                path=str(vectordb_path),
                settings=Settings(anonymized_telemetry=False)
            )
            
            try:
                collection = client.get_collection(name="research_context")
                db_chunks = collection.count()
            except:
                pass
            
            # Calculate directory size
            total_size = sum(f.stat().st_size for f in vectordb_path.rglob('*') if f.is_file())
            db_size_mb = round(total_size / (1024 * 1024), 2)
            
        except ImportError:
            pass
    
    # Enrich sources with relative time
    for source in sources:
        source["added_relative"] = get_relative_time(source.get("added", ""))
    
    # Group by type for stats
    by_type = {}
    for source in sources:
        stype = source.get("type", "unknown")
        if stype not in by_type:
            by_type[stype] = {"count": 0, "chunks": 0}
        by_type[stype]["count"] += 1
        by_type[stype]["chunks"] += source.get("chunks", 0)
    
    result = {
        "success": True,
        "empty": len(sources) == 0,
        "total_sources": len(sources),
        "total_chunks": db_chunks or manifest.get("stats", {}).get("total_chunks", 0),
        "created": manifest.get("created", ""),
        "updated": manifest.get("updated", ""),
        "sources": sources,
        "by_type": by_type,
    }
    
    if show_stats:
        result["stats"] = {
            "database_size_mb": db_size_mb,
            "embedding_model": "all-MiniLM-L6-v2",
            "vector_dimensions": 384,
        }
    
    return result


def main():
    parser = argparse.ArgumentParser(description="List research context")
    parser.add_argument("--stats", action="store_true", help="Show detailed statistics")
    
    args = parser.parse_args()
    
    result = list_context(show_stats=args.stats)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

