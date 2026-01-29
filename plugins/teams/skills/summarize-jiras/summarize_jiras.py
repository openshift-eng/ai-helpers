#!/usr/bin/env python3
"""
JIRA Bug Summarization Script

This script queries JIRA bugs for a specified project and generates summary statistics.
It leverages the list_jiras.py script to fetch raw data, then calculates counts by
status, priority, and component.

Environment Variables:
    JIRA_URL: Base URL for JIRA instance (e.g., "https://issues.redhat.com")
    JIRA_PERSONAL_TOKEN: Your JIRA API bearer token or personal access token

Usage:
    python3 summarize_jiras.py --project OCPBUGS
    python3 summarize_jiras.py --project OCPBUGS --component "kube-apiserver"
    python3 summarize_jiras.py --project OCPBUGS --team "API Server"
    python3 summarize_jiras.py --project OCPBUGS --status New "In Progress"
    python3 summarize_jiras.py --project OCPBUGS --include-closed --limit 500
"""

import argparse
import json
import os
import sys
import subprocess
from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def get_team_components(team_name: str) -> List[str]:
    """
    Get the list of components for a given team from team_component_map.json.

    Args:
        team_name: Name of the team (case-sensitive)

    Returns:
        List of component names for the team

    Raises:
        FileNotFoundError: If the mapping file doesn't exist
        KeyError: If the team is not found in the mapping
        ValueError: If the mapping file is invalid
    """
    # Get path to team_component_map.json (relative to this script)
    script_dir = Path(__file__).parent
    plugin_dir = script_dir.parent.parent
    mapping_path = plugin_dir / "team_component_map.json"

    if not mapping_path.exists():
        raise FileNotFoundError(f"Team component mapping file not found at {mapping_path}")

    try:
        with open(mapping_path, 'r') as f:
            mapping_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse team component mapping file: {e}")

    teams = mapping_data.get("teams", {})

    if team_name not in teams:
        available_teams = sorted(teams.keys())
        raise KeyError(f"Team '{team_name}' not found in mapping. Available teams: {', '.join(available_teams)}")

    return teams[team_name]


def call_list_jiras(project: str, components: List[str] = None,
                    statuses: List[str] = None,
                    include_closed: bool = False,
                    limit: int = 100) -> Dict[str, Any]:
    """
    Call the list_jiras.py script to fetch raw JIRA data.

    Args:
        project: JIRA project key
        components: Optional list of component names to filter by
        statuses: Optional list of status values to filter by
        include_closed: Whether to include closed bugs
        limit: Maximum number of issues to fetch

    Returns:
        Dictionary containing raw JIRA data from list_jiras.py
    """
    # Build command to call list_jiras.py
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'list-jiras',
        'list_jiras.py'
    )

    cmd = ['python3', script_path, '--project', project, '--limit', str(limit)]

    if components:
        cmd.append('--component')
        cmd.extend(components)

    if statuses:
        cmd.append('--status')
        cmd.extend(statuses)

    if include_closed:
        cmd.append('--include-closed')

    print(f"Calling list_jiras.py to fetch raw data...", file=sys.stderr)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300  # 5 minutes to allow for multiple component queries
        )
        # Pass through stderr to show progress messages from list_jiras.py
        if result.stderr:
            print(result.stderr, file=sys.stderr, end='')
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error calling list_jiras.py: {e}", file=sys.stderr)
        if e.stderr:
            print(f"Error output: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"Timeout calling list_jiras.py (exceeded 5 minutes)", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from list_jiras.py: {e}", file=sys.stderr)
        sys.exit(1)


def generate_summary(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate summary statistics from issues.

    Args:
        issues: List of JIRA issue objects

    Returns:
        Dictionary containing overall summary and per-component summaries
    """
    # Calculate cutoff dates
    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)
    ninety_days_ago = now - timedelta(days=90)
    one_eighty_days_ago = now - timedelta(days=180)

    # Overall summary
    overall_summary = {
        'total': 0,
        'opened_last_30_days': 0,
        'closed_last_30_days': 0,
        'by_status': defaultdict(int),
        'by_priority': defaultdict(int),
        'by_component': defaultdict(int),
        'open_bugs_by_age': {
            '0-30d': 0,
            '30-90d': 0,
            '90-180d': 0,
            '>180d': 0
        }
    }

    # Per-component data
    components_data = defaultdict(lambda: {
        'total': 0,
        'opened_last_30_days': 0,
        'closed_last_30_days': 0,
        'by_status': defaultdict(int),
        'by_priority': defaultdict(int),
        'open_bugs_by_age': {
            '0-30d': 0,
            '30-90d': 0,
            '90-180d': 0,
            '>180d': 0
        }
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

        # Calculate age for open bugs
        is_open = status != 'Closed'
        age_bucket = None
        if is_open and created_str:
            try:
                created_date = datetime.strptime(created_str[:19], '%Y-%m-%dT%H:%M:%S')
                age_days = (now - created_date).days

                if age_days <= 30:
                    age_bucket = '0-30d'
                elif age_days <= 90:
                    age_bucket = '30-90d'
                elif age_days <= 180:
                    age_bucket = '90-180d'
                else:
                    age_bucket = '>180d'

                overall_summary['open_bugs_by_age'][age_bucket] += 1
            except (ValueError, TypeError):
                pass

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
            if age_bucket:
                components_data[component_name]['open_bugs_by_age'][age_bucket] += 1

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
            )),
            'open_bugs_by_age': comp_data['open_bugs_by_age']
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
        '--team',
        type=str,
        help='Filter by team name (looks up all components for the team). Mutually exclusive with --component.'
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
        default=1000,
        help='Maximum number of issues to fetch per component (default: 1000, max: 1000)'
    )

    args = parser.parse_args()

    # Validate mutually exclusive arguments
    if args.team and args.component:
        print("Error: --team and --component are mutually exclusive. Use one or the other.", file=sys.stderr)
        sys.exit(1)

    # Validate limit
    if args.limit < 1 or args.limit > 1000:
        print("Error: --limit must be between 1 and 1000", file=sys.stderr)
        sys.exit(1)

    # If team is specified, look up components for that team
    components_to_filter = args.component
    team_name = None
    if args.team:
        try:
            team_name = args.team
            components_to_filter = get_team_components(args.team)
            print(f"Team '{args.team}' has {len(components_to_filter)} components: {', '.join(components_to_filter)}", file=sys.stderr)
        except (FileNotFoundError, KeyError, ValueError) as e:
            print(f"Error resolving team components: {e}", file=sys.stderr)
            sys.exit(1)

    # Fetch raw JIRA data using list_jiras.py
    print(f"Fetching JIRA data for project {args.project}...", file=sys.stderr)
    raw_data = call_list_jiras(
        project=args.project,
        components=components_to_filter,
        statuses=args.status,
        include_closed=args.include_closed,
        limit=args.limit
    )

    # Extract issues from raw data
    issues = raw_data.get('issues', [])
    print(f"Generating summary statistics from {len(issues)} issues...", file=sys.stderr)

    # Generate summary statistics
    summary_data = generate_summary(issues)

    # Build output with metadata and summaries
    output = {
        'project': raw_data.get('project'),
        'total_count': raw_data.get('total_count'),
        'fetched_count': raw_data.get('fetched_count'),
        'query': raw_data.get('query'),
        'filters': raw_data.get('filters'),
        'summary': summary_data['summary'],
        'components': summary_data['components']
    }

    # Add team name if filtering by team
    if team_name:
        output['team'] = team_name

    # Add note if present in raw data
    if 'note' in raw_data:
        output['note'] = raw_data['note']

    # Output JSON to stdout
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
