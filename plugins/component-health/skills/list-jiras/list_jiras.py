#!/usr/bin/env python3
"""
JIRA Bug Query Script

This script queries JIRA bugs for a specified project and returns raw issue data.
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
from datetime import datetime, timedelta


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

    # Calculate date for 30 days ago
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    # Add status filter - include recently closed bugs (within last 30 days) or open bugs
    if statuses:
        # If specific statuses are requested, use them
        status_list = ', '.join(f'"{s}"' for s in statuses)
        parts.append(f'status IN ({status_list})')
    elif not include_closed:
        # Default: open bugs OR bugs closed in the last 30 days
        parts.append(f'(status != Closed OR (status = Closed AND resolved >= "{thirty_days_ago}"))')
    # If include_closed is True, get all bugs (no status filter)

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

    # Build query parameters - Note: fields should be comma-separated without URL encoding the commas
    fields_list = [
        'summary', 'status', 'priority', 'components', 'assignee',
        'created', 'updated', 'resolutiondate',
        'versions',  # Affects Version/s
        'fixVersions',  # Fix Version/s
        'customfield_12319940'  # Target Version
    ]

    params = {
        'jql': jql,
        'maxResults': max_results,
        'fields': ','.join(fields_list)
    }

    # Encode parameters - but don't encode commas in fields parameter
    encoded_params = []
    for k, v in params.items():
        if k == 'fields':
            # Don't encode commas in fields list
            encoded_params.append(f'{k}={v}')
        else:
            encoded_params.append(f'{k}={urllib.parse.quote(str(v))}')

    query_string = '&'.join(encoded_params)
    full_url = f"{api_url}?{query_string}"

    # Create request with bearer token authentication
    request = urllib.request.Request(full_url)
    request.add_header('Authorization', f'Bearer {token}')
    # Note: Don't add Content-Type for GET requests

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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Query JIRA bugs and return raw issue data',
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
        help='Maximum number of issues to fetch per component (default: 100, max: 1000)'
    )

    args = parser.parse_args()

    # Validate limit
    if args.limit < 1 or args.limit > 1000:
        print("Error: --limit must be between 1 and 1000", file=sys.stderr)
        sys.exit(1)

    # Get environment variables
    jira_url = get_env_var('JIRA_URL').rstrip('/')
    token = get_env_var('JIRA_PERSONAL_TOKEN')

    # If multiple components are provided, warn user and iterate through them
    if args.component and len(args.component) > 1:
        print(f"\nQuerying {len(args.component)} components individually...", file=sys.stderr)
        print("This may take a few seconds.", file=sys.stderr)
        print(f"Components: {', '.join(args.component)}\n", file=sys.stderr)

        # Initialize aggregated results
        all_issues = []
        all_total_count = 0
        component_queries = []

        # Iterate through each component
        for idx, component in enumerate(args.component, 1):
            print(f"[{idx}/{len(args.component)}] Querying component: {component}...", file=sys.stderr)

            # Build JQL query for this component
            jql = build_jql_query(
                project=args.project,
                components=[component],
                statuses=args.status,
                include_closed=args.include_closed
            )

            # Fetch issues for this component
            response = fetch_jira_issues(jira_url, token, jql, args.limit)

            # Aggregate results
            component_issues = response.get('issues', [])
            component_total = response.get('total', 0)

            all_issues.extend(component_issues)
            all_total_count += component_total
            component_queries.append(f"{component}: {jql}")

            print(f"  Found {len(component_issues)} of {component_total} total issues for {component}",
                  file=sys.stderr)

        print(f"\nTotal issues fetched: {len(all_issues)} (from {all_total_count} total across all components)\n",
              file=sys.stderr)

        # Build combined JQL query string for output (informational only)
        combined_jql = build_jql_query(
            project=args.project,
            components=args.component,
            statuses=args.status,
            include_closed=args.include_closed
        )

        # Build output with aggregated data
        output = {
            'project': args.project,
            'total_count': all_total_count,
            'fetched_count': len(all_issues),
            'query': combined_jql,
            'component_queries': component_queries,
            'filters': {
                'components': args.component,
                'statuses': args.status,
                'include_closed': args.include_closed,
                'limit': args.limit
            },
            'issues': all_issues
        }

        # Add note if results are truncated
        if len(all_issues) < all_total_count:
            output['note'] = (
                f"Showing {len(all_issues)} of {all_total_count} total results across {len(args.component)} components. "
                f"Increase --limit to fetch more per component."
            )
    else:
        # Single component or no component filter - use original logic
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

        # Build output with metadata and raw issues
        output = {
            'project': args.project,
            'total_count': total_count,
            'fetched_count': fetched_count,
            'query': jql,
            'filters': {
                'components': args.component,
                'statuses': args.status,
                'include_closed': args.include_closed,
                'limit': args.limit
            },
            'issues': issues
        }

        # Add note if results are truncated
        if fetched_count < total_count:
            output['note'] = (
                f"Showing first {fetched_count} of {total_count} total results. "
                f"Increase --limit for more data."
            )

    # Output JSON to stdout
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
