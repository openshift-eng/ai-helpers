#!/usr/bin/env python3
"""
Analyze node logs from must-gather data.
Provides pattern-based summaries of errors and warnings in node logs.

Node logs are located in: nodes/<hostname>/
Each node directory contains:
- <hostname>_logs_kubelet.gz - gzipped kubelet logs
- sysinfo.log - system information
- dmesg - kernel messages
"""

import sys
import os
import re
import argparse
import gzip
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


def extract_error_pattern(line: str) -> str:
    """Extract a meaningful error pattern from a log line."""
    # Remove timestamp prefix if present (kubelet format: I0818 10:59:38.123456)
    line = re.sub(r'^[IWEF]\d{4}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+[^\]]+\]\s*', '', line)

    # Try to extract common error message patterns

    # Look for quoted error messages
    quoted = re.search(r'"([^"]*(?:error|failed|unable|fatal|panic|failure)[^"]*)"', line, re.IGNORECASE)
    if quoted:
        return quoted.group(1)[:100]

    # Look for error after 'err=' or 'error='
    err_match = re.search(r'(?:err|error)=\"?([^\"]+)\"?', line, re.IGNORECASE)
    if err_match:
        msg = err_match.group(1).split(',')[0]  # Take first part before comma
        return msg[:100]

    # Look for message after 'msg='
    msg_match = re.search(r'msg=\"([^\"]+)\"', line)
    if msg_match:
        return msg_match.group(1)[:100]

    # Look for kubelet/k8s-style errors: E0818 ... "message"
    kube_match = re.search(r'[EWF]\d{4}.*?\"([^\"]+)\"', line)
    if kube_match:
        return kube_match.group(1)[:100]

    # Look for panic messages
    panic_match = re.search(r'panic:\s*(.+)', line, re.IGNORECASE)
    if panic_match:
        return "panic: " + panic_match.group(1)[:80]

    # Fallback: extract the part after error/warning/fatal keyword
    fallback = re.search(r'(?:error|warning|failed|fatal|panic|failure):\s*(.+)', line, re.IGNORECASE)
    if fallback:
        return fallback.group(1)[:100]

    # Last resort: take first 100 chars after removing timestamp
    return line[:100] if line else "Unknown error pattern"


def parse_log_file(file_path: Path, is_gzipped: bool = False) -> Dict[str, any]:
    """Parse a log file for ERROR and WARN patterns."""
    error_patterns = defaultdict(int)
    warning_patterns = defaultdict(int)
    total_errors = 0
    total_warnings = 0
    total_lines = 0

    try:
        if is_gzipped:
            file_handle = gzip.open(file_path, 'rt', errors='ignore')
        else:
            file_handle = open(file_path, 'r', errors='ignore')

        with file_handle as f:
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


def find_node_logs(must_gather_path: str, node: str = None) -> List[Tuple[str, str, Path, bool]]:
    """Find node log files matching the criteria.

    Returns list of (node_name, log_type, log_path, is_gzipped) tuples.
    """
    base_path = Path(must_gather_path)
    node_logs = []

    # Pattern to find node directories
    patterns = [
        "nodes/*",
        "*/nodes/*",
    ]

    for pattern in patterns:
        for node_dir in base_path.glob(pattern):
            if not node_dir.is_dir():
                continue

            node_name = node_dir.name

            # Apply filter
            if node and node.lower() not in node_name.lower():
                continue

            # Find kubelet logs (gzipped)
            for kubelet_log in node_dir.glob("*_logs_kubelet.gz"):
                node_logs.append((node_name, "kubelet", kubelet_log, True))

            # Find sysinfo.log (not gzipped)
            sysinfo_log = node_dir / "sysinfo.log"
            if sysinfo_log.exists() and sysinfo_log.stat().st_size > 0:
                node_logs.append((node_name, "sysinfo", sysinfo_log, False))

            # Find dmesg (not gzipped, often empty)
            dmesg_log = node_dir / "dmesg"
            if dmesg_log.exists() and dmesg_log.stat().st_size > 0:
                node_logs.append((node_name, "dmesg", dmesg_log, False))

    return node_logs


def print_node_logs_summary(node_logs_data: List[Tuple[str, str, Dict]]):
    """Print summary table of node logs."""
    if not node_logs_data:
        print("No node logs found matching criteria.")
        return

    print(f"{'NODE':<45} {'LOG TYPE':<15} {'ERRORS':<10} {'WARNINGS':<10} {'LINES':<10}")
    print("=" * 90)

    for node, log_type, data in sorted(node_logs_data):
        node_name = node[:45]
        log_type_str = log_type[:15]
        errors = str(data['total_errors'])[:10]
        warnings = str(data['total_warnings'])[:10]
        lines = str(data['total_lines'])[:10]

        print(f"{node_name:<45} {log_type_str:<15} {errors:<10} {warnings:<10} {lines:<10}")


def print_node_logs_details(node_logs_data: List[Tuple[str, str, Dict]],
                            show_warnings: bool = False, top_n: int = 10):
    """Print detailed pattern analysis for node logs."""

    for node, log_type, data in sorted(node_logs_data):
        error_patterns = data['error_patterns']
        warning_patterns = data['warning_patterns']
        total_errors = data['total_errors']
        total_warnings = data['total_warnings']

        if error_patterns:
            print(f"\n{'='*80}")
            print(f"NODE: {node}")
            print(f"LOG TYPE: {log_type}")
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


def analyze_node_logs(must_gather_path: str, node: str = None, log_type: str = None,
                      show_warnings: bool = False, errors_only: bool = False,
                      top_n: int = 10, skip_kubelet: bool = False):
    """Analyze node logs in a must-gather directory."""

    # Find node logs
    node_logs = find_node_logs(must_gather_path, node)

    if not node_logs:
        print("No node logs found matching criteria.")
        return 1

    # Filter by log type if specified
    if log_type:
        node_logs = [(n, t, p, gz) for n, t, p, gz in node_logs if t == log_type]

    # Skip kubelet logs if requested (useful if user doesn't want to process gzipped files)
    if skip_kubelet:
        node_logs = [(n, t, p, gz) for n, t, p, gz in node_logs if t != "kubelet"]

    if not node_logs:
        print(f"No node logs found matching criteria (log_type={log_type}).")
        return 1

    # Check if we have gzipped files and warn user
    has_gzipped = any(gz for _, _, _, gz in node_logs)
    if has_gzipped:
        print("\n" + "="*80)
        print("NOTE: Kubelet logs are gzipped and will be extracted on-the-fly.")
        print("This may take a moment for large log files...")
        print("="*80 + "\n")

    # Parse each log file
    node_logs_data = []
    for node_name, log_type_name, log_file, is_gzipped in node_logs:
        log_data = parse_log_file(log_file, is_gzipped)

        # Skip if errors_only and no errors
        if errors_only and log_data['total_errors'] == 0:
            continue

        # Only include if there are errors or warnings
        if log_data['total_errors'] > 0 or log_data['total_warnings'] > 0:
            node_logs_data.append((node_name, log_type_name, log_data))

    if not node_logs_data:
        print("No node logs with errors or warnings found.")
        return 0

    # Print results
    print(f"\n{'='*80}")
    print("NODE LOGS SUMMARY")
    print(f"{'='*80}\n")

    print_node_logs_summary(node_logs_data)
    print_node_logs_details(node_logs_data, show_warnings, top_n)

    # Print overall summary
    total_nodes = len(set(node for node, _, _ in node_logs_data))
    total_errors = sum(data['total_errors'] for _, _, data in node_logs_data)
    total_warnings = sum(data['total_warnings'] for _, _, data in node_logs_data)
    nodes_with_errors = len(set(node for node, _, data in node_logs_data if data['total_errors'] > 0))
    nodes_with_warnings = len(set(node for node, _, data in node_logs_data if data['total_warnings'] > 0))

    print(f"\n{'='*80}")
    print(f"TOTAL: {len(node_logs_data)} node log(s) analyzed from {total_nodes} node(s)")
    print(f"  Total errors: {total_errors}")
    print(f"  Total warnings: {total_warnings}")
    if nodes_with_errors > 0:
        print(f"  ⚠️  {nodes_with_errors} node(s) with errors")
    if nodes_with_warnings > 0:
        print(f"  ⚠️  {nodes_with_warnings} node(s) with warnings")
    if nodes_with_errors == 0 and nodes_with_warnings == 0:
        print(f"  ✅ No issues found!")
    print(f"{'='*80}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze node logs from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all node logs (kubelet, sysinfo, dmesg)
  %(prog)s ./must-gather

  # Analyze logs for a specific node
  %(prog)s ./must-gather --node ip-10-0-45-79

  # Analyze only kubelet logs
  %(prog)s ./must-gather --log-type kubelet

  # Analyze only sysinfo logs (skip gzipped kubelet logs)
  %(prog)s ./must-gather --log-type sysinfo

  # Show top 5 error patterns
  %(prog)s ./must-gather --top 5

  # Show warnings in addition to errors
  %(prog)s ./must-gather --show-warnings

  # Show only nodes with errors
  %(prog)s ./must-gather --errors-only

  # Skip kubelet logs (useful to avoid extracting gzipped files)
  %(prog)s ./must-gather --skip-kubelet
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('-n', '--node', help='Filter by node name (partial match)')
    parser.add_argument('-l', '--log-type',
                        choices=['kubelet', 'sysinfo', 'dmesg'],
                        help='Filter by log type')
    parser.add_argument('-w', '--show-warnings', action='store_true',
                        help='Show warnings in addition to errors')
    parser.add_argument('-e', '--errors-only', action='store_true',
                        help='Show only nodes with errors')
    parser.add_argument('-t', '--top', type=int, default=10, metavar='N',
                        help='Show top N error patterns (default: 10)')
    parser.add_argument('--skip-kubelet', action='store_true',
                        help='Skip kubelet logs (avoids extracting gzipped files)')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_node_logs(args.must_gather_path, args.node, args.log_type,
                            args.show_warnings, args.errors_only, args.top,
                            args.skip_kubelet)


if __name__ == '__main__':
    sys.exit(main())
