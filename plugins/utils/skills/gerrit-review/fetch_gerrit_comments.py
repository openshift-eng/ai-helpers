#!/usr/bin/env python3
"""
Fetch review comments from a Gerrit change.

This script retrieves all inline comments and patchset-level comments from a
Gerrit change and outputs them in a plain text format suitable for AI agents
to process and address.

Usage:
    python fetch_gerrit_comments.py <gerrit_url>
    python fetch_gerrit_comments.py https://review.example.com/c/org/project/+/123456

Supports:
    - Any Gerrit instance with REST API enabled (e.g., review.opendev.org, gerrit.googlesource.com)
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional


def parse_gerrit_url(url: str) -> tuple[str, str, Optional[int]]:
    """
    Parse a Gerrit URL to extract base URL, change ID, and optional patchset.
    
    Supports formats:
    - https://review.example.com/c/org/project/+/123456
    - https://review.example.com/c/org/project/+/123456/1
    - https://review.example.com/#/c/123456/
    - https://review.example.com/123456
    
    Returns:
        Tuple of (base_url, change_id, patchset_number or None)
    """
    # Remove trailing slashes
    url = url.rstrip('/')
    
    # Pattern for new-style URLs: /c/project/+/change_number[/patchset]
    new_style = re.match(
        r'^(https?://[^/]+)/c/([^/]+(?:/[^/]+)*)/\+/(\d+)(?:/(\d+))?',
        url
    )
    if new_style:
        base_url = new_style.group(1)
        project = new_style.group(2)
        change_num = new_style.group(3)
        patchset = new_style.group(4)
        # Gerrit API uses project~change_number format
        change_id = f"{urllib.parse.quote(project, safe='')}~{change_num}"
        return base_url, change_id, int(patchset) if patchset else None
    
    # Pattern for old-style URLs: /#/c/change_number/
    old_style = re.match(r'^(https?://[^/]+)/#/c/(\d+)(?:/(\d+))?', url)
    if old_style:
        base_url = old_style.group(1)
        change_num = old_style.group(2)
        patchset = old_style.group(3)
        return base_url, change_num, int(patchset) if patchset else None
    
    # Pattern for direct change number URLs
    direct = re.match(r'^(https?://[^/]+)/(\d+)(?:/(\d+))?$', url)
    if direct:
        base_url = direct.group(1)
        change_num = direct.group(2)
        patchset = direct.group(3)
        return base_url, change_num, int(patchset) if patchset else None
    
    raise ValueError(f"Could not parse Gerrit URL: {url}")


def fetch_json(url: str) -> dict:
    """Fetch JSON from Gerrit API (handles the )]}' prefix)."""
    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8')
            # Gerrit prefixes JSON with )]}' to prevent XSSI
            if content.startswith(")]}'"):
                content = content[4:].lstrip()
            return json.loads(content)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Change not found: {url}")
        raise RuntimeError(f"HTTP error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def fetch_change_details(base_url: str, change_id: str) -> dict:
    """Fetch change metadata including subject and owner."""
    url = f"{base_url}/changes/{change_id}/detail"
    return fetch_json(url)


def fetch_comments(base_url: str, change_id: str) -> dict:
    """Fetch all comments for a change."""
    url = f"{base_url}/changes/{change_id}/comments"
    return fetch_json(url)


def format_comment(comment: dict, file_path: str, author_cache: dict) -> str:
    """Format a single comment for output."""
    author = comment.get('author', {})
    author_name = author.get('display_name') or author.get('name') or author.get('username', 'Unknown')
    
    # Cache author ID to name mapping
    author_id = author.get('_account_id')
    if author_id:
        author_cache[author_id] = author_name
    
    line = comment.get('line')
    message = comment.get('message', '').strip()
    patch_set = comment.get('patch_set', 'N/A')
    unresolved = comment.get('unresolved', False)
    
    # Build location string
    if file_path == '/PATCHSET_LEVEL':
        location = f"[Patchset {patch_set} - General Comment]"
    elif line:
        location = f"[{file_path}:{line}]"
    else:
        location = f"[{file_path}]"
    
    # Status indicator
    status = " (UNRESOLVED)" if unresolved else ""
    
    return f"""
---
Author: {author_name}{status}
Location: {location}
Patchset: {patch_set}

{message}
"""


def format_output(change_details: dict, comments: dict, patchset_filter: Optional[int] = None) -> str:
    """Format all comments into a readable output."""
    output_lines = []
    
    # Header with change info
    subject = change_details.get('subject', 'Unknown')
    change_num = change_details.get('_number', 'Unknown')
    project = change_details.get('project', 'Unknown')
    branch = change_details.get('branch', 'Unknown')
    status = change_details.get('status', 'Unknown')
    owner = change_details.get('owner', {})
    owner_name = owner.get('display_name') or owner.get('name') or owner.get('username', 'Unknown')
    
    output_lines.append("=" * 70)
    output_lines.append(f"GERRIT CHANGE: {change_num}")
    output_lines.append(f"Project: {project}")
    output_lines.append(f"Branch: {branch}")
    output_lines.append(f"Status: {status}")
    output_lines.append(f"Subject: {subject}")
    output_lines.append(f"Owner: {owner_name}")
    output_lines.append("=" * 70)
    
    # Collect and sort comments
    all_comments = []
    author_cache = {}
    
    for file_path, file_comments in comments.items():
        for comment in file_comments:
            patch_set = comment.get('patch_set', 0)
            # Filter by patchset if specified
            if patchset_filter is not None and patch_set != patchset_filter:
                continue
            all_comments.append((file_path, comment))
    
    if not all_comments:
        if patchset_filter:
            output_lines.append(f"\nNo comments found for patchset {patchset_filter}.")
        else:
            output_lines.append("\nNo comments found on this change.")
        return '\n'.join(output_lines)
    
    # Sort: patchset-level first, then by file, then by line
    def sort_key(item):
        file_path, comment = item
        is_patchset_level = 0 if file_path == '/PATCHSET_LEVEL' else 1
        line = comment.get('line', 0) or 0
        return (is_patchset_level, file_path, line)
    
    all_comments.sort(key=sort_key)
    
    # Statistics
    unresolved_count = sum(1 for _, c in all_comments if c.get('unresolved', False))
    resolved_count = len(all_comments) - unresolved_count
    
    output_lines.append(f"\nTotal comments: {len(all_comments)}")
    output_lines.append(f"  - Unresolved: {unresolved_count}")
    output_lines.append(f"  - Resolved: {resolved_count}")
    
    if patchset_filter:
        output_lines.append(f"  - Showing patchset: {patchset_filter}")
    else:
        # Show which patchsets have comments
        patchsets = sorted(set(c.get('patch_set', 0) for _, c in all_comments))
        output_lines.append(f"  - Patchsets with comments: {', '.join(map(str, patchsets))}")
    
    output_lines.append("\n" + "=" * 70)
    output_lines.append("COMMENTS")
    output_lines.append("=" * 70)
    
    # Output comments
    current_file = None
    for file_path, comment in all_comments:
        # Add file header when switching files
        if file_path != current_file:
            current_file = file_path
            if file_path == '/PATCHSET_LEVEL':
                output_lines.append("\n### PATCHSET-LEVEL COMMENTS ###")
            else:
                output_lines.append(f"\n### FILE: {file_path} ###")
        
        output_lines.append(format_comment(comment, file_path, author_cache))
    
    # Footer with actionable summary
    output_lines.append("\n" + "=" * 70)
    output_lines.append("ACTION ITEMS")
    output_lines.append("=" * 70)
    
    if unresolved_count > 0:
        output_lines.append(f"\n{unresolved_count} unresolved comment(s) require attention.")
        output_lines.append("Review each unresolved comment above and address the feedback.")
    else:
        output_lines.append("\nAll comments have been resolved.")
    
    return '\n'.join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch review comments from a Gerrit change.',
        epilog='Example: %(prog)s https://review.example.com/c/org/project/+/123456'
    )
    parser.add_argument(
        'url',
        help='Gerrit change URL'
    )
    parser.add_argument(
        '-p', '--patchset',
        type=int,
        help='Filter comments to a specific patchset number'
    )
    parser.add_argument(
        '--unresolved-only',
        action='store_true',
        help='Show only unresolved comments'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        dest='output_json',
        help='Output raw JSON instead of formatted text'
    )
    
    args = parser.parse_args()
    
    try:
        # Parse the URL
        base_url, change_id, url_patchset = parse_gerrit_url(args.url)
        
        # Use patchset from URL if not specified via argument
        patchset = args.patchset or url_patchset
        
        # Fetch data
        change_details = fetch_change_details(base_url, change_id)
        comments = fetch_comments(base_url, change_id)
        
        # Filter unresolved if requested
        if args.unresolved_only:
            filtered_comments = {}
            for file_path, file_comments in comments.items():
                unresolved = [c for c in file_comments if c.get('unresolved', False)]
                if unresolved:
                    filtered_comments[file_path] = unresolved
            comments = filtered_comments
        
        if args.output_json:
            output = {
                'change': change_details,
                'comments': comments
            }
            print(json.dumps(output, indent=2))
        else:
            print(format_output(change_details, comments, patchset))
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

