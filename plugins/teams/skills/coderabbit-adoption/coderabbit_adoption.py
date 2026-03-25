#!/usr/bin/env python3
"""
CodeRabbit Adoption Report Script

Measures CodeRabbit Pro adoption across OCP payload repositories by comparing
all merged PRs against those with "Plan: Pro" CodeRabbit comments.

Uses one org-wide search for Pro-reviewed PRs, then batched repo queries for
all merged PRs. Per-repo breakdowns are calculated in Python.

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
from collections import defaultdict
from datetime import datetime, timedelta

SEARCH_API_SLEEP = 3
RETRY_SLEEP = 30
MAX_RETRIES = 3
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALLOWED_REPOS_FILE = os.path.join(SCRIPT_DIR, "allowed-repos.txt")
CR_ENABLEMENT_DATE = "2026-03-09"
# Repos per search query batch. Keeps results under GitHub's 1000-item search cap
# and query URL length limits. 20 repos * ~40 chars each = ~800 chars for repo: filters.
REPO_BATCH_SIZE = 20


def load_allowed_repos():
    with open(ALLOWED_REPOS_FILE) as f:
        return sorted(line.strip() for line in f if line.strip())


def search_paginated(query, max_pages=10):
    """Fetch all search results via pagination.

    Returns (items, total_count, truncated).
    Each item is a dict with repo, number, title, author, url.
    """
    items = []
    total_count = 0
    truncated = False
    for page in range(1, max_pages + 1):
        cmd = [
            "gh", "api", "-X", "GET", "/search/issues",
            "-f", f"q={query}",
            "-f", "per_page=100",
            "-f", f"page={page}",
        ]
        data = None
        for attempt in range(MAX_RETRIES):
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           universal_newlines=True, timeout=30)
            except subprocess.TimeoutExpired:
                print(f"  Timeout after 30s (attempt {attempt + 1}/{MAX_RETRIES})...", file=sys.stderr)
                continue
            if result.returncode == 0:
                data = json.loads(result.stdout)
                break
            if "secondary rate limit" in result.stderr.lower() or "403" in result.stderr:
                wait = RETRY_SLEEP * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s (attempt {attempt + 1}/{MAX_RETRIES})...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"  Error: {result.stderr.strip()}", file=sys.stderr)
                break
        if data is None:
            truncated = True
            break
        if page == 1:
            total_count = data.get("total_count", 0)
        page_items = data.get("items", [])
        if not page_items:
            break
        for item in page_items:
            repo_url = item.get("repository_url", "")
            parts = repo_url.split("/repos/", 1)
            repo = parts[1] if len(parts) == 2 else ""
            author = (item.get("user") or {}).get("login", "")
            number = item.get("number", 0)
            title = item.get("title", "")
            html_url = item.get("html_url", "")
            items.append({
                "repo": repo,
                "number": number,
                "title": title,
                "author": author,
                "url": html_url,
            })
        if len(page_items) < 100:
            break
        if page == max_pages:
            truncated = True
        time.sleep(SEARCH_API_SLEEP)
    return items, total_count, truncated


def is_bot(author):
    return author.endswith("[bot]") or author in {"openshift-merge-robot"}


def main():
    parser = argparse.ArgumentParser(description="CodeRabbit Adoption Report")
    parser.add_argument("--start-date", help="Start date YYYY-MM-DD (default: 7 days ago)")
    parser.add_argument("--end-date", help="End date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = args.start_date or (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")

    allowed_repos = load_allowed_repos()
    allowed_set = set(allowed_repos)
    print(f"Loaded {len(allowed_repos)} repos from allowed list", file=sys.stderr)
    print(f"Date range: {start_date} to {end_date}", file=sys.stderr)

    created_filter = f"created:>={CR_ENABLEMENT_DATE}"
    base_query = f"is:pr is:merged merged:{start_date}..{end_date} {created_filter}"

    # Query 1: Single org-wide search for PRs with Pro CodeRabbit reviews
    print("Fetching PRs with CodeRabbit Pro reviews...", file=sys.stderr)
    pro_query = f'{base_query} org:openshift commenter:coderabbitai[bot] "Plan: Pro"'
    pro_items, pro_total, pro_truncated = search_paginated(pro_query)
    pro_items = [i for i in pro_items if i["repo"] in allowed_set]
    print(f"  {len(pro_items)} PRs with Pro reviews in allowed repos ({pro_total} org-wide)", file=sys.stderr)
    time.sleep(SEARCH_API_SLEEP)

    # Query 2: All merged PRs in allowed repos, batched to stay under 1000-result cap
    batches = [allowed_repos[i:i + REPO_BATCH_SIZE] for i in range(0, len(allowed_repos), REPO_BATCH_SIZE)]
    print(f"Fetching all merged PRs ({len(batches)} batches)...", file=sys.stderr)
    all_items = []
    all_truncated = False
    for batch_num, batch in enumerate(batches, 1):
        repo_filter = " ".join(f"repo:{r}" for r in batch)
        batch_query = f"{base_query} {repo_filter}"
        items, count, truncated = search_paginated(batch_query)
        all_items.extend(items)
        if truncated:
            all_truncated = True
        if count > 0:
            print(f"  Batch {batch_num}/{len(batches)}: {count} PRs", file=sys.stderr)
        time.sleep(SEARCH_API_SLEEP)
    print(f"  {len(all_items)} total merged PRs", file=sys.stderr)

    # Build lookup of PRs with Pro reviews
    pro_keys = {(i["repo"], i["number"]) for i in pro_items}

    # Per-repo breakdown
    repos_all = defaultdict(list)
    for item in all_items:
        repos_all[item["repo"]].append(item)

    repos_pro = defaultdict(list)
    for item in pro_items:
        repos_pro[item["repo"]].append(item)

    # Missed PRs (no Pro review)
    missed_prs = [item for item in all_items if (item["repo"], item["number"]) not in pro_keys]

    # Per-repo breakdown sorted by total PRs descending
    repo_breakdown = []
    for repo in sorted(repos_all.keys(), key=lambda r: len(repos_all[r]), reverse=True):
        total = len(repos_all[repo])
        pro_count = len(repos_pro.get(repo, []))
        repo_breakdown.append({
            "repo": repo,
            "pro_count": pro_count,
            "total": total,
            "adoption_pct": round(pro_count / total * 100, 1) if total > 0 else 0,
        })

    # Repos with no activity
    active_repos = set(repos_all.keys())
    repos_without_activity_count = len(allowed_set - active_repos)

    total_prs = len(all_items)
    total_pro = len(pro_items)
    adoption_pct = round(total_pro / total_prs * 100, 1) if total_prs > 0 else 0

    # Non-bot users with missed PRs
    non_bot_missed = [m for m in missed_prs if not is_bot(m["author"])]
    missed_by_user = defaultdict(list)
    for m in non_bot_missed:
        missed_by_user[m["author"]].append(m["repo"])

    output = {
        "start_date": start_date,
        "end_date": end_date,
        "cr_enablement_date": CR_ENABLEMENT_DATE,
        "total_allowed_repos": len(allowed_repos),
        "repos_with_activity": len(active_repos),
        "repos_without_activity_count": repos_without_activity_count,
        "total_merged_prs": total_prs,
        "prs_with_pro_review": total_pro,
        "adoption_pct": adoption_pct,
        "truncated": pro_truncated or all_truncated,
        "repo_breakdown": repo_breakdown,
        "missed_prs": [
            {
                "repo": m["repo"],
                "number": m["number"],
                "title": m["title"],
                "author": m["author"],
                "url": m["url"],
                "is_bot": is_bot(m["author"]),
            }
            for m in missed_prs
        ],
        "missed_prs_count": len(missed_prs),
        "missed_non_bot_count": len(non_bot_missed),
        "missed_by_user": {user: sorted(set(repos)) for user, repos in sorted(missed_by_user.items())},
    }

    json.dump(output, sys.stdout, indent=2)
    print(file=sys.stdout)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
