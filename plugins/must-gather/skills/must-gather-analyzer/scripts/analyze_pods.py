#!/usr/bin/env python3
"""
Analyze Pod resources from must-gather data.
Displays output similar to 'oc get pods -A' command.
"""

import sys
import os
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


def parse_pod(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a single pod YAML file."""
    try:
        with open(file_path, 'r') as f:
            doc = yaml.safe_load(f)
            if doc and doc.get('kind') == 'Pod':
                return doc
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return None


def calculate_age(creation_timestamp: str) -> str:
    """Calculate age from creation timestamp."""
    try:
        ts = datetime.fromisoformat(creation_timestamp.replace('Z', '+00:00'))
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


def get_pod_status(pod: Dict[str, Any]) -> Dict[str, Any]:
    """Extract pod status information."""
    metadata = pod.get('metadata', {})
    status = pod.get('status', {})
    spec = pod.get('spec', {})

    name = metadata.get('name', 'unknown')
    namespace = metadata.get('namespace', 'unknown')
    creation_time = metadata.get('creationTimestamp', '')

    # Get container statuses
    container_statuses = status.get('containerStatuses', [])
    init_container_statuses = status.get('initContainerStatuses', [])

    # Calculate ready containers
    total_containers = len(spec.get('containers', []))
    ready_containers = sum(1 for cs in container_statuses if cs.get('ready', False))

    # Get overall phase
    phase = status.get('phase', 'Unknown')

    # Determine more specific status
    pod_status = phase
    reason = status.get('reason', '')

    # Check for specific container states
    for cs in container_statuses:
        state = cs.get('state', {})
        if 'waiting' in state:
            waiting = state['waiting']
            pod_status = waiting.get('reason', 'Waiting')
        elif 'terminated' in state:
            terminated = state['terminated']
            if terminated.get('exitCode', 0) != 0:
                pod_status = terminated.get('reason', 'Error')

    # Check init containers
    for ics in init_container_statuses:
        state = ics.get('state', {})
        if 'waiting' in state:
            waiting = state['waiting']
            if waiting.get('reason') in ['CrashLoopBackOff', 'ImagePullBackOff', 'ErrImagePull']:
                pod_status = f"Init:{waiting.get('reason', 'Waiting')}"

    # Calculate total restarts
    total_restarts = sum(cs.get('restartCount', 0) for cs in container_statuses)

    # Calculate age
    age = calculate_age(creation_time) if creation_time else ''

    return {
        'namespace': namespace,
        'name': name,
        'ready': f"{ready_containers}/{total_containers}",
        'status': pod_status,
        'restarts': str(total_restarts),
        'age': age,
        'node': spec.get('nodeName', ''),
        'is_problem': pod_status not in ['Running', 'Succeeded', 'Completed'] or total_restarts > 0
    }


def print_pods_table(pods: List[Dict[str, Any]], show_namespace: bool = True):
    """Print pods in a formatted table like 'oc get pods'."""
    if not pods:
        print("No resources found.")
        return

    # Print header
    if show_namespace:
        print(f"{'NAMESPACE':<42} {'NAME':<50} {'READY':<7} {'STATUS':<20} {'RESTARTS':<9} AGE")
    else:
        print(f"{'NAME':<50} {'READY':<7} {'STATUS':<20} {'RESTARTS':<9} AGE")

    # Print rows
    for pod in pods:
        name = pod['name'][:50]
        ready = pod['ready'][:7]
        status = pod['status'][:20]
        restarts = pod['restarts'][:9]
        age = pod['age']

        if show_namespace:
            namespace = pod['namespace'][:42]
            print(f"{namespace:<42} {name:<50} {ready:<7} {status:<20} {restarts:<9} {age}")
        else:
            print(f"{name:<50} {ready:<7} {status:<20} {restarts:<9} {age}")


def analyze_pods(must_gather_path: str, namespace: Optional[str] = None, problems_only: bool = False):
    """Analyze all pods in a must-gather directory."""
    base_path = Path(must_gather_path)

    pods = []

    # Find all pod YAML files
    # Structure: namespaces/<namespace>/pods/<pod-name>/<pod-name>.yaml
    if namespace:
        # Specific namespace
        patterns = [
            f"namespaces/{namespace}/pods/*/*.yaml",
            f"*/namespaces/{namespace}/pods/*/*.yaml",
        ]
    else:
        # All namespaces
        patterns = [
            "namespaces/*/pods/*/*.yaml",
            "*/namespaces/*/pods/*/*.yaml",
        ]

    for pattern in patterns:
        for pod_file in base_path.glob(pattern):
            pod = parse_pod(pod_file)
            if pod:
                pod_status = get_pod_status(pod)
                pods.append(pod_status)

    if not pods:
        print("No resources found.")
        return 1

    # Remove duplicates
    seen = set()
    unique_pods = []
    for p in pods:
        key = f"{p['namespace']}/{p['name']}"
        if key not in seen:
            seen.add(key)
            unique_pods.append(p)

    # Sort by namespace, then name
    unique_pods.sort(key=lambda x: (x['namespace'], x['name']))

    # Filter if problems only
    if problems_only:
        unique_pods = [p for p in unique_pods if p['is_problem']]
        if not unique_pods:
            print("No resources found.")
            return 0

    # Print results
    print_pods_table(unique_pods, show_namespace=(namespace is None))

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze pod resources from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./must-gather.local.123456789
  %(prog)s ./must-gather.local.123456789 --namespace openshift-etcd
  %(prog)s ./must-gather.local.123456789 --problems-only
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('-n', '--namespace', help='Filter by namespace')
    parser.add_argument('-p', '--problems-only', action='store_true',
                        help='Show only pods with issues')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_pods(args.must_gather_path, args.namespace, args.problems_only)


if __name__ == '__main__':
    sys.exit(main())
