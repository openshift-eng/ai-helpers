#!/usr/bin/env python3
"""Extract content from GitHub repos: Clone → Index → Delete."""

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


# File extensions to include
INCLUDE_EXTENSIONS = {
    ".md", ".mdx", ".rst", ".txt", ".adoc",
    ".go", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".c", ".cpp", ".h", ".hpp", ".rs", ".rb",
    ".yaml", ".yml", ".json", ".toml",
    ".sh", ".bash",
}

# Directories to skip
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "__pycache__",
    ".venv", "venv", "env", ".env",
    "dist", "build", "target", "bin", "obj",
    "test", "tests", "testdata", "testing",
    "examples", "example", "samples", "sample",
    ".github", ".circleci", ".travis",
}

# Priority files
PRIORITY_FILES = {
    "README.md", "README", "CONTRIBUTING.md",
    "ARCHITECTURE.md", "DESIGN.md",
}

# Priority directories
PRIORITY_DIRS = ["api/", "apis/", "pkg/api/", "docs/", "doc/", "cmd/", "controllers/"]


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
    """Check if file should be included."""
    relative = file_path.relative_to(repo_root)
    
    # Skip hidden files
    if any(part.startswith('.') for part in relative.parts):
        return False
    
    # Skip excluded directories
    if any(part in SKIP_DIRS for part in relative.parts):
        return False
    
    # Priority files always included
    if file_path.name in PRIORITY_FILES:
        return True
    
    # Check extension
    if file_path.suffix.lower() in INCLUDE_EXTENSIONS:
        return True
    
    return False


def get_file_priority(file_path: Path, repo_root: Path) -> int:
    """Score file importance."""
    relative = str(file_path.relative_to(repo_root))
    name = file_path.name.lower()
    
    # README at root
    if name.startswith("readme") and relative.count("/") == 0:
        return 100
    
    # Priority directories
    for pdir in PRIORITY_DIRS:
        if pdir in relative:
            return 70
    
    # Nested README
    if name.startswith("readme"):
        return 50
    
    # Docs
    if file_path.suffix in {".md", ".rst", ".adoc"}:
        return 40
    
    # Source code
    if file_path.suffix in {".go", ".py", ".js", ".ts"}:
        return 20
    
    return 10


def extract_github_temp(url: str, output_dir: str, max_files: int = 75) -> dict:
    """Extract content from GitHub repo: Clone → Extract → Delete.
    
    Args:
        url: GitHub repository URL
        output_dir: Directory to save extracted content
        max_files: Maximum files to extract
        
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
    
    print(f"Processing GitHub repo: {owner}/{repo}", file=sys.stderr)
    
    # Clone to TEMP directory (will be deleted)
    temp_dir = tempfile.mkdtemp(prefix=f"research-github-{repo}-")
    clone_path = Path(temp_dir) / repo
    
    try:
        print(f"  Cloning to temp: {temp_dir}", file=sys.stderr)
        
        # Shallow clone
        clone_cmd = [
            "git", "clone",
            "--depth", "1",
            "--single-branch",
            f"https://github.com/{owner}/{repo}.git",
            str(clone_path),
        ]
        
        result = subprocess.run(
            clone_cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Clone failed: {result.stderr[:100]}",
                "url": url,
            }
        
        # Find all eligible files
        all_files = []
        for file_path in clone_path.rglob("*"):
            if file_path.is_file() and should_include_file(file_path, clone_path):
                priority = get_file_priority(file_path, clone_path)
                all_files.append((priority, file_path))
        
        # Sort by priority and limit
        all_files.sort(key=lambda x: -x[0])
        selected_files = all_files[:max_files]
        
        print(f"  Found {len(all_files)} files, selecting {len(selected_files)}", file=sys.stderr)
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate source ID
        source_id = f"github-{owner}-{repo}-{hashlib.md5(url.encode()).hexdigest()[:6]}"
        
        # Extract content
        extracted = []
        total_content = []
        
        for priority, file_path in selected_files:
            relative = file_path.relative_to(clone_path)
            
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                continue
            
            # Skip empty or huge files
            if len(content) < 10 or len(content) > 100000:
                continue
            
            ext = file_path.suffix.lstrip('.') or 'text'
            file_content = f"\n\n## File: {relative}\n\n```{ext}\n{content}\n```\n"
            total_content.append(file_content)
            
            extracted.append({
                "path": str(relative),
                "size": len(content),
            })
        
        # Create single output file
        output_file = output_path / f"{source_id}.md"
        
        combined_content = f"""---
source_type: github
source_url: {url}
source_id: {source_id}
repo_owner: {owner}
repo_name: {repo}
files_extracted: {len(extracted)}
extracted_at: {datetime.now(timezone.utc).isoformat()}
---

# GitHub: {owner}/{repo}

**Repository:** https://github.com/{owner}/{repo}  
**Files extracted:** {len(extracted)}

{''.join(total_content)}
"""
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(combined_content)
        
        print(f"  Extracted to: {output_file}", file=sys.stderr)
        
        extraction_result = {
            "success": True,
            "source_id": source_id,
            "source_type": "github",
            "url": url,
            "owner": owner,
            "repo": repo,
            "files_extracted": len(extracted),
            "total_eligible": len(all_files),
            "output_file": str(output_file),
        }
        
    finally:
        # ALWAYS delete the clone
        print(f"  Cleaning up temp clone...", file=sys.stderr)
        try:
            shutil.rmtree(temp_dir)
            print(f"  ✓ Temp clone deleted", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠ Failed to delete temp: {e}", file=sys.stderr)
    
    return extraction_result


def main():
    parser = argparse.ArgumentParser(description="Extract GitHub repo (clone → index → delete)")
    parser.add_argument("--url", required=True, help="GitHub repository URL")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--max-files", type=int, default=75, help="Max files to extract")
    
    args = parser.parse_args()
    
    result = extract_github_temp(args.url, args.output, args.max_files)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

