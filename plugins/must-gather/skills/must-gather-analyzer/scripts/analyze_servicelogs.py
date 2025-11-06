#!/usr/bin/env python3
"""
Analyze host service logs from must-gather data.
Shows ERROR and WARN patterns from systemd services (kubelet, crio, etc.).

NOTE: Host service logs (systemd) are typically collected only from master nodes in must-gather.
The script will analyze logs from host_service_logs/masters/ and host_service_logs/workers/
if present, with each service labeled by node type (e.g., "kubelet (masters)").
"""

import sys
import os
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


def extract_error_pattern(line: str) -> str:
    """Extract a meaningful error pattern from a log line."""
    # Try to extract common error message patterns
    # Example: 'Error syncing pod' or 'Failed to start container'

    # Look for quoted error messages
    quoted = re.search(r'"([^"]*(?:error|failed|unable|killing|fatal)[^"]*)"', line, re.IGNORECASE)
    if quoted:
        return quoted.group(1)

    # Look for error after 'err=' or 'error='
    err_match = re.search(r'(?:err|error)="?([^"]+)"?', line, re.IGNORECASE)
    if err_match:
        msg = err_match.group(1).split(',')[0]  # Take first part before comma
        return msg[:100]

    # Look for message after 'msg='
    msg_match = re.search(r'msg="([^"]+)"', line)
    if msg_match:
        return msg_match.group(1)[:100]

    # Look for kubelet-style errors: E1022 ... "message"
    kube_match = re.search(r'[EWF]\d{4}.*?"([^"]+)"', line)
    if kube_match:
        return kube_match.group(1)

    # Fallback: extract the part after error/warning keyword
    fallback = re.search(r'(?:error|warning|failed|fatal):\s*(.+)', line, re.IGNORECASE)
    if fallback:
        return fallback.group(1)[:100]

    return "Unknown error pattern"


def parse_service_log(file_path: Path) -> Dict[str, any]:
    """Parse a service log file for ERROR and WARN patterns."""
    error_patterns = defaultdict(int)
    warning_patterns = defaultdict(int)
    total_errors = 0
    total_warnings = 0

    try:
        with open(file_path, 'r', errors='ignore') as f:
            for line in f:
                line = line.strip()
                # Look for common error patterns
                if re.search(r'\b(ERROR|Error|error|FATAL|Fatal|fatal|CRIT|Critical)\b', line):
                    total_errors += 1
                    pattern = extract_error_pattern(line)
                    error_patterns[pattern] += 1
                elif re.search(r'\b(WARN|Warning|warning)\b', line):
                    total_warnings += 1
                    pattern = extract_error_pattern(line)
                    warning_patterns[pattern] += 1
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}", file=sys.stderr)

    return {
        'total_errors': total_errors,
        'total_warnings': total_warnings,
        'error_patterns': dict(error_patterns),
        'warning_patterns': dict(warning_patterns)
    }


def get_service_name(filename: str) -> str:
    """Extract service name from filename."""
    # Remove _service.log suffix
    return filename.replace('_service.log', '').replace('.log', '')


def print_service_summary(service_data: Dict[str, Dict]):
    """Print summary of service issues."""
    if not service_data:
        print("No service logs found.")
        return

    print(f"{'SERVICE':<40} {'ERRORS':<10} {'WARNINGS':<10} STATUS")
    print("=" * 70)

    for service, data in sorted(service_data.items()):
        error_count = data['total_errors']
        warning_count = data['total_warnings']

        # Determine status
        if error_count > 0:
            status = "⚠️  HAS ERRORS"
        elif warning_count > 0:
            status = "⚠️  HAS WARNINGS"
        else:
            status = "✅ OK"

        print(f"{service:<40} {error_count:<10} {warning_count:<10} {status}")


def print_service_details(service_data: Dict[str, Dict], show_warnings: bool = False):
    """Print pattern-based summary of errors and warnings."""
    has_issues = False

    for service, data in sorted(service_data.items()):
        error_patterns = data['error_patterns']
        warning_patterns = data['warning_patterns']
        total_errors = data['total_errors']
        total_warnings = data['total_warnings']

        if error_patterns:
            has_issues = True
            print(f"\n{'='*80}")
            print(f"SERVICE: {service}")
            print(f"ERROR PATTERNS ({total_errors} total occurrences):")
            print(f"{'='*80}")

            # Sort patterns by count (descending)
            sorted_patterns = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)
            for i, (pattern, count) in enumerate(sorted_patterns[:10], 1):  # Show top 10
                print(f"{i}. [{count}x] {pattern}")

            if len(sorted_patterns) > 10:
                remaining = sum(count for pattern, count in sorted_patterns[10:])
                print(f"... and {len(sorted_patterns) - 10} more patterns ({remaining} occurrences)")

        if show_warnings and warning_patterns:
            has_issues = True
            print(f"\n{'-'*80}")
            print(f"WARNING PATTERNS ({total_warnings} total occurrences):")
            print(f"{'-'*80}")

            # Sort patterns by count (descending)
            sorted_patterns = sorted(warning_patterns.items(), key=lambda x: x[1], reverse=True)
            for i, (pattern, count) in enumerate(sorted_patterns[:10], 1):  # Show top 10
                print(f"{i}. [{count}x] {pattern}")

            if len(sorted_patterns) > 10:
                remaining = sum(count for pattern, count in sorted_patterns[10:])
                print(f"... and {len(sorted_patterns) - 10} more patterns ({remaining} occurrences)")

    if not has_issues:
        print("\n✅ No errors or warnings found in service logs!")


def analyze_service_logs(must_gather_path: str, service_filter: str = None,
                         show_warnings: bool = False, errors_only: bool = False):
    """Analyze service logs in a must-gather directory."""
    base_path = Path(must_gather_path)

    # Find service log directories
    service_log_dirs = []
    patterns = [
        "host_service_logs/masters",
        "*/host_service_logs/masters",
        "host_service_logs/workers",
        "*/host_service_logs/workers",
    ]

    for pattern in patterns:
        for log_dir in base_path.glob(pattern):
            if log_dir.is_dir():
                service_log_dirs.append(log_dir)

    if not service_log_dirs:
        print("No service logs found in must-gather data.")
        return 1

    # Parse all service logs
    service_data = {}

    for log_dir in service_log_dirs:
        node_type = log_dir.name  # masters or workers

        for log_file in log_dir.glob("*_service.log"):
            service_name = get_service_name(log_file.name)

            # Apply filter if specified
            if service_filter and service_filter.lower() not in service_name.lower():
                continue

            full_service_name = f"{service_name} ({node_type})"

            # Parse the log
            log_data = parse_service_log(log_file)

            # Filter out if errors_only and no errors
            if errors_only and log_data['total_errors'] == 0:
                continue

            service_data[full_service_name] = log_data

    if not service_data:
        print("No matching service logs found.")
        return 0

    # Print results
    print(f"\n{'='*80}")
    print("SERVICE LOGS SUMMARY")
    print(f"{'='*80}\n")

    print_service_summary(service_data)
    print_service_details(service_data, show_warnings)

    # Print overall summary
    total_services = len(service_data)
    services_with_errors = sum(1 for d in service_data.values() if d['total_errors'] > 0)
    services_with_warnings = sum(1 for d in service_data.values() if d['total_warnings'] > 0)

    print(f"\n{'='*80}")
    print(f"TOTAL: {total_services} services analyzed")
    if services_with_errors > 0:
        print(f"  ⚠️  {services_with_errors} service(s) with errors")
    if services_with_warnings > 0:
        print(f"  ⚠️  {services_with_warnings} service(s) with warnings")
    if services_with_errors == 0 and services_with_warnings == 0:
        print(f"  ✅ No issues found!")
    print(f"{'='*80}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze service logs from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./must-gather
  %(prog)s ./must-gather --service kubelet
  %(prog)s ./must-gather --errors-only
  %(prog)s ./must-gather --show-warnings
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('-s', '--service', help='Filter by service name (e.g., kubelet, crio)')
    parser.add_argument('-w', '--show-warnings', action='store_true',
                        help='Show warnings in addition to errors')
    parser.add_argument('-e', '--errors-only', action='store_true',
                        help='Show only services with errors')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_service_logs(args.must_gather_path, args.service,
                                args.show_warnings, args.errors_only)


if __name__ == '__main__':
    sys.exit(main())
