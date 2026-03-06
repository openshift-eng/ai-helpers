#!/usr/bin/env python3
"""
CodeRabbit Adoption Report Script

Measures CodeRabbit adoption across the openshift GitHub organization by
querying the GitHub search API for merged PRs with coderabbitai[bot] comments.

By default, produces a lightweight org-wide summary using only 2 API calls.
Use --detailed to add per-repo breakdowns with adoption percentages and a
check for well-known repos missing CodeRabbit activity. The detailed mode
makes many additional API calls and is prone to hitting GitHub rate limits.

GitHub search API rate limit: 30 requests/minute for authenticated users.
The --detailed mode uses 2-second sleeps between calls to stay under this.

Prerequisites:
    GitHub CLI (gh) must be installed and authenticated.

Usage:
    python3 coderabbit_adoption.py
    python3 coderabbit_adoption.py --start-date 2026-02-01 --end-date 2026-02-28
    python3 coderabbit_adoption.py --detailed
"""

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

# GitHub search API allows 30 requests/minute for authenticated users.
# 2-second sleep keeps us at ~30 req/min with headroom.
SEARCH_API_SLEEP = 2


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
    """Fetch search results with pagination, returning repository_url list."""
    urls = []
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
            if len(parts) == 2:
                urls.append(parts[1])
        if len(items) < 100:
            break
        time.sleep(SEARCH_API_SLEEP)
    return urls


def main():
    parser = argparse.ArgumentParser(description="CodeRabbit Adoption Report")
    parser.add_argument("--start-date", help="Start date YYYY-MM-DD (default: 30 days ago)")
    parser.add_argument("--end-date", help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--top-n", type=int, default=20,
                        help="Number of top repos to show in breakdown (default: 20)")
    parser.add_argument("--detailed", action="store_true",
                        help="Fetch per-repo breakdowns with adoption percentages "
                             "and check well-known repos for missing activity. "
                             "Makes many extra API calls; prone to rate limiting.")
    args = parser.parse_args()

    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    if args.start_date:
        start_date = args.start_date
    else:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    print(f"Querying GitHub search API for merged PRs in openshift org...", file=sys.stderr)
    print(f"Date range: {start_date} to {end_date}", file=sys.stderr)

    # Step 1: Get total merged PRs (1 API call)
    base_query = f"is:pr is:merged org:openshift merged:{start_date}..{end_date}"
    total = search_count(base_query)
    print(f"Total merged PRs: {total}", file=sys.stderr)

    # Step 2: Get merged PRs with CodeRabbit comments (1 API call)
    cr_query = f"{base_query} commenter:coderabbitai[bot]"
    with_cr = search_count(cr_query)
    print(f"PRs with CodeRabbit comments: {with_cr}", file=sys.stderr)

    adoption_pct = (with_cr / total * 100) if total > 0 else 0

    output = {
        "start_date": start_date,
        "end_date": end_date,
        "total_merged_prs": total,
        "prs_with_coderabbit": with_cr,
        "adoption_pct": round(adoption_pct, 1),
        "detailed": args.detailed,
        "repo_breakdown": [],
        "no_coderabbit_activity": [],
    }

    if args.detailed:
        print("Detailed mode: fetching per-repo breakdown "
              "(2s between calls to respect rate limits)...", file=sys.stderr)

        # Step 3: Paginate for per-repo CR counts (up to 10 API calls)
        repo_urls = search_items_paginated(cr_query)
        repo_counts = Counter(repo_urls)
        output["per_repo_approximate"] = len(repo_urls) < with_cr

        top_repos = repo_counts.most_common(args.top_n)

        # Step 4: Fetch per-repo totals for adoption percentages
        repo_breakdown = []
        print(f"Fetching total PR counts for top {len(top_repos)} repos...", file=sys.stderr)
        for repo_name, cr_count in top_repos:
            repo_total = search_count(
                f"is:pr is:merged repo:{repo_name} merged:{start_date}..{end_date}")
            repo_breakdown.append({
                "repo": repo_name,
                "cr_count": cr_count,
                "total": repo_total,
                "adoption_pct": round(
                    (cr_count / repo_total * 100) if repo_total > 0 else 0, 1),
            })
            time.sleep(SEARCH_API_SLEEP)

        output["repo_breakdown"] = repo_breakdown

        # Step 5: Find high-volume repos with no CodeRabbit activity
        well_known_repos = [
            "openshift/release",
            "openshift/installer",
            "openshift/machine-config-operator",
            "openshift/ovn-kubernetes",
            "openshift/openshift-tests-private",
            "openshift/cluster-logging-operator",
            "openshift/library-go",
            "openshift/kubernetes",
            "openshift/enhancements",
            "openshift/cluster-monitoring-operator",
            "openshift/router",
            "openshift/cluster-node-tuning-operator",
            "openshift/machine-api-operator",
            "openshift/openshift-controller-manager",
            "openshift/cluster-storage-operator",
            "openshift/cluster-openshift-apiserver-operator",
            "openshift/multus-cni",
            "openshift/sriov-network-operator",
        ]
        repos_with_cr = set(repo_counts.keys())
        repos_to_check = [r for r in well_known_repos if r not in repos_with_cr]
        if repos_to_check:
            print(f"Checking {len(repos_to_check)} well-known repos for activity...",
                  file=sys.stderr)
        no_cr_repos = {}
        for repo_name in repos_to_check:
            repo_total = search_count(
                f"is:pr is:merged repo:{repo_name} merged:{start_date}..{end_date}")
            if repo_total >= 10:
                no_cr_repos[repo_name] = repo_total
            time.sleep(SEARCH_API_SLEEP)

        output["no_coderabbit_activity"] = [
            {"repo": k, "total": v}
            for k, v in sorted(no_cr_repos.items(), key=lambda x: x[1], reverse=True)
        ]

    json.dump(output, sys.stdout, indent=2)
    print(file=sys.stdout)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
