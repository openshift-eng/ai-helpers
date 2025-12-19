#!/usr/bin/env python3
"""Extract content from local files."""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".rst", ".adoc",
    ".py", ".go", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".c", ".cpp", ".h", ".hpp",
    ".rs", ".rb", ".php", ".swift", ".kt",
    ".sh", ".bash", ".zsh",
    ".yaml", ".yml", ".json", ".toml",
    ".html", ".css", ".scss",
}


def extract_local(path: str, output_dir: str) -> dict:
    """Extract content from a local file.
    
    Args:
        path: Path to the local file
        output_dir: Directory to save extracted content
        
    Returns:
        dict with extraction result
    """
    # Expand user home directory
    file_path = Path(path).expanduser().resolve()
    
    if not file_path.exists():
        return {
            "success": False,
            "error": f"File not found: {path}",
            "path": str(file_path),
        }
    
    if not file_path.is_file():
        return {
            "success": False,
            "error": f"Path is not a file: {path}",
            "path": str(file_path),
        }
    
    # Check extension
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS and file_path.suffix:
        print(f"Warning: Unsupported file type {file_path.suffix}", file=sys.stderr)
    
    print(f"Extracting: {file_path}", file=sys.stderr)
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not read file: {str(e)}",
            "path": str(file_path),
        }
    
    if not content.strip():
        return {
            "success": False,
            "error": "File is empty",
            "path": str(file_path),
        }
    
    # Generate file ID
    file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
    file_id = f"{file_path.stem}-{file_hash}"
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create output file
    output_file = output_path / f"{file_id}.md"
    
    # Determine if content needs code block wrapping
    ext = file_path.suffix.lower()
    is_markdown = ext in {".md", ".mdx"}
    is_text = ext in {".txt", ".rst", ".adoc"}
    
    if is_markdown or is_text:
        # Keep as-is for markdown/text
        body = content
    else:
        # Wrap in code block for code files
        lang = ext.lstrip('.') if ext else 'text'
        body = f"```{lang}\n{content}\n```"
    
    file_content = f"""---
source_type: local
source_path: {file_path}
source_title: {file_path.name}
extracted_at: {datetime.now(timezone.utc).isoformat()}
---

# {file_path.name}

{body}
"""
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(file_content)
    
    print(f"Extracted to: {output_file}", file=sys.stderr)
    
    return {
        "success": True,
        "path": str(file_path),
        "title": file_path.name,
        "file_id": file_id,
        "output_file": str(output_file),
        "content_length": len(content),
        "word_count": len(content.split()),
    }


def main():
    parser = argparse.ArgumentParser(description="Extract content from local files")
    parser.add_argument("--path", required=True, help="Path to local file")
    parser.add_argument("--output", required=True, help="Output directory")
    
    args = parser.parse_args()
    
    result = extract_local(args.path, args.output)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()


