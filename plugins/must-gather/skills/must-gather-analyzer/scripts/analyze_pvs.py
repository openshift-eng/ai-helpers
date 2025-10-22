#!/usr/bin/env python3
"""
Analyze PersistentVolumes and PersistentVolumeClaims from must-gather data.
Shows PV/PVC status, capacity, and binding information.
"""

import sys
import os
import yaml
import argparse
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


def format_pv(pv: Dict[str, Any]) -> Dict[str, str]:
    """Format a PersistentVolume for display."""
    name = pv.get('metadata', {}).get('name', 'unknown')
    spec = pv.get('spec', {})
    status = pv.get('status', {})

    capacity = spec.get('capacity', {}).get('storage', '')
    access_modes = ','.join(spec.get('accessModes', []))[:20]
    reclaim_policy = spec.get('persistentVolumeReclaimPolicy', '')
    pv_status = status.get('phase', 'Unknown')

    claim_ref = spec.get('claimRef', {})
    claim = ''
    if claim_ref:
        claim_ns = claim_ref.get('namespace', '')
        claim_name = claim_ref.get('name', '')
        claim = f"{claim_ns}/{claim_name}" if claim_ns else claim_name

    storage_class = spec.get('storageClassName', '')

    return {
        'name': name,
        'capacity': capacity,
        'access_modes': access_modes,
        'reclaim_policy': reclaim_policy,
        'status': pv_status,
        'claim': claim,
        'storage_class': storage_class
    }


def format_pvc(pvc: Dict[str, Any]) -> Dict[str, str]:
    """Format a PersistentVolumeClaim for display."""
    metadata = pvc.get('metadata', {})
    name = metadata.get('name', 'unknown')
    namespace = metadata.get('namespace', 'unknown')
    spec = pvc.get('spec', {})
    status = pvc.get('status', {})

    pvc_status = status.get('phase', 'Unknown')
    volume = spec.get('volumeName', '')
    capacity = status.get('capacity', {}).get('storage', '')
    access_modes = ','.join(status.get('accessModes', []))[:20]
    storage_class = spec.get('storageClassName', '')

    return {
        'namespace': namespace,
        'name': name,
        'status': pvc_status,
        'volume': volume,
        'capacity': capacity,
        'access_modes': access_modes,
        'storage_class': storage_class
    }


def print_pvs_table(pvs: List[Dict[str, str]]):
    """Print PVs in a table format."""
    if not pvs:
        print("No PersistentVolumes found.")
        return

    print("PERSISTENT VOLUMES")
    print(f"{'NAME':<50} {'CAPACITY':<10} {'ACCESS MODES':<20} {'RECLAIM':<10} {'STATUS':<10} {'CLAIM':<40} STORAGECLASS")

    for pv in pvs:
        name = pv['name'][:50]
        capacity = pv['capacity'][:10]
        access = pv['access_modes'][:20]
        reclaim = pv['reclaim_policy'][:10]
        status = pv['status'][:10]
        claim = pv['claim'][:40]
        sc = pv['storage_class']

        print(f"{name:<50} {capacity:<10} {access:<20} {reclaim:<10} {status:<10} {claim:<40} {sc}")


def print_pvcs_table(pvcs: List[Dict[str, str]]):
    """Print PVCs in a table format."""
    if not pvcs:
        print("\nNo PersistentVolumeClaims found.")
        return

    print("\nPERSISTENT VOLUME CLAIMS")
    print(f"{'NAMESPACE':<30} {'NAME':<40} {'STATUS':<10} {'VOLUME':<50} {'CAPACITY':<10} {'ACCESS MODES':<20} STORAGECLASS")

    for pvc in pvcs:
        namespace = pvc['namespace'][:30]
        name = pvc['name'][:40]
        status = pvc['status'][:10]
        volume = pvc['volume'][:50]
        capacity = pvc['capacity'][:10]
        access = pvc['access_modes'][:20]
        sc = pvc['storage_class']

        print(f"{namespace:<30} {name:<40} {status:<10} {volume:<50} {capacity:<10} {access:<20} {sc}")


def analyze_storage(must_gather_path: str, namespace: Optional[str] = None):
    """Analyze PVs and PVCs in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Find PVs (cluster-scoped)
    pv_patterns = [
        "cluster-scoped-resources/core/persistentvolumes/*.yaml",
        "*/cluster-scoped-resources/core/persistentvolumes/*.yaml",
    ]

    pvs = []
    for pattern in pv_patterns:
        for pv_file in base_path.glob(pattern):
            if pv_file.name == 'persistentvolumes.yaml':
                continue
            pv = parse_yaml_file(pv_file)
            if pv and pv.get('kind') == 'PersistentVolume':
                pvs.append(format_pv(pv))

    # Find PVCs (namespace-scoped)
    if namespace:
        pvc_patterns = [
            f"namespaces/{namespace}/core/persistentvolumeclaims.yaml",
            f"*/namespaces/{namespace}/core/persistentvolumeclaims.yaml",
        ]
    else:
        pvc_patterns = [
            "namespaces/*/core/persistentvolumeclaims.yaml",
            "*/namespaces/*/core/persistentvolumeclaims.yaml",
        ]

    pvcs = []
    for pattern in pvc_patterns:
        for pvc_file in base_path.glob(pattern):
            pvc_doc = parse_yaml_file(pvc_file)
            if pvc_doc:
                if pvc_doc.get('kind') == 'PersistentVolumeClaim':
                    pvcs.append(format_pvc(pvc_doc))
                elif pvc_doc.get('kind') == 'List':
                    for item in pvc_doc.get('items', []):
                        if item.get('kind') == 'PersistentVolumeClaim':
                            pvcs.append(format_pvc(item))

    # Remove duplicates
    seen_pvs = set()
    unique_pvs = []
    for pv in pvs:
        if pv['name'] not in seen_pvs:
            seen_pvs.add(pv['name'])
            unique_pvs.append(pv)

    seen_pvcs = set()
    unique_pvcs = []
    for pvc in pvcs:
        key = f"{pvc['namespace']}/{pvc['name']}"
        if key not in seen_pvcs:
            seen_pvcs.add(key)
            unique_pvcs.append(pvc)

    # Sort
    unique_pvs.sort(key=lambda x: x['name'])
    unique_pvcs.sort(key=lambda x: (x['namespace'], x['name']))

    # Print results
    print_pvs_table(unique_pvs)
    print_pvcs_table(unique_pvcs)

    # Summary
    total_pvs = len(unique_pvs)
    bound_pvs = sum(1 for pv in unique_pvs if pv['status'] == 'Bound')
    available_pvs = sum(1 for pv in unique_pvs if pv['status'] == 'Available')

    total_pvcs = len(unique_pvcs)
    bound_pvcs = sum(1 for pvc in unique_pvcs if pvc['status'] == 'Bound')
    pending_pvcs = sum(1 for pvc in unique_pvcs if pvc['status'] == 'Pending')

    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"PVs: {total_pvs} total ({bound_pvs} bound, {available_pvs} available)")
    print(f"PVCs: {total_pvcs} total ({bound_pvcs} bound, {pending_pvcs} pending)")
    if pending_pvcs > 0:
        print(f"  ⚠️  {pending_pvcs} PVC(s) pending - check storage provisioner")
    print(f"{'='*80}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze PVs and PVCs from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./must-gather
  %(prog)s ./must-gather --namespace openshift-monitoring
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('-n', '--namespace', help='Filter PVCs by namespace')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_storage(args.must_gather_path, args.namespace)


if __name__ == '__main__':
    sys.exit(main())
