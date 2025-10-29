#!/usr/bin/env python3
"""
Analyze ClusterVersion from must-gather data.
Displays output similar to 'oc get clusterversion' command.
"""

import sys
import os
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


def parse_clusterversion(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse the clusterversion YAML file."""
    try:
        with open(file_path, 'r') as f:
            doc = yaml.safe_load(f)
            if doc and doc.get('kind') == 'ClusterVersion':
                return doc
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return None


def get_condition_status(conditions: list, condition_type: str) -> str:
    """Get status for a specific condition type."""
    for condition in conditions:
        if condition.get('type') == condition_type:
            return condition.get('status', 'Unknown')
    return 'Unknown'


def calculate_duration(timestamp_str: str) -> str:
    """Calculate duration from timestamp to now."""
    try:
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
        return ""


def format_clusterversion(cv: Dict[str, Any]) -> Dict[str, str]:
    """Format ClusterVersion for display."""
    name = cv.get('metadata', {}).get('name', 'version')
    status = cv.get('status', {})

    # Get version from desired
    desired = status.get('desired', {})
    version = desired.get('version', '')

    # Get available updates count
    available_updates = status.get('availableUpdates')
    if available_updates and isinstance(available_updates, list):
        available = str(len(available_updates))
    elif available_updates is None:
        available = ''
    else:
        available = '0'

    # Get conditions
    conditions = status.get('conditions', [])
    progressing = get_condition_status(conditions, 'Progressing')
    since = ''

    # Get time since progressing started (if true) or since last update
    for condition in conditions:
        if condition.get('type') == 'Progressing':
            last_transition = condition.get('lastTransitionTime')
            if last_transition:
                since = calculate_duration(last_transition)
            break

    # Get status message
    status_msg = ''
    for condition in conditions:
        if condition.get('type') == 'Progressing' and condition.get('status') == 'True':
            status_msg = condition.get('message', '')[:80]
            break

    # If not progressing, check if failed
    if progressing != 'True':
        for condition in conditions:
            if condition.get('type') == 'Failing' and condition.get('status') == 'True':
                status_msg = condition.get('message', '')[:80]
                break

    return {
        'name': name,
        'version': version,
        'available': available,
        'progressing': progressing,
        'since': since,
        'status': status_msg
    }


def print_clusterversion_table(cv_info: Dict[str, str]):
    """Print ClusterVersion in a formatted table like 'oc get clusterversion'."""
    # Print header
    print(f"{'NAME':<10} {'VERSION':<50} {'AVAILABLE':<11} {'PROGRESSING':<13} {'SINCE':<7} STATUS")

    # Print row
    name = cv_info['name'][:10]
    version = cv_info['version'][:50]
    available = cv_info['available'][:11]
    progressing = cv_info['progressing'][:13]
    since = cv_info['since'][:7]
    status = cv_info['status']

    print(f"{name:<10} {version:<50} {available:<11} {progressing:<13} {since:<7} {status}")


def print_detailed_info(cv: Dict[str, Any]):
    """Print detailed cluster version information."""
    status = cv.get('status', {})
    spec = cv.get('spec', {})

    print(f"\n{'='*80}")
    print("CLUSTER VERSION DETAILS")
    print(f"{'='*80}")

    # Cluster ID
    cluster_id = spec.get('clusterID', 'unknown')
    print(f"Cluster ID: {cluster_id}")

    # Desired version
    desired = status.get('desired', {})
    print(f"Desired Version: {desired.get('version', 'unknown')}")
    print(f"Desired Image: {desired.get('image', 'unknown')}")

    # Version hash
    version_hash = status.get('versionHash', '')
    if version_hash:
        print(f"Version Hash: {version_hash}")

    # Upstream
    upstream = spec.get('upstream', '')
    if upstream:
        print(f"Update Server: {upstream}")

    # Conditions
    conditions = status.get('conditions', [])
    print(f"\nCONDITIONS:")
    for condition in conditions:
        cond_type = condition.get('type', 'Unknown')
        cond_status = condition.get('status', 'Unknown')
        last_transition = condition.get('lastTransitionTime', '')
        message = condition.get('message', '')

        # Calculate time since transition
        age = calculate_duration(last_transition) if last_transition else ''

        status_indicator = "✅" if cond_status == "True" else "❌" if cond_status == "False" else "❓"
        print(f"  {status_indicator} {cond_type}: {cond_status} (for {age})")
        if message and cond_status == 'True':
            print(f"     Message: {message[:100]}")

    # Update history
    history = status.get('history', [])
    if history:
        print(f"\nUPDATE HISTORY (last 5):")
        for i, entry in enumerate(history[:5]):
            state = entry.get('state', 'Unknown')
            version = entry.get('version', 'unknown')
            image = entry.get('image', '')
            completion_time = entry.get('completionTime', '')

            age = calculate_duration(completion_time) if completion_time else ''
            print(f"  {i+1}. {version} - {state} {f'({age} ago)' if age else ''}")

    # Available updates
    available_updates = status.get('availableUpdates')
    if available_updates and isinstance(available_updates, list) and len(available_updates) > 0:
        print(f"\nAVAILABLE UPDATES ({len(available_updates)}):")
        for i, update in enumerate(available_updates[:5]):
            version = update.get('version', 'unknown')
            image = update.get('image', '')
            print(f"  {i+1}. {version}")
    elif available_updates is None:
        print(f"\nAVAILABLE UPDATES: Unable to retrieve updates")

    # Capabilities
    capabilities = status.get('capabilities', {})
    enabled_caps = capabilities.get('enabledCapabilities', [])
    if enabled_caps:
        print(f"\nENABLED CAPABILITIES ({len(enabled_caps)}):")
        # Print in columns
        for i in range(0, len(enabled_caps), 3):
            caps = enabled_caps[i:i+3]
            print(f"  {', '.join(caps)}")

    print(f"{'='*80}\n")


def analyze_clusterversion(must_gather_path: str):
    """Analyze ClusterVersion in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Find ClusterVersion file
    possible_patterns = [
        "cluster-scoped-resources/config.openshift.io/clusterversions/version.yaml",
        "*/cluster-scoped-resources/config.openshift.io/clusterversions/version.yaml",
    ]

    cv = None
    for pattern in possible_patterns:
        for cv_file in base_path.glob(pattern):
            cv = parse_clusterversion(cv_file)
            if cv:
                break
        if cv:
            break

    if not cv:
        print("No ClusterVersion found.")
        return 1

    # Format and print table
    cv_info = format_clusterversion(cv)
    print_clusterversion_table(cv_info)

    # Print detailed information
    print_detailed_info(cv)

    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_clusterversion.py <must-gather-directory>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  analyze_clusterversion.py ./must-gather.local.123456789", file=sys.stderr)
        return 1

    must_gather_path = sys.argv[1]

    if not os.path.isdir(must_gather_path):
        print(f"Error: Directory not found: {must_gather_path}", file=sys.stderr)
        return 1

    return analyze_clusterversion(must_gather_path)


if __name__ == '__main__':
    sys.exit(main())
