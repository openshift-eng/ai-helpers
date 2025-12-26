#!/usr/bin/env python3
"""Extract content from current codebase with auto-detection."""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# File extensions to include by project type
CODE_EXTENSIONS = {
    ".go", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".c", ".cpp", ".h", ".hpp", ".rs", ".rb",
}

DOC_EXTENSIONS = {
    ".md", ".mdx", ".rst", ".txt", ".adoc",
}

CONFIG_EXTENSIONS = {
    ".yaml", ".yml", ".json", ".toml",
}

# Directories to skip
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "__pycache__",
    ".venv", "venv", "env", ".env",
    "dist", "build", "target", "bin", "obj",
    ".idea", ".vscode", ".eclipse",
    ".work", ".cache", "coverage",
}

# Priority files to always include
PRIORITY_FILES = [
    "README.md", "README", "readme.md",
    "CONTRIBUTING.md", "ARCHITECTURE.md", "DESIGN.md",
    "go.mod", "go.sum",
    "package.json", "package-lock.json",
    "requirements.txt", "pyproject.toml", "setup.py",
    "Makefile", "Dockerfile", "docker-compose.yml",
    "Cargo.toml", "build.gradle", "pom.xml",
]

# Priority directories
PRIORITY_DIRS = [
    "api", "apis", "pkg/api", "pkg/apis",
    "controllers", "controller", "pkg/controller",
    "cmd", "main",
    "docs", "doc", "documentation",
    "config", "configs", "deploy",
]


def detect_project_type(path: Path) -> dict:
    """Detect the project type and gather metadata."""
    project_info = {
        "type": "unknown",
        "name": path.name,
        "language": "unknown",
        "framework": None,
        "dependencies": [],
    }
    
    # Check for Go project
    if (path / "go.mod").exists():
        project_info["type"] = "go"
        project_info["language"] = "go"
        try:
            with open(path / "go.mod", "r") as f:
                content = f.read()
                for line in content.split("\n"):
                    if line.startswith("module "):
                        project_info["name"] = line.split()[1]
                    if "operator-sdk" in line:
                        project_info["framework"] = "operator-sdk"
                    if "controller-runtime" in line:
                        project_info["framework"] = "controller-runtime"
        except:
            pass
    
    # Check for Node.js project
    elif (path / "package.json").exists():
        project_info["type"] = "nodejs"
        project_info["language"] = "javascript"
        try:
            with open(path / "package.json", "r") as f:
                pkg = json.load(f)
                project_info["name"] = pkg.get("name", path.name)
                if "react" in pkg.get("dependencies", {}):
                    project_info["framework"] = "react"
                elif "next" in pkg.get("dependencies", {}):
                    project_info["framework"] = "next"
        except:
            pass
    
    # Check for Python project
    elif (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
        project_info["type"] = "python"
        project_info["language"] = "python"
    
    # Check for Rust project
    elif (path / "Cargo.toml").exists():
        project_info["type"] = "rust"
        project_info["language"] = "rust"
    
    return project_info


def should_include_file(file_path: Path, project_root: Path) -> bool:
    """Check if a file should be included."""
    relative = file_path.relative_to(project_root)
    
    # Skip hidden files/dirs
    if any(part.startswith('.') for part in relative.parts):
        return False
    
    # Skip excluded directories
    if any(part in SKIP_DIRS for part in relative.parts):
        return False
    
    # Include priority files
    if file_path.name in PRIORITY_FILES:
        return True
    
    # Check extension
    ext = file_path.suffix.lower()
    if ext in CODE_EXTENSIONS or ext in DOC_EXTENSIONS or ext in CONFIG_EXTENSIONS:
        return True
    
    return False


def get_file_priority(file_path: Path, project_root: Path) -> int:
    """Score file importance (higher = more important)."""
    relative = file_path.relative_to(project_root)
    name = file_path.name.lower()
    relative_str = str(relative)
    
    # Priority files
    if name in ["readme.md", "readme"]:
        return 100
    if name == "go.mod" or name == "package.json":
        return 90
    
    # API types (for operators)
    if "api/" in relative_str and "_types.go" in name:
        return 85
    
    # Controllers
    if "controller" in relative_str.lower() and file_path.suffix == ".go":
        return 80
    
    # Docs
    if "docs/" in relative_str or "doc/" in relative_str:
        return 70
    
    # Config
    if "config/" in relative_str:
        return 60
    
    # Main/cmd
    if "cmd/" in relative_str or name == "main.go":
        return 55
    
    # Other Go files
    if file_path.suffix == ".go":
        return 30
    
    # Other code
    if file_path.suffix in CODE_EXTENSIONS:
        return 20
    
    return 10


def extract_codebase(path: str, output_dir: str, max_files: int = 100) -> dict:
    """Extract content from a codebase.
    
    Args:
        path: Path to the codebase root
        output_dir: Directory to save extracted content
        max_files: Maximum files to extract
        
    Returns:
        dict with extraction result
    """
    project_path = Path(path).expanduser().resolve()
    
    if not project_path.exists():
        return {
            "success": False,
            "error": f"Path not found: {path}",
        }
    
    if not project_path.is_dir():
        return {
            "success": False,
            "error": f"Path is not a directory: {path}",
        }
    
    print(f"Analyzing codebase: {project_path}", file=sys.stderr)
    
    # Detect project type
    project_info = detect_project_type(project_path)
    print(f"  Project type: {project_info['type']}", file=sys.stderr)
    print(f"  Language: {project_info['language']}", file=sys.stderr)
    if project_info['framework']:
        print(f"  Framework: {project_info['framework']}", file=sys.stderr)
    
    # Find all eligible files
    all_files = []
    for file_path in project_path.rglob("*"):
        if file_path.is_file() and should_include_file(file_path, project_path):
            priority = get_file_priority(file_path, project_path)
            all_files.append((priority, file_path))
    
    # Sort by priority and limit
    all_files.sort(key=lambda x: -x[0])
    selected_files = all_files[:max_files]
    
    print(f"  Found {len(all_files)} files, selecting {len(selected_files)}", file=sys.stderr)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate source ID
    source_id = f"codebase-{hashlib.md5(str(project_path).encode()).hexdigest()[:8]}"
    
    # Extract files
    extracted = []
    total_content = []
    
    for priority, file_path in selected_files:
        relative = file_path.relative_to(project_path)
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"  Skipping {relative}: {e}", file=sys.stderr)
            continue
        
        # Skip very large or empty files
        if len(content) < 10 or len(content) > 100000:
            continue
        
        # Add to combined content
        ext = file_path.suffix.lstrip('.') or 'text'
        file_content = f"\n\n## File: {relative}\n\n```{ext}\n{content}\n```\n"
        total_content.append(file_content)
        
        extracted.append({
            "path": str(relative),
            "size": len(content),
            "priority": priority,
        })
    
    # Create single output file with all content
    output_file = output_path / f"{source_id}.md"
    
    combined_content = f"""---
source_type: codebase
source_path: {project_path}
source_id: {source_id}
project_name: {project_info['name']}
project_type: {project_info['type']}
project_language: {project_info['language']}
project_framework: {project_info.get('framework', 'none')}
files_extracted: {len(extracted)}
extracted_at: {datetime.now(timezone.utc).isoformat()}
---

# Codebase: {project_info['name']}

**Type:** {project_info['type']}  
**Language:** {project_info['language']}  
**Framework:** {project_info.get('framework', 'N/A')}  
**Path:** {project_path}

{''.join(total_content)}
"""
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(combined_content)
    
    print(f"  Extracted to: {output_file}", file=sys.stderr)
    
    return {
        "success": True,
        "source_id": source_id,
        "source_type": "codebase",
        "project_name": project_info["name"],
        "project_type": project_info["type"],
        "project_language": project_info["language"],
        "files_extracted": len(extracted),
        "total_eligible": len(all_files),
        "output_file": str(output_file),
        "files": extracted[:20],  # Just first 20 for summary
    }


def main():
    parser = argparse.ArgumentParser(description="Extract content from codebase")
    parser.add_argument("--path", default=".", help="Path to codebase (default: current dir)")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--max-files", type=int, default=100, help="Max files to extract")
    
    args = parser.parse_args()
    
    result = extract_codebase(args.path, args.output, args.max_files)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

