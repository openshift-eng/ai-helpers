#!/usr/bin/env python3
"""
Analyze pod logs from must-gather data.
Provides pattern-based summaries of errors and warnings in pod logs.

Pod logs are located in: namespaces/<ns>/pods/<pod>/<container>/<container>/logs/
Each pod/container can have current.log, previous.log, and previous.insecure.log
"""

import sys
import os
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


def extract_error_pattern(line: str) -> str:
    """Extract a meaningful error pattern from a log line."""
    # Remove timestamp prefix if present (ISO format: 2024-01-01T12:34:56.789Z)
    line = re.sub(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s*', '', line)
    # Remove kubelet-style log prefix if present (E1106 12:34:56.123456 12345 file.go:123])
    line = re.sub(r'^[IWEF]\d{4}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+[^\]]+\]\s*', '', line)

    # Try to extract common error message patterns

    # Look for quoted error messages
    quoted = re.search(r'"([^"]*(?:error|failed|unable|fatal|panic)[^"]*)"', line, re.IGNORECASE)
    if quoted:
        return quoted.group(1)[:100]

    # Look for error after 'err=' or 'error='
    err_match = re.search(r'(?:err|error)="?([^"]+)"?', line, re.IGNORECASE)
    if err_match:
        msg = err_match.group(1).split(',')[0]  # Take first part before comma
        return msg[:100]

    # Look for message after 'msg='
    msg_match = re.search(r'msg="([^"]+)"', line)
    if msg_match:
        return msg_match.group(1)[:100]

    # Look for kubelet/k8s-style errors: E1022 ... "message"
    kube_match = re.search(r'[EWF]\d{4}.*?"([^"]+)"', line)
    if kube_match:
        return kube_match.group(1)[:100]

    # Look for panic messages
    panic_match = re.search(r'panic:\s*(.+)', line, re.IGNORECASE)
    if panic_match:
        return "panic: " + panic_match.group(1)[:80]

    # Fallback: extract the part after error/warning/fatal keyword
    fallback = re.search(r'(?:error|warning|failed|fatal|panic):\s*(.+)', line, re.IGNORECASE)
    if fallback:
        return fallback.group(1)[:100]

    return "Unknown error pattern"


def parse_log_file(file_path: Path) -> Dict[str, any]:
    """Parse a log file for ERROR and WARN patterns."""
    error_patterns = defaultdict(int)
    warning_patterns = defaultdict(int)
    total_errors = 0
    total_warnings = 0
    total_lines = 0

    try:
        with open(file_path, 'r', errors='ignore') as f:
            for line in f:
                total_lines += 1
                line = line.strip()

                # Look for common error patterns (case insensitive)
                # Kubelet uses: E (Error), W (Warning), I (Info), F (Fatal)
                if re.search(r'\b(ERROR|Error|error|FATAL|Fatal|fatal|CRIT|Critical|PANIC|Panic|panic)\b', line) or re.match(r'^E\d{4}', line):
                    total_errors += 1
                    pattern = extract_error_pattern(line)
                    error_patterns[pattern] += 1
                elif re.search(r'\b(WARN|Warning|warning)\b', line) or re.match(r'^W\d{4}', line):
                    total_warnings += 1
                    pattern = extract_error_pattern(line)
                    warning_patterns[pattern] += 1
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}", file=sys.stderr)

    return {
        'total_errors': total_errors,
        'total_warnings': total_warnings,
        'total_lines': total_lines,
        'error_patterns': dict(error_patterns),
        'warning_patterns': dict(warning_patterns)
    }


def find_pod_logs(must_gather_path: str, namespace: str = None, pod: str = None,
                  container: str = None) -> List[Tuple[str, str, str, Path]]:
    """Find pod log files matching the criteria.

    Returns list of (namespace, pod, container, log_path) tuples.
    """
    base_path = Path(must_gather_path)
    pod_logs = []

    # Pattern to find log files
    patterns = [
        "namespaces/*/pods/*/*/*/logs/current.log",
        "*/namespaces/*/pods/*/*/*/logs/current.log",
    ]

    for pattern in patterns:
        for log_file in base_path.glob(pattern):
            # Extract namespace, pod, container from path
            parts = log_file.parts
            try:
                ns_index = parts.index('namespaces') + 1
                pods_index = parts.index('pods') + 1

                if ns_index < len(parts) and pods_index < len(parts):
                    ns = parts[ns_index]
                    pod_name = parts[pods_index]
                    # Container name is the directory name before /logs/
                    container_name = parts[-3]

                    # Apply filters
                    if namespace and namespace != ns:
                        continue
                    if pod and pod.lower() not in pod_name.lower():
                        continue
                    if container and container.lower() not in container_name.lower():
                        continue

                    pod_logs.append((ns, pod_name, container_name, log_file))
            except (ValueError, IndexError):
                continue

    return pod_logs


def print_pod_logs_summary(pod_logs_data: List[Tuple[str, str, str, Dict]]):
    """Print summary table of pod logs."""
    if not pod_logs_data:
        print("No pod logs found matching criteria.")
        return

    print(f"{'NAMESPACE':<30} {'POD':<50} {'CONTAINER':<40} {'ERRORS':<10} {'WARNINGS':<10} {'LINES':<10}")
    print("=" * 150)

    for ns, pod, container, data in sorted(pod_logs_data):
        namespace = ns[:30]
        pod_name = pod[:50]
        container_name = container[:40]
        errors = str(data['total_errors'])[:10]
        warnings = str(data['total_warnings'])[:10]
        lines = str(data['total_lines'])[:10]

        print(f"{namespace:<30} {pod_name:<50} {container_name:<40} {errors:<10} {warnings:<10} {lines:<10}")


def print_pod_logs_details(pod_logs_data: List[Tuple[str, str, str, Dict]],
                           show_warnings: bool = False, top_n: int = 10):
    """Print detailed pattern analysis for pod logs."""

    for ns, pod, container, data in sorted(pod_logs_data):
        error_patterns = data['error_patterns']
        warning_patterns = data['warning_patterns']
        total_errors = data['total_errors']
        total_warnings = data['total_warnings']

        if error_patterns:
            print(f"\n{'='*80}")
            print(f"NAMESPACE: {ns}")
            print(f"POD: {pod}")
            print(f"CONTAINER: {container}")
            print(f"ERROR PATTERNS ({total_errors} total occurrences):")
            print(f"{'='*80}")

            # Sort patterns by count (descending)
            sorted_patterns = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)
            for i, (pattern, count) in enumerate(sorted_patterns[:top_n], 1):
                print(f"{i}. [{count}x] {pattern}")

            if len(sorted_patterns) > top_n:
                remaining = sum(count for pattern, count in sorted_patterns[top_n:])
                print(f"... and {len(sorted_patterns) - top_n} more patterns ({remaining} occurrences)")

        if show_warnings and warning_patterns:
            print(f"\n{'-'*80}")
            print(f"WARNING PATTERNS ({total_warnings} total occurrences):")
            print(f"{'-'*80}")

            # Sort patterns by count (descending)
            sorted_patterns = sorted(warning_patterns.items(), key=lambda x: x[1], reverse=True)
            for i, (pattern, count) in enumerate(sorted_patterns[:top_n], 1):
                print(f"{i}. [{count}x] {pattern}")

            if len(sorted_patterns) > top_n:
                remaining = sum(count for pattern, count in sorted_patterns[top_n:])
                print(f"... and {len(sorted_patterns) - top_n} more patterns ({remaining} occurrences)")


def analyze_pod_logs(must_gather_path: str, namespace: str = None, pod: str = None,
                    container: str = None, show_warnings: bool = False,
                    errors_only: bool = False, top_n: int = 10):
    """Analyze pod logs in a must-gather directory."""

    # Find pod logs
    pod_logs = find_pod_logs(must_gather_path, namespace, pod, container)

    if not pod_logs:
        print("No pod logs found matching criteria.")
        return 1

    # Parse each log file
    pod_logs_data = []
    for ns, pod_name, container_name, log_file in pod_logs:
        log_data = parse_log_file(log_file)

        # Skip if errors_only and no errors
        if errors_only and log_data['total_errors'] == 0:
            continue

        # Only include if there are errors or warnings
        if log_data['total_errors'] > 0 or log_data['total_warnings'] > 0:
            pod_logs_data.append((ns, pod_name, container_name, log_data))

    if not pod_logs_data:
        print("No pod logs with errors or warnings found.")
        return 0

    # Print results
    print(f"\n{'='*80}")
    print("POD LOGS SUMMARY")
    print(f"{'='*80}\n")

    print_pod_logs_summary(pod_logs_data)
    print_pod_logs_details(pod_logs_data, show_warnings, top_n)

    # Print overall summary
    total_pods = len(pod_logs_data)
    total_errors = sum(data['total_errors'] for _, _, _, data in pod_logs_data)
    total_warnings = sum(data['total_warnings'] for _, _, _, data in pod_logs_data)
    pods_with_errors = sum(1 for _, _, _, data in pod_logs_data if data['total_errors'] > 0)
    pods_with_warnings = sum(1 for _, _, _, data in pod_logs_data if data['total_warnings'] > 0)

    print(f"\n{'='*80}")
    print(f"TOTAL: {total_pods} pod/container log(s) analyzed")
    print(f"  Total errors: {total_errors}")
    print(f"  Total warnings: {total_warnings}")
    if pods_with_errors > 0:
        print(f"  ⚠️  {pods_with_errors} container(s) with errors")
    if pods_with_warnings > 0:
        print(f"  ⚠️  {pods_with_warnings} container(s) with warnings")
    if pods_with_errors == 0 and pods_with_warnings == 0:
        print(f"  ✅ No issues found!")
    print(f"{'='*80}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze pod logs from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all pod logs with errors
  %(prog)s ./must-gather

  # Analyze logs for a specific namespace
  %(prog)s ./must-gather --namespace openshift-etcd

  # Analyze logs for a specific pod (partial name match)
  %(prog)s ./must-gather --pod etcd

  # Analyze specific container logs
  %(prog)s ./must-gather --namespace openshift-etcd --container etcd

  # Show top 5 error patterns
  %(prog)s ./must-gather --top 5

  # Show warnings in addition to errors
  %(prog)s ./must-gather --show-warnings

  # Show only pods with errors
  %(prog)s ./must-gather --errors-only
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('-n', '--namespace', help='Filter by namespace')
    parser.add_argument('-p', '--pod', help='Filter by pod name (partial match)')
    parser.add_argument('-c', '--container', help='Filter by container name')
    parser.add_argument('-w', '--show-warnings', action='store_true',
                        help='Show warnings in addition to errors')
    parser.add_argument('-e', '--errors-only', action='store_true',
                        help='Show only pods/containers with errors')
    parser.add_argument('-t', '--top', type=int, default=10, metavar='N',
                        help='Show top N error patterns (default: 10)')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_pod_logs(args.must_gather_path, args.namespace, args.pod,
                           args.container, args.show_warnings, args.errors_only,
                           args.top)


if __name__ == '__main__':
    sys.exit(main())
