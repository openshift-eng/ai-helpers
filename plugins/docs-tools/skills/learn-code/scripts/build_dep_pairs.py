#!/usr/bin/env python3
"""Build deduplicated dependency pairs from module analysis summaries.

Reads summary.json, extracts dependencies from each module, creates unique
bidirectional pairs for relationship analysis.

Usage:
    python3 build_dep_pairs.py --summaries /path/to/summary.json [--registry /path/to/registry.json]
"""

import argparse
import json
import sys


def build_dep_pairs(summaries: list[dict], known_modules: set[str] | None = None) -> dict:
    """Build deduplicated dependency pairs from module summaries."""
    seen = set()
    pairs = []

    for s in summaries:
        module_name = s.get("module", "")
        deps = s.get("dependencies", [])

        for dep in deps:
            if known_modules and dep not in known_modules:
                continue

            key = tuple(sorted([module_name, dep]))
            if key[0] == key[1]:
                continue
            if key not in seen:
                seen.add(key)
                pairs.append(
                    {
                        "module_a": module_name,
                        "module_b": dep,
                        "direction": f"{module_name} -> {dep}",
                    }
                )

    return {
        "pairs": pairs,
        "total_pairs": len(pairs),
    }


def main():
    parser = argparse.ArgumentParser(description="Build dependency pairs from module summaries")
    parser.add_argument("--summaries", required=True, help="Path to summary.json")
    parser.add_argument(
        "--registry",
        default=None,
        help="Path to registry.json (for known module list)",
    )
    args = parser.parse_args()

    with open(args.summaries) as f:
        summaries = json.load(f)

    known_modules = None
    if args.registry:
        with open(args.registry) as f:
            registry_data = json.load(f)
            if isinstance(registry_data, list):
                known_modules = {r.get("module", "") for r in registry_data}
            elif isinstance(registry_data, dict) and "modules" in registry_data:
                known_modules = set(registry_data["modules"].keys())

    result = build_dep_pairs(summaries, known_modules)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
