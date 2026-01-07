#!/usr/bin/env python3
"""List sources in a research project or all projects."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


def list_all_projects(base_dir: str = ".work/research") -> Dict[str, Any]:
    """List all research projects.
    
    Args:
        base_dir: Base directory for research projects
        
    Returns:
        dict with project list
    """
    base_path = Path(base_dir)
    
    if not base_path.exists():
        return {
            "success": True,
            "projects": [],
            "message": "No research projects found. Create one with /research:add",
        }
    
    projects = []
    
    for project_dir in base_path.iterdir():
        if not project_dir.is_dir():
            continue
        
        manifest_path = project_dir / "manifest.json"
        
        project_info = {
            "name": project_dir.name,
            "path": str(project_dir),
        }
        
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                
                project_info["created"] = manifest.get("created", "")
                project_info["updated"] = manifest.get("updated", "")
                project_info["sources"] = len(manifest.get("sources", []))
                project_info["chunks"] = manifest.get("stats", {}).get("total_chunks", 0)
                
            except Exception as e:
                project_info["error"] = f"Could not read manifest: {str(e)}"
        else:
            project_info["sources"] = 0
            project_info["chunks"] = 0
        
        projects.append(project_info)
    
    # Sort by updated date (most recent first)
    projects.sort(key=lambda p: p.get("updated", ""), reverse=True)
    
    return {
        "success": True,
        "total_projects": len(projects),
        "projects": projects,
    }


def list_project_sources(
    project_name: str,
    base_dir: str = ".work/research",
) -> Dict[str, Any]:
    """List sources in a specific project.
    
    Args:
        project_name: Name of the project
        base_dir: Base directory for research projects
        
    Returns:
        dict with source list
    """
    project_path = Path(base_dir) / project_name
    
    if not project_path.exists():
        return {
            "success": False,
            "error": f"Project not found: {project_name}",
            "suggestion": "Run /research:list to see available projects",
        }
    
    manifest_path = project_path / "manifest.json"
    
    if not manifest_path.exists():
        return {
            "success": False,
            "error": f"Project manifest not found: {project_name}",
        }
    
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not read manifest: {str(e)}",
        }
    
    # Get ChromaDB stats if available
    vectordb_path = project_path / "vectordb"
    db_chunks = 0
    
    if vectordb_path.exists():
        try:
            import chromadb
            from chromadb.config import Settings
            
            client = chromadb.PersistentClient(
                path=str(vectordb_path),
                settings=Settings(anonymized_telemetry=False)
            )
            
            try:
                collection = client.get_collection(name=project_name)
                db_chunks = collection.count()
            except:
                pass
                
        except ImportError:
            pass
    
    sources = manifest.get("sources", [])
    
    # Group sources by type
    by_type = {}
    for source in sources:
        source_type = source.get("type", "unknown")
        if source_type not in by_type:
            by_type[source_type] = []
        by_type[source_type].append(source)
    
    return {
        "success": True,
        "project": project_name,
        "created": manifest.get("created", ""),
        "updated": manifest.get("updated", ""),
        "total_sources": len(sources),
        "total_chunks": db_chunks or manifest.get("stats", {}).get("total_chunks", 0),
        "sources_by_type": by_type,
        "sources": sources,
    }


def main():
    parser = argparse.ArgumentParser(description="List research sources")
    parser.add_argument("--project", help="Project name (omit for all projects)")
    parser.add_argument("--base-dir", default=".work/research", help="Base directory")
    
    args = parser.parse_args()
    
    if args.project:
        result = list_project_sources(args.project, args.base_dir)
    else:
        result = list_all_projects(args.base_dir)
    
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()


