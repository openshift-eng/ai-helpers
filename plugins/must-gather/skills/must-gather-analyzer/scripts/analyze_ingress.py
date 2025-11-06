#!/usr/bin/env python3
"""
Analyze IngressControllers and Routes from must-gather data.
Displays output similar to 'oc get ingresscontroller' and 'oc get routes' commands.
"""

import sys
import os
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict


def parse_ingresscontroller(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse an IngressController YAML file."""
    try:
        with open(file_path, 'r') as f:
            doc = yaml.safe_load(f)
            if doc and doc.get('kind') == 'IngressController':
                return doc
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return None


def parse_routes(file_path: Path) -> List[Dict[str, Any]]:
    """Parse routes from a RouteList YAML file."""
    routes = []
    try:
        with open(file_path, 'r') as f:
            doc = yaml.safe_load(f)
            if doc and doc.get('kind') == 'RouteList':
                items = doc.get('items')
                if items is not None:
                    routes.extend(items)
            elif doc and doc.get('kind') == 'Route':
                routes.append(doc)
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return routes


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


def format_ingresscontroller(ic: Dict[str, Any]) -> Dict[str, str]:
    """Format IngressController for display."""
    name = ic.get('metadata', {}).get('name', '')
    status = ic.get('status', {})
    spec = ic.get('spec', {})

    # Get conditions
    conditions = status.get('conditions', [])
    available = get_condition_status(conditions, 'Available')
    progressing = get_condition_status(conditions, 'Progressing')
    degraded = get_condition_status(conditions, 'Degraded')

    # Get replica counts
    replicas = spec.get('replicas', 0)
    available_replicas = status.get('availableReplicas', 0)

    # Get domain
    domain = status.get('domain', '')

    # Get endpoint publishing strategy
    endpoint_strategy = status.get('endpointPublishingStrategy', {})
    publish_type = endpoint_strategy.get('type', '')

    # Get age from creation timestamp
    creation_time = ic.get('metadata', {}).get('creationTimestamp', '')
    age = calculate_duration(creation_time) if creation_time else ''

    return {
        'name': name,
        'domain': domain,
        'replicas': f"{available_replicas}/{replicas}",
        'available': available,
        'progressing': progressing,
        'degraded': degraded,
        'publish_type': publish_type,
        'age': age
    }


def format_route(route: Dict[str, Any], namespace: str) -> Dict[str, str]:
    """Format Route for display."""
    name = route.get('metadata', {}).get('name', '')
    spec = route.get('spec', {})
    status = route.get('status', {})

    # Get host
    host = spec.get('host', '')

    # Get target service
    to = spec.get('to', {})
    service = to.get('name', '')

    # Get TLS termination
    tls = spec.get('tls', {})
    termination = tls.get('termination', '') if tls else ''

    # Get admission status
    ingress_list = status.get('ingress', [])
    admitted = 'False'
    if ingress_list:
        for ingress in ingress_list:
            conditions = ingress.get('conditions', [])
            for condition in conditions:
                if condition.get('type') == 'Admitted':
                    admitted = condition.get('status', 'Unknown')
                    break

    # Get age
    creation_time = route.get('metadata', {}).get('creationTimestamp', '')
    age = calculate_duration(creation_time) if creation_time else ''

    return {
        'namespace': namespace,
        'name': name,
        'host': host,
        'service': service,
        'termination': termination,
        'admitted': admitted,
        'age': age
    }


def print_ingresscontroller_table(ic_list: List[Dict[str, str]]):
    """Print IngressControllers in a formatted table."""
    if not ic_list:
        print("No IngressControllers found.")
        return

    # Print header
    print(f"{'NAME':<20} {'DOMAIN':<60} {'REPLICAS':<10} {'AVAILABLE':<11} {'PROGRESSING':<13} {'DEGRADED':<10} TYPE")

    # Print rows
    for ic in ic_list:
        name = ic['name'][:20]
        domain = ic['domain'][:60]
        replicas = ic['replicas'][:10]
        available = ic['available'][:11]
        progressing = ic['progressing'][:13]
        degraded = ic['degraded'][:10]
        publish_type = ic['publish_type']

        print(f"{name:<20} {domain:<60} {replicas:<10} {available:<11} {progressing:<13} {degraded:<10} {publish_type}")


def print_route_table(route_list: List[Dict[str, str]], namespace_filter: str = None):
    """Print Routes in a formatted table."""
    if not route_list:
        if namespace_filter:
            print(f"No Routes found in namespace '{namespace_filter}'.")
        else:
            print("No Routes found.")
        return

    # Print header
    print(f"{'NAMESPACE':<30} {'NAME':<40} {'HOST':<80} {'ADMITTED':<10} AGE")

    # Print rows
    for route in route_list:
        namespace = route['namespace'][:30]
        name = route['name'][:40]
        host = route['host'][:80]
        admitted = route['admitted'][:10]
        age = route['age']

        print(f"{namespace:<30} {name:<40} {host:<80} {admitted:<10} {age}")


def print_ingresscontroller_details(ic_list: List[Dict[str, Any]]):
    """Print detailed IngressController information."""
    if not ic_list:
        return

    print(f"\n{'='*80}")
    print("INGRESSCONTROLLER DETAILS")
    print(f"{'='*80}\n")

    for ic in ic_list:
        name = ic.get('metadata', {}).get('name', 'unknown')
        status = ic.get('status', {})
        spec = ic.get('spec', {})

        print(f"IngressController: {name}")
        print(f"  Domain: {status.get('domain', 'unknown')}")
        print(f"  Replicas: {status.get('availableReplicas', 0)}/{spec.get('replicas', 0)}")

        # Endpoint publishing strategy
        endpoint_strategy = status.get('endpointPublishingStrategy', {})
        print(f"  Publishing Type: {endpoint_strategy.get('type', 'unknown')}")

        # Conditions
        conditions = status.get('conditions', [])
        print(f"  Conditions:")

        important_conditions = ['Available', 'Progressing', 'Degraded', 'LoadBalancerReady', 'DNSReady']
        for cond_type in important_conditions:
            for condition in conditions:
                if condition.get('type') == cond_type:
                    cond_status = condition.get('status', 'Unknown')
                    message = condition.get('message', '')

                    status_indicator = "✅" if cond_status == "True" else "❌" if cond_status == "False" else "❓"
                    print(f"    {status_indicator} {cond_type}: {cond_status}")
                    if message and cond_status == 'True':
                        print(f"       {message[:100]}")
                    break

        print()


def analyze_ingresscontrollers(must_gather_path: str):
    """Analyze IngressControllers in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Find IngressController files
    patterns = [
        "namespaces/openshift-ingress-operator/operator.openshift.io/ingresscontrollers/*.yaml",
        "*/namespaces/openshift-ingress-operator/operator.openshift.io/ingresscontrollers/*.yaml",
    ]

    ic_list = []
    for pattern in patterns:
        for ic_file in base_path.glob(pattern):
            ic = parse_ingresscontroller(ic_file)
            if ic:
                ic_list.append(ic)

    if not ic_list:
        print("No IngressControllers found.")
        return 1

    # Format and print table
    ic_info_list = [format_ingresscontroller(ic) for ic in ic_list]
    print_ingresscontroller_table(ic_info_list)

    # Print detailed information
    print_ingresscontroller_details(ic_list)

    # Summary
    total = len(ic_list)
    available = sum(1 for ic in ic_info_list if ic['available'] == 'True')
    degraded = sum(1 for ic in ic_info_list if ic['degraded'] == 'True')

    print(f"{'='*80}")
    print(f"SUMMARY: {available}/{total} IngressControllers available")
    if degraded > 0:
        print(f"  ⚠️  {degraded} IngressController(s) degraded")
    else:
        print(f"  ✅ No issues found")
    print(f"{'='*80}\n")

    return 0


def analyze_routes(must_gather_path: str, namespace: str = None, problems_only: bool = False):
    """Analyze Routes in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Find route files
    patterns = [
        "namespaces/*/route.openshift.io/routes.yaml",
        "*/namespaces/*/route.openshift.io/routes.yaml",
    ]

    routes = []
    for pattern in patterns:
        for route_file in base_path.glob(pattern):
            # Extract namespace from path
            parts = route_file.parts
            ns_index = parts.index('namespaces') + 1
            if ns_index < len(parts):
                ns = parts[ns_index]
                route_list = parse_routes(route_file)
                for route in route_list:
                    routes.append((ns, route))

    if not routes:
        print("No Routes found.")
        return 1

    # Format routes
    route_info_list = [format_route(route, ns) for ns, route in routes]

    # Filter by namespace if specified
    if namespace:
        route_info_list = [r for r in route_info_list if r['namespace'] == namespace]

    # Filter problems only
    if problems_only:
        route_info_list = [r for r in route_info_list if r['admitted'] != 'True']

    # Sort by namespace, then name
    route_info_list.sort(key=lambda r: (r['namespace'], r['name']))

    # Print table (no longer needs to filter by namespace)
    print_route_table(route_info_list, namespace)

    # Summary
    total = len(route_info_list)
    admitted = sum(1 for r in route_info_list if r['admitted'] == 'True')
    not_admitted = total - admitted

    print(f"\n{'='*80}")
    print(f"SUMMARY: {admitted}/{total} Routes admitted")
    if not_admitted > 0:
        print(f"  ⚠️  {not_admitted} Route(s) not admitted")
    else:
        print(f"  ✅ All routes admitted")
    print(f"{'='*80}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze IngressControllers and Routes from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze IngressControllers
  %(prog)s ./must-gather --ingresscontrollers

  # Analyze Routes (all namespaces)
  %(prog)s ./must-gather --routes

  # Routes in specific namespace
  %(prog)s ./must-gather --routes --namespace openshift-console

  # Only routes with problems
  %(prog)s ./must-gather --routes --problems-only
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('--ingresscontrollers', action='store_true',
                        help='Analyze IngressControllers')
    parser.add_argument('--routes', action='store_true',
                        help='Analyze Routes')
    parser.add_argument('-n', '--namespace', help='Filter by namespace (for routes)')
    parser.add_argument('-p', '--problems-only', action='store_true',
                        help='Show only routes with problems')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    # Default to showing both if neither flag specified
    show_ic = args.ingresscontrollers or (not args.routes and not args.ingresscontrollers)
    show_routes = args.routes or (not args.routes and not args.ingresscontrollers)

    exit_code = 0

    if show_ic:
        exit_code = analyze_ingresscontrollers(args.must_gather_path)

    if show_routes:
        if show_ic:
            print("\n")  # Spacing between sections
        route_exit = analyze_routes(args.must_gather_path, args.namespace, args.problems_only)
        if route_exit != 0:
            exit_code = route_exit

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
