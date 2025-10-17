#!/usr/bin/env python3
"""Parse audit logs for resource lifecycle analysis."""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

def parse_audit_logs(log_files: List[str], resource_name: str) -> List[Dict[str, Any]]:
    """Parse audit log files for matching resource entries."""
    entries = []

    for log_file in log_files:
        try:
            with open(log_file, 'r') as f:
                line_num = 0
                for line in f:
                    line_num += 1
                    try:
                        entry = json.loads(line.strip())

                        # Check if this entry matches our resource
                        obj_ref = entry.get('objectRef', {})
                        if obj_ref.get('name') == resource_name:
                            # Extract relevant fields
                            verb = entry.get('verb', '')
                            user = entry.get('user', {}).get('username', 'unknown')
                            response_code = entry.get('responseStatus', {}).get('code', 0)
                            namespace = obj_ref.get('namespace', '')
                            resource_type = obj_ref.get('resource', '')
                            timestamp_str = entry.get('requestReceivedTimestamp', '')

                            # Determine log level based on response code
                            if 200 <= response_code < 300:
                                level = 'info'
                            elif 400 <= response_code < 500:
                                level = 'warn'
                            elif 500 <= response_code < 600:
                                level = 'error'
                            else:
                                level = 'info'

                            # Parse timestamp
                            timestamp = None
                            if timestamp_str:
                                try:
                                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                except:
                                    pass

                            # Generate summary
                            summary = f"{verb} {resource_type}/{resource_name}"
                            if namespace:
                                summary += f" in {namespace}"
                            summary += f" by {user} → HTTP {response_code}"

                            entries.append({
                                'filename': log_file,
                                'line_number': line_num,
                                'level': level,
                                'timestamp': timestamp,
                                'timestamp_str': timestamp_str,
                                'content': line.strip(),
                                'summary': summary,
                                'verb': verb,
                                'resource_type': resource_type,
                                'namespace': namespace,
                                'user': user,
                                'response_code': response_code
                            })
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error processing {log_file}: {e}", file=sys.stderr)
            continue

    return entries

def main():
    if len(sys.argv) < 3:
        print("Usage: parse_audit_logs.py <resource_name> <log_file1> [log_file2 ...]")
        sys.exit(1)

    resource_name = sys.argv[1]
    log_files = sys.argv[2:]

    entries = parse_audit_logs(log_files, resource_name)

    # Sort by timestamp
    entries.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.max)

    # Output as JSON
    print(json.dumps(entries, default=str, indent=2))

if __name__ == '__main__':
    main()
