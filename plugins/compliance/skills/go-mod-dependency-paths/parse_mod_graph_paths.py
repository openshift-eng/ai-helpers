#!/usr/bin/env python3
"""Parse `go mod graph` output and list paths from the root module to a target module.

Reads a text file produced by `go mod graph` (module pairs per line) and prints
ASCII trees for each path from the graph root to a vulnerable module coordinate.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict, deque


def parse_mod_graph(filename: str) -> tuple[dict[str, list[str]], set[str]]:
    """Parse go mod graph output into an adjacency list."""
    graph: dict[str, list[str]] = defaultdict(list)
    all_modules: set[str] = set()

    with open(filename, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 2:
                source, target = parts[0], parts[1]
                graph[source].append(target)
                all_modules.add(source)
                all_modules.add(target)

    return graph, all_modules


def find_all_paths(
    graph: dict[str, list[str]],
    start: str,
    target: str,
    max_depth: int,
) -> list[list[str]]:
    """Find paths from start to target using BFS over unique nodes in each path."""
    paths: list[list[str]] = []
    queue: deque[tuple[str, list[str]]] = deque([(start, [start])])

    while queue:
        current, path = queue.popleft()

        if len(path) > max_depth:
            continue

        target_base = target.split("@", 1)[0]
        if current == target or current.startswith(target_base):
            paths.append(path)
            continue

        for neighbor in graph.get(current, []):
            if neighbor not in path:
                queue.append((neighbor, path + [neighbor]))

    return paths


def extract_package_name(module: str) -> str:
    """Return module path without version suffix."""
    return module.split("@", 1)[0] if "@" in module else module


def format_tree(
    path: list[str],
    indent_char: str = "│   ",
    last_indent: str = "└── ",
    mid_indent: str = "├── ",
) -> str:
    """Format a module path as an ASCII tree."""
    lines: list[str] = []
    for i, module in enumerate(path):
        pkg_name = extract_package_name(module)
        version = module.split("@", 1)[1] if "@" in module else "unknown"

        if i == 0:
            lines.append(f"{pkg_name} {version}")
        else:
            prefix = indent_char * (i - 1)
            branch = last_indent if i == len(path) - 1 else mid_indent
            lines.append(f"{prefix}{branch}{pkg_name} {version}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List dependency paths from go mod graph root to a target module.",
    )
    parser.add_argument(
        "mod_graph",
        help="Path to file containing `go mod graph` output",
    )
    parser.add_argument(
        "vulnerable_pkg",
        help="Target module, e.g. golang.org/x/net@v0.0.0-20211015210444 or path prefix",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=20,
        metavar="N",
        help="Maximum path length to explore (default: 20)",
    )
    args = parser.parse_args()

    graph, modules = parse_mod_graph(args.mod_graph)

    with open(args.mod_graph, encoding="utf-8") as f:
        first = f.readline().strip().split()
        if not first:
            print("mod graph file is empty", file=sys.stderr)
            sys.exit(1)
        root = first[0]

    paths = find_all_paths(graph, root, args.vulnerable_pkg, args.max_depth)

    if not paths:
        print(f"No dependency path found to {args.vulnerable_pkg}")
        print("\nSearching for similar packages:")
        pkg_base = args.vulnerable_pkg.split("@", 1)[0]
        similar = [m for m in modules if pkg_base in m]
        for m in similar[:10]:
            print(f"  - {m}")
        sys.exit(1)

    print(f"Found {len(paths)} dependency path(s) to {args.vulnerable_pkg}:\n")

    for i, path in enumerate(paths, 1):
        print(f"Path {i}:")
        print(format_tree(path))
        print(f"\nPath length: {len(path)} modules")

        if len(path) == 2:
            print("Dependency type: DIRECT")
        else:
            print(f"Dependency type: TRANSITIVE (via {extract_package_name(path[1])})")
        print()


if __name__ == "__main__":
    main()
