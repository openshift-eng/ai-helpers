#!/usr/bin/env python3
"""Query the research project's vector database."""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List


def query_project(
    project_name: str,
    question: str,
    top_k: int = 10,
    base_dir: str = ".work/research",
) -> Dict[str, Any]:
    """Query a project's vector database.
    
    Args:
        project_name: Name of the project
        question: Natural language question
        top_k: Number of results to return
        base_dir: Base directory for research projects
        
    Returns:
        dict with query results
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
            "error": f"Project not found: {project_name}",
            "suggestion": f"Create with: /research:add {project_name} <source-url>",
        }
    
    vectordb_path = project_path / "vectordb"
    if not vectordb_path.exists():
        return {
            "success": False,
            "error": f"Vector database not initialized for project: {project_name}",
        }
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(
        path=str(vectordb_path),
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
    
    # Get collection
    try:
        collection = client.get_collection(
            name=project_name,
            embedding_function=embedding_fn,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Collection not found: {project_name}",
        }
    
    total_chunks = collection.count()
    
    if total_chunks == 0:
        return {
            "success": False,
            "error": "Project database is empty",
            "suggestion": "Add sources with: /research:add",
        }
    
    print(f"Searching {total_chunks} chunks in project '{project_name}'...", file=sys.stderr)
    
    # Perform query
    try:
        results = collection.query(
            query_texts=[question],
            n_results=min(top_k, total_chunks),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Query failed: {str(e)}",
        }
    
    # Format results
    formatted_results = []
    
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            
            # Convert distance to relevance score (0-1, higher is better)
            # ChromaDB uses L2 distance by default, smaller is better
            relevance = max(0, 1 - (distance / 2))
            
            formatted_results.append({
                "content": doc,
                "source_url": metadata.get("source_url", ""),
                "source_title": metadata.get("source_title", ""),
                "source_type": metadata.get("source_type", ""),
                "chunk_index": metadata.get("chunk_index", 0),
                "total_chunks": metadata.get("total_chunks", 1),
                "relevance_score": round(relevance, 3),
            })
    
    return {
        "success": True,
        "query": question,
        "project": project_name,
        "total_chunks_searched": total_chunks,
        "results_returned": len(formatted_results),
        "results": formatted_results,
    }


def main():
    parser = argparse.ArgumentParser(description="Query research project")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--question", required=True, help="Question to ask")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results")
    parser.add_argument("--base-dir", default=".work/research", help="Base directory")
    
    args = parser.parse_args()
    
    result = query_project(
        args.project,
        args.question,
        top_k=args.top_k,
        base_dir=args.base_dir,
    )
    
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()


