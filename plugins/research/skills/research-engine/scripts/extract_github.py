#!/usr/bin/env python3
"""Extract content from GitHub repositories."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


# File extensions to include
INCLUDE_EXTENSIONS = {
    # Documentation
    ".md", ".mdx", ".rst", ".txt", ".adoc",
    # Code (common languages)
    ".py", ".go", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".c", ".cpp", ".h", ".hpp",
    ".rs", ".rb", ".php", ".swift", ".kt",
    ".sh", ".bash", ".zsh",
    # Config
    ".yaml", ".yml", ".json", ".toml",
    # Web
    ".html", ".css", ".scss",
}

# Directories to skip
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "__pycache__",
    ".venv", "venv", "env", ".env",
    "dist", "build", "target", "bin", "obj",
    ".idea", ".vscode", ".eclipse",
    "test", "tests", "spec", "specs",  # Often too verbose
}

# Files to prioritize
PRIORITY_FILES = {
    "README.md", "README", "readme.md",
    "CONTRIBUTING.md", "ARCHITECTURE.md",
    "docs/", "doc/", "documentation/",
}


def extract_repo_info(url: str) -> tuple:
    """Extract owner and repo name from GitHub URL."""
    patterns = [
        r'github\.com/([^/]+)/([^/\?#]+)',
        r'github\.com:([^/]+)/([^/\?#]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            owner = match.group(1)
            repo = match.group(2).rstrip('.git')
            return owner, repo
    
    return None, None


def should_include_file(file_path: Path, repo_root: Path) -> bool:
    """Check if a file should be included in extraction."""
    relative = file_path.relative_to(repo_root)
    
    # Skip hidden files
    if any(part.startswith('.') for part in relative.parts):
        return False
    
    # Skip excluded directories
    if any(part in SKIP_DIRS for part in relative.parts):
        return False
    
    # Check extension
    if file_path.suffix.lower() in INCLUDE_EXTENSIONS:
        return True
    
    # Include files without extension if they look like docs
    if not file_path.suffix and file_path.name.upper() in {"README", "LICENSE", "CHANGELOG", "CONTRIBUTING"}:
        return True
    
    return False


def get_file_priority(file_path: Path, repo_root: Path) -> int:
    """Get priority score for a file (higher = more important)."""
    relative = str(file_path.relative_to(repo_root))
    name = file_path.name.lower()
    
    # README files are highest priority
    if name.startswith("readme"):
        if relative.count("/") == 0:
            return 100  # Root README
        return 50  # Nested README
    
    # Docs folder
    if "docs/" in relative or "doc/" in relative:
        return 40
    
    # Contributing, architecture docs
    if name in {"contributing.md", "architecture.md", "design.md"}:
        return 35
    
    # Root-level markdown
    if file_path.suffix == ".md" and relative.count("/") == 0:
        return 30
    
    # Source code
    if file_path.suffix in {".go", ".py", ".js", ".ts", ".java", ".rs"}:
        return 10
    
    return 5


def extract_github(url: str, output_dir: str, max_files: int = 100) -> dict:
    """Extract content from a GitHub repository.
    
    Args:
        url: GitHub repository URL
        output_dir: Directory to save extracted content
        max_files: Maximum number of files to extract
        
    Returns:
        dict with extraction result
    """
    if not shutil.which("git"):
        return {
            "success": False,
            "error": "git not installed",
            "url": url,
        }
    
    owner, repo = extract_repo_info(url)
    if not owner or not repo:
        return {
            "success": False,
            "error": f"Could not parse GitHub URL: {url}",
            "url": url,
        }
    
    print(f"Cloning repository: {owner}/{repo}", file=sys.stderr)
    
    # Clone to temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        clone_path = Path(temp_dir) / repo
        
        # Shallow clone
        clone_cmd = [
            "git", "clone",
            "--depth", "1",
            "--single-branch",
            f"https://github.com/{owner}/{repo}.git",
            str(clone_path),
        ]
        
        try:
            result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Clone failed: {result.stderr}",
                    "url": url,
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Clone timeout - repository may be too large",
                "url": url,
            }
        
        # Find all eligible files
        all_files = []
        for file_path in clone_path.rglob("*"):
            if file_path.is_file() and should_include_file(file_path, clone_path):
                priority = get_file_priority(file_path, clone_path)
                all_files.append((priority, file_path))
        
        # Sort by priority (descending) and limit
        all_files.sort(key=lambda x: -x[0])
        selected_files = all_files[:max_files]
        
        print(f"Found {len(all_files)} eligible files, selecting {len(selected_files)}", file=sys.stderr)
        
        # Create output directory
        output_path = Path(output_dir) / repo
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create manifest for this repo
        repo_manifest = {
            "source_type": "github",
            "source_url": url,
            "owner": owner,
            "repo": repo,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "files": [],
        }
        
        # Extract selected files
        for priority, file_path in selected_files:
            relative = file_path.relative_to(clone_path)
            
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                print(f"  Skipping {relative}: {e}", file=sys.stderr)
                continue
            
            # Skip very small or very large files
            if len(content) < 50 or len(content) > 500000:
                continue
            
            # Create output file
            safe_name = str(relative).replace("/", "__").replace("\\", "__")
            output_file = output_path / f"{safe_name}"
            
            file_content = f"""---
source_type: github
source_url: {url}
source_repo: {owner}/{repo}
source_file: {relative}
extracted_at: {datetime.now(timezone.utc).isoformat()}
---

# {relative}

```{file_path.suffix.lstrip('.') or 'text'}
{content}
```
"""
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(file_content)
            
            repo_manifest["files"].append({
                "path": str(relative),
                "output": str(output_file),
                "size": len(content),
            })
        
        # Save manifest
        manifest_file = output_path / "_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(repo_manifest, f, indent=2)
    
    print(f"Extracted {len(repo_manifest['files'])} files to: {output_path}", file=sys.stderr)
    
    return {
        "success": True,
        "url": url,
        "owner": owner,
        "repo": repo,
        "files_extracted": len(repo_manifest["files"]),
        "total_eligible": len(all_files),
        "output_dir": str(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Extract content from GitHub repositories")
    parser.add_argument("--url", required=True, help="GitHub repository URL")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--max-files", type=int, default=100, help="Maximum files to extract")
    
    args = parser.parse_args()
    
    result = extract_github(args.url, args.output, args.max_files)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()


