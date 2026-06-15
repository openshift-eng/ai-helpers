#!/usr/bin/env python3
"""Walk a repository and group source files into modules based on language-specific boundary rules.

Uses language-aware grouping:
- Python: directory of .py files = one module
- Go: directory of .go files = one package
- JS/TS: directory under src/ with source files = one module

Outputs JSON to stdout.

Usage:
    python3 build_module_map.py --repo /path/to/repo --lang python [--exclude "test/*"]
"""

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    "out",
    "target",
    "bin",
    "obj",
    ".idea",
    ".vscode",
    ".claude",
    ".agent_workspace",
    "coverage",
    ".nyc_output",
    ".next",
    ".nuxt",
    ".cache",
    "tmp",
    "temp",
    ".ruff_cache",
    ".vale",
    ".work",
}

LANG_EXTENSIONS = {
    "python": {".py"},
    "go": {".go"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "typescript": {".ts", ".tsx", ".mts", ".cts"},
    "yaml": {".yaml", ".yml"},
}

CONFIG_FILES = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "README.md"],
    "go": ["go.mod", "go.sum", "README.md"],
    "javascript": ["package.json", "README.md"],
    "typescript": ["package.json", "tsconfig.json", "README.md"],
    "yaml": ["README.md"],
}


def count_lines(filepath: str) -> int:
    try:
        with open(filepath, errors="replace") as f:
            return sum(1 for _ in f)
    except (OSError, UnicodeDecodeError):
        return 0


def should_exclude(rel_path: str, exclude_patterns: list[str]) -> bool:
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def build_module_map(
    repo_path: str,
    language: str,
    exclude_patterns: list[str] | None = None,
) -> dict:
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return {"error": f"Not a directory: {root}"}

    exclude_patterns = exclude_patterns or []
    extensions = LANG_EXTENSIONS.get(language, set())
    if not extensions:
        return {"error": f"Unsupported language: {language}"}

    modules: dict[str, dict] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)

        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = "root"

        if should_exclude(rel_dir, exclude_patterns):
            dirnames.clear()
            continue

        source_files = []
        for fname in sorted(filenames):
            ext = Path(fname).suffix.lower()
            if ext not in extensions:
                continue
            rel_file = os.path.relpath(os.path.join(dirpath, fname), root)
            if should_exclude(rel_file, exclude_patterns):
                continue
            source_files.append(rel_file)

        if source_files:
            total_lines = sum(count_lines(os.path.join(root, f)) for f in source_files)
            module_name = rel_dir.replace(os.sep, "/")
            modules[module_name] = {
                "path": module_name,
                "files": source_files,
                "file_count": len(source_files),
                "total_lines": total_lines,
            }

    config_found = []
    for cfg in CONFIG_FILES.get(language, []):
        if (root / cfg).exists():
            config_found.append(cfg)

    return {
        "language": language,
        "repo_root": str(root),
        "modules": modules,
        "module_count": len(modules),
        "config_files": config_found,
        "excluded_patterns": exclude_patterns,
    }


def main():
    parser = argparse.ArgumentParser(description="Build module map for a repository")
    parser.add_argument("--repo", required=True, help="Path to the repository root")
    parser.add_argument("--lang", required=True, help="Primary language")
    parser.add_argument("--exclude", nargs="*", default=[], help="Glob patterns to exclude")
    args = parser.parse_args()

    result = build_module_map(args.repo, args.lang, args.exclude)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
