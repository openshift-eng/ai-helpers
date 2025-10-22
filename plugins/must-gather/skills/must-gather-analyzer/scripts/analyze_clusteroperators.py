#!/usr/bin/env python3
"""
Analyze ClusterOperator resources from must-gather data.
Displays output similar to 'oc get clusteroperators' command.
"""

import sys
import os
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


def parse_clusteroperator(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a single clusteroperator YAML file."""
    try:
        with open(file_path, 'r') as f:
            doc = yaml.safe_load(f)
            if doc and doc.get('kind') == 'ClusterOperator':
                return doc
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return None


def get_condition_status(conditions: List[Dict], condition_type: str) -> tuple[str, str, str]:
    """
    Get status, reason, and message for a specific condition type.
    Returns (status, reason, message).
    """
    for condition in conditions:
        if condition.get('type') == condition_type:
            status = condition.get('status', 'Unknown')
            reason = condition.get('reason', '')
            message = condition.get('message', '')
            return status, reason, message
    return 'Unknown', '', ''


def calculate_duration(timestamp_str: str) -> str:
    """Calculate duration from timestamp to now."""
    try:
        # Parse Kubernetes timestamp format
        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(ts.tzinfo)
        delta = now - ts

        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60

        if days > 0:
            return f"{days}d"
        elif hours > 0:
            return f"{hours}h"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return "<1m"
    except Exception:
        return "unknown"


def get_condition_duration(conditions: List[Dict], condition_type: str) -> str:
    """Get the duration since a condition last transitioned."""
    for condition in conditions:
        if condition.get('type') == condition_type:
            last_transition = condition.get('lastTransitionTime')
            if last_transition:
                return calculate_duration(last_transition)
    return ""


def format_operator_row(operator: Dict[str, Any]) -> Dict[str, str]:
    """Format a ClusterOperator into a row for display."""
    name = operator.get('metadata', {}).get('name', 'unknown')
    conditions = operator.get('status', {}).get('conditions', [])
    versions = operator.get('status', {}).get('versions', [])

    # Get version (first version in the list, usually the operator version)
    version = versions[0].get('version', '') if versions else ''

    # Get condition statuses
    available_status, _, _ = get_condition_status(conditions, 'Available')
    progressing_status, _, _ = get_condition_status(conditions, 'Progressing')
    degraded_status, degraded_reason, degraded_msg = get_condition_status(conditions, 'Degraded')

    # Determine which condition to show duration and message for
    # Priority: Degraded > Progressing > Available (if false)
    if degraded_status == 'True':
        since = get_condition_duration(conditions, 'Degraded')
        message = degraded_msg if degraded_msg else degraded_reason
    elif progressing_status == 'True':
        since = get_condition_duration(conditions, 'Progressing')
        _, prog_reason, prog_msg = get_condition_status(conditions, 'Progressing')
        message = prog_msg if prog_msg else prog_reason
    elif available_status == 'False':
        since = get_condition_duration(conditions, 'Available')
        _, avail_reason, avail_msg = get_condition_status(conditions, 'Available')
        message = avail_msg if avail_msg else avail_reason
    else:
        # All good, show time since available
        since = get_condition_duration(conditions, 'Available')
        message = ''

    return {
        'name': name,
        'version': version,
        'available': available_status,
        'progressing': progressing_status,
        'degraded': degraded_status,
        'since': since,
        'message': message
    }


def print_operators_table(operators: List[Dict[str, str]]):
    """Print operators in a formatted table like 'oc get clusteroperators'."""
    if not operators:
        print("No resources found.")
        return

    # Print header - no width limit on VERSION to match oc output
    print(f"{'NAME':<42} {'VERSION':<50} {'AVAILABLE':<11} {'PROGRESSING':<13} {'DEGRADED':<10} {'SINCE':<7} MESSAGE")

    # Print rows
    for op in operators:
        name = op['name'][:42]
        version = op['version']  # Don't truncate version
        available = op['available'][:11]
        progressing = op['progressing'][:13]
        degraded = op['degraded'][:10]
        since = op['since'][:7]
        message = op['message']

        print(f"{name:<42} {version:<50} {available:<11} {progressing:<13} {degraded:<10} {since:<7} {message}")


def analyze_clusteroperators(must_gather_path: str):
    """Analyze all clusteroperators in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Common paths where clusteroperators might be
    possible_patterns = [
        "cluster-scoped-resources/config.openshift.io/clusteroperators/*.yaml",
        "*/cluster-scoped-resources/config.openshift.io/clusteroperators/*.yaml",
    ]

    clusteroperators = []

    # Find and parse all clusteroperator files
    for pattern in possible_patterns:
        for co_file in base_path.glob(pattern):
            operator = parse_clusteroperator(co_file)
            if operator:
                clusteroperators.append(operator)

    if not clusteroperators:
        print("No resources found.", file=sys.stderr)
        return 1

    # Remove duplicates (same operator from different glob patterns)
    seen = set()
    unique_operators = []
    for op in clusteroperators:
        name = op.get('metadata', {}).get('name')
        if name and name not in seen:
            seen.add(name)
            unique_operators.append(op)

    # Format and sort operators by name
    formatted_ops = [format_operator_row(op) for op in unique_operators]
    formatted_ops.sort(key=lambda x: x['name'])

    # Print results
    print_operators_table(formatted_ops)

    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_clusteroperators.py <must-gather-directory>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  analyze_clusteroperators.py ./must-gather.local.123456789", file=sys.stderr)
        return 1

    must_gather_path = sys.argv[1]

    if not os.path.isdir(must_gather_path):
        print(f"Error: Directory not found: {must_gather_path}", file=sys.stderr)
        return 1

    return analyze_clusteroperators(must_gather_path)


if __name__ == '__main__':
    sys.exit(main())
