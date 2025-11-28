#!/usr/bin/env python3
"""
Search GitHub for repositories implementing a specific pattern.

This script uses the GitHub Code Search API to find repositories that implement
a specific design pattern (e.g., NetworkPolicy, ValidatingWebhook).
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
import urllib.error
import os
from datetime import datetime


def search_github(pattern, orgs, language='go', max_results=100):
    """
    Search GitHub Code Search API for pattern usage.
    
    Args:
        pattern: Pattern name to search for (e.g., "NetworkPolicy")
        orgs: List of GitHub organizations to search
        language: Programming language filter (default: go)
        max_results: Maximum number of code search results (default: 100, GitHub API max per page)
    
    Returns:
        List of repository objects with metadata
    """
    # Construct search query
    org_query = ' '.join([f'org:{org}' for org in orgs])
    query = f'{pattern} {org_query} language:{language}'
    
    encoded_query = urllib.parse.quote(query)
    url = f'https://api.github.com/search/code?q={encoded_query}&per_page={max_results}'
    
    # Create request with headers
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'openshift-pattern-analyzer/1.0'
    }
    
    # Add GitHub token if available (increases rate limit)
    github_token = os.environ.get('GITHUB_TOKEN')
    if github_token:
        headers['Authorization'] = f'token {github_token}'
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            return data.get('items', [])
    except urllib.error.HTTPError as e:
        if e.code == 403:
            error_body = e.read().decode()
            if 'rate limit' in error_body.lower():
                print("ERROR: GitHub API rate limit exceeded", file=sys.stderr)
                print("Set GITHUB_TOKEN environment variable to increase limit", file=sys.stderr)
                print("Create token at: https://github.com/settings/tokens", file=sys.stderr)
            else:
                print(f"ERROR: GitHub API returned 403: {error_body}", file=sys.stderr)
        else:
            print(f"ERROR: GitHub API request failed: {e}", file=sys.stderr)
        sys.exit(2)
    except urllib.error.URLError as e:
        print(f"ERROR: Network error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def get_repo_details(repo_full_name):
    """
    Get detailed repository information from GitHub API.
    
    Args:
        repo_full_name: Full repository name (e.g., "openshift/cluster-network-operator")
    
    Returns:
        Repository details dict
    """
    url = f'https://api.github.com/repos/{repo_full_name}'
    
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'openshift-pattern-analyzer/1.0'
    }
    
    github_token = os.environ.get('GITHUB_TOKEN')
    if github_token:
        headers['Authorization'] = f'token {github_token}'
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"WARNING: Failed to get details for {repo_full_name}: {e}", file=sys.stderr)
        return None


def score_repository(repo_details, match_count):
    """
    Score repository based on quality signals.
    
    Args:
        repo_details: Repository details from GitHub API
        match_count: Number of times pattern appears in repo
    
    Returns:
        Quality score (float)
    """
    if not repo_details:
        return 0.0
    
    score = 0.0
    
    # Stars (popularity/quality signal) - max 5 points
    stars = repo_details.get('stargazers_count', 0)
    score += min(stars / 10, 5.0)
    
    # Recent activity - max 3 points
    updated_at = repo_details.get('updated_at', '')
    if updated_at:
        try:
            updated_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            days_old = (datetime.now(updated_date.tzinfo) - updated_date).days
            if days_old < 30:
                score += 3.0
            elif days_old < 90:
                score += 2.0
            elif days_old < 180:
                score += 1.0
        except:
            pass
    
    # OpenShift org (trusted source) - 5 points
    if repo_details.get('owner', {}).get('login') == 'openshift':
        score += 5.0
    
    # Kubernetes org (trusted source) - 4 points
    elif repo_details.get('owner', {}).get('login') == 'kubernetes':
        score += 4.0
    
    # Not archived - 2 points
    if not repo_details.get('archived', False):
        score += 2.0
    else:
        score = 0.0  # Archived repos are not useful
    
    # Not a fork (prefer originals) - 1 point
    if not repo_details.get('fork', False):
        score += 1.0
    
    # Match count relevance - max 3 points
    score += min(match_count / 5, 3.0)
    
    return score


def filter_and_rank_repos(search_results, max_repos=7):
    """
    Filter and rank repositories by quality.
    
    Args:
        search_results: List of code search results from GitHub
        max_repos: Maximum number of repos to return
    
    Returns:
        List of top-ranked repositories with metadata
    """
    # Group by repository and count matches
    repo_matches = {}
    for item in search_results:
        repo = item.get('repository', {})
        repo_full_name = repo.get('full_name')
        
        if not repo_full_name:
            continue
        
        if repo_full_name not in repo_matches:
            repo_matches[repo_full_name] = {
                'repo': repo,
                'match_count': 0
            }
        repo_matches[repo_full_name]['match_count'] += 1
    
    # Get detailed info and score each repo
    scored_repos = []
    for repo_full_name, data in repo_matches.items():
        print(f"  Analyzing {repo_full_name}...", end=' ', file=sys.stderr)
        
        # Get detailed repo info
        repo_details = get_repo_details(repo_full_name)
        
        if not repo_details:
            print("✗ (failed to fetch)", file=sys.stderr)
            continue
        
        # Calculate score
        score = score_repository(repo_details, data['match_count'])
        
        # Skip archived or very low quality repos
        if score < 1.0:
            print(f"✗ (score too low: {score:.1f})", file=sys.stderr)
            continue
        
        print(f"✓ (score: {score:.1f})", file=sys.stderr)
        
        scored_repos.append({
            'name': repo_details['name'],
            'org': repo_details['owner']['login'],
            'full_name': repo_full_name,
            'url': repo_details['html_url'],
            'clone_url': repo_details['clone_url'],
            'stars': repo_details['stargazers_count'],
            'last_updated': repo_details['updated_at'],
            'language': repo_details.get('language', 'Unknown'),
            'archived': repo_details.get('archived', False),
            'fork': repo_details.get('fork', False),
            'description': repo_details.get('description', ''),
            'match_count': data['match_count'],
            'relevance_score': round(score, 2)
        })
    
    # Sort by score descending
    scored_repos.sort(key=lambda x: x['relevance_score'], reverse=True)
    
    # Return top N
    return scored_repos[:max_repos]


def main():
    parser = argparse.ArgumentParser(
        description='Search GitHub for repositories implementing a design pattern'
    )
    parser.add_argument('--pattern', required=True, help='Pattern name (e.g., NetworkPolicy)')
    parser.add_argument('--orgs', required=True, help='Comma-separated list of GitHub orgs')
    parser.add_argument('--max-repos', type=int, default=50, help='Maximum repos to return (default: 50)')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Parse orgs
    orgs = [org.strip() for org in args.orgs.split(',')]
    
    # Validate
    if not args.pattern:
        print("ERROR: Pattern name is required", file=sys.stderr)
        sys.exit(1)
    
    if args.max_repos < 3 or args.max_repos > 50:
        print("ERROR: --max-repos must be between 3 and 50", file=sys.stderr)
        sys.exit(1)
    
    print(f"Searching GitHub for '{args.pattern}' in {', '.join(orgs)}...", file=sys.stderr)
    
    # Search GitHub
    search_results = search_github(args.pattern, orgs)
    
    if not search_results:
        print(f"ERROR: No repositories found implementing '{args.pattern}'", file=sys.stderr)
        print("Suggestions:", file=sys.stderr)
        print("- Check pattern name spelling", file=sys.stderr)
        print("- Try related patterns", file=sys.stderr)
        print("- Add more orgs with --orgs flag", file=sys.stderr)
        sys.exit(2)
    
    print(f"✓ Found {len(search_results)} code matches", file=sys.stderr)
    print(f"\nFiltering and ranking repositories...", file=sys.stderr)
    
    # Filter and rank
    top_repos = filter_and_rank_repos(search_results, args.max_repos)
    
    if not top_repos:
        print(f"ERROR: No quality repositories found", file=sys.stderr)
        sys.exit(2)
    
    print(f"\n✓ Selected top {len(top_repos)} repositories:\n", file=sys.stderr)
    for i, repo in enumerate(top_repos, 1):
        print(f"  {i}. {repo['full_name']} (⭐ {repo['stars']}, score: {repo['relevance_score']})", file=sys.stderr)
    
    # Prepare output
    output = {
        'pattern': args.pattern,
        'search_date': datetime.now().isoformat(),
        'orgs': orgs,
        'repos_found': len(search_results),
        'repos_selected': len(top_repos),
        'repos': top_repos
    }
    
    # Write to file
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Results saved to {args.output}", file=sys.stderr)


if __name__ == '__main__':
    main()

