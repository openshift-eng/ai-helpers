#!/usr/bin/env python3
"""
Analyze MachineConfigPools from must-gather data.
Displays output similar to 'oc get mcp' command.

MachineConfigPools manage the rollout of machine configurations to nodes.
Issues here commonly indicate stuck node updates or upgrade problems.
"""

import sys
import os
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def parse_machineconfigpool(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a MachineConfigPool YAML file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()

            # Check if file is redacted
            if content == "REDACTED" or not content:
                return None

            doc = yaml.safe_load(content)
            if doc and doc.get('kind') == 'MachineConfigPool':
                return doc
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return None


def get_condition_status(conditions: list, condition_type: str) -> str:
    """Get status for a specific condition type."""
    if not conditions:
        return 'Unknown'
    for condition in conditions:
        if condition.get('type') == condition_type:
            return condition.get('status', 'Unknown')
    return 'Unknown'


def get_condition_message(conditions: list, condition_type: str) -> str:
    """Get message for a specific condition type."""
    if not conditions:
        return ''
    for condition in conditions:
        if condition.get('type') == condition_type:
            return condition.get('message', '')
    return ''


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


def format_machineconfigpool(mcp: Dict[str, Any]) -> Dict[str, str]:
    """Format MachineConfigPool for display."""
    name = mcp.get('metadata', {}).get('name', '')
    status = mcp.get('status', {})

    # Get configuration info
    config = status.get('configuration', {})
    current_config = config.get('name', '')

    # Get machine counts
    machine_count = status.get('machineCount', 0)
    ready_machine_count = status.get('readyMachineCount', 0)
    updated_machine_count = status.get('updatedMachineCount', 0)
    degraded_machine_count = status.get('degradedMachineCount', 0)

    # Get conditions
    conditions = status.get('conditions', [])
    updated = get_condition_status(conditions, 'Updated')
    updating = get_condition_status(conditions, 'Updating')
    degraded = get_condition_status(conditions, 'Degraded')

    return {
        'name': name,
        'config': current_config,
        'updated': updated,
        'updating': updating,
        'degraded': degraded,
        'machine_count': str(machine_count),
        'ready_count': str(ready_machine_count),
        'updated_count': str(updated_machine_count),
        'degraded_count': str(degraded_machine_count),
    }


def print_mcp_table(mcp_list: List[Dict[str, str]]):
    """Print MachineConfigPools in a formatted table."""
    if not mcp_list:
        print("No MachineConfigPools found.")
        return

    # Print header (similar to oc get mcp)
    print(f"{'NAME':<20} {'CONFIG':<50} {'UPDATED':<9} {'UPDATING':<10} {'DEGRADED':<10} {'MACHINECOUNT':<14} {'READYMACHINECOUNT':<18} {'UPDATEDMACHINECOUNT':<20} {'DEGRADEDMACHINECOUNT':<21}")

    # Print rows
    for mcp in mcp_list:
        name = mcp['name'][:20]
        config = mcp['config'][:50]
        updated = mcp['updated'][:9]
        updating = mcp['updating'][:10]
        degraded = mcp['degraded'][:10]
        machine_count = mcp['machine_count'][:14]
        ready_count = mcp['ready_count'][:18]
        updated_count = mcp['updated_count'][:20]
        degraded_count = mcp['degraded_count'][:21]

        print(f"{name:<20} {config:<50} {updated:<9} {updating:<10} {degraded:<10} {machine_count:<14} {ready_count:<18} {updated_count:<20} {degraded_count:<21}")


def print_mcp_details(mcp_list: List[Dict[str, Any]]):
    """Print detailed MachineConfigPool information."""
    if not mcp_list:
        return

    print(f"\n{'='*80}")
    print("MACHINECONFIGPOOL DETAILS")
    print(f"{'='*80}\n")

    for mcp in mcp_list:
        name = mcp.get('metadata', {}).get('name', 'unknown')
        status = mcp.get('status', {})

        print(f"MachineConfigPool: {name}")

        # Configuration
        config = status.get('configuration', {})
        print(f"  Current Config: {config.get('name', 'unknown')}")

        # Machine counts
        machine_count = status.get('machineCount', 0)
        ready_count = status.get('readyMachineCount', 0)
        updated_count = status.get('updatedMachineCount', 0)
        degraded_count = status.get('degradedMachineCount', 0)
        unavailable_count = status.get('unavailableMachineCount', 0)

        print(f"  Machines: {ready_count}/{machine_count} ready, {updated_count}/{machine_count} updated")
        if degraded_count > 0:
            print(f"  ⚠️  Degraded Machines: {degraded_count}")
        if unavailable_count > 0:
            print(f"  ⚠️  Unavailable Machines: {unavailable_count}")

        # Conditions
        conditions = status.get('conditions', [])
        print(f"  Conditions:")

        important_conditions = ['Updated', 'Updating', 'Degraded', 'RenderDegraded', 'NodeDegraded']
        for cond_type in important_conditions:
            for condition in conditions:
                if condition.get('type') == cond_type:
                    cond_status = condition.get('status', 'Unknown')
                    message = condition.get('message', '')
                    reason = condition.get('reason', '')

                    # For Updating and Degraded, True is a warning; for Updated, False is a warning
                    if cond_type in ['Updating', 'Degraded', 'RenderDegraded', 'NodeDegraded']:
                        status_indicator = "⚠️" if cond_status == "True" else "✅"
                    else:  # Updated
                        status_indicator = "✅" if cond_status == "True" else "⚠️"

                    print(f"    {status_indicator} {cond_type}: {cond_status}")
                    if message and cond_status == 'True':
                        print(f"       Reason: {reason}")
                        print(f"       Message: {message[:150]}")
                    break

        print()


def analyze_machineconfigpools(must_gather_path: str, problems_only: bool = False):
    """Analyze MachineConfigPools in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Find MachineConfigPool files
    patterns = [
        "cluster-scoped-resources/machineconfiguration.openshift.io/machineconfigpools/*.yaml",
        "cluster-scoped-resources/machineconfiguration.openshift.io/machineconfigpools/*.yaml.redacted",
        "*/cluster-scoped-resources/machineconfiguration.openshift.io/machineconfigpools/*.yaml",
        "*/cluster-scoped-resources/machineconfiguration.openshift.io/machineconfigpools/*.yaml.redacted",
    ]

    mcp_list = []
    redacted_count = 0

    for pattern in patterns:
        for mcp_file in base_path.glob(pattern):
            mcp = parse_machineconfigpool(mcp_file)
            if mcp is None and mcp_file.name.endswith('.redacted'):
                redacted_count += 1
            elif mcp:
                mcp_list.append(mcp)

    if not mcp_list and redacted_count > 0:
        print(f"Found {redacted_count} MachineConfigPool(s) but data is redacted.")
        return 1

    if not mcp_list:
        print("No MachineConfigPools found.")
        return 1

    # Filter problems only if requested
    if problems_only:
        filtered_list = []
        for mcp in mcp_list:
            status = mcp.get('status', {})
            conditions = status.get('conditions', [])

            # Check if there are problems
            degraded = get_condition_status(conditions, 'Degraded') == 'True'
            updating = get_condition_status(conditions, 'Updating') == 'True'
            not_updated = get_condition_status(conditions, 'Updated') == 'False'
            degraded_machines = status.get('degradedMachineCount', 0) > 0

            if degraded or not_updated or degraded_machines or updating:
                filtered_list.append(mcp)

        mcp_list = filtered_list

        if not mcp_list:
            print("No MachineConfigPools with problems found.")
            return 0

    # Format and print table
    mcp_info_list = [format_machineconfigpool(mcp) for mcp in mcp_list]
    print_mcp_table(mcp_info_list)

    # Print detailed information
    print_mcp_details(mcp_list)

    # Summary
    total = len(mcp_list)
    degraded = sum(1 for mcp in mcp_info_list if mcp['degraded'] == 'True')
    updating = sum(1 for mcp in mcp_info_list if mcp['updating'] == 'True')
    not_updated = sum(1 for mcp in mcp_info_list if mcp['updated'] == 'False')

    print(f"{'='*80}")
    print(f"SUMMARY: {total} MachineConfigPool(s)")
    if degraded > 0:
        print(f"  ⚠️  {degraded} pool(s) degraded")
    if not_updated > 0:
        print(f"  ⚠️  {not_updated} pool(s) not fully updated")
    if updating > 0:
        print(f"  🔄 {updating} pool(s) updating")
    if degraded == 0 and not_updated == 0:
        print(f"  ✅ All pools healthy and updated")
    print(f"{'='*80}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze MachineConfigPools from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show all MachineConfigPools
  %(prog)s ./must-gather

  # Show only pools with problems
  %(prog)s ./must-gather --problems-only
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('-p', '--problems-only', action='store_true',
                        help='Show only MachineConfigPools with problems')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_machineconfigpools(args.must_gather_path, args.problems_only)


if __name__ == '__main__':
    sys.exit(main())
