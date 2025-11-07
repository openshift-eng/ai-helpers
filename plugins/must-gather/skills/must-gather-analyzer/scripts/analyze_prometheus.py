#!/usr/bin/env python3
"""
Analyze Prometheus data from must-gather data.
Shows Prometheus status, targets, and active alerts.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

def parse_json_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a JSON file."""
    try:
        with open(file_path, 'r') as f:
            doc = json.load(f)
            return doc
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return None


def print_alerts_table(alerts):
    """Print alerts in a table format."""
    if not alerts:
        print("No alerts found.")
        return

    print("ALERTS")
    print(f"{'STATE':<10} {'NAMESPACE':<50} {'NAME':<50} {'SEVERITY':<10} {'SINCE':<20} LABELS")

    for alert in alerts:
        state = alert.get('state', '')
        since = alert.get('activeAt', '')[:19] + 'Z' # timestamps are always UTC.
        labels = alert.get('labels', {})
        namespace = labels.pop('namespace', '')[:50]
        name = labels.pop('alertname', '')[:50]
        severity = labels.pop('severity', '')[:10]

        print(f"{state:<10} {namespace:<50} {name:<50} {severity:<10} {since:<20} {labels}")


def analyze_prometheus(must_gather_path: str, namespace: Optional[str] = None):
    """Analyze Prometheus data in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Retrieve active alerts.
    rules_file = f"{base_path}/monitoring/prometheus/rules.json"
    rules = parse_json_file(rules_file)
    if rules is None:
        return 1
    status = rules.get("status", "")
    if status != "success":
        print(f"{rules_file}: unexpected status ${status}")
        return 1

    if "data" not in rules or "groups" not in rules["data"]:
        print(f"Error: Unexpected JSON structure in {rules_file}", file=sys.stderr)
        return 1

    alerts = []
    for group in rules["data"]["groups"]:
        for rule in group["rules"]:
            if rule["type"] == 'alerting' and rule["state"] != 'inactive':
                for alert in rule["alerts"]:
                    if namespace is None or namespace == '':
                        alerts.append(alert)
                    elif alert.get('labels', {}).get('namespace', '') == namespace:
                        alerts.append(alert)

    # Sort alerts by namespace, alertname and severity.
    alerts.sort(key=lambda x: (x.get('labels', {}).get('namespace', ''), x.get('labels', {}).get('alertname', ''), x.get('labels', {}).get('severity', '')))

    # Print results
    print_alerts_table(alerts)

    # Summary
    total_alerts = len(alerts)
    pending = sum(1 for alert in alerts if alert['state'] == 'pending')
    firing = sum(1 for alert in alerts if alert['state'] == 'firing')

    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"Active alerts: {total_alerts} total ({pending} pending, {firing} firing)")
    print(f"{'='*80}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze Prometheus data from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./must-gather
  %(prog)s ./must-gather --namespace openshift-monitoring
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('-n', '--namespace', help='Filter information by namespace')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_prometheus(args.must_gather_path, args.namespace)


if __name__ == '__main__':
    sys.exit(main())

