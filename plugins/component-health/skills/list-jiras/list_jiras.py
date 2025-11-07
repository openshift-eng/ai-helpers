#!/usr/bin/env python3
"""
JIRA Bug Query Script

This script queries JIRA bugs for a specified project and generates summary statistics.
It uses environment variables for authentication and supports filtering by component,
status, and other criteria.

Environment Variables:
    JIRA_URL: Base URL for JIRA instance (e.g., "https://issues.redhat.com")
    JIRA_PERSONAL_TOKEN: Your JIRA API bearer token or personal access token

Usage:
    python3 list_jiras.py --project OCPBUGS
    python3 list_jiras.py --project OCPBUGS --component "kube-apiserver"
    python3 list_jiras.py --project OCPBUGS --status New "In Progress"
    python3 list_jiras.py --project OCPBUGS --include-closed --limit 500
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, List, Dict, Any
from collections import defaultdict


def get_env_var(name: str) -> str:
    """Get required environment variable or exit with error."""
    value = os.environ.get(name)
    if not value:
        print(f"Error: Environment variable {name} is not set", file=sys.stderr)
        print(f"Please set {name} before running this script", file=sys.stderr)
        sys.exit(1)
    return value


def build_jql_query(project: str, components: Optional[List[str]] = None,
                    statuses: Optional[List[str]] = None,
                    include_closed: bool = False) -> str:
    """Build JQL query string from parameters."""
    parts = [f'project = {project}']

    # Add status filter
    if statuses:
        # If specific statuses are requested, use them
        status_list = ', '.join(f'"{s}"' for s in statuses)
        parts.append(f'status IN ({status_list})')
    elif not include_closed:
        # Default: exclude closed bugs
        parts.append('status != Closed')

    # Add component filter
    if components:
        component_list = ', '.join(f'"{c}"' for c in components)
        parts.append(f'component IN ({component_list})')

    return ' AND '.join(parts)


def fetch_jira_issues(jira_url: str, token: str,
                      jql: str, max_results: int = 100) -> Dict[str, Any]:
    """
    Fetch issues from JIRA using JQL query.

    Args:
        jira_url: Base JIRA URL
        token: JIRA bearer token
        jql: JQL query string
        max_results: Maximum number of results to fetch

    Returns:
        Dictionary containing JIRA API response
    """
    # Build API URL
    api_url = f"{jira_url}/rest/api/2/search"

    # Build query parameters
    params = {
        'jql': jql,
        'maxResults': max_results,
        'fields': 'summary,status,priority,components,assignee,created,updated'
    }

    # Encode parameters
    query_string = '&'.join(f'{k}={urllib.parse.quote(str(v))}' for k, v in params.items())
    full_url = f"{api_url}?{query_string}"

    # Create request with bearer token authentication
    request = urllib.request.Request(full_url)
    request.add_header('Authorization', f'Bearer {token}')
    request.add_header('Content-Type', 'application/json')

    print(f"Fetching issues from JIRA...", file=sys.stderr)
    print(f"JQL: {jql}", file=sys.stderr)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode())
            print(f"Fetched {len(data.get('issues', []))} of {data.get('total', 0)} total issues",
                  file=sys.stderr)
            return data
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        try:
            error_body = e.read().decode()
            print(f"Response: {error_body}", file=sys.stderr)
        except:
            pass
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error fetching data: {e}", file=sys.stderr)
        sys.exit(1)


def generate_summary(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate summary statistics from issues.

    Args:
        issues: List of JIRA issue objects

    Returns:
        Dictionary containing summary statistics
    """
    summary = {
        'by_status': defaultdict(int),
        'by_priority': defaultdict(int),
        'by_component': defaultdict(int)
    }

    for issue in issues:
        fields = issue.get('fields', {})

        # Count by status
        status = fields.get('status', {}).get('name', 'Unknown')
        summary['by_status'][status] += 1

        # Count by priority
        priority = fields.get('priority')
        if priority:
            priority_name = priority.get('name', 'Undefined')
        else:
            priority_name = 'Undefined'
        summary['by_priority'][priority_name] += 1

        # Count by component (issues can have multiple components)
        components = fields.get('components', [])
        if components:
            for component in components:
                component_name = component.get('name', 'Unknown')
                summary['by_component'][component_name] += 1
        else:
            summary['by_component']['No Component'] += 1

    # Convert defaultdicts to regular dicts and sort by count (descending)
    return {
        'by_status': dict(sorted(summary['by_status'].items(),
                                key=lambda x: x[1], reverse=True)),
        'by_priority': dict(sorted(summary['by_priority'].items(),
                                  key=lambda x: x[1], reverse=True)),
        'by_component': dict(sorted(summary['by_component'].items(),
                                   key=lambda x: x[1], reverse=True))
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Query JIRA bugs and generate summary statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --project OCPBUGS
  %(prog)s --project OCPBUGS --component "kube-apiserver"
  %(prog)s --project OCPBUGS --component "kube-apiserver" "etcd"
  %(prog)s --project OCPBUGS --status New "In Progress"
  %(prog)s --project OCPBUGS --include-closed --limit 500
        """
    )

    parser.add_argument(
        '--project',
        required=True,
        help='JIRA project key (e.g., OCPBUGS, OCPSTRAT)'
    )

    parser.add_argument(
        '--component',
        nargs='+',
        help='Filter by component names (space-separated)'
    )

    parser.add_argument(
        '--status',
        nargs='+',
        help='Filter by status values (space-separated)'
    )

    parser.add_argument(
        '--include-closed',
        action='store_true',
        help='Include closed bugs in results (default: only open bugs)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of issues to fetch (default: 100, max: 1000)'
    )

    args = parser.parse_args()

    # Validate limit
    if args.limit < 1 or args.limit > 1000:
        print("Error: --limit must be between 1 and 1000", file=sys.stderr)
        sys.exit(1)

    # Get environment variables
    jira_url = get_env_var('JIRA_URL').rstrip('/')
    token = get_env_var('JIRA_PERSONAL_TOKEN')

    # Build JQL query
    jql = build_jql_query(
        project=args.project,
        components=args.component,
        statuses=args.status,
        include_closed=args.include_closed
    )

    # Fetch issues
    response = fetch_jira_issues(jira_url, token, jql, args.limit)

    # Extract data
    issues = response.get('issues', [])
    total_count = response.get('total', 0)
    fetched_count = len(issues)

    # Generate summary
    summary = generate_summary(issues)

    # Build output
    output = {
        'project': args.project,
        'total_count': total_count,
        'query': jql,
        'filters': {
            'components': args.component,
            'statuses': args.status,
            'include_closed': args.include_closed,
            'limit': args.limit
        },
        'summary': summary,
        'fetched_count': fetched_count
    }

    # Add note if results are truncated
    if fetched_count < total_count:
        output['note'] = (
            f"Showing first {fetched_count} of {total_count} total results. "
            f"Increase --limit for more accurate statistics."
        )

    # Output JSON to stdout
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
