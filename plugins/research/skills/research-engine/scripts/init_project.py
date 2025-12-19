#!/usr/bin/env python3
"""Initialize a research project with directory structure and ChromaDB collection."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def init_project(project_name: str, base_dir: str = ".work/research") -> dict:
    """Initialize a new research project.
    
    Args:
        project_name: Name of the project
        base_dir: Base directory for research projects
        
    Returns:
        dict with project info
    """
    project_path = Path(base_dir) / project_name
    
    # Create directory structure
    directories = [
        project_path / "sources" / "web",
        project_path / "sources" / "youtube",
        project_path / "sources" / "github",
        project_path / "sources" / "local",
        project_path / "sources" / "gdocs",
        project_path / "vectordb",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Created: {directory}", file=sys.stderr)
    
    # Create or update manifest
    manifest_path = project_path / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        print(f"Project '{project_name}' already exists, updating...", file=sys.stderr)
    else:
        manifest = {
            "project": project_name,
            "created": datetime.now(timezone.utc).isoformat(),
            "updated": datetime.now(timezone.utc).isoformat(),
            "sources": [],
            "stats": {
                "total_sources": 0,
                "total_chunks": 0,
            }
        }
    
    manifest["updated"] = datetime.now(timezone.utc).isoformat()
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    # Initialize ChromaDB collection
    try:
        import chromadb
        from chromadb.config import Settings
        
        client = chromadb.PersistentClient(
            path=str(project_path / "vectordb"),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        collection = client.get_or_create_collection(
            name=project_name,
            metadata={"description": f"Research project: {project_name}"}
        )
        
        print(f"ChromaDB collection '{project_name}' ready with {collection.count()} documents", file=sys.stderr)
        
    except ImportError:
        print("Warning: chromadb not installed. Run: pip install chromadb", file=sys.stderr)
        return {
            "success": False,
            "error": "chromadb not installed",
            "project": project_name,
            "path": str(project_path),
        }
    
    result = {
        "success": True,
        "project": project_name,
        "path": str(project_path),
        "created": manifest["created"],
        "collection_count": collection.count(),
    }
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Initialize a research project")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--base-dir", default=".work/research", help="Base directory")
    
    args = parser.parse_args()
    
    result = init_project(args.project, args.base_dir)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()


