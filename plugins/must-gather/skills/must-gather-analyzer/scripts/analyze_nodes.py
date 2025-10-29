#!/usr/bin/env python3
"""
Analyze Node resources from must-gather data.
Displays output similar to 'oc get nodes' command.
"""

import sys
import os
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


def parse_node(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a single node YAML file."""
    try:
        with open(file_path, 'r') as f:
            doc = yaml.safe_load(f)
            if doc and doc.get('kind') == 'Node':
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

        if days > 0:
            return f"{days}d"
        elif hours > 0:
            return f"{hours}h"
        else:
            return "<1h"
    except Exception:
        return ""


def get_node_roles(labels: Dict[str, str]) -> str:
    """Extract node roles from labels."""
    roles = []
    for key in labels:
        if key.startswith('node-role.kubernetes.io/'):
            role = key.split('/')[-1]
            if role:
                roles.append(role)

    return ','.join(sorted(roles)) if roles else '<none>'


def get_node_status(node: Dict[str, Any]) -> Dict[str, Any]:
    """Extract node status information."""
    metadata = node.get('metadata', {})
    status = node.get('status', {})

    name = metadata.get('name', 'unknown')
    labels = metadata.get('labels', {})
    creation_time = metadata.get('creationTimestamp', '')

    # Get roles
    roles = get_node_roles(labels)

    # Get conditions
    conditions = status.get('conditions', [])
    ready_condition = 'Unknown'
    node_issues = []

    for condition in conditions:
        cond_type = condition.get('type', '')
        cond_status = condition.get('status', 'Unknown')

        if cond_type == 'Ready':
            ready_condition = cond_status
        elif cond_status == 'True' and cond_type in ['MemoryPressure', 'DiskPressure', 'PIDPressure', 'NetworkUnavailable']:
            node_issues.append(cond_type)

    # Determine overall status
    if ready_condition == 'True':
        node_status = 'Ready'
    elif ready_condition == 'False':
        node_status = 'NotReady'
    else:
        node_status = 'Unknown'

    # Add issues to status
    if node_issues:
        node_status = f"{node_status},{','.join(node_issues)}"

    # Get version
    node_info = status.get('nodeInfo', {})
    version = node_info.get('kubeletVersion', '')

    # Get age
    age = calculate_age(creation_time) if creation_time else ''

    # Internal IP
    addresses = status.get('addresses', [])
    internal_ip = ''
    for addr in addresses:
        if addr.get('type') == 'InternalIP':
            internal_ip = addr.get('address', '')
            break

    # OS Image
    os_image = node_info.get('osImage', '')

    return {
        'name': name,
        'status': node_status,
        'roles': roles,
        'age': age,
        'version': version,
        'internal_ip': internal_ip,
        'os_image': os_image,
        'is_problem': node_status != 'Ready' or len(node_issues) > 0
    }


def print_nodes_table(nodes: List[Dict[str, Any]]):
    """Print nodes in a formatted table like 'oc get nodes'."""
    if not nodes:
        print("No resources found.")
        return

    # Print header
    print(f"{'NAME':<50} {'STATUS':<30} {'ROLES':<20} {'AGE':<7} VERSION")

    # Print rows
    for node in nodes:
        name = node['name'][:50]
        status = node['status'][:30]
        roles = node['roles'][:20]
        age = node['age'][:7]
        version = node['version']

        print(f"{name:<50} {status:<30} {roles:<20} {age:<7} {version}")


def analyze_nodes(must_gather_path: str, problems_only: bool = False):
    """Analyze all nodes in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Find all node YAML files
    possible_patterns = [
        "cluster-scoped-resources/core/nodes/*.yaml",
        "*/cluster-scoped-resources/core/nodes/*.yaml",
    ]

    nodes = []

    for pattern in possible_patterns:
        for node_file in base_path.glob(pattern):
            # Skip the nodes.yaml file that contains all nodes
            if node_file.name == 'nodes.yaml':
                continue

            node = parse_node(node_file)
            if node:
                node_status = get_node_status(node)
                nodes.append(node_status)

    if not nodes:
        print("No resources found.")
        return 1

    # Remove duplicates
    seen = set()
    unique_nodes = []
    for n in nodes:
        if n['name'] not in seen:
            seen.add(n['name'])
            unique_nodes.append(n)

    # Sort by name
    unique_nodes.sort(key=lambda x: x['name'])

    # Filter if problems only
    if problems_only:
        unique_nodes = [n for n in unique_nodes if n['is_problem']]
        if not unique_nodes:
            print("No resources found.")
            return 0

    # Print results
    print_nodes_table(unique_nodes)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze node resources from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./must-gather.local.123456789
  %(prog)s ./must-gather.local.123456789 --problems-only
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('-p', '--problems-only', action='store_true',
                        help='Show only nodes with issues')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_nodes(args.must_gather_path, args.problems_only)


if __name__ == '__main__':
    sys.exit(main())
