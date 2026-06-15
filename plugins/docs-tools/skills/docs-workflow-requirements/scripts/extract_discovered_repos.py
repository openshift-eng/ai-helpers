#!/usr/bin/env python3
"""Extract repo/PR URLs from JIRA ticket graph data and discovery output.

Reads JSON ticket data on stdin (from jira_reader.py --graph or similar),
extracts all repo and PR URLs from git_links and auto_discovered_urls,
groups by normalized repo URL, and writes discovered_repos.json.

Optionally merges PR URLs from discovery.json (requirements-discoverer output)
to capture PRs found via description/comment text scanning that aren't in the
JIRA graph's formal git_links.

Usage:
    python3 jira_reader.py --graph PROJ-123 | \
        python3 extract_discovered_repos.py \
        --output-dir .agent_workspace/proj-123/requirements

    python3 jira_reader.py --graph PROJ-123 | \
        python3 extract_discovered_repos.py \
        --output-dir .agent_workspace/proj-123/requirements \
        --merge-discovery .agent_workspace/proj-123/requirements/discovery.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "docs-orchestrator" / "scripts"),
)
from resolve_source import extract_repo_url, normalize_git_url

GITHUB_PR_RE = re.compile(r"https?://github\.com/[^/]+/[^/]+/pull/\d+")
GITLAB_MR_RE = re.compile(r"https?://gitlab\.[^/]+/.+?/-/merge_requests/\d+")


def extract_repos_from_graph(graph_data):
    """Extract and group repo/PR URLs from JIRA graph data.

    Accepts either:
    - A single ticket's graph output (from jira_reader.py --graph): has
      "ticket" or "issue_key", "git_links", "auto_discovered_urls",
      "children", etc.
    - A dict of tickets keyed by ticket key (from jira_graph_walker.py):
      each value has "git_links", "auto_discovered_urls"

    Returns dict matching discovered_repos.json schema.
    """
    tickets = {}

    if "issue_key" in graph_data or "ticket" in graph_data:
        key = graph_data.get("issue_key") or graph_data.get("ticket")
        tickets[key] = graph_data
        for child in graph_data.get("children", {}).get("issues", []):
            child_key = child.get("key")
            if child_key:
                tickets[child_key] = child
        for link in graph_data.get("issue_links", {}).get("links", []):
            link_key = link.get("key")
            if link_key:
                tickets[link_key] = link
    elif "tickets" in graph_data:
        tickets = graph_data["tickets"]
    else:
        tickets = graph_data

    repo_groups = {}

    for ticket_key, ticket in tickets.items():
        all_urls = list(ticket.get("git_links", []))

        auto = ticket.get("auto_discovered_urls", {})
        for pr_url in auto.get("pull_requests", []):
            if pr_url not in all_urls:
                all_urls.append(pr_url)

        seen_urls = set()
        unique_urls = []
        for url in all_urls:
            if url not in seen_urls:
                seen_urls.add(url)
                unique_urls.append(url)

        for url in unique_urls:
            repo_url = extract_repo_url(url)
            if not repo_url:
                continue

            normalized = normalize_git_url(repo_url)

            if normalized not in repo_groups:
                repo_groups[normalized] = {
                    "repo_url": repo_url,
                    "pr_urls": set(),
                    "source_tickets": set(),
                }

            repo_groups[normalized]["source_tickets"].add(ticket_key)

            if GITHUB_PR_RE.match(url) or GITLAB_MR_RE.match(url):
                repo_groups[normalized]["pr_urls"].add(url)

    return _serialize_repo_groups(repo_groups)


def _extract_prs_from_discovery(discovery_path):
    """Extract PR URLs from requirements-discoverer output (discovery.json).

    Returns a list of PR URL strings, or empty list on error.
    """
    try:
        with open(discovery_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    urls = set()

    for pr in data.get("sources_consulted", {}).get("pull_requests", []):
        url = pr.get("url") if isinstance(pr, dict) else pr
        if url:
            urls.add(url)

    for req in data.get("requirements", []):
        for src in req.get("sources", []):
            if src.get("type") == "pr" and src.get("url"):
                urls.add(src["url"])

    return list(urls)


def merge_discovery_prs(repo_groups, discovery_path):
    """Merge PR URLs from discovery.json into repo_groups.

    For each PR URL found in discovery.json, derives the repo URL and either
    augments an existing repo_groups entry or creates a new one. Merges are
    deduplicated — a PR already in the group's pr_urls is not added again.

    Mutates repo_groups in place and returns it.
    """
    pr_urls = _extract_prs_from_discovery(discovery_path)
    if not pr_urls:
        return repo_groups

    for url in pr_urls:
        repo_url = extract_repo_url(url)
        if not repo_url:
            continue

        normalized = normalize_git_url(repo_url)

        if normalized not in repo_groups:
            repo_groups[normalized] = {
                "repo_url": repo_url,
                "pr_urls": set(),
                "source_tickets": set(),
            }

        if GITHUB_PR_RE.match(url) or GITLAB_MR_RE.match(url):
            repo_groups[normalized]["pr_urls"].add(url)

    return repo_groups


def _rebuild_repo_groups(result):
    """Reconstruct repo_groups dict from serialized discovered_repos.json data."""
    groups = {}
    for repo in result.get("repos", []):
        groups[repo["normalized"]] = {
            "repo_url": repo["repo_url"],
            "pr_urls": set(repo.get("pr_urls", [])),
            "source_tickets": set(repo.get("source_tickets", [])),
        }
    return groups


def _serialize_repo_groups(repo_groups):
    """Sort and serialize repo_groups into the discovered_repos.json schema."""
    repos = []
    total_prs = 0
    for _normalized, group in sorted(
        repo_groups.items(),
        key=lambda x: (len(x[1]["pr_urls"]), len(x[1]["source_tickets"])),
        reverse=True,
    ):
        pr_list = sorted(group["pr_urls"])
        repos.append(
            {
                "repo_url": group["repo_url"],
                "normalized": _normalized,
                "reference_count": len(group["source_tickets"]),
                "pr_urls": pr_list,
                "source_tickets": sorted(group["source_tickets"]),
            }
        )
        total_prs += len(pr_list)

    return {
        "repos": repos,
        "total_repos": len(repos),
        "total_prs": total_prs,
    }


def _traverse_linked_tickets(graph_data, jira_reader_path):
    """Run --graph on each issue_link to capture their children's git links.

    Returns a merged tickets dict containing all linked tickets and their
    children, suitable for feeding into the same extraction logic.
    """
    import subprocess

    linked_keys = []
    for link in graph_data.get("issue_links", {}).get("links", []):
        key = link.get("key")
        if key:
            linked_keys.append(key)

    if not linked_keys:
        return {}

    extra_tickets = {}
    for key in linked_keys:
        try:
            result = subprocess.run(  # noqa: S603
                ["python3", jira_reader_path, "--graph", key, "--max-graph-tokens", "10000"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print(f"WARNING: --graph {key} failed: {result.stderr.strip()}", file=sys.stderr)
                continue
            linked_graph = json.loads(result.stdout)
            extra_tickets[key] = linked_graph
            for child in linked_graph.get("children", {}).get("issues", []):
                child_key = child.get("key")
                if child_key:
                    extra_tickets[child_key] = child
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            print(f"WARNING: --graph {key} error: {e}", file=sys.stderr)

    return extra_tickets


def main():
    parser = argparse.ArgumentParser(description="Extract repo/PR URLs from JIRA ticket graph data")
    parser.add_argument(
        "--output-dir", required=True, help="Directory to write discovered_repos.json"
    )
    parser.add_argument(
        "--merge-discovery",
        help="Path to discovery.json to merge text-discovered PRs",
    )
    parser.add_argument(
        "--traverse-links",
        metavar="JIRA_READER_PATH",
        help="Path to jira_reader.py; runs --graph on each "
        "issue_link to find PRs on linked tickets' children",
    )
    args = parser.parse_args()

    try:
        graph_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)

    result = extract_repos_from_graph(graph_data)

    if args.traverse_links:
        extra_tickets = _traverse_linked_tickets(graph_data, args.traverse_links)
        if extra_tickets:
            extra_result = extract_repos_from_graph({"tickets": extra_tickets})
            repo_groups = _rebuild_repo_groups(result)
            for repo in extra_result.get("repos", []):
                normalized = repo["normalized"]
                if normalized not in repo_groups:
                    repo_groups[normalized] = {
                        "repo_url": repo["repo_url"],
                        "pr_urls": set(),
                        "source_tickets": set(),
                    }
                repo_groups[normalized]["pr_urls"].update(repo.get("pr_urls", []))
                repo_groups[normalized]["source_tickets"].update(repo.get("source_tickets", []))
            result = _serialize_repo_groups(repo_groups)
            print(
                f"Traversed {len(extra_tickets)} linked tickets",
                file=sys.stderr,
            )

    if args.merge_discovery:
        repo_groups = _rebuild_repo_groups(result)
        merge_discovery_prs(repo_groups, args.merge_discovery)
        result = _serialize_repo_groups(repo_groups)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "discovered_repos.json"

    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(
        f"Wrote {output_file}: {result['total_repos']} repos, {result['total_prs']} PRs",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
