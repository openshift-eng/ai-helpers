#!/usr/bin/env python3
"""
Analyze Events from must-gather data.
Shows warning and error events sorted by last occurrence.
"""

import sys
import os
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict


def parse_events_file(file_path: Path) -> List[Dict[str, Any]]:
    """Parse events YAML file which may contain multiple events."""
    events = []
    try:
        with open(file_path, 'r') as f:
            docs = yaml.safe_load_all(f)
            for doc in docs:
                if doc and doc.get('kind') == 'Event':
                    events.append(doc)
                elif doc and doc.get('kind') == 'EventList':
                    # Handle EventList
                    events.extend(doc.get('items', []))
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return events


def calculate_age(timestamp_str: str) -> str:
    """Calculate age from timestamp."""
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


def format_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Format an event for display."""
    metadata = event.get('metadata', {})

    namespace = metadata.get('namespace', '')
    name = metadata.get('name', 'unknown')

    # Get last timestamp
    last_timestamp = event.get('lastTimestamp') or event.get('eventTime') or metadata.get('creationTimestamp', '')
    age = calculate_age(last_timestamp) if last_timestamp else ''

    # Event details
    event_type = event.get('type', 'Normal')
    reason = event.get('reason', '')
    message = event.get('message', '')
    count = event.get('count', 1)

    # Involved object
    involved = event.get('involvedObject', {})
    obj_kind = involved.get('kind', '')
    obj_name = involved.get('name', '')

    return {
        'namespace': namespace,
        'last_seen': age,
        'type': event_type,
        'reason': reason,
        'object_kind': obj_kind,
        'object_name': obj_name,
        'message': message,
        'count': count,
        'timestamp': last_timestamp
    }


def print_events_table(events: List[Dict[str, Any]]):
    """Print events in a table format."""
    if not events:
        print("No resources found.")
        return

    # Print header
    print(f"{'NAMESPACE':<30} {'LAST SEEN':<10} {'TYPE':<10} {'REASON':<30} {'OBJECT':<40} {'MESSAGE':<60}")

    # Print rows
    for event in events:
        namespace = event['namespace'][:30] if event['namespace'] else '<cluster>'
        last_seen = event['last_seen'][:10]
        event_type = event['type'][:10]
        reason = event['reason'][:30]
        obj = f"{event['object_kind']}/{event['object_name']}"[:40]
        message = event['message'][:60]

        print(f"{namespace:<30} {last_seen:<10} {event_type:<10} {reason:<30} {obj:<40} {message:<60}")


def analyze_events(must_gather_path: str, namespace: Optional[str] = None,
                   event_type: Optional[str] = None, show_count: int = 100):
    """Analyze events in a must-gather directory."""
    base_path = Path(must_gather_path)

    all_events = []

    # Find all events files
    if namespace:
        patterns = [
            f"namespaces/{namespace}/core/events.yaml",
            f"*/namespaces/{namespace}/core/events.yaml",
        ]
    else:
        patterns = [
            "namespaces/*/core/events.yaml",
            "*/namespaces/*/core/events.yaml",
        ]

    for pattern in patterns:
        for events_file in base_path.glob(pattern):
            events = parse_events_file(events_file)
            all_events.extend(events)

    if not all_events:
        print("No resources found.")
        return 1

    # Format events
    formatted_events = [format_event(e) for e in all_events]

    # Filter by type if specified
    if event_type:
        formatted_events = [e for e in formatted_events if e['type'].lower() == event_type.lower()]

    # Sort by timestamp (most recent first)
    formatted_events.sort(key=lambda x: x['timestamp'], reverse=True)

    # Limit count
    if show_count and show_count > 0:
        formatted_events = formatted_events[:show_count]

    # Print results
    print_events_table(formatted_events)

    # Summary
    total = len(formatted_events)
    warnings = sum(1 for e in formatted_events if e['type'] == 'Warning')
    normal = sum(1 for e in formatted_events if e['type'] == 'Normal')

    print(f"\nShowing {total} most recent events")
    if warnings > 0:
        print(f"  ⚠️  {warnings} Warning events")
    if normal > 0:
        print(f"  ℹ️  {normal} Normal events")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze events from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./must-gather
  %(prog)s ./must-gather --namespace openshift-etcd
  %(prog)s ./must-gather --type Warning
  %(prog)s ./must-gather --count 50
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('-n', '--namespace', help='Filter by namespace')
    parser.add_argument('-t', '--type', help='Filter by event type (Warning, Normal)')
    parser.add_argument('-c', '--count', type=int, default=100,
                        help='Number of events to show (default: 100)')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_events(args.must_gather_path, args.namespace, args.type, args.count)


if __name__ == '__main__':
    sys.exit(main())
