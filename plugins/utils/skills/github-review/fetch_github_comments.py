#!/usr/bin/env python3
"""
Fetch review comments from a GitHub pull request.

This script retrieves all review comments, issue comments, and reviews from a
GitHub pull request and outputs them in a plain text format suitable for AI
agents to process and address.

Usage:
    python fetch_github_comments.py <pr_url_or_number> [--repo owner/repo]
    python fetch_github_comments.py https://github.com/example-org/example-repo/pull/123
    python fetch_github_comments.py 123 --repo example-org/example-repo

Requires:
    - gh CLI installed and authenticated (https://cli.github.com/)
"""

import argparse
import json
import re
import subprocess
import sys
from typing import Optional


def run_gh_command(args: list[str]) -> tuple[str, int]:
    """Run a gh CLI command and return output and exit code."""
    try:
        result = subprocess.run(
            ['gh'] + args,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout.strip(), result.returncode
    except FileNotFoundError:
        print("Error: 'gh' CLI not found. Install from https://cli.github.com/", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Error: gh command timed out", file=sys.stderr)
        sys.exit(1)


def parse_github_url(url: str) -> tuple[str, str, int]:
    """
    Parse a GitHub PR URL to extract owner, repo, and PR number.

    Supports formats:
    - https://github.com/owner/repo/pull/123
    - github.com/owner/repo/pull/123
    - owner/repo#123

    Returns:
        Tuple of (owner, repo, pr_number)
    """
    # Full URL pattern
    url_match = re.match(
        r'^(?:https?://)?github\.com/([^/]+)/([^/]+)/pull/(\d+)',
        url
    )
    if url_match:
        return url_match.group(1), url_match.group(2), int(url_match.group(3))

    # Short format: owner/repo#123
    short_match = re.match(r'^([^/]+)/([^#]+)#(\d+)$', url)
    if short_match:
        return short_match.group(1), short_match.group(2), int(short_match.group(3))

    raise ValueError(f"Could not parse GitHub PR URL: {url}")


def get_current_repo() -> Optional[tuple[str, str]]:
    """Get the current repository from git remote."""
    output, code = run_gh_command(['repo', 'view', '--json', 'owner,name'])
    if code != 0:
        return None
    try:
        data = json.loads(output)
        return data.get('owner', {}).get('login'), data.get('name')
    except json.JSONDecodeError:
        return None


def fetch_pr_details(owner: str, repo: str, pr_number: int) -> dict:
    """Fetch PR metadata."""
    output, code = run_gh_command([
        'api', f'repos/{owner}/{repo}/pulls/{pr_number}',
        '--jq', '''{
            number,
            title,
            state,
            user: .user.login,
            head: .head.ref,
            base: .base.ref,
            html_url,
            created_at,
            updated_at
        }'''
    ])
    if code != 0:
        raise RuntimeError(f"Failed to fetch PR details: {output}")
    return json.loads(output)


def fetch_issue_comments(owner: str, repo: str, pr_number: int) -> list[dict]:
    """Fetch issue comments (general PR conversation)."""
    output, code = run_gh_command([
        'api', f'repos/{owner}/{repo}/issues/{pr_number}/comments',
        '--paginate',
        '--jq', '''[.[] | {
            id,
            author: .user.login,
            body,
            created_at,
            updated_at,
            url: .html_url,
            type: "issue_comment"
        }]'''
    ])
    if code != 0:
        return []
    try:
        # Handle paginated output (multiple JSON arrays)
        comments = []
        for line in output.strip().split('\n'):
            if line:
                comments.extend(json.loads(line))
        return comments
    except json.JSONDecodeError:
        return []


def fetch_reviews(owner: str, repo: str, pr_number: int) -> list[dict]:
    """Fetch review submissions."""
    output, code = run_gh_command([
        'api', f'repos/{owner}/{repo}/pulls/{pr_number}/reviews',
        '--paginate',
        '--jq', '''[.[] | {
            id,
            author: .user.login,
            body,
            state,
            submitted_at,
            url: .html_url,
            type: "review"
        }]'''
    ])
    if code != 0:
        return []
    try:
        reviews = []
        for line in output.strip().split('\n'):
            if line:
                reviews.extend(json.loads(line))
        return reviews
    except json.JSONDecodeError:
        return []


def fetch_review_comments(owner: str, repo: str, pr_number: int) -> list[dict]:
    """Fetch inline review comments."""
    output, code = run_gh_command([
        'api', f'repos/{owner}/{repo}/pulls/{pr_number}/comments',
        '--paginate',
        '--jq', '''[.[] | {
            id,
            author: .user.login,
            body,
            path,
            line: .line,
            original_line: .original_line,
            diff_hunk,
            created_at,
            updated_at,
            url: .html_url,
            in_reply_to_id,
            type: "review_comment"
        }]'''
    ])
    if code != 0:
        return []
    try:
        comments = []
        for line in output.strip().split('\n'):
            if line:
                comments.extend(json.loads(line))
        return comments
    except json.JSONDecodeError:
        return []


def is_bot_author(author: str) -> bool:
    """Check if the author is a known bot."""
    bots = [
        'openshift-ci-robot',
        'openshift-ci',
        'openshift-bot',
        'metal3-io-bot',
        'github-actions',
        'dependabot',
        'renovate',
        'codecov',
        'sonarcloud',
        'netlify',
        'vercel',
    ]
    author_lower = author.lower()
    return any(bot in author_lower for bot in bots) or author_lower.endswith('[bot]')


def is_outdated_comment(comment: dict) -> bool:
    """Check if a review comment is outdated (no longer on current diff)."""
    if comment.get('type') != 'review_comment':
        return False
    # If line is None but original_line exists, comment is on outdated code
    return comment.get('line') is None and comment.get('original_line') is not None


def format_comment(comment: dict, show_outdated: bool = False) -> Optional[str]:
    """Format a single comment for output."""
    author = comment.get('author', 'Unknown')
    body = comment.get('body', '').strip()
    comment_type = comment.get('type', 'unknown')

    # Skip empty bodies (except for reviews which may just be approvals)
    if not body and comment_type != 'review':
        return None

    # Build location string
    if comment_type == 'review_comment':
        path = comment.get('path', 'unknown')
        line = comment.get('line') or comment.get('original_line')
        outdated = is_outdated_comment(comment)

        if outdated and not show_outdated:
            return None

        outdated_marker = " (OUTDATED)" if outdated else ""
        if line:
            location = f"[{path}:{line}]{outdated_marker}"
        else:
            location = f"[{path}]{outdated_marker}"
    elif comment_type == 'review':
        state = comment.get('state', 'COMMENTED')
        location = f"[Review - {state}]"
        # Skip empty review bodies (just state changes)
        if not body:
            return None
    else:
        location = "[PR Comment]"

    # Timestamp
    timestamp = comment.get('created_at') or comment.get('submitted_at', 'Unknown')

    return f"""
---
Author: {author}
Location: {location}
Time: {timestamp}

{body}
"""


def format_output(
    pr_details: dict,
    issue_comments: list[dict],
    reviews: list[dict],
    review_comments: list[dict],
    filter_bots: bool = True,
    filter_outdated: bool = True,
    unresolved_only: bool = False
) -> str:
    """Format all comments into a readable output."""
    output_lines = []

    # Header with PR info
    pr_number = pr_details.get('number', 'Unknown')
    title = pr_details.get('title', 'Unknown')
    state = pr_details.get('state', 'Unknown')
    author = pr_details.get('user', 'Unknown')
    head = pr_details.get('head', 'Unknown')
    base = pr_details.get('base', 'Unknown')
    url = pr_details.get('html_url', '')

    output_lines.append("=" * 70)
    output_lines.append(f"GITHUB PULL REQUEST: #{pr_number}")
    output_lines.append(f"Title: {title}")
    output_lines.append(f"State: {state}")
    output_lines.append(f"Author: {author}")
    output_lines.append(f"Branch: {head} → {base}")
    output_lines.append(f"URL: {url}")
    output_lines.append("=" * 70)

    # Combine and filter comments
    all_comments = []
    filtered_stats = {'bots': 0, 'outdated': 0, 'empty': 0}

    for comment in issue_comments + reviews + review_comments:
        author = comment.get('author', '')

        # Filter bots
        if filter_bots and is_bot_author(author):
            filtered_stats['bots'] += 1
            continue

        # Filter outdated
        if filter_outdated and is_outdated_comment(comment):
            filtered_stats['outdated'] += 1
            continue

        all_comments.append(comment)

    # Sort by timestamp
    def get_timestamp(c):
        ts = c.get('created_at') or c.get('submitted_at') or ''
        return ts

    all_comments.sort(key=get_timestamp)

    # Statistics
    total_raw = len(issue_comments) + len(reviews) + len(review_comments)
    total_filtered = len(all_comments)

    output_lines.append(f"\nTotal comments: {total_filtered} (of {total_raw} raw)")
    if filtered_stats['bots'] > 0:
        output_lines.append(f"  - Filtered bot comments: {filtered_stats['bots']}")
    if filtered_stats['outdated'] > 0:
        output_lines.append(f"  - Filtered outdated comments: {filtered_stats['outdated']}")

    # Group by type
    pr_comments = [c for c in all_comments if c.get('type') == 'issue_comment']
    review_submissions = [c for c in all_comments if c.get('type') == 'review']
    inline_comments = [c for c in all_comments if c.get('type') == 'review_comment']

    output_lines.append(f"\n  - PR conversation comments: {len(pr_comments)}")
    output_lines.append(f"  - Review submissions: {len(review_submissions)}")
    output_lines.append(f"  - Inline code comments: {len(inline_comments)}")

    if not all_comments:
        output_lines.append("\nNo comments found on this pull request.")
        return '\n'.join(output_lines)

    output_lines.append("\n" + "=" * 70)
    output_lines.append("COMMENTS")
    output_lines.append("=" * 70)

    # Group inline comments by file
    comments_by_file: dict[str, list[dict]] = {}
    other_comments: list[dict] = []

    for comment in all_comments:
        if comment.get('type') == 'review_comment':
            path = comment.get('path', 'unknown')
            if path not in comments_by_file:
                comments_by_file[path] = []
            comments_by_file[path].append(comment)
        else:
            other_comments.append(comment)

    # Output PR-level comments first
    if other_comments:
        output_lines.append("\n### PR-LEVEL COMMENTS ###")
        for comment in other_comments:
            formatted = format_comment(comment, show_outdated=not filter_outdated)
            if formatted:
                output_lines.append(formatted)

    # Output inline comments by file
    for path in sorted(comments_by_file.keys()):
        file_comments = comments_by_file[path]
        # Sort by line number
        file_comments.sort(key=lambda c: c.get('line') or c.get('original_line') or 0)

        output_lines.append(f"\n### FILE: {path} ###")
        for comment in file_comments:
            formatted = format_comment(comment, show_outdated=not filter_outdated)
            if formatted:
                output_lines.append(formatted)

    # Footer with action items
    output_lines.append("\n" + "=" * 70)
    output_lines.append("ACTION ITEMS")
    output_lines.append("=" * 70)

    # Count actionable comments (inline with line numbers)
    actionable = [c for c in inline_comments if c.get('line') is not None]
    if actionable:
        output_lines.append(f"\n{len(actionable)} inline comment(s) on current code require attention.")
        output_lines.append("Review each comment above and address the feedback.")
    else:
        output_lines.append("\nNo inline comments on current code.")
        if pr_comments or review_submissions:
            output_lines.append("Review PR-level comments above for any action items.")

    return '\n'.join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch review comments from a GitHub pull request.',
        epilog='Example: %(prog)s https://github.com/example-org/example-repo/pull/123'
    )
    parser.add_argument(
        'pr',
        help='PR URL, number, or owner/repo#number'
    )
    parser.add_argument(
        '-r', '--repo',
        help='Repository in owner/repo format (auto-detected if in a git repo)'
    )
    parser.add_argument(
        '--include-bots',
        action='store_true',
        help='Include comments from bots (filtered by default)'
    )
    parser.add_argument(
        '--include-outdated',
        action='store_true',
        help='Include outdated comments (filtered by default)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        dest='output_json',
        help='Output raw JSON instead of formatted text'
    )

    args = parser.parse_args()

    try:
        # Parse PR reference
        if args.pr.startswith('http') or 'github.com' in args.pr:
            owner, repo, pr_number = parse_github_url(args.pr)
        elif '#' in args.pr:
            owner, repo, pr_number = parse_github_url(args.pr)
        elif args.pr.isdigit():
            pr_number = int(args.pr)
            if args.repo:
                parts = args.repo.split('/')
                if len(parts) != 2:
                    raise ValueError("--repo must be in owner/repo format")
                owner, repo = parts
            else:
                # Try to get from current repo
                repo_info = get_current_repo()
                if not repo_info:
                    raise ValueError("Could not determine repository. Use --repo or provide full URL.")
                owner, repo = repo_info
        else:
            raise ValueError(f"Invalid PR reference: {args.pr}")

        # Fetch all data
        pr_details = fetch_pr_details(owner, repo, pr_number)
        issue_comments = fetch_issue_comments(owner, repo, pr_number)
        reviews = fetch_reviews(owner, repo, pr_number)
        review_comments = fetch_review_comments(owner, repo, pr_number)

        if args.output_json:
            output = {
                'pr': pr_details,
                'issue_comments': issue_comments,
                'reviews': reviews,
                'review_comments': review_comments
            }
            print(json.dumps(output, indent=2))
        else:
            print(format_output(
                pr_details,
                issue_comments,
                reviews,
                review_comments,
                filter_bots=not args.include_bots,
                filter_outdated=not args.include_outdated
            ))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

