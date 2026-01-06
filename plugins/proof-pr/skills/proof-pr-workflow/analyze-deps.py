#!/usr/bin/env python3
"""
Analyze Go module dependency graphs to detect chains and relationships.

This script uses 'go mod graph' to build a dependency graph and find
paths from a repository to a target module. Includes caching for performance.

Cache Strategy:
    - Cache key: SHA256 hash of go.mod file content
    - Cache location: ~/.cache/proof-pr/dep-graphs/{hash}.pkl
    - Cache TTL: 1 hour
    - Invalidated when go.mod changes
"""

import os
import re
import sys
import json
import subprocess
import hashlib
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from collections import deque
from datetime import datetime, timedelta


@dataclass
class DependencyChain:
    """Represents a dependency chain from target to original repo"""

    # List of repos in the chain: [target, intermediate1, ..., original]
    repos: List[str]

    # Type of relationship
    relationship: str  # "direct", "transitive", "generated-code"

    # Go module path (not repo URL)
    module_path: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'DependencyChain':
        """Create from dictionary"""
        return cls(**data)


class DependencyAnalyzer:
    """Analyzes Go module dependencies to find dependency chains"""

    CACHE_DIR = Path.home() / '.cache' / 'proof-pr' / 'dep-graphs'
    CACHE_TTL = timedelta(hours=1)

    # Patterns that indicate generated code repositories
    GENERATED_CODE_PATTERNS = [
        'client-go',
        '/generated',
        '/listers',
        '/informers',
        '/clientset',
        'api/typed',
    ]

    def __init__(self, repo_path: str, verbose: bool = True):
        self.repo_path = Path(repo_path).resolve()
        self.verbose = verbose
        self.go_module = self._get_go_module()
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, message: str):
        """Print verbose logging"""
        if self.verbose:
            print(f"[analyze-deps] {message}", file=sys.stderr)

    def _get_go_module(self) -> Optional[str]:
        """Get the Go module name from go.mod"""
        go_mod = self.repo_path / 'go.mod'
        if not go_mod.exists():
            return None

        try:
            content = go_mod.read_text()
            for line in content.split('\n'):
                if line.startswith('module '):
                    return line.split()[1].strip()
        except Exception as e:
            self._log(f"Error reading go.mod: {e}")

        return None

    def _get_go_mod_hash(self) -> str:
        """Get SHA256 hash of go.mod file for cache key"""
        go_mod = self.repo_path / 'go.mod'
        if not go_mod.exists():
            return ""

        content = go_mod.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def _get_cache_path(self) -> Path:
        """Get path to cached dependency graph"""
        cache_key = self._get_go_mod_hash()
        return self.CACHE_DIR / f"{cache_key}.pkl"

    def _load_from_cache(self) -> Optional[Dict[str, List[str]]]:
        """Load dependency graph from cache if valid"""
        cache_path = self._get_cache_path()

        if not cache_path.exists():
            self._log("No cache found")
            return None

        try:
            # Check cache age
            cache_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
            age = datetime.now() - cache_time

            if age > self.CACHE_TTL:
                self._log(f"Cache expired (age: {age})")
                cache_path.unlink()
                return None

            # Load cache
            with open(cache_path, 'rb') as f:
                graph = pickle.load(f)

            self._log(f"Loaded from cache (age: {age})")
            return graph

        except Exception as e:
            self._log(f"Error loading cache: {e}")
            return None

    def _save_to_cache(self, graph: Dict[str, List[str]]) -> None:
        """Save dependency graph to cache"""
        cache_path = self._get_cache_path()

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(graph, f)

            self._log(f"Saved to cache: {cache_path}")

        except Exception as e:
            self._log(f"Warning: Could not save cache: {e}")

    def get_dependency_graph(self, use_cache: bool = True) -> Dict[str, List[str]]:
        """
        Get dependency graph from 'go mod graph'.

        Returns:
            Dict mapping module -> [list of dependencies]
        """
        # Try cache first
        if use_cache:
            cached = self._load_from_cache()
            if cached is not None:
                return cached

        self._log("Building dependency graph from go mod graph...")

        try:
            result = subprocess.run(
                ['go', 'mod', 'graph'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            # Parse output: each line is "module1 module2" (module1 depends on module2)
            graph = {}

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split()
                if len(parts) != 2:
                    continue

                source, target = parts

                # Strip version info (module@version -> module)
                source = source.split('@')[0]
                target = target.split('@')[0]

                if source not in graph:
                    graph[source] = []

                graph[source].append(target)

            self._log(f"Built graph with {len(graph)} nodes")

            # Save to cache
            if use_cache:
                self._save_to_cache(graph)

            return graph

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"go mod graph failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("go mod graph timed out")

    def _find_path_bfs(
        self,
        graph: Dict[str, List[str]],
        start: str,
        target: str
    ) -> Optional[List[str]]:
        """
        Find shortest path from start to target using BFS.

        Args:
            graph: Dependency graph (module -> [dependencies])
            start: Starting module
            target: Target module to find

        Returns:
            List of modules in path from start to target, or None if no path
        """
        if start == target:
            return [start]

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            # Get dependencies of current module
            dependencies = graph.get(current, [])

            for dep in dependencies:
                if dep in visited:
                    continue

                new_path = path + [dep]

                # Check if we found the target
                if dep == target:
                    return new_path

                visited.add(dep)
                queue.append((dep, new_path))

        return None

    def _module_to_repo(self, module: str) -> str:
        """
        Convert Go module path to repository name.

        Examples:
            github.com/openshift/client-go -> openshift/client-go
            k8s.io/client-go -> kubernetes/client-go (approximation)
        """
        # Handle github.com modules
        if module.startswith('github.com/'):
            parts = module.split('/')
            if len(parts) >= 3:
                return f"{parts[1]}/{parts[2]}"

        # Handle k8s.io modules (map to kubernetes org)
        if module.startswith('k8s.io/'):
            return f"kubernetes/{module.split('/')[1]}"

        # Fallback: use last two path components
        parts = module.split('/')
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"

        return module

    def _is_generated_code_repo(self, module: str) -> bool:
        """Check if module path indicates generated code"""
        for pattern in self.GENERATED_CODE_PATTERNS:
            if pattern in module:
                return True
        return False

    def find_chain_to(self, target_module: str) -> Optional[DependencyChain]:
        """
        Find dependency chain from current repo to target module.

        Args:
            target_module: Target module to find (e.g., "github.com/openshift/api")

        Returns:
            DependencyChain if found, None otherwise
        """
        if not self.go_module:
            self._log("No go.mod found in repository")
            return None

        self._log(f"Finding chain from {self.go_module} to {target_module}")

        # Build dependency graph
        graph = self.get_dependency_graph(use_cache=True)

        # Find path using BFS
        path = self._find_path_bfs(graph, self.go_module, target_module)

        if not path:
            self._log("No dependency chain found")
            return None

        # Convert module paths to repo names
        repos = [self._module_to_repo(m) for m in path]

        # Determine relationship type
        if len(path) == 2:
            relationship = "direct"
        else:
            relationship = "transitive"

        # Check if any intermediate repos are generated-code repos
        for module in path[1:]:  # Skip root module
            if self._is_generated_code_repo(module):
                relationship = "generated-code"
                break

        self._log(f"Found chain: {' -> '.join(repos)}")
        self._log(f"Relationship: {relationship}")

        return DependencyChain(
            repos=repos,
            relationship=relationship,
            module_path=path
        )


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze Go module dependencies"
    )
    parser.add_argument(
        'target_module',
        help='Target module to find dependency chain to'
    )
    parser.add_argument(
        'repo_path',
        nargs='?',
        default='.',
        help='Path to repository (default: current directory)'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable caching'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose logging'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )

    args = parser.parse_args()

    analyzer = DependencyAnalyzer(args.repo_path, verbose=not args.quiet)

    try:
        chain = analyzer.find_chain_to(args.target_module)

        if chain:
            if args.json:
                print(json.dumps(chain.to_dict(), indent=2))
            else:
                print(f"\nDependency chain found:")
                print(f"  Repos: {' -> '.join(chain.repos)}")
                print(f"  Relationship: {chain.relationship}")
                print(f"  Module path: {' -> '.join(chain.module_path)}")

            sys.exit(0)
        else:
            if not args.json:
                print("No dependency chain found")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    main()
