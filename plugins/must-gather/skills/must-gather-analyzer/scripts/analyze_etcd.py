#!/usr/bin/env python3
"""
Analyze etcd information from must-gather data.
Shows etcd cluster health, member status, and diagnostics.
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


def parse_etcd_info(must_gather_path: Path) -> Dict[str, Any]:
    """Parse etcd_info directory for cluster health information."""
    etcd_data = {
        'member_health': [],
        'member_list': [],
        'endpoint_health': [],
        'endpoint_status': []
    }

    # Find etcd_info directory
    etcd_dirs = list(must_gather_path.glob("etcd_info")) + \
                list(must_gather_path.glob("*/etcd_info"))

    if not etcd_dirs:
        return etcd_data

    etcd_info_dir = etcd_dirs[0]

    # Parse member health
    member_health_file = etcd_info_dir / "endpoint_health.json"
    if member_health_file.exists():
        try:
            with open(member_health_file, 'r') as f:
                data = json.load(f)
                etcd_data['member_health'] = data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"Warning: Failed to parse endpoint_health.json: {e}", file=sys.stderr)

    # Parse member list
    member_list_file = etcd_info_dir / "member_list.json"
    if member_list_file.exists():
        try:
            with open(member_list_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'members' in data:
                    etcd_data['member_list'] = data['members']
                elif isinstance(data, list):
                    etcd_data['member_list'] = data
        except Exception as e:
            print(f"Warning: Failed to parse member_list.json: {e}", file=sys.stderr)

    # Parse endpoint health
    endpoint_health_file = etcd_info_dir / "endpoint_health.json"
    if endpoint_health_file.exists():
        try:
            with open(endpoint_health_file, 'r') as f:
                data = json.load(f)
                etcd_data['endpoint_health'] = data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"Warning: Failed to parse endpoint_health.json: {e}", file=sys.stderr)

    # Parse endpoint status
    endpoint_status_file = etcd_info_dir / "endpoint_status.json"
    if endpoint_status_file.exists():
        try:
            with open(endpoint_status_file, 'r') as f:
                data = json.load(f)
                etcd_data['endpoint_status'] = data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"Warning: Failed to parse endpoint_status.json: {e}", file=sys.stderr)

    return etcd_data


def print_member_health(members: List[Dict[str, Any]]):
    """Print etcd member health status."""
    if not members:
        print("No member health data found.")
        return

    print("ETCD MEMBER HEALTH")
    print(f"{'ENDPOINT':<60} {'HEALTH':<10} {'TOOK':<10} ERROR")

    for member in members:
        endpoint = member.get('endpoint', 'unknown')[:60]
        health = 'true' if member.get('health') else 'false'
        took = member.get('took', '')
        error = member.get('error', '')

        print(f"{endpoint:<60} {health:<10} {took:<10} {error}")


def print_member_list(members: List[Dict[str, Any]]):
    """Print etcd member list."""
    if not members:
        print("\nNo member list data found.")
        return

    print("\nETCD MEMBER LIST")
    print(f"{'ID':<20} {'NAME':<40} {'PEER URLS':<60} {'CLIENT URLS':<60}")

    for member in members:
        member_id = str(member.get('ID', member.get('id', 'unknown')))[:20]
        name = member.get('name', 'unknown')[:40]
        peer_urls = ','.join(member.get('peerURLs', []))[:60]
        client_urls = ','.join(member.get('clientURLs', []))[:60]

        print(f"{member_id:<20} {name:<40} {peer_urls:<60} {client_urls:<60}")


def print_endpoint_status(endpoints: List[Dict[str, Any]]):
    """Print etcd endpoint status."""
    if not endpoints:
        print("\nNo endpoint status data found.")
        return

    print("\nETCD ENDPOINT STATUS")
    print(f"{'ENDPOINT':<60} {'LEADER':<20} {'VERSION':<10} {'DB SIZE':<10} {'IS LEARNER'}")

    for endpoint in endpoints:
        ep = endpoint.get('Endpoint', 'unknown')[:60]

        status = endpoint.get('Status', {})
        leader = str(status.get('leader', 'unknown'))[:20]
        version = status.get('version', 'unknown')[:10]

        db_size = status.get('dbSize', 0)
        db_size_mb = f"{db_size / (1024*1024):.1f}MB" if db_size else '0MB'

        is_learner = 'true' if status.get('isLearner') else 'false'

        print(f"{ep:<60} {leader:<20} {version:<10} {db_size_mb:<10} {is_learner}")


def print_summary(etcd_data: Dict[str, Any]):
    """Print summary of etcd cluster health."""
    member_health = etcd_data.get('member_health', [])
    member_list = etcd_data.get('member_list', [])

    total_members = len(member_list)
    healthy_members = sum(1 for m in member_health if m.get('health'))

    print(f"\n{'='*80}")
    print(f"ETCD CLUSTER SUMMARY")
    print(f"{'='*80}")
    print(f"Total Members: {total_members}")
    print(f"Healthy Members: {healthy_members}/{len(member_health) if member_health else total_members}")

    if healthy_members < total_members:
        print(f"  ⚠️  Warning: Not all members are healthy!")
    elif healthy_members == total_members and total_members > 0:
        print(f"  ✅ All members healthy")

    # Check for quorum
    if total_members >= 3:
        quorum = (total_members // 2) + 1
        if healthy_members >= quorum:
            print(f"  ✅ Quorum achieved ({healthy_members}/{quorum})")
        else:
            print(f"  ❌ Quorum lost! ({healthy_members}/{quorum})")
    print(f"{'='*80}\n")


def analyze_etcd(must_gather_path: str):
    """Analyze etcd information in a must-gather directory."""
    base_path = Path(must_gather_path)

    etcd_data = parse_etcd_info(base_path)

    if not any(etcd_data.values()):
        print("No etcd_info data found in must-gather.")
        print("Expected location: etcd_info/ directory")
        return 1

    # Print summary first
    print_summary(etcd_data)

    # Print detailed information
    print_member_health(etcd_data.get('member_health', []))
    print_member_list(etcd_data.get('member_list', []))
    print_endpoint_status(etcd_data.get('endpoint_status', []))

    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_etcd.py <must-gather-directory>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  analyze_etcd.py ./must-gather.local.123456789", file=sys.stderr)
        return 1

    must_gather_path = sys.argv[1]

    if not os.path.isdir(must_gather_path):
        print(f"Error: Directory not found: {must_gather_path}", file=sys.stderr)
        return 1

    return analyze_etcd(must_gather_path)


if __name__ == '__main__':
    sys.exit(main())
