#!/usr/bin/env python3
"""
Git Blame Analysis Helper for suggest-reviewers command.

This script helps identify the authors of code lines being modified in a PR,
aggregating git blame data to suggest the most relevant reviewers.

Usage:
    python analyze_blame.py --mode <uncommitted|committed> --file <filepath> [--base-branch <branch>]

Modes:
    uncommitted: Analyze uncommitted changes (compares against HEAD)
    committed:   Analyze committed changes on feature branch (compares against base branch)
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple, Optional


class BlameAnalyzer:
    """Analyzes git blame for changed lines in files."""

    # Bot patterns to filter out
    BOT_PATTERNS = [
        r'.*\[bot\]',
        r'openshift-bot',
        r'k8s-ci-robot',
        r'openshift-merge-robot',
        r'openshift-ci\[bot\]',
        r'dependabot',
        r'renovate\[bot\]',
    ]

    def __init__(self, mode: str, base_branch: Optional[str] = None):
        """
        Initialize the analyzer.

        Args:
            mode: 'uncommitted' or 'committed'
            base_branch: Base branch for committed mode (e.g., 'main')
        """
        self.mode = mode
        self.base_branch = base_branch
        self.authors = defaultdict(lambda: {
            'line_count': 0,
            'most_recent_date': None,
            'files': set(),
            'email': None
        })

        if mode == 'committed' and not base_branch:
            raise ValueError("base_branch required for 'committed' mode")

        # Get current user to exclude from suggestions
        self.current_user_name = self._get_git_config('user.name')
        self.current_user_email = self._get_git_config('user.email')

    def _get_git_config(self, key: str) -> Optional[str]:
        """Get a git config value."""
        try:
            result = subprocess.run(
                ['git', 'config', '--get', key],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def is_bot(self, author: str) -> bool:
        """Check if an author name matches bot patterns."""
        for pattern in self.BOT_PATTERNS:
            if re.match(pattern, author, re.IGNORECASE):
                return True
        return False

    def is_current_user(self, author: str, email: Optional[str]) -> bool:
        """Check if the author is the current user."""
        if self.current_user_name and author == self.current_user_name:
            return True
        if self.current_user_email and email and email == self.current_user_email:
            return True
        return False

    def parse_diff_ranges(self, file_path: str) -> List[Tuple[int, int]]:
        """
        Parse git diff output to extract changed line ranges.

        Returns:
            List of (start_line, line_count) tuples for changed ranges
        """
        ranges = []

        try:
            if self.mode == 'uncommitted':
                # Check staged changes
                diff_cmd = ['git', 'diff', '--cached', '--unified=0', file_path]
                result = subprocess.run(diff_cmd, capture_output=True, text=True, check=False)
                ranges.extend(self._extract_ranges_from_diff(result.stdout))

                # Check unstaged changes
                diff_cmd = ['git', 'diff', 'HEAD', '--unified=0', file_path]
                result = subprocess.run(diff_cmd, capture_output=True, text=True, check=False)
                ranges.extend(self._extract_ranges_from_diff(result.stdout))
            else:
                # Committed changes: compare against base branch
                diff_cmd = ['git', 'diff', f'{self.base_branch}...HEAD', '--unified=0', file_path]
                result = subprocess.run(diff_cmd, capture_output=True, text=True, check=True)
                ranges.extend(self._extract_ranges_from_diff(result.stdout))

        except subprocess.CalledProcessError as e:
            print(f"Error running diff for {file_path}: {e}", file=sys.stderr)
            return []

        # Deduplicate and merge overlapping ranges
        return self._merge_ranges(ranges)

    def _extract_ranges_from_diff(self, diff_output: str) -> List[Tuple[int, int]]:
        """
        Extract line ranges from diff @@ markers.

        Diff format: @@ -old_start,old_count +new_start,new_count @@
        We want the 'old' ranges (lines being replaced/modified in the base)

        For pure additions (count=0), we analyze context lines before the insertion
        point to find relevant code owners.
        """
        ranges = []
        # Match @@ -start[,count] +start[,count] @@
        pattern = r'^@@\s+-(\d+)(?:,(\d+))?\s+\+\d+(?:,\d+)?\s+@@'

        for line in diff_output.split('\n'):
            match = re.match(pattern, line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2)) if match.group(2) else 1

                if start > 0:
                    if count > 0:
                        # Regular modification/deletion
                        ranges.append((start, count))
                    else:
                        # Pure addition (count=0): analyze context before insertion
                        # Look at up to 5 lines before the insertion point
                        context_start = max(1, start - 5)
                        context_count = start - context_start
                        if context_count > 0:
                            ranges.append((context_start, context_count))

        return ranges

    def _merge_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Merge overlapping line ranges."""
        if not ranges:
            return []

        # Sort by start line
        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        merged = [sorted_ranges[0]]

        for start, count in sorted_ranges[1:]:
            last_start, last_count = merged[-1]
            last_end = last_start + last_count - 1
            current_end = start + count - 1

            # Check if ranges overlap or are adjacent
            if start <= last_end + 1:
                # Merge ranges
                new_end = max(last_end, current_end)
                new_count = new_end - last_start + 1
                merged[-1] = (last_start, new_count)
            else:
                merged.append((start, count))

        return merged

    def analyze_file(self, file_path: str) -> None:
        """
        Analyze git blame for a specific file.

        Args:
            file_path: Path to file relative to repo root
        """
        # Get changed line ranges
        ranges = self.parse_diff_ranges(file_path)

        if not ranges:
            return

        # Determine which revision to blame
        if self.mode == 'uncommitted':
            blame_target = 'HEAD'
        else:
            blame_target = self.base_branch

        # Run git blame on each range
        for start, count in ranges:
            end = start + count - 1
            self._blame_range(file_path, start, end, blame_target)

    def _blame_range(self, file_path: str, start: int, end: int, revision: str) -> None:
        """
        Run git blame on a specific line range and extract author data.

        Args:
            file_path: File to blame
            start: Start line number
            end: End line number
            revision: Git revision to blame (e.g., 'HEAD', 'main')
        """
        try:
            # Use porcelain format for easier parsing
            blame_cmd = [
                'git', 'blame',
                '--porcelain',
                '-L', f'{start},{end}',
                revision,
                '--',
                file_path
            ]

            result = subprocess.run(blame_cmd, capture_output=True, text=True, check=True)
            self._parse_blame_output(result.stdout, file_path)

        except subprocess.CalledProcessError as e:
            print(f"Error running blame on {file_path}:{start}-{end}: {e}", file=sys.stderr)

    def _parse_blame_output(self, blame_output: str, file_path: str) -> None:
        """
        Parse git blame --porcelain output and aggregate author data.

        Porcelain format:
            <commit-hash> <original-line> <final-line> <num-lines>
            author <author-name>
            author-mail <email>
            author-time <unix-timestamp>
            ...
            \t<line-content>
        """
        lines = blame_output.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if this is a commit header line
            if line and not line.startswith('\t'):
                parts = line.split()
                if len(parts) >= 4 and len(parts[0]) == 40:  # Looks like a SHA
                    # Parse commit metadata
                    author = None
                    email = None
                    timestamp = None

                    # Look ahead for author info
                    j = i + 1
                    while j < len(lines) and not lines[j].startswith('\t'):
                        if lines[j].startswith('author '):
                            author = lines[j][7:]  # Remove 'author ' prefix
                        elif lines[j].startswith('author-mail '):
                            email = lines[j][12:].strip('<>')  # Remove 'author-mail ' and <>
                        elif lines[j].startswith('author-time '):
                            timestamp = int(lines[j][12:])
                        j += 1

                    # Update author data (exclude bots and current user)
                    if author and not self.is_bot(author) and not self.is_current_user(author, email):
                        author_date = datetime.fromtimestamp(timestamp) if timestamp else None

                        self.authors[author]['line_count'] += 1
                        self.authors[author]['files'].add(file_path)
                        self.authors[author]['email'] = email

                        # Track most recent contribution
                        if author_date:
                            current_recent = self.authors[author]['most_recent_date']
                            if current_recent is None or author_date > current_recent:
                                self.authors[author]['most_recent_date'] = author_date

                    i = j
                    continue

            i += 1

    def get_results(self) -> Dict:
        """
        Get aggregated results as a dictionary.

        Returns:
            Dictionary mapping author names to their statistics
        """
        results = {}

        for author, data in self.authors.items():
            results[author] = {
                'line_count': data['line_count'],
                'most_recent_date': data['most_recent_date'].isoformat() if data['most_recent_date'] else None,
                'files': sorted(list(data['files'])),
                'email': data['email']
            }

        return results


def main():
    parser = argparse.ArgumentParser(
        description='Analyze git blame for changed lines to identify code authors'
    )
    parser.add_argument(
        '--mode',
        choices=['uncommitted', 'committed'],
        required=True,
        help='Analysis mode: uncommitted (vs HEAD) or committed (vs base branch)'
    )
    parser.add_argument(
        '--file',
        required=True,
        action='append',
        dest='files',
        help='File(s) to analyze (can be specified multiple times)'
    )
    parser.add_argument(
        '--base-branch',
        help='Base branch for committed mode (e.g., main, master)'
    )
    parser.add_argument(
        '--output',
        choices=['json', 'text'],
        default='json',
        help='Output format (default: json)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.mode == 'committed' and not args.base_branch:
        print("Error: --base-branch required for 'committed' mode", file=sys.stderr)
        sys.exit(1)

    # Analyze files
    analyzer = BlameAnalyzer(mode=args.mode, base_branch=args.base_branch)

    for file_path in args.files:
        analyzer.analyze_file(file_path)

    # Output results
    results = analyzer.get_results()

    if args.output == 'json':
        print(json.dumps(results, indent=2))
    else:
        # Text output
        print(f"\nAuthors of modified code ({len(results)} found):\n")

        # Sort by line count
        sorted_authors = sorted(
            results.items(),
            key=lambda x: x[1]['line_count'],
            reverse=True
        )

        for author, data in sorted_authors:
            print(f"{author} <{data['email']}>")
            print(f"  Lines: {data['line_count']}")
            print(f"  Most recent: {data['most_recent_date'] or 'unknown'}")
            print(f"  Files: {', '.join(data['files'])}")
            print()


if __name__ == '__main__':
    main()
