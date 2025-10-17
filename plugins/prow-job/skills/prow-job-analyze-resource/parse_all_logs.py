#!/usr/bin/env python3
"""Parse audit logs and pod logs for resource lifecycle analysis."""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

def parse_timestamp(ts_str: str) -> datetime:
    """Parse various timestamp formats."""
    if not ts_str:
        return None

    try:
        # ISO 8601 with Z
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        pass

    try:
        # Standard datetime
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
    except:
        pass

    return None

def parse_audit_logs(log_files: List[str], resource_pattern: str) -> List[Dict[str, Any]]:
    """Parse audit log files for matching resource entries."""
    entries = []

    # Compile regex pattern for efficient matching
    pattern_regex = re.compile(resource_pattern)

    for log_file in log_files:
        try:
            with open(log_file, 'r') as f:
                line_num = 0
                for line in f:
                    line_num += 1
                    # Quick substring check first for performance (only if pattern has no regex chars)
                    if '|' not in resource_pattern and '.*' not in resource_pattern and '[' not in resource_pattern:
                        if resource_pattern not in line:
                            continue
                    else:
                        # For regex patterns, check if pattern matches the line
                        if not pattern_regex.search(line):
                            continue

                    try:
                        entry = json.loads(line.strip())

                        # Extract relevant fields
                        verb = entry.get('verb', '')
                        user = entry.get('user', {}).get('username', 'unknown')
                        response_code = entry.get('responseStatus', {}).get('code', 0)
                        obj_ref = entry.get('objectRef', {})
                        namespace = obj_ref.get('namespace', '')
                        resource_type = obj_ref.get('resource', '')
                        name = obj_ref.get('name', '')
                        timestamp_str = entry.get('requestReceivedTimestamp', '')

                        # Skip if doesn't match the pattern (using regex)
                        if not (pattern_regex.search(namespace) or pattern_regex.search(name)):
                            continue

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
                        timestamp = parse_timestamp(timestamp_str)

                        # Generate summary
                        summary = f"{verb} {resource_type}"
                        if name:
                            summary += f"/{name}"
                        if namespace and namespace != name:
                            summary += f" in {namespace}"
                        summary += f" by {user} → HTTP {response_code}"

                        entries.append({
                            'source': 'audit',
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
                            'name': name,
                            'user': user,
                            'response_code': response_code
                        })
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error processing {log_file}: {e}", file=sys.stderr)
            continue

    return entries

def parse_pod_logs(log_files: List[str], resource_pattern: str) -> List[Dict[str, Any]]:
    """Parse pod log files for matching resource mentions."""
    entries = []

    # Common timestamp patterns in pod logs
    timestamp_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.\d]*Z?)')

    # Glog format: E0910 11:43:41.153414 ... or W1234 12:34:56.123456 ...
    # Format: <severity><MMDD> <HH:MM:SS.microseconds>
    # Capture: severity, month, day, time
    glog_pattern = re.compile(r'^([EIWF])(\d{2})(\d{2})\s+(\d{2}:\d{2}:\d{2}\.\d+)')

    # Compile resource pattern regex for efficient matching
    pattern_regex = re.compile(resource_pattern)

    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                line_num = 0
                for line in f:
                    line_num += 1
                    # Quick substring check first for performance (only if pattern has no regex chars)
                    if '|' not in resource_pattern and '.*' not in resource_pattern and '[' not in resource_pattern:
                        if resource_pattern not in line:
                            continue
                    else:
                        # For regex patterns, use regex search
                        if not pattern_regex.search(line):
                            continue

                    # Detect log level and timestamp from glog format
                    level = 'info'  # Default level
                    timestamp_str = ''
                    timestamp = None
                    timestamp_end = 0  # Track where timestamp ends for summary extraction

                    glog_match = glog_pattern.match(line)
                    if glog_match:
                        severity = glog_match.group(1)
                        month = glog_match.group(2)
                        day = glog_match.group(3)
                        time_part = glog_match.group(4)

                        # Map glog severity to our level scheme
                        if severity == 'E' or severity == 'F':  # Error or Fatal
                            level = 'error'
                        elif severity == 'W':  # Warning
                            level = 'warn'
                        elif severity == 'I':  # Info
                            level = 'info'

                        # Parse glog timestamp - glog doesn't include year, so we infer it
                        # Use 2025 as a reasonable default (current test year based on audit logs)
                        # In production, you might want to get this from the prowjob metadata
                        year = 2025
                        timestamp_str = f"{year}-{month}-{day}T{time_part}Z"
                        timestamp = parse_timestamp(timestamp_str)
                        timestamp_end = glog_match.end()
                    else:
                        # Try ISO 8601 format for non-glog logs
                        match = timestamp_pattern.match(line)
                        if match:
                            timestamp_str = match.group(1)
                            timestamp = parse_timestamp(timestamp_str)
                            timestamp_end = match.end()

                    # Generate summary - use first 200 chars of line (after timestamp)
                    if timestamp_end > 0:
                        summary = line[timestamp_end:].strip()[:200]
                    else:
                        summary = line.strip()[:200]

                    entries.append({
                        'source': 'pod',
                        'filename': log_file,
                        'line_number': line_num,
                        'level': level,
                        'timestamp': timestamp,
                        'timestamp_str': timestamp_str,
                        'content': line.strip(),
                        'summary': summary,
                        'verb': '',  # Pod logs don't have verbs
                        'resource_type': '',
                        'namespace': '',
                        'name': '',
                        'user': '',
                        'response_code': 0
                    })
        except Exception as e:
            print(f"Error processing pod log {log_file}: {e}", file=sys.stderr)
            continue

    return entries

def main():
    if len(sys.argv) < 4:
        print("Usage: parse_all_logs.py <resource_pattern> <audit_logs_dir> <pods_dir>")
        print("  resource_pattern: Regex pattern to match resource names (e.g., 'resource1|resource2')")
        sys.exit(1)

    resource_pattern = sys.argv[1]
    audit_logs_dir = Path(sys.argv[2])
    pods_dir = Path(sys.argv[3])

    # Find all audit log files
    audit_log_files = list(audit_logs_dir.glob('**/*.log'))
    print(f"Found {len(audit_log_files)} audit log files", file=sys.stderr)

    # Find all pod log files
    pod_log_files = list(pods_dir.glob('**/*.log'))
    print(f"Found {len(pod_log_files)} pod log files", file=sys.stderr)

    # Parse audit logs
    audit_entries = parse_audit_logs([str(f) for f in audit_log_files], resource_pattern)
    print(f"Found {len(audit_entries)} matching audit log entries", file=sys.stderr)

    # Parse pod logs
    pod_entries = parse_pod_logs([str(f) for f in pod_log_files], resource_pattern)
    print(f"Found {len(pod_entries)} matching pod log entries", file=sys.stderr)

    # Combine and sort by timestamp
    all_entries = audit_entries + pod_entries
    # Use a large datetime with timezone for sorting entries without timestamps
    from datetime import timezone
    max_datetime = datetime(9999, 12, 31, tzinfo=timezone.utc)
    all_entries.sort(key=lambda x: x['timestamp'] if x['timestamp'] else max_datetime)

    print(f"Total {len(all_entries)} entries", file=sys.stderr)

    # Output as JSON
    print(json.dumps(all_entries, default=str, indent=2))

if __name__ == '__main__':
    main()
