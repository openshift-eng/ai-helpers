#!/usr/bin/env python3
"""Extract public API surface from source files using AST parsing.

For Python: uses the `ast` module to extract public classes, functions, and their signatures.
For other languages: use --raw to emit raw source with file headers (agents handle interpretation).

Usage:
    python3 extract_public_api.py --files file1.py file2.py --lang python
    python3 extract_public_api.py --files file1.py file2.py --lang python --raw
"""

import argparse
import ast
import json
import os
import sys


def _get_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Reconstruct a function signature from AST."""
    args = node.args
    parts = []

    for i, arg in enumerate(args.args):
        name = arg.arg
        annotation = ""
        if arg.annotation:
            annotation = f": {ast.unparse(arg.annotation)}"

        default_offset = len(args.args) - len(args.defaults)
        if i >= default_offset:
            default = ast.unparse(args.defaults[i - default_offset])
            parts.append(f"{name}{annotation} = {default}")
        else:
            parts.append(f"{name}{annotation}")

    if args.vararg:
        ann = f": {ast.unparse(args.vararg.annotation)}" if args.vararg.annotation else ""
        parts.append(f"*{args.vararg.arg}{ann}")
    elif args.kwonlyargs:
        parts.append("*")

    for i, kwarg in enumerate(args.kwonlyargs):
        ann = f": {ast.unparse(kwarg.annotation)}" if kwarg.annotation else ""
        kw_default = args.kw_defaults[i] if i < len(args.kw_defaults) else None
        if kw_default is not None:
            default = ast.unparse(kw_default)
            parts.append(f"{kwarg.arg}{ann} = {default}")
        else:
            parts.append(f"{kwarg.arg}{ann}")

    if args.kwarg:
        ann = f": {ast.unparse(args.kwarg.annotation)}" if args.kwarg.annotation else ""
        parts.append(f"**{args.kwarg.arg}{ann}")

    returns = ""
    if node.returns:
        returns = f" -> {ast.unparse(node.returns)}"

    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(parts)}){returns}"


def _get_class_signature(node: ast.ClassDef) -> str:
    """Reconstruct a class signature from AST."""
    bases = [ast.unparse(b) for b in node.bases]
    keywords = [f"{kw.arg}={ast.unparse(kw.value)}" for kw in node.keywords if kw.arg]
    all_args = bases + keywords
    if all_args:
        return f"class {node.name}({', '.join(all_args)})"
    return f"class {node.name}"


def _get_docstring(node) -> str | None:
    """Extract docstring from a node, truncated to 200 chars."""
    ds = ast.get_docstring(node)
    if ds:
        first_line = ds.split("\n")[0].strip()
        return first_line[:200]
    return None


def extract_python_api(files: list[str]) -> list[dict]:
    """Extract public API from Python files using AST."""
    exports = []

    for filepath in files:
        try:
            with open(filepath, errors="replace") as f:
                source = f.read()
        except OSError:
            continue

        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError:
            continue

        rel_path = os.path.basename(filepath)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                exports.append(
                    {
                        "name": node.name,
                        "kind": "function",
                        "file": rel_path,
                        "line": node.lineno,
                        "signature": _get_signature(node),
                        "docstring": _get_docstring(node),
                    }
                )

            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                methods = []
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        dunder_keep = (
                            "__init__",
                            "__call__",
                            "__enter__",
                            "__exit__",
                            "__aenter__",
                            "__aexit__",
                        )
                        if not item.name.startswith("_") or item.name in dunder_keep:
                            methods.append(
                                {
                                    "name": item.name,
                                    "signature": _get_signature(item),
                                    "docstring": _get_docstring(item),
                                }
                            )

                exports.append(
                    {
                        "name": node.name,
                        "kind": "class",
                        "file": rel_path,
                        "line": node.lineno,
                        "signature": _get_class_signature(node),
                        "docstring": _get_docstring(node),
                        "methods": methods,
                    }
                )

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        if target.id.isupper() or target.id[0].isupper():
                            exports.append(
                                {
                                    "name": target.id,
                                    "kind": "constant",
                                    "file": rel_path,
                                    "line": node.lineno,
                                    "signature": f"{target.id} = ...",
                                    "docstring": None,
                                }
                            )

    return exports


def extract_python_imports(files: list[str]) -> list[dict]:
    """Extract import statements from Python files using AST."""
    imports = []

    for filepath in files:
        try:
            with open(filepath, errors="replace") as f:
                source = f.read()
            tree = ast.parse(source, filename=filepath)
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        {
                            "module": alias.name,
                            "name": None,
                            "file": os.path.basename(filepath),
                        }
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        imports.append(
                            {
                                "module": node.module,
                                "name": alias.name,
                                "file": os.path.basename(filepath),
                            }
                        )

    return imports


def load_raw_source(files: list[str]) -> str:
    """Load source files with file headers for non-Python languages."""
    parts = []
    for filepath in files:
        try:
            with open(filepath, errors="replace") as f:
                source = f.read()
            rel = os.path.basename(filepath)
            parts.append(f"### FILE: {rel}\n{source}")
        except OSError:
            continue
    return "\n\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Extract public API from source files")
    parser.add_argument("--files", nargs="+", required=True, help="Source files to analyze")
    parser.add_argument("--lang", required=True, help="Language of the source files")
    parser.add_argument("--module", default="unknown", help="Module name")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw source with headers instead of parsed API",
    )
    args = parser.parse_args()

    if args.raw:
        result = {
            "module": args.module,
            "language": args.lang,
            "raw_source": load_raw_source(args.files),
        }
    elif args.lang == "python":
        exports = extract_python_api(args.files)
        imports = extract_python_imports(args.files)
        result = {
            "module": args.module,
            "language": "python",
            "exports": exports,
            "imports": imports,
            "export_count": len(exports),
        }
    else:
        result = {
            "module": args.module,
            "language": args.lang,
            "raw_source": load_raw_source(args.files),
            "note": f"AST parsing not available for {args.lang} in this script. "
            "Use extract_public_api_treesitter.mjs for Go/JS/TS.",
        }

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
