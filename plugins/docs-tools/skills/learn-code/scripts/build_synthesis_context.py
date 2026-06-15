#!/usr/bin/env python3
"""Assemble module summaries and relationship data into a single synthesis context.

Reads summary.json and optionally relationships.json from the agent workspace.
Produces a combined context object for the synthesis agent.

When the context exceeds --max-size, applies progressive truncation:
  1. Compact summaries (keep key fields only, first gotcha only)
  2. Compact relationships (keep pair, type, strength, description)
  3. Drop api-only module summaries entirely

Usage:
    python3 build_synthesis_context.py --base-path /path/to/.agent_workspace/repo-name
    python3 build_synthesis_context.py --base-path /path --max-size 80000
"""

import argparse
import json
import os
import sys


def _compact_summary(s: dict) -> dict:
    api = s.get("public_api", [])
    if api and isinstance(api[0], dict):
        api = [a.get("name", str(a)) for a in api]
    elif api and not isinstance(api[0], str):
        api = [str(a) for a in api]

    deps = s.get("dependencies", [])
    if deps and isinstance(deps[0], dict):
        deps = [d.get("module", str(d)) for d in deps]

    gotchas = s.get("gotchas", [])
    first_gotcha = ""
    if gotchas:
        g = gotchas[0]
        first_gotcha = g.get("description", str(g)) if isinstance(g, dict) else str(g)

    return {
        "module": s.get("module", ""),
        "purpose": s.get("purpose", ""),
        "public_api": api[:10],
        "dependencies": deps[:5],
        "onboarding_priority": s.get("onboarding_priority", "skim"),
        "gotchas": [first_gotcha] if first_gotcha else [],
        "analysis_depth": s.get("analysis_depth", "full"),
    }


def _compact_relationship(r: dict) -> dict:
    return {
        "pair": r.get("pair", []),
        "coupling_type": r.get("coupling_type", "unknown"),
        "strength": r.get("strength", "unknown"),
        "description": r.get("description", ""),
    }


def _context_size(context: dict) -> int:
    return len(json.dumps(context).encode("utf-8"))


def build_context(base_path: str, max_size: int = 0) -> dict:
    summary_path = os.path.join(base_path, "module-analysis", "summary.json")
    relationships_path = os.path.join(base_path, "relationships", "relationships.json")
    detection_path = os.path.join(base_path, "detection", "detection.json")

    if not os.path.exists(summary_path):
        return {"error": f"summary.json not found at {summary_path}"}

    with open(summary_path) as f:
        summaries = json.load(f)

    relationships = []
    if os.path.exists(relationships_path):
        with open(relationships_path) as f:
            relationships = json.load(f)

    detection = {}
    if os.path.exists(detection_path):
        with open(detection_path) as f:
            detection = json.load(f)

    repo_name = os.path.basename(base_path)
    primary_language = detection.get("primary_language", "unknown")

    context = {
        "repo_name": repo_name,
        "primary_language": primary_language,
        "module_count": len(summaries),
        "relationship_count": len(relationships),
        "summaries": summaries,
        "relationships": relationships,
    }

    if max_size > 0 and _context_size(context) > max_size:
        context["summaries"] = [_compact_summary(s) for s in summaries]
        context["relationships"] = [_compact_relationship(r) for r in relationships]
        context["truncated"] = "compacted"

    if max_size > 0 and _context_size(context) > max_size:
        context["summaries"] = [
            s for s in context["summaries"] if s.get("analysis_depth") != "api-only"
        ]
        context["module_count"] = len(context["summaries"])
        context["truncated"] = "api-only-dropped"

    context["context_size_bytes"] = _context_size(context)

    return context


def main():
    parser = argparse.ArgumentParser(description="Build synthesis context")
    parser.add_argument("--base-path", required=True, help="Base path for the agent workspace")
    parser.add_argument(
        "--max-size",
        type=int,
        default=80000,
        help="Max context size in bytes (default: 80000, 0 = no limit)",
    )
    args = parser.parse_args()

    result = build_context(args.base_path, args.max_size)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
