#!/usr/bin/env python3
"""
CodeRabbit Adoption Report Script

Measures CodeRabbit adoption across a curated list of OCP payload repositories
by querying the GitHub search API for merged PRs with coderabbitai[bot] comments.

The script always produces per-repo breakdowns. It first queries org-wide for
CodeRabbit-commented PRs (efficient pagination), then fetches per-repo total
PR counts only for repos with CodeRabbit activity. Repos with no activity are
listed separately without needing individual API calls.

GitHub search API rate limit: 30 requests/minute for authenticated users.
The script uses 2-second sleeps between calls to stay under this limit.

Prerequisites:
    GitHub CLI (gh) must be installed and authenticated.

Usage:
    python3 coderabbit_adoption.py
    python3 coderabbit_adoption.py --start-date 2026-02-01 --end-date 2026-02-28
"""

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

SEARCH_API_SLEEP = 2
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALLOWED_REPOS_FILE = os.path.join(SCRIPT_DIR, "allowed-repos.txt")


def load_allowed_repos():
    """Load the curated list of repos to report on."""
    with open(ALLOWED_REPOS_FILE) as f:
        return set(line.strip() for line in f if line.strip())


def gh_api_get(endpoint, params=None):
    """Call GitHub API via gh CLI and return parsed JSON."""
    cmd = ["gh", "api", "-X", "GET", endpoint]
    if params:
        for key, value in params.items():
            cmd.extend(["-f", f"{key}={value}"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error calling gh api: {result.stderr}", file=sys.stderr)
        return None
    return json.loads(result.stdout)


def search_count(query):
    """Get total_count from a GitHub search query."""
    data = gh_api_get("/search/issues", {"q": query})
    if data is None:
        return 0
    return data.get("total_count", 0)


def search_items_paginated(query, max_pages=10):
    """Fetch search results with pagination, returning (results, truncated).

    results is a list of (repo, author) tuples.
    truncated is True if pagination hit the max_pages limit or GitHub's 1000-item cap.
    """
    results = []
    truncated = False
    for page in range(1, max_pages + 1):
        data = gh_api_get("/search/issues", {
            "q": query,
            "per_page": "100",
            "page": str(page),
        })
        if data is None:
            break
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            repo_url = item.get("repository_url", "")
            parts = repo_url.split("/repos/", 1)
            author = item.get("user", {}).get("login")
            if len(parts) == 2 and author:
                results.append((parts[1], author))
        if len(items) < 100:
            break
        if page == max_pages:
            truncated = True
        time.sleep(SEARCH_API_SLEEP)
    return results, truncated


def search_authors_paginated(query, max_pages=10):
    """Fetch search results with pagination, returning (authors, total_count, truncated)."""
    authors = set()
    total_count = 0
    truncated = False
    for page in range(1, max_pages + 1):
        data = gh_api_get("/search/issues", {
            "q": query,
            "per_page": "100",
            "page": str(page),
        })
        if data is None:
            break
        if page == 1:
            total_count = data.get("total_count", 0)
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            author = item.get("user", {}).get("login")
            if author:
                authors.add(author)
        if len(items) < 100:
            break
        if page == max_pages:
            truncated = True
        time.sleep(SEARCH_API_SLEEP)
    return authors, total_count, truncated


def main():
    parser = argparse.ArgumentParser(description="CodeRabbit Adoption Report")
    parser.add_argument("--start-date", help="Start date YYYY-MM-DD (default: 7 days ago)")
    parser.add_argument("--end-date", help="End date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = args.start_date or (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")

    allowed_repos = load_allowed_repos()
    print(f"Loaded {len(allowed_repos)} repos from allowed list", file=sys.stderr)
    print(f"Date range: {start_date} to {end_date}", file=sys.stderr)

    # Phase 1: Get org-wide CR PR count (1 API call)
    print("Querying org-wide CodeRabbit PR count...", file=sys.stderr)
    cr_query = f"is:pr is:merged org:openshift merged:{start_date}..{end_date} commenter:coderabbitai[bot]"
    org_cr_total = search_count(cr_query)
    print(f"  Org-wide PRs with CodeRabbit: {org_cr_total}", file=sys.stderr)
    time.sleep(SEARCH_API_SLEEP)

    # Phase 2: Paginate CR results to get per-repo counts and authors (~10 API calls)
    print("Fetching per-repo CodeRabbit counts via pagination...", file=sys.stderr)
    cr_results, cr_truncated = search_items_paginated(cr_query)
    cr_repo_urls = [repo for repo, _ in cr_results]
    all_cr_counts = Counter(cr_repo_urls)
    cr_counts = {repo: count for repo, count in all_cr_counts.items() if repo in allowed_repos}
    # Collect CR authors per repo
    cr_authors_by_repo = {}
    for repo, author in cr_results:
        if repo in allowed_repos:
            cr_authors_by_repo.setdefault(repo, set()).add(author)
    approximate = len(cr_repo_urls) < org_cr_total
    print(f"  Found CodeRabbit activity in {len(cr_counts)} allowed repos "
          f"(paginated {len(cr_repo_urls)}/{org_cr_total} results"
          f"{', approximate' if approximate else ''})", file=sys.stderr)
    time.sleep(SEARCH_API_SLEEP)

    # Phase 3: Query per-repo total PRs for repos with CR activity
    repos_with_cr = sorted(cr_counts.keys(), key=lambda r: cr_counts[r], reverse=True)
    repo_breakdown = []
    total_prs = 0
    total_cr_prs = sum(cr_counts.values())

    if repos_with_cr:
        print(f"Fetching total PR counts for {len(repos_with_cr)} active repos "
              f"(~{len(repos_with_cr) * SEARCH_API_SLEEP}s)...", file=sys.stderr)

    all_unlicensed_users = set()
    any_truncated = False
    for i, repo in enumerate(repos_with_cr, 1):
        cr_count = cr_counts[repo]
        repo_query = f"is:pr is:merged repo:{repo} merged:{start_date}..{end_date}"
        all_authors, repo_total, authors_truncated = search_authors_paginated(repo_query)
        total_prs += repo_total
        adoption_pct = round((cr_count / repo_total * 100) if repo_total > 0 else 0, 1)
        cr_authors = cr_authors_by_repo.get(repo, set())
        bot_users = {u for u in all_authors if u.endswith("[bot]")} | {"openshift-merge-robot"}
        repo_truncated = authors_truncated or cr_truncated
        unlicensed = sorted(all_authors - cr_authors - bot_users) if not repo_truncated else []
        if not repo_truncated:
            all_unlicensed_users.update(unlicensed)
        else:
            any_truncated = True
        repo_breakdown.append({
            "repo": repo,
            "cr_count": cr_count,
            "total": repo_total,
            "adoption_pct": adoption_pct,
            "unlicensed_users": unlicensed,
            "truncated": repo_truncated,
        })
        print(f"  [{i}/{len(repos_with_cr)}] {repo}: {cr_count}/{repo_total} ({adoption_pct}%)",
              file=sys.stderr)
        time.sleep(SEARCH_API_SLEEP)

    # Repos with no CR activity
    repos_without_cr = sorted(allowed_repos - set(cr_counts.keys()))

    overall_adoption = round((total_cr_prs / total_prs * 100) if total_prs > 0 else 0, 1)

    output = {
        "start_date": start_date,
        "end_date": end_date,
        "total_merged_prs": total_prs,
        "prs_with_coderabbit": total_cr_prs,
        "adoption_pct": overall_adoption,
        "per_repo_approximate": approximate,
        "repo_breakdown": repo_breakdown,
        "repos_without_cr_activity": repos_without_cr,
        "repos_without_cr_count": len(repos_without_cr),
        "repos_with_cr_count": len(repos_with_cr),
        "total_allowed_repos": len(allowed_repos),
        "unlicensed_users": sorted(all_unlicensed_users),
        "unlicensed_user_count": len(all_unlicensed_users),
        "unlicensed_users_approximate": any_truncated,
    }

    json.dump(output, sys.stdout, indent=2)
    print(file=sys.stdout)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
