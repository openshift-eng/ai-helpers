#!/usr/bin/env python3
"""
Analyze Network resources and diagnostics from must-gather data.
Shows network operator status, OVN pods, and connectivity checks.
"""

import sys
import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional


def parse_yaml_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a YAML file."""
    try:
        with open(file_path, 'r') as f:
            doc = yaml.safe_load(f)
            return doc
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return None


def get_network_type(must_gather_path: Path) -> str:
    """Determine the network type from cluster network config."""
    # First try to find networks.yaml (List object)
    patterns = [
        "cluster-scoped-resources/config.openshift.io/networks.yaml",
        "*/cluster-scoped-resources/config.openshift.io/networks.yaml",
    ]

    for pattern in patterns:
        for network_file in must_gather_path.glob(pattern):
            network_list = parse_yaml_file(network_file)
            if network_list:
                # Handle NetworkList object
                items = network_list.get('items', [])
                if items:
                    # Get the first network item
                    network = items[0]
                    spec = network.get('spec', {})
                    network_type = spec.get('networkType', 'Unknown')
                    if network_type != 'Unknown':
                        return network_type

    # Fallback: try individual network config files
    patterns = [
        "cluster-scoped-resources/config.openshift.io/*.yaml",
    ]

    for pattern in patterns:
        for network_file in must_gather_path.glob(pattern):
            if network_file.name in ['networks.yaml']:
                continue

            network = parse_yaml_file(network_file)
            if network:
                spec = network.get('spec', {})
                network_type = spec.get('networkType', 'Unknown')
                if network_type != 'Unknown':
                    return network_type

    return 'Unknown'


def analyze_network_operator(must_gather_path: Path) -> Optional[Dict[str, Any]]:
    """Analyze network operator status."""
    patterns = [
        "cluster-scoped-resources/config.openshift.io/clusteroperators/network.yaml",
        "*/cluster-scoped-resources/config.openshift.io/clusteroperators/network.yaml",
    ]

    for pattern in patterns:
        for op_file in must_gather_path.glob(pattern):
            operator = parse_yaml_file(op_file)
            if operator:
                conditions = operator.get('status', {}).get('conditions', [])
                result = {}

                for cond in conditions:
                    cond_type = cond.get('type')
                    if cond_type in ['Available', 'Progressing', 'Degraded']:
                        result[cond_type] = cond.get('status', 'Unknown')
                        result[f'{cond_type}_message'] = cond.get('message', '')

                return result

    return None


def analyze_ovn_pods(must_gather_path: Path) -> List[Dict[str, str]]:
    """Analyze OVN-Kubernetes pods."""
    pods = []

    patterns = [
        "namespaces/openshift-ovn-kubernetes/pods/*/*.yaml",
        "*/namespaces/openshift-ovn-kubernetes/pods/*/*.yaml",
    ]

    for pattern in patterns:
        for pod_file in must_gather_path.glob(pattern):
            if pod_file.name == 'pods.yaml':
                continue

            pod = parse_yaml_file(pod_file)
            if pod:
                name = pod.get('metadata', {}).get('name', 'unknown')
                status = pod.get('status', {})
                phase = status.get('phase', 'Unknown')

                container_statuses = status.get('containerStatuses', [])
                total = len(pod.get('spec', {}).get('containers', []))
                ready = sum(1 for cs in container_statuses if cs.get('ready', False))

                pods.append({
                    'name': name,
                    'ready': f"{ready}/{total}",
                    'status': phase
                })

    # Remove duplicates
    seen = set()
    unique_pods = []
    for p in pods:
        if p['name'] not in seen:
            seen.add(p['name'])
            unique_pods.append(p)

    return sorted(unique_pods, key=lambda x: x['name'])


def analyze_connectivity_checks(must_gather_path: Path) -> Dict[str, Any]:
    """Analyze PodNetworkConnectivityCheck resources."""
    # First try to find podnetworkconnectivitychecks.yaml (List object)
    patterns = [
        "pod_network_connectivity_check/podnetworkconnectivitychecks.yaml",
        "*/pod_network_connectivity_check/podnetworkconnectivitychecks.yaml",
    ]

    total_checks = 0
    failed_checks = []

    for pattern in patterns:
        for check_file in must_gather_path.glob(pattern):
            check_list = parse_yaml_file(check_file)
            if check_list:
                items = check_list.get('items', [])
                for check in items:
                    total_checks += 1
                    name = check.get('metadata', {}).get('name', 'unknown')
                    status = check.get('status', {})

                    conditions = status.get('conditions', [])
                    for cond in conditions:
                        if cond.get('type') == 'Reachable' and cond.get('status') == 'False':
                            failed_checks.append({
                                'name': name,
                                'message': cond.get('message', 'Unknown')
                            })

                # If we found the list file, no need to continue
                if total_checks > 0:
                    return {
                        'total': total_checks,
                        'failed': failed_checks
                    }

    # Fallback: try individual check files
    patterns = [
        "*/pod_network_connectivity_check/*.yaml",
    ]

    for pattern in patterns:
        for check_file in must_gather_path.glob(pattern):
            if check_file.name == 'podnetworkconnectivitychecks.yaml':
                continue

            check = parse_yaml_file(check_file)
            if check:
                total_checks += 1
                name = check.get('metadata', {}).get('name', 'unknown')
                status = check.get('status', {})

                conditions = status.get('conditions', [])
                for cond in conditions:
                    if cond.get('type') == 'Reachable' and cond.get('status') == 'False':
                        failed_checks.append({
                            'name': name,
                            'message': cond.get('message', 'Unknown')
                        })

    return {
        'total': total_checks,
        'failed': failed_checks
    }


def print_network_summary(network_type: str, operator_status: Optional[Dict],
                         ovn_pods: List[Dict], connectivity: Dict):
    """Print network analysis summary."""
    print(f"{'NETWORK TYPE':<30} {network_type}")
    print()

    if operator_status:
        print("NETWORK OPERATOR STATUS")
        print(f"{'Available':<15} {operator_status.get('Available', 'Unknown')}")
        print(f"{'Progressing':<15} {operator_status.get('Progressing', 'Unknown')}")
        print(f"{'Degraded':<15} {operator_status.get('Degraded', 'Unknown')}")

        if operator_status.get('Degraded') == 'True':
            msg = operator_status.get('Degraded_message', '')
            if msg:
                print(f"  Message: {msg}")
        print()

    if ovn_pods and network_type == 'OVNKubernetes':
        print("OVN-KUBERNETES PODS")
        print(f"{'NAME':<60} {'READY':<10} STATUS")
        for pod in ovn_pods:
            name = pod['name'][:60]
            ready = pod['ready'][:10]
            status = pod['status']
            print(f"{name:<60} {ready:<10} {status}")
        print()

    if connectivity['total'] > 0:
        print(f"NETWORK CONNECTIVITY CHECKS: {connectivity['total']} total")
        if connectivity['failed']:
            print(f"  Failed: {len(connectivity['failed'])}")
            for failed in connectivity['failed'][:10]:  # Show first 10
                print(f"    - {failed['name']}")
                if failed['message']:
                    print(f"      {failed['message'][:100]}")
        else:
            print("  All checks passing")
        print()


def analyze_network(must_gather_path: str):
    """Analyze network resources in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Get network type
    network_type = get_network_type(base_path)

    # Get network operator status
    operator_status = analyze_network_operator(base_path)

    # Get OVN pods if applicable
    ovn_pods = []
    if network_type == 'OVNKubernetes':
        ovn_pods = analyze_ovn_pods(base_path)

    # Get connectivity checks
    connectivity = analyze_connectivity_checks(base_path)

    # Print summary
    print_network_summary(network_type, operator_status, ovn_pods, connectivity)

    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_network.py <must-gather-directory>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  analyze_network.py ./must-gather.local.123456789", file=sys.stderr)
        return 1

    must_gather_path = sys.argv[1]

    if not os.path.isdir(must_gather_path):
        print(f"Error: Directory not found: {must_gather_path}", file=sys.stderr)
        return 1

    return analyze_network(must_gather_path)


if __name__ == '__main__':
    sys.exit(main())
