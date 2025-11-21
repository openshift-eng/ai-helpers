#!/usr/bin/env python3
"""
Analyze IPsec configuration and tunnel status from must-gather data.

This script analyzes:
1. IPsec configuration from cluster network resources
2. ovn-ipsec-host daemonset pod status
3. IPsec tunnel establishment status per pod

Usage:
    analyze_ipsec.py <must-gather-path> [node-name]

Arguments:
    must-gather-path: Path to the must-gather directory
    node-name: Optional. Filter analysis to specific node. Use 'all' or omit for all nodes.

Examples:
    # Analyze all nodes
    analyze_ipsec.py ./must-gather.local.123456789

    # Analyze specific node
    analyze_ipsec.py ./must-gather.local.123456789 worker-0

    # Explicitly analyze all nodes
    analyze_ipsec.py ./must-gather.local.123456789 all
"""

import sys
import os
import yaml
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


def parse_yaml_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a YAML file and return the document."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Warning: File not found: {file_path}", file=sys.stderr)
        return None
    except yaml.YAMLError as e:
        print(f"Warning: Invalid YAML in {file_path}: {e}", file=sys.stderr)
        return None


def get_ipsec_config(must_gather_path: Path) -> Optional[Dict[str, Any]]:
    """
    Get IPsec configuration from cluster network resources.

    Looks for: cluster-scoped-resources/operator.openshift.io/networks/cluster.yaml

    Returns dict with:
        - enabled: bool indicating if IPsec is enabled (mode != 'Disabled')
        - mode: IPsec mode ('Full', 'External', or 'Disabled')
        - config: Full ipsecConfig dict if available
    """
    patterns = [
        "cluster-scoped-resources/operator.openshift.io/networks/cluster.yaml",
        "*/cluster-scoped-resources/operator.openshift.io/networks/cluster.yaml",
    ]

    for pattern in patterns:
        for network_file in must_gather_path.glob(pattern):
            network = parse_yaml_file(network_file)
            if not network:
                continue

            spec = network.get('spec', {})
            default_network = spec.get('defaultNetwork', {})
            ovn_config = default_network.get('ovnKubernetesConfig', {})
            ipsec_config = ovn_config.get('ipsecConfig')

            mode = ipsec_config.get('mode') if ipsec_config else None
            return {
                'enabled': ipsec_config is not None and mode != 'Disabled',
                'mode': mode,
                'config': ipsec_config
            }

    return None


def analyze_ovn_ipsec_host_pods(must_gather_path: Path, filter_node: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Analyze ovn-ipsec-host daemonset pods.

    Args:
        must_gather_path: Path to must-gather directory
        filter_node: Optional node name to filter results. None means all nodes.

    Returns list of pod info dicts with:
        - name: Pod name
        - ready: Ready containers ratio (e.g., "1/1")
        - status: Pod phase (Running, CrashLoopBackOff, etc.)
        - restarts: Total restart count across all containers
        - node: Node name where pod is scheduled
    """
    pods = []

    patterns = [
        "namespaces/openshift-ovn-kubernetes/pods/ovn-ipsec-host-*/*.yaml",
        "*/namespaces/openshift-ovn-kubernetes/pods/ovn-ipsec-host-*/*.yaml",
    ]

    seen = set()  # Track pod names to avoid duplicates

    for pattern in patterns:
        for pod_file in must_gather_path.glob(pattern):
            # Skip aggregated pods.yaml files
            if pod_file.name == 'pods.yaml':
                continue

            pod = parse_yaml_file(pod_file)
            if not pod:
                continue

            name = pod.get('metadata', {}).get('name', 'unknown')

            # Only process ovn-ipsec-host pods
            if not name.startswith('ovn-ipsec-host-'):
                continue

            # Skip duplicates
            if name in seen:
                continue
            seen.add(name)

            spec = pod.get('spec', {})
            status = pod.get('status', {})
            node_name = spec.get('nodeName', 'Unknown')

            # Apply node filter if specified
            if filter_node and filter_node.lower() != 'all' and node_name != filter_node:
                continue

            phase = status.get('phase', 'Unknown')
            containers = spec.get('containers', [])
            container_statuses = status.get('containerStatuses', [])

            total = len(containers)
            ready = sum(1 for cs in container_statuses if cs.get('ready', False))

            # Calculate total restarts across all containers
            restart_count = sum(cs.get('restartCount', 0) for cs in container_statuses)

            pods.append({
                'name': name,
                'ready': f"{ready}/{total}",
                'status': phase,
                'restarts': restart_count,
                'node': node_name
            })

    return sorted(pods, key=lambda x: x['name'])


def parse_ipsec_connections(openshift_conf_path: Path) -> List[str]:
    """
    Parse openshift.conf to extract IPsec connection names.

    Connection definitions start with 'conn <name>' where <name> is the connection identifier.
    Ignores special connections like '%default'.

    Returns list of connection names.
    """
    connections = []

    if not openshift_conf_path.exists():
        return connections

    try:
        with open(openshift_conf_path, 'r', errors='ignore') as f:
            for line in f:
                # Match lines like: "conn connection-name"
                match = re.match(r'^\s*conn\s+(\S+)', line)
                if match:
                    conn_name = match.group(1)
                    # Skip special connection names
                    if conn_name not in ['%default']:
                        connections.append(conn_name)
    except OSError as e:
        print(f"Warning: Failed to parse {openshift_conf_path}: {e}", file=sys.stderr)

    return connections


def check_connection_status(status_log_path: Path, connection_name: str) -> Dict[str, Any]:
    """
    Check if a connection is established by examining the status log.

    A connection is considered established if 'ESTABLISHED_CHILD_SA' appears in
    a log line that also mentions the connection name.

    Args:
        status_log_path: Path to the status log file
        connection_name: Name of the connection to check

    Returns dict with:
        - established: bool indicating if ESTABLISHED_CHILD_SA was found
        - info: String with status information
    """
    if not status_log_path.exists():
        return {
            'established': False,
            'info': 'Status log not found'
        }

    try:
        with open(status_log_path, 'r', errors='ignore') as f:
            for line in f:
                # Look for lines mentioning this connection
                if connection_name in line:
                    # Check if this line indicates established state
                    if 'ESTABLISHED_CHILD_SA' in line:
                        return {
                            'established': True,
                            'info': 'ESTABLISHED_CHILD_SA'
                        }
    except OSError as e:
        print(f"Warning: Failed to read {status_log_path}: {e}", file=sys.stderr)
        return {
            'established': False,
            'info': f'Error reading log: {e}'
        }

    return {
        'established': False,
        'info': 'No ESTABLISHED_CHILD_SA found'
    }


def analyze_ipsec_tunnels(must_gather_path: Path, filter_node: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze IPsec tunnel status from network_logs/ipsec/ directory.

    Directory structure:
        network_logs/ipsec/
            ├── <pod>_ipsec.d/
            │   └── openshift.conf      # Connection definitions
            └── status/
                └── <pod>.log           # Connection status logs

    Args:
        must_gather_path: Path to must-gather directory
        filter_node: Optional node name to filter results

    Returns dict with:
        - pods: List of pod tunnel analyses
        - total_connections: Total number of connections found
        - established_connections: Number of established connections
        - failed_connections: Number of not established connections
    """
    tunnel_analysis = {
        'pods': [],
        'total_connections': 0,
        'established_connections': 0,
        'failed_connections': 0
    }

    # Build a mapping of pod name to node name from the pod analysis
    # This requires re-reading pod info, so we'll do a lightweight version
    pod_to_node = {}
    patterns = [
        "namespaces/openshift-ovn-kubernetes/pods/ovn-ipsec-host-*/*.yaml",
        "*/namespaces/openshift-ovn-kubernetes/pods/ovn-ipsec-host-*/*.yaml",
    ]

    seen_pods = set()
    for pattern in patterns:
        for pod_file in must_gather_path.glob(pattern):
            if pod_file.name == 'pods.yaml':
                continue

            pod = parse_yaml_file(pod_file)
            if pod:
                name = pod.get('metadata', {}).get('name', '')
                if name.startswith('ovn-ipsec-host-') and name not in seen_pods:
                    seen_pods.add(name)
                    node = pod.get('spec', {}).get('nodeName', 'Unknown')
                    pod_to_node[name] = node

    # Look for ipsec directories
    ipsec_d_patterns = [
        "network_logs/ipsec/*_ipsec.d",
        "*/network_logs/ipsec/*_ipsec.d"
    ]

    for pattern in ipsec_d_patterns:
        for ipsec_d_dir in must_gather_path.glob(pattern):
            if not ipsec_d_dir.is_dir():
                continue

            # Extract pod name from directory (e.g., "ovn-ipsec-host-abc_ipsec.d" -> "ovn-ipsec-host-abc")
            pod_name = ipsec_d_dir.name.replace('_ipsec.d', '')

            # Apply node filter if specified
            node_name = pod_to_node.get(pod_name, 'Unknown')
            if filter_node and filter_node.lower() != 'all' and node_name != filter_node:
                continue

            openshift_conf = ipsec_d_dir / 'openshift.conf'
            # Status directory is at network_logs/ipsec/status, not inside the pod's ipsec.d directory
            status_dir = ipsec_d_dir.parent / 'status'

            pod_info = {
                'pod': pod_name,
                'node': node_name,
                'config_found': openshift_conf.exists(),
                'status_dir_found': status_dir.exists(),
                'connections': []
            }

            if not openshift_conf.exists():
                pod_info['error'] = 'openshift.conf not found'
                tunnel_analysis['pods'].append(pod_info)
                continue

            # Parse connections from openshift.conf
            connections = parse_ipsec_connections(openshift_conf)
            tunnel_analysis['total_connections'] += len(connections)

            # Status log file follows naming convention: status/<pod_name>.log
            status_log = status_dir / f"{pod_name}.log" if status_dir.exists() else None
            # Check status for each connection
            for conn_name in connections:
                if status_log:

                    conn_status = check_connection_status(status_log, conn_name)
                    established = conn_status['established']
                    info = conn_status['info']
                else:
                    established = False
                    info = 'Status log not found'

                pod_info['connections'].append({
                    'name': conn_name,
                    'established': established,
                    'info': info
                })

                if established:
                    tunnel_analysis['established_connections'] += 1
                else:
                    tunnel_analysis['failed_connections'] += 1

            if not status_dir.exists():
                pod_info['status_warning'] = 'status directory not found'

            tunnel_analysis['pods'].append(pod_info)

    return tunnel_analysis


def print_section_header(title: str):
    """Print a section header with separator lines."""
    print("=" * 100)
    print(title)
    print("=" * 100)


def print_subsection_separator():
    """Print a subsection separator line."""
    print("-" * 100)


def print_ipsec_analysis(ipsec_config: Optional[Dict], ipsec_pods: List[Dict],
                        tunnel_analysis: Dict, filter_node: Optional[str] = None):
    """
    Print the complete IPsec analysis report.

    Follows the format specified in ipsec.md command specification.
    """

    # Section 1: IPsec Configuration
    print_section_header("IPSEC CONFIGURATION")

    if ipsec_config:
        enabled = ipsec_config.get('enabled', False)
        status_symbol = "✓" if enabled else "✗"
        status_text = "ENABLED" if enabled else "DISABLED"

        print(f"Status: {status_symbol} {status_text}")

        if enabled and ipsec_config.get('mode'):
            mode = ipsec_config['mode']
            print(f"Mode:   {mode}")
    else:
        print("Status: Unable to determine IPsec configuration")
        print("(Network configuration not found in must-gather)")

    print()

    # Section 2: OVN-IPSEC-HOST Pods
    print_section_header("OVN-IPSEC-HOST PODS (Daemonset)")
    print()

    if ipsec_pods:
        filter_msg = f" (filtered to node: {filter_node})" if filter_node and filter_node.lower() != 'all' else ""
        print(f"Found {len(ipsec_pods)} ovn-ipsec-host pod(s){filter_msg}:")
        print(f"{'NAME':<40} {'READY':<10} {'STATUS':<15} {'RESTARTS':<10} NODE")
        print_subsection_separator()

        for pod in ipsec_pods:
            name = pod['name'][:40]
            ready = pod['ready']
            status = pod['status'][:15]
            restarts = str(pod['restarts'])
            node = pod['node'][:35]

            # Add warning marker for problematic pods
            marker = ""
            if pod['status'] != 'Running':
                marker = " ⚠"
            elif pod['restarts'] > 5:
                marker = " ⚠"

            print(f"{name:<40} {ready:<10} {status:<15} {restarts:<10} {node}{marker}")
    else:
        if filter_node and filter_node.lower() != 'all':
            print(f"No ovn-ipsec-host pods found for node: {filter_node}")
        else:
            print("No ovn-ipsec-host pods found")
            print("(This is expected if IPsec is not enabled)")

    print()

    # Section 3: IPsec Tunnel Status
    print_section_header("IPSEC TUNNEL STATUS")
    print()

    if tunnel_analysis['pods']:
        print(f"Total Connections: {tunnel_analysis['total_connections']}")
        print(f"Established:       {tunnel_analysis['established_connections']} ✓")
        print(f"Not Established:   {tunnel_analysis['failed_connections']} ✗")
        print()

        for pod_info in tunnel_analysis['pods']:
            print_subsection_separator()
            pod_display = f"Pod: {pod_info['pod']}"
            if pod_info['node'] != 'Unknown':
                pod_display += f" (Node: {pod_info['node']})"
            print(pod_display)
            print_subsection_separator()

            if 'error' in pod_info:
                print(f"  ⚠ Error: {pod_info['error']}")
                print()
                continue

            if not pod_info['config_found']:
                print("  ⚠ Error: openshift.conf not found")
                print()
                continue

            if 'status_warning' in pod_info:
                print(f"  ⚠ {pod_info['status_warning']}")

            if pod_info['connections']:
                print(f"\n  Connections ({len(pod_info['connections'])}):")
                print(f"  {'CONNECTION NAME':<50} {'STATUS':<15} INFO")
                print("  " + "-" * 95)

                for conn in pod_info['connections']:
                    conn_name = conn['name'][:48]
                    marker = "✓" if conn['established'] else "✗"
                    status_text = "ESTABLISHED" if conn['established'] else "NOT ESTABLISHED"
                    info = conn['info'][:40]

                    print(f"  {marker} {conn_name:<48} {status_text:<15} {info}")
            else:
                print("  No connections found in openshift.conf")

            print()
    else:
        if filter_node and filter_node.lower() != 'all':
            print(f"No IPsec tunnel data found for node: {filter_node}")
        else:
            print("No IPsec tunnel data found in network_logs/ipsec/")
            print("(Expected location: network_logs/ipsec/<pod>_ipsec.d/)")

    print()

    # Section 4: Summary
    print_section_header("SUMMARY")
    print()

    issues = []
    mode = ipsec_config.get('mode') if ipsec_config else None

    # Only check for pods and tunnels in Full mode
    # External mode is expected to have no ovn-ipsec-host pods or tunnel data
    if ipsec_config and ipsec_config.get('enabled') and mode == 'Full':
        if not ipsec_pods:
            if filter_node and filter_node.lower() != 'all':
                issues.append(f"No ovn-ipsec-host pods found for node {filter_node}")
            else:
                issues.append("IPsec is enabled but no ovn-ipsec-host pods found")

        if any(p['status'] != 'Running' for p in ipsec_pods):
            issues.append("Some ovn-ipsec-host pods are not in Running state")

        if tunnel_analysis['failed_connections'] > 0:
            issues.append(f"{tunnel_analysis['failed_connections']} IPsec connections not established")

        if not tunnel_analysis['pods'] and not filter_node:
            issues.append("No IPsec tunnel data found in network_logs/ipsec/")

    if issues:
        print("⚠ Issues Detected:")
        for idx, issue in enumerate(issues, 1):
            print(f"{idx}. {issue}")
    else:
        if ipsec_config and ipsec_config.get('enabled'):
            if mode == 'External':
                print("✓ IPsec is enabled in External mode (managed outside of OVN)")
            elif tunnel_analysis['total_connections'] > 0:
                print(f"✓ All {tunnel_analysis['established_connections']} IPsec connections are established")
            else:
                print("✓ IPsec is enabled (no tunnel data available for verification)")
        else:
            print("IPsec is not enabled on this cluster")

    print()


def analyze_ipsec(must_gather_path: str, node_filter: Optional[str] = None):
    """
    Analyze IPsec configuration and status in a must-gather directory.

    Args:
        must_gather_path: Path to the must-gather directory
        node_filter: Optional node name to filter results. None or 'all' for all nodes.

    Returns:
        0 on success, 1 on error
    """
    base_path = Path(must_gather_path)

    if not base_path.exists():
        print(f"Error: Directory not found: {must_gather_path}", file=sys.stderr)
        return 1

    if not base_path.is_dir():
        print(f"Error: Not a directory: {must_gather_path}", file=sys.stderr)
        return 1

    # Normalize node filter
    filter_node = None
    if node_filter and node_filter.lower() != 'all':
        filter_node = node_filter

    # Get IPsec configuration
    ipsec_config = get_ipsec_config(base_path)

    # Only analyze pods and tunnels if IPsec mode is "Full"
    # In "Disabled" or "External" mode, no ovn-ipsec-host pods or tunnels exist
    ipsec_pods = []
    tunnel_analysis = {
        'pods': [],
        'total_connections': 0,
        'established_connections': 0,
        'failed_connections': 0
    }

    mode = ipsec_config.get('mode') if ipsec_config else None
    if mode == 'Full':
        # Analyze ovn-ipsec-host pods
        ipsec_pods = analyze_ovn_ipsec_host_pods(base_path, filter_node)

        # Analyze IPsec tunnels
        tunnel_analysis = analyze_ipsec_tunnels(base_path, filter_node)

    # Print analysis
    print_ipsec_analysis(ipsec_config, ipsec_pods, tunnel_analysis, filter_node)

    return 0


def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("Usage: analyze_ipsec.py <must-gather-directory> [node-name]", file=sys.stderr)
        print("\nArguments:", file=sys.stderr)
        print("  must-gather-directory  Path to the must-gather directory", file=sys.stderr)
        print("  node-name             Optional. Node to analyze (default: all nodes)", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  # Analyze all nodes", file=sys.stderr)
        print("  analyze_ipsec.py ./must-gather.local.123456789", file=sys.stderr)
        print("\n  # Analyze specific node", file=sys.stderr)
        print("  analyze_ipsec.py ./must-gather.local.123456789 worker-0", file=sys.stderr)
        return 1

    must_gather_path = sys.argv[1]
    node_filter = sys.argv[2] if len(sys.argv) > 2 else None

    return analyze_ipsec(must_gather_path, node_filter)


if __name__ == '__main__':
    sys.exit(main())
