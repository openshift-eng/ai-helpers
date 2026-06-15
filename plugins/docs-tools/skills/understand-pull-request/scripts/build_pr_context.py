#!/usr/bin/env python3
"""Assemble all PR analysis data into a single context JSON for the synthesis agent.

Reads PR metadata, repo overview, affected modules, change summary, and diff.
Applies progressive truncation if the assembled context exceeds --max-size.

Outputs JSON to stdout.

Usage:
    python3 build_pr_context.py --pr-base /path/to/pr-42 --max-size 80000
"""

import argparse
import json
import os
import sys


def read_json(path: str) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def read_text(path: str, max_chars: int = 0) -> str:
    try:
        with open(path) as f:
            content = f.read()
            if max_chars > 0 and len(content) > max_chars:
                return content[:max_chars] + "\n\n[TRUNCATED]"
            return content
    except FileNotFoundError:
        return ""


def build_context(pr_base: str, max_size: int) -> dict:
    metadata = read_json(os.path.join(pr_base, "pr-metadata", "metadata.json"))
    if metadata is None:
        return {"error": "metadata.json not found"}

    repo_overview = read_text(os.path.join(pr_base, "repo-context", "repo-overview.md"))
    affected_modules = read_json(os.path.join(pr_base, "change-analysis", "affected-modules.json"))
    change_summary = read_json(os.path.join(pr_base, "change-analysis", "change-summary.json"))
    diff_text = read_text(os.path.join(pr_base, "pr-metadata", "diff.patch"))

    context = {
        "pr_number": metadata.get("pr_number"),
        "platform": metadata.get("platform"),
        "title": metadata.get("title", ""),
        "description": metadata.get("description", ""),
        "state": metadata.get("state", ""),
        "author": metadata.get("author", ""),
        "base_branch": metadata.get("base_branch", ""),
        "head_branch": metadata.get("head_branch", ""),
        "labels": metadata.get("labels", []),
        "commits": metadata.get("commits", []),
        "changed_files": metadata.get("changed_files", []),
        "url": metadata.get("url", ""),
        "repo_overview": repo_overview,
        "affected_modules": affected_modules or {},
        "change_analyses": change_summary or [],
        "diff": diff_text,
    }

    context_bytes = len(json.dumps(context, indent=2).encode("utf-8"))

    if context_bytes > max_size:
        diff_budget = max(max_size // 4, 5000)
        context["diff"] = (
            context["diff"][:diff_budget] + "\n\n[DIFF TRUNCATED — full diff in diff.patch]"
        )
        context["truncated"] = True
        context_bytes = len(json.dumps(context, indent=2).encode("utf-8"))

    if context_bytes > max_size and isinstance(context["change_analyses"], list):
        for analysis in context["change_analyses"]:
            if isinstance(analysis, dict) and "files_analyzed" in analysis:
                for fa in analysis["files_analyzed"]:
                    if isinstance(fa, dict):
                        fa.pop("key_changes", None)
        context_bytes = len(json.dumps(context, indent=2).encode("utf-8"))

    if context_bytes > max_size:
        context["diff"] = "[DIFF OMITTED — see diff.patch on disk]"
        context_bytes = len(json.dumps(context, indent=2).encode("utf-8"))

    context["context_size_bytes"] = context_bytes
    context.setdefault("truncated", False)

    return context


def main():
    parser = argparse.ArgumentParser(description="Build PR synthesis context")
    parser.add_argument("--pr-base", required=True, help="Path to the PR base directory")
    parser.add_argument("--max-size", type=int, default=80000, help="Max context size in bytes")
    args = parser.parse_args()

    result = build_context(args.pr_base, args.max_size)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
