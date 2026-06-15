#!/usr/bin/env python3
"""Detect the primary programming language in a repository by counting file extensions.

Uses os.walk with common exclusions. Outputs JSON to stdout.

Usage:
    python3 detect_language.py --repo /path/to/repo [--lang python]
"""

import argparse
import json
import os
import sys
from collections import Counter
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

EXCLUDED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".so",
    ".dylib",
    ".dll",
    ".min.js",
    ".bundle.js",
    ".map",
    ".lock",
    ".sum",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
}

SOURCE_EXTENSIONS = {
    ".py": "python",
    ".go": "go",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".mts": "typescript",
    ".cjs": "javascript",
    ".cts": "typescript",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def detect_language(repo_path: str, lang_override: str | None = None) -> dict:
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return {"error": f"Not a directory: {root}"}

    ext_counts: Counter = Counter()
    total_files = 0

    for _dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext in EXCLUDED_EXTENSIONS:
                continue
            total_files += 1
            if ext:
                ext_counts[ext] += 1

    lang_counts: Counter = Counter()
    for ext, count in ext_counts.items():
        lang = SOURCE_EXTENSIONS.get(ext)
        if lang:
            lang_counts[lang] += count

    if lang_override and lang_override in ("python", "go", "javascript", "typescript", "yaml"):
        primary = lang_override
    elif lang_counts:
        primary = lang_counts.most_common(1)[0][0]
    else:
        primary = "unknown"

    source_file_count = sum(count for ext, count in ext_counts.items() if ext in SOURCE_EXTENSIONS)

    return {
        "primary_language": primary,
        "language_counts": dict(lang_counts.most_common()),
        "extension_counts": dict(ext_counts.most_common(20)),
        "total_files": total_files,
        "total_source_files": source_file_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Detect primary language in a repo")
    parser.add_argument("--repo", required=True, help="Path to the repository root")
    parser.add_argument("--lang", default=None, help="Override language detection")
    args = parser.parse_args()

    result = detect_language(args.repo, args.lang)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
