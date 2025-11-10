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
            
            # Write raw response to file for inspection
            with open('jira_response.json', 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Wrote raw response to jira_response.json", file=sys.stderr)
            
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
        Dictionary containing overall summary and per-component summaries
    """
    # Calculate cutoff date for 30 days ago
    thirty_days_ago = datetime.now() - timedelta(days=30)

    # Overall summary
    overall_summary = {
        'total': 0,
        'opened_last_30_days': 0,
        'closed_last_30_days': 0,
        'by_status': defaultdict(int),
        'by_priority': defaultdict(int),
        'by_component': defaultdict(int)
    }

    # Per-component data
    components_data = defaultdict(lambda: {
        'total': 0,
        'opened_last_30_days': 0,
        'closed_last_30_days': 0,
        'by_status': defaultdict(int),
        'by_priority': defaultdict(int)
    })

    for issue in issues:
        fields = issue.get('fields', {})
        overall_summary['total'] += 1

        # Parse created date
        created_str = fields.get('created')
        if created_str:
            try:
                # JIRA date format: 2024-01-15T10:30:00.000+0000
                created_date = datetime.strptime(created_str[:19], '%Y-%m-%dT%H:%M:%S')
                if created_date >= thirty_days_ago:
                    overall_summary['opened_last_30_days'] += 1
                    is_recently_opened = True
                else:
                    is_recently_opened = False
            except (ValueError, TypeError):
                is_recently_opened = False
        else:
            is_recently_opened = False

        # Parse resolution date (when issue was closed)
        resolution_date_str = fields.get('resolutiondate')
        if resolution_date_str:
            try:
                resolution_date = datetime.strptime(resolution_date_str[:19], '%Y-%m-%dT%H:%M:%S')
                if resolution_date >= thirty_days_ago:
                    overall_summary['closed_last_30_days'] += 1
                    is_recently_closed = True
                else:
                    is_recently_closed = False
            except (ValueError, TypeError):
                is_recently_closed = False
        else:
            is_recently_closed = False

        # Count by status
        status = fields.get('status', {}).get('name', 'Unknown')
        overall_summary['by_status'][status] += 1

        # Count by priority
        priority = fields.get('priority')
        if priority:
            priority_name = priority.get('name', 'Undefined')
        else:
            priority_name = 'Undefined'
        overall_summary['by_priority'][priority_name] += 1

        # Process components (issues can have multiple components)
        components = fields.get('components', [])
        component_names = []

        if components:
            for component in components:
                component_name = component.get('name', 'Unknown')
                component_names.append(component_name)
                overall_summary['by_component'][component_name] += 1
        else:
            component_names = ['No Component']
            overall_summary['by_component']['No Component'] += 1

        # Update per-component statistics
        for component_name in component_names:
            components_data[component_name]['total'] += 1
            components_data[component_name]['by_status'][status] += 1
            components_data[component_name]['by_priority'][priority_name] += 1
            if is_recently_opened:
                components_data[component_name]['opened_last_30_days'] += 1
            if is_recently_closed:
                components_data[component_name]['closed_last_30_days'] += 1

    # Convert defaultdicts to regular dicts and sort
    overall_summary['by_status'] = dict(sorted(
        overall_summary['by_status'].items(),
        key=lambda x: x[1], reverse=True
    ))
    overall_summary['by_priority'] = dict(sorted(
        overall_summary['by_priority'].items(),
        key=lambda x: x[1], reverse=True
    ))
    overall_summary['by_component'] = dict(sorted(
        overall_summary['by_component'].items(),
        key=lambda x: x[1], reverse=True
    ))

    # Convert component data to regular dicts and sort
    components = {}
    for comp_name, comp_data in sorted(components_data.items()):
        components[comp_name] = {
            'total': comp_data['total'],
            'opened_last_30_days': comp_data['opened_last_30_days'],
            'closed_last_30_days': comp_data['closed_last_30_days'],
            'by_status': dict(sorted(
                comp_data['by_status'].items(),
                key=lambda x: x[1], reverse=True
            )),
            'by_priority': dict(sorted(
                comp_data['by_priority'].items(),
                key=lambda x: x[1], reverse=True
            ))
        }

    return {
        'summary': overall_summary,
        'components': components
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

    # Generate summary and component breakdowns
    data = generate_summary(issues)

    # Build output with metadata
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
        'summary': data['summary'],
        'components': data['components']
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
