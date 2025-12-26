#!/usr/bin/env python3
"""Query the unified research context vector database."""

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
import json
from pathlib import Path
from typing import Dict, Any


# Unified storage location
RESEARCH_DIR = ".work/research"
VECTORDB_DIR = f"{RESEARCH_DIR}/context.db"


def query_context(
    question: str,
    top_k: int = 15,
) -> Dict[str, Any]:
    """Query the unified context database.
    
    Args:
        question: Natural language question
        top_k: Number of results to return
        
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
    
    vectordb_path = Path(VECTORDB_DIR)
    
    if not vectordb_path.exists():
        return {
            "success": False,
            "error": "No research context found",
            "suggestion": "Build context first with: /research:build --include-cwd",
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
            name="research_context",
            embedding_function=embedding_fn,
        )
    except Exception as e:
        return {
            "success": False,
            "error": "Context collection not found. Run /research:build first.",
        }
    
    total_chunks = collection.count()
    
    if total_chunks == 0:
        return {
            "success": False,
            "error": "Context is empty",
            "suggestion": "Add sources with: /research:build",
        }
    
    print(f"Searching {total_chunks} chunks...", file=sys.stderr)
    
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
            relevance = max(0, 1 - (distance / 2))
            
            formatted_results.append({
                "content": doc,
                "source_type": metadata.get("source_type", "unknown"),
                "source_id": metadata.get("source_id", ""),
                "source_url": metadata.get("source_url", ""),
                "source_title": metadata.get("source_title", ""),
                "chunk_index": metadata.get("chunk_index", 0),
                "total_chunks": metadata.get("total_chunks", 1),
                "relevance_score": round(relevance, 3),
            })
    
    # Group by source for summary
    sources_found = {}
    for r in formatted_results:
        sid = r["source_id"]
        if sid not in sources_found:
            sources_found[sid] = {
                "type": r["source_type"],
                "title": r["source_title"],
                "url": r["source_url"],
                "chunks_matched": 0,
                "max_relevance": 0,
            }
        sources_found[sid]["chunks_matched"] += 1
        sources_found[sid]["max_relevance"] = max(sources_found[sid]["max_relevance"], r["relevance_score"])
    
    return {
        "success": True,
        "query": question,
        "total_chunks_searched": total_chunks,
        "results_returned": len(formatted_results),
        "sources_matched": len(sources_found),
        "sources_summary": list(sources_found.values()),
        "results": formatted_results,
    }


def main():
    parser = argparse.ArgumentParser(description="Query research context")
    parser.add_argument("--question", required=True, help="Question to ask")
    parser.add_argument("--top-k", type=int, default=15, help="Number of results")
    
    args = parser.parse_args()
    
    result = query_context(args.question, top_k=args.top_k)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
