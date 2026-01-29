#!/usr/bin/env python3
"""
Script to fetch regression data for OpenShift components.

Usage:
    python3 list_regressions.py --release <release> [--components comp1 comp2 ...] [--short]
    python3 list_regressions.py --release <release> --team "Team Name" [--short]

Example:
    python3 list_regressions.py --release 4.17
    python3 list_regressions.py --release 4.21 --components Monitoring etcd
    python3 list_regressions.py --release 4.21 --team "API Server"
    python3 list_regressions.py --release 4.21 --short
"""

import argparse
import os
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path


def get_team_components(team_name: str) -> list:
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

    # Extract components from team object
    team_data = teams[team_name]
    if isinstance(team_data, dict):
        return team_data.get("components", [])
    else:
        # Fallback for old format (simple array)
        return team_data


def calculate_hours_between(start_timestamp: str, end_timestamp: str) -> int:
    """
    Calculate the number of hours between two timestamps, rounded to the nearest hour.
    
    Args:
        start_timestamp: ISO format timestamp string (e.g., "2025-09-26T00:02:51.385944Z")
        end_timestamp: ISO format timestamp string (e.g., "2025-09-27T12:04:24.966914Z")
    
    Returns:
        Number of hours between the timestamps, rounded to the nearest hour
    
    Raises:
        ValueError: If timestamp parsing fails
    """
    start_time = datetime.fromisoformat(start_timestamp.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(end_timestamp.replace('Z', '+00:00'))
    
    time_diff = end_time - start_time
    return round(time_diff.total_seconds() / 3600)


def fetch_regressions(release: str) -> dict:
    """
    Fetch regression data from the component health API.
    
    Args:
        release: The release version (e.g., "4.17", "4.16")
    
    Returns:
        Dictionary containing the regression data
    
    Raises:
        urllib.error.URLError: If the request fails
    """
    # Construct the base URL
    base_url = f"https://sippy.dptools.openshift.org/api/component_readiness/regressions"
    
    # Build query parameters
    params = [f"release={release}"]
    
    url = f"{base_url}?{'&'.join(params)}"
    
    print(f"Fetching regressions from: {url}", file=sys.stderr)
    
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data
            else:
                raise Exception(f"HTTP {response.status}: {response.reason}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise


def filter_by_components(data: list, components: list = None) -> list:
    """
    Filter regression data by component names.
    
    Args:
        data: List of regression dictionaries
        components: Optional list of component names to filter by
    
    Returns:
        Filtered list of regressions matching the specified components
    """
    # Always filter out regressions with empty component names
    # These are legacy prior to a code change to ensure it is always set.
    filtered = [
        regression for regression in data
        if regression.get('component', '') != ''
    ]
    
    # If no specific components requested, return all non-empty components
    if not components:
        return filtered
    
    # Convert components to lowercase for case-insensitive comparison
    components_lower = [c.lower() for c in components]
    
    # Further filter by specified components
    filtered = [
        regression for regression in filtered
        if regression.get('component', '').lower() in components_lower
    ]
    
    print(f"Filtered to {len(filtered)} regressions for components: {', '.join(components)}", 
          file=sys.stderr)
    
    return filtered


def simplify_time_fields(data: list) -> list:
    """
    Simplify time fields in regression data.
    
    Converts time fields from a nested structure like:
      {"Time": "2025-09-27T12:04:24.966914Z", "Valid": true}
    to either:
      - The timestamp string if Valid is true
      - null if Valid is false
    
    This applies to fields: 'closed', 'last_failure'
    
    Args:
        data: List of regression dictionaries
    
    Returns:
        List of regressions with simplified time fields
    """
    time_fields = ['closed', 'last_failure']
    
    for regression in data:
        for field in time_fields:
            if field in regression:
                value = regression[field]
                # Check if the field is a dict with Valid and Time fields
                if isinstance(value, dict):
                    if value.get('Valid') is True:
                        # Replace with just the timestamp string
                        regression[field] = value.get('Time')
                    else:
                        # Replace with null if not valid
                        regression[field] = None
    
    return data


def filter_by_date_range(regressions: list, start_date: str = None, end_date: str = None) -> list:
    """
    Filter regressions by date range.
    
    Args:
        regressions: List of regression dictionaries
        start_date: Start date in YYYY-MM-DD format. Filters out regressions closed before this date.
        end_date: End date in YYYY-MM-DD format. Filters out regressions opened after this date.
    
    Returns:
        Filtered list of regressions
        
    Note:
        - If start_date is provided: excludes regressions that were closed before start_date
        - If end_date is provided: excludes regressions that were opened after end_date
        - This allows filtering to a development window (e.g., from development_start to GA)
    """
    if not start_date and not end_date:
        return regressions
    
    filtered = []
    
    for regression in regressions:
        # Skip if opened after end_date
        if end_date and regression.get('opened'):
            opened_date = regression['opened'].split('T')[0]  # Extract YYYY-MM-DD
            if opened_date > end_date:
                continue
        
        # Skip if closed before start_date
        if start_date and regression.get('closed'):
            closed_date = regression['closed'].split('T')[0]  # Extract YYYY-MM-DD
            if closed_date < start_date:
                continue
        
        filtered.append(regression)
    
    return filtered


def remove_unnecessary_fields(regressions: list) -> list:
    """
    Remove unnecessary fields from regressions to reduce response size.
    
    Removes 'links' and 'test_id' fields from each regression object.
    
    Args:
        regressions: List of regression dictionaries
    
    Returns:
        List of regression dictionaries with unnecessary fields removed
    """
    for regression in regressions:
        # Remove links and test_id to reduce response size
        regression.pop('links', None)
        regression.pop('test_id', None)
    
    return regressions


def exclude_suspected_infra_regressions(regressions: list) -> tuple[list, int]:
    """
    Filter out suspected infrastructure-related mass regressions.
    
    This is an imprecise attempt to filter out mass regressions caused by infrastructure
    issues which the TRT handles via a separate mechanism. These
    mass incidents typically result in many short-lived regressions being opened and
    closed on the same day.
    
    Algorithm:
    1. First pass: Count how many short-lived regressions (closed within 96 hours of opening)
       were closed on each date.
    2. Second pass: Filter out regressions that:
       - Were closed within 96 hours of being opened, AND
       - Were closed on a date where >50 short-lived regressions were closed
    
    Args:
        regressions: List of regression dictionaries
    
    Returns:
        Tuple of (filtered_regressions, count_of_filtered_regressions)
    """
    # First pass: Track count of short-lived regressions closed on each date
    short_lived_closures_by_date = {}
    
    for regression in regressions:
        opened = regression.get('opened')
        closed = regression.get('closed')
        
        # Skip if not closed or missing opened timestamp
        if not closed or not opened:
            continue
        
        try:
            # Calculate how long the regression was open
            hours_open = calculate_hours_between(opened, closed)
            
            # If closed within 96 hours, increment counter for the closed date
            if hours_open <= 96:
                closed_date = closed.split('T')[0]  # Extract YYYY-MM-DD
                short_lived_closures_by_date[closed_date] = short_lived_closures_by_date.get(closed_date, 0) + 1
        except (ValueError, KeyError, TypeError):
            # Skip if timestamp parsing fails
            continue
    
    # Second pass: Filter out suspected infra regressions
    filtered_regressions = []
    filtered_count = 0
    
    for regression in regressions:
        opened = regression.get('opened')
        closed = regression.get('closed')
        
        # Keep open regressions
        if not closed or not opened:
            filtered_regressions.append(regression)
            continue
        
        try:
            # Calculate how long the regression was open
            hours_open = calculate_hours_between(opened, closed)
            closed_date = closed.split('T')[0]  # Extract YYYY-MM-DD
            
            # Filter out if:
            # 1. Was closed within 96 hours, AND
            # 2. More than 50 short-lived regressions were closed on that date
            if hours_open <= 96 and short_lived_closures_by_date.get(closed_date, 0) > 50:
                filtered_count += 1
                continue
            
            # Keep this regression
            filtered_regressions.append(regression)
        except (ValueError, KeyError, TypeError):
            # If timestamp parsing fails, keep the regression
            filtered_regressions.append(regression)
    
    return filtered_regressions, filtered_count


def group_by_component(data: list) -> dict:
    """
    Group regressions by component name and split into open/closed.
    
    Args:
        data: List of regression dictionaries
    
    Returns:
        Dictionary mapping component names to objects containing open and closed regression lists
    """
    components = {}
    
    for regression in data:
        component = regression.get('component', 'Unknown')
        if component not in components:
            components[component] = {
                "open": [],
                "closed": []
            }
        
        # Split based on whether closed field is null
        if regression.get('closed') is None:
            components[component]["open"].append(regression)
        else:
            components[component]["closed"].append(regression)
    
    # Sort component names for consistent output
    return dict(sorted(components.items()))


def calculate_summary(regressions: list, filtered_suspected_infra: int = 0) -> dict:
    """
    Calculate summary statistics for a list of regressions.
    
    Args:
        regressions: List of regression dictionaries
        filtered_suspected_infra: Count of regressions filtered out as suspected infrastructure issues
    
    Returns:
        Dictionary containing summary statistics with nested open/closed totals, triaged counts,
        and average time to triage
    """
    total = 0
    open_total = 0
    open_triaged = 0
    open_triage_times = []
    open_times = []
    closed_total = 0
    closed_triaged = 0
    closed_triage_times = []
    closed_times = []
    triaged_to_closed_times = []
    
    # Get current time for calculating open duration
    current_time = datetime.now(timezone.utc)
    current_time_str = current_time.isoformat().replace('+00:00', 'Z')
    
    # Single pass through all regressions
    for regression in regressions:
        total += 1
        triages = regression.get('triages', [])
        is_triaged = bool(triages)
        
        # Calculate time to triage if regression is triaged
        time_to_triage_hrs = None
        if is_triaged and regression.get('opened'):
            try:
                # Find earliest triage timestamp
                earliest_triage_time = min(
                    t['created_at'] for t in triages if t.get('created_at')
                )
                
                # Calculate difference in hours
                time_to_triage_hrs = calculate_hours_between(
                    regression['opened'],
                    earliest_triage_time
                )
            except (ValueError, KeyError, TypeError):
                # Skip if timestamp parsing fails
                pass
        
        # It is common for a triage to be reused as new regressions appear, which makes this a very tricky case to calculate time to triage. 
        # If you triaged a first round of regressions, then added more 24 hours later, we don't actually know when you triaged them in the db. 
        # Treating them as if they were immediately triaged would skew results. 
        # Best we can do is ignore these from consideration. They will count as if they got triaged, but we have no idea what to do with the time to triage.
        if regression.get('closed') is None:
            # Open regression
            open_total += 1
            if is_triaged:
                open_triaged += 1
                if time_to_triage_hrs is not None and time_to_triage_hrs > 0:
                    open_triage_times.append(time_to_triage_hrs)
            
            # Calculate how long regression has been open
            if regression.get('opened'):
                try:
                    time_open_hrs = calculate_hours_between(
                        regression['opened'],
                        current_time_str
                    )
                    # Only include positive time differences
                    if time_open_hrs > 0:
                        open_times.append(time_open_hrs)
                except (ValueError, KeyError, TypeError):
                    # Skip if timestamp parsing fails
                    pass
        else:
            # Closed regression
            closed_total += 1
            if is_triaged:
                closed_triaged += 1
                if time_to_triage_hrs is not None and time_to_triage_hrs > 0:
                    closed_triage_times.append(time_to_triage_hrs)
                
                # Calculate time from triage to closed
                if regression.get('closed') and triages:
                    try:
                        earliest_triage_time = min(
                            t['created_at'] for t in triages if t.get('created_at')
                        )
                        time_triaged_to_closed_hrs = calculate_hours_between(
                            earliest_triage_time,
                            regression['closed']
                        )
                        # Only include positive time differences:
                        if time_triaged_to_closed_hrs > 0:
                            triaged_to_closed_times.append(time_triaged_to_closed_hrs)
                    except (ValueError, KeyError, TypeError):
                        # Skip if timestamp parsing fails
                        pass
                
            # Calculate time to close
            if regression.get('opened') and regression.get('closed'):
                try:
                    time_to_close_hrs = calculate_hours_between(
                        regression['opened'],
                        regression['closed']
                    )
                    # Only include positive time differences
                    if time_to_close_hrs > 0:
                        closed_times.append(time_to_close_hrs)
                except (ValueError, KeyError, TypeError):
                    # Skip if timestamp parsing fails
                    pass
    
    # Calculate averages and maximums
    open_avg_triage_time = round(sum(open_triage_times) / len(open_triage_times)) if open_triage_times else None
    open_max_triage_time = max(open_triage_times) if open_triage_times else None
    open_avg_time = round(sum(open_times) / len(open_times)) if open_times else None
    open_max_time = max(open_times) if open_times else None
    closed_avg_triage_time = round(sum(closed_triage_times) / len(closed_triage_times)) if closed_triage_times else None
    closed_max_triage_time = max(closed_triage_times) if closed_triage_times else None
    closed_avg_time = round(sum(closed_times) / len(closed_times)) if closed_times else None
    closed_max_time = max(closed_times) if closed_times else None
    triaged_to_closed_avg_time = round(sum(triaged_to_closed_times) / len(triaged_to_closed_times)) if triaged_to_closed_times else None
    triaged_to_closed_max_time = max(triaged_to_closed_times) if triaged_to_closed_times else None

    # Calculate triage percentages
    total_triaged = open_triaged + closed_triaged
    triage_percentage = round((total_triaged / total * 100), 1) if total > 0 else 0
    open_triage_percentage = round((open_triaged / open_total * 100), 1) if open_total > 0 else 0
    closed_triage_percentage = round((closed_triaged / closed_total * 100), 1) if closed_total > 0 else 0
    
    # Calculate overall time to triage (combining open and closed)
    all_triage_times = open_triage_times + closed_triage_times
    overall_avg_triage_time = round(sum(all_triage_times) / len(all_triage_times)) if all_triage_times else None
    overall_max_triage_time = max(all_triage_times) if all_triage_times else None
    
    # Time to close is only for closed regressions (already calculated in closed_avg_time/closed_max_time)
    
    return {
        "total": total,
        "triaged": total_triaged,
        "triage_percentage": triage_percentage,
        "filtered_suspected_infra_regressions": filtered_suspected_infra,
        "time_to_triage_hrs_avg": overall_avg_triage_time,
        "time_to_triage_hrs_max": overall_max_triage_time,
        "time_to_close_hrs_avg": closed_avg_time,
        "time_to_close_hrs_max": closed_max_time,
        "open": {
            "total": open_total,
            "triaged": open_triaged,
            "triage_percentage": open_triage_percentage,
            "time_to_triage_hrs_avg": open_avg_triage_time,
            "time_to_triage_hrs_max": open_max_triage_time,
            "open_hrs_avg": open_avg_time,
            "open_hrs_max": open_max_time
        },
        "closed": {
            "total": closed_total,
            "triaged": closed_triaged,
            "triage_percentage": closed_triage_percentage,
            "time_to_triage_hrs_avg": closed_avg_triage_time,
            "time_to_triage_hrs_max": closed_max_triage_time,
            "time_to_close_hrs_avg": closed_avg_time,
            "time_to_close_hrs_max": closed_max_time,
            "time_triaged_closed_hrs_avg": triaged_to_closed_avg_time,
            "time_triaged_closed_hrs_max": triaged_to_closed_max_time
        }
    }


def add_component_summaries(components: dict) -> dict:
    """
    Add summary statistics to each component object.
    
    Args:
        components: Dictionary mapping component names to objects containing open and closed regression lists
    
    Returns:
        Dictionary with summaries added to each component
    """
    for component, component_data in components.items():
        # Combine open and closed to get all regressions for this component
        all_regressions = component_data["open"] + component_data["closed"]
        component_data["summary"] = calculate_summary(all_regressions)
    
    return components


def format_output(data: dict) -> str:
    """
    Format the regression data for output.

    Args:
        data: Dictionary containing regression data with keys:
            - 'summary': Overall statistics (total, open, closed)
            - 'components': Dictionary mapping component names to objects with:
                - 'summary': Per-component statistics
                - 'open': List of open regression objects
                - 'closed': List of closed regression objects

    Returns:
        Formatted JSON string output
    """
    return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch regression data for OpenShift components',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all regressions for release 4.17
  %(prog)s --release 4.17
  
  # Filter by specific components
  %(prog)s --release 4.21 --components Monitoring "kube-apiserver"
  
  # Filter by multiple components
  %(prog)s --release 4.21 --components Monitoring etcd "kube-apiserver"
  
  # Short output mode (summaries only, no regression data)
  %(prog)s --release 4.17 --short
        """
    )
    
    parser.add_argument(
        '--release',
        type=str,
        required=True,
        help='Release version (e.g., "4.17", "4.16")'
    )
    
    parser.add_argument(
        '--components',
        type=str,
        nargs='+',
        default=None,
        help='Filter by component names (space-separated list, case-insensitive)'
    )

    parser.add_argument(
        '--team',
        type=str,
        default=None,
        help='Filter by team name (looks up all components for the team). Mutually exclusive with --components.'
    )

    parser.add_argument(
        '--start',
        type=str,
        default=None,
        help='Start date for filtering (YYYY-MM-DD format, e.g., "2022-03-10"). Filters out regressions closed before this date.'
    )
    
    parser.add_argument(
        '--end',
        type=str,
        default=None,
        help='End date for filtering (YYYY-MM-DD format, e.g., "2022-08-10"). Filters out regressions opened after this date.'
    )
    
    parser.add_argument(
        '--short',
        action='store_true',
        help='Short output mode: exclude regression data, only include summaries'
    )
    args = parser.parse_args()

    # Validate mutually exclusive arguments
    if args.team and args.components:
        print("Error: --team and --components are mutually exclusive. Use one or the other.", file=sys.stderr)
        return 1

    # If team is specified, look up components for that team
    components_to_filter = args.components
    team_name = None
    if args.team:
        try:
            team_name = args.team
            components_to_filter = get_team_components(args.team)
            print(f"Team '{args.team}' has {len(components_to_filter)} components: {', '.join(components_to_filter)}", file=sys.stderr)
        except (FileNotFoundError, KeyError, ValueError) as e:
            print(f"Error resolving team components: {e}", file=sys.stderr)
            return 1

    try:
        # Fetch regressions
        regressions = fetch_regressions(args.release)

        # Filter by components (always called to remove empty component names)
        if isinstance(regressions, list):
            regressions = filter_by_components(regressions, components_to_filter)

        # Simplify time field structures (closed, last_failure)
        if isinstance(regressions, list):
            regressions = simplify_time_fields(regressions)

        # Filter by date range (to focus on development window)
        if isinstance(regressions, list):
            regressions = filter_by_date_range(regressions, args.start, args.end)

        # Remove unnecessary fields to reduce response size
        if isinstance(regressions, list):
            regressions = remove_unnecessary_fields(regressions)

        # Filter out suspected infrastructure regressions
        filtered_infra_count = 0
        if isinstance(regressions, list):
            regressions, filtered_infra_count = exclude_suspected_infra_regressions(regressions)
            print(f"Filtered out {filtered_infra_count} suspected infrastructure regressions", 
                  file=sys.stderr)

        # Group regressions by component
        if isinstance(regressions, list):
            components = group_by_component(regressions)
        else:
            components = {}

        # Add summaries to each component
        if isinstance(components, dict):
            components = add_component_summaries(components)

        # Calculate overall summary statistics from all regressions
        all_regressions = []
        for comp_data in components.values():
            all_regressions.extend(comp_data["open"])
            all_regressions.extend(comp_data["closed"])
        
        overall_summary = calculate_summary(all_regressions, filtered_infra_count)

        # Construct output with summary and components
        # If --team is specified, include both team summary and per-component breakdown
        if team_name:
            components_short = {}
            for component_name, component_data in components.items():
                components_short[component_name] = {
                    "summary": component_data["summary"]
                }
            output_data = {
                "team": team_name,
                "summary": overall_summary,
                "components": components_short
            }
        # If --short flag is specified, remove regression data from components
        elif args.short:
            # Create a copy of components with only summaries
            components_short = {}
            for component_name, component_data in components.items():
                components_short[component_name] = {
                    "summary": component_data["summary"]
                }
            output_data = {
                "summary": overall_summary,
                "components": components_short
            }
        else:
            output_data = {
                "summary": overall_summary,
                "components": components
            }

        # Format and print output
        output = format_output(output_data)
        print(output)

        return 0
    
    except Exception as e:
        print(f"Failed to fetch regressions: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

