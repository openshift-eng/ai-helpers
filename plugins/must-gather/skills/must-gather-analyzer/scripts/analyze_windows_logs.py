#!/usr/bin/env python3
"""
Analyze Windows node logs from must-gather data.
Parses logs from host_service_logs/windows/log_files/ and identifies issues.
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
import re


# Windows-specific error patterns for different components
ERROR_PATTERNS = {
    'HNS': [
        r'hns.*failed',
        r'host network service.*error',
        r'hnsnetwork.*failed',
        r'hnsendpoint.*failed',
        r'failed.*create.*endpoint',
        r'failed.*delete.*endpoint',
        r'network.*attach.*failed',
    ],
    'Containerd': [
        r'containerd.*error',
        r'failed to create container',
        r'failed to start container',
        r'runtime.*error',
        r'failed.*pull.*image',
        r'container.*exit.*code',
    ],
    'Hybrid-Overlay': [
        r'failed.*setup.*overlay',
        r'failed.*configure.*tunnel',
        r'tunnel.*failed',
        r'ovn.*error',
    ],
    'Kubelet': [
        r'failed.*start.*pod',
        r'failed.*create.*pod',
        r'sandbox.*failed',
        r'runtime.*not.*ready',
    ],
    'Kube-Proxy': [
        r'failed.*sync.*proxy',
        r'failed.*update.*service',
        r'winkernel.*error',
    ],
    'WICD': [
        r'ERROR',
        r'failed to configure',
        r'instance config.*failed',
        r'failed.*apply.*configuration',
    ],
    'CSI-Proxy': [
        r'volume.*mount.*failed',
        r'failed.*disk.*operation',
        r'iscsi.*error',
    ]
}

# Warning patterns
WARNING_PATTERNS = [
    r'warning',
    r'warn\s',
    r'deprecated',
]


def parse_log_file(log_path: Path, component: str, max_errors: int = 50) -> Dict[str, Any]:
    """Parse a single Windows log file and extract errors and warnings."""
    errors = []
    warnings = []
    total_lines = 0

    if not log_path.exists():
        return {
            'component': component,
            'log_path': str(log_path),
            'exists': False,
            'errors': [],
            'warnings': [],
            'error_count': 0,
            'warning_count': 0,
            'total_lines': 0
        }

    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                total_lines += 1
                line_lower = line.lower()

                # Check for errors
                if 'error' in line_lower or 'failed' in line_lower or 'fatal' in line_lower:
                    # Try to categorize the error by checking ALL patterns
                    categorized = False
                    for category, patterns in ERROR_PATTERNS.items():
                        for pattern in patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                if len(errors) < max_errors:
                                    errors.append({
                                        'line_num': line_num,
                                        'category': category,
                                        'message': line.strip()[:200]  # Limit message length
                                    })
                                categorized = True
                                break
                        if categorized:
                            break

                    # If not categorized but still an error, add as generic
                    if not categorized and len(errors) < max_errors:
                        errors.append({
                            'line_num': line_num,
                            'category': 'General',
                            'message': line.strip()[:200]
                        })

                # Check for warnings
                for pattern in WARNING_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        if len(warnings) < max_errors:
                            warnings.append({
                                'line_num': line_num,
                                'message': line.strip()[:200]
                            })
                        break

    except Exception as e:
        print(f"Warning: Failed to parse {log_path}: {e}", file=sys.stderr)

    return {
        'component': component,
        'log_path': str(log_path),
        'exists': True,
        'errors': errors,
        'warnings': warnings,
        'error_count': len(errors),
        'warning_count': len(warnings),
        'total_lines': total_lines
    }


def detect_common_issues(results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Detect common Windows node issues from parsed logs."""
    issues = []

    # Collect all errors by category
    errors_by_category = defaultdict(list)
    for result in results:
        for error in result['errors']:
            errors_by_category[error['category']].append({
                'component': result['component'],
                'line_num': error['line_num'],
                'message': error['message']
            })

    # Detect HNS failures
    if 'HNS' in errors_by_category and len(errors_by_category['HNS']) > 0:
        issues.append({
            'severity': 'CRITICAL',
            'issue': 'HNS (Host Network Service) Failures Detected',
            'description': f"Found {len(errors_by_category['HNS'])} HNS-related errors. This typically causes pods to fail in ContainerCreating state.",
            'recommendation': 'Check Windows node networking configuration. May need to restart HNS service or reboot node.'
        })

    # Detect containerd issues
    if 'Containerd' in errors_by_category and len(errors_by_category['Containerd']) > 5:
        issues.append({
            'severity': 'CRITICAL',
            'issue': 'Container Runtime Failures',
            'description': f"Found {len(errors_by_category['Containerd'])} containerd errors. Containers may fail to start.",
            'recommendation': 'Check containerd service status on Windows node. Review container image compatibility.'
        })

    # Detect hybrid-overlay issues
    if 'Hybrid-Overlay' in errors_by_category and len(errors_by_category['Hybrid-Overlay']) > 0:
        issues.append({
            'severity': 'HIGH',
            'issue': 'Hybrid Overlay Networking Issues',
            'description': f"Found {len(errors_by_category['Hybrid-Overlay'])} hybrid-overlay errors. Linux-Windows pod connectivity may be affected.",
            'recommendation': 'Verify OVN-Kubernetes hybrid-overlay configuration. Check tunnel connectivity between Linux and Windows nodes.'
        })

    # Detect kubelet issues
    if 'Kubelet' in errors_by_category and len(errors_by_category['Kubelet']) > 10:
        issues.append({
            'severity': 'HIGH',
            'issue': 'Kubelet Errors',
            'description': f"Found {len(errors_by_category['Kubelet'])} kubelet errors. Pod scheduling and management may be impacted.",
            'recommendation': 'Check kubelet service status. Review pod events for specific failures.'
        })

    # Detect CSI-Proxy issues
    if 'CSI-Proxy' in errors_by_category and len(errors_by_category['CSI-Proxy']) > 0:
        issues.append({
            'severity': 'HIGH',
            'issue': 'CSI Proxy Volume Errors',
            'description': f"Found {len(errors_by_category['CSI-Proxy'])} CSI-Proxy errors. Persistent volume operations may fail.",
            'recommendation': 'Check CSI-Proxy service status. Verify storage backend connectivity and disk operations.'
        })

    return issues


def analyze_windows_logs(must_gather_path: str, component: Optional[str] = None,
                         errors_only: bool = False, max_errors: int = 50) -> int:
    """Analyze all Windows node logs in must-gather."""
    base_path = Path(must_gather_path)

    # Check for Windows logs directory
    windows_logs_path = base_path / "host_service_logs" / "windows" / "log_files"

    if not windows_logs_path.exists():
        print("=" * 80)
        print("WINDOWS NODE LOGS ANALYSIS")
        print("=" * 80)
        print()
        print("❌ No Windows node logs found in must-gather.")
        print(f"   Expected path: {windows_logs_path}")
        print()
        print("This could mean:")
        print("  1. The cluster has no Windows nodes")
        print("  2. Windows logs were not collected during must-gather")
        print("  3. The must-gather path is incorrect")
        print()
        return 1

    print("=" * 80)
    print("WINDOWS NODE LOGS ANALYSIS")
    print("=" * 80)
    print(f"Log directory: {windows_logs_path}")
    print()

    # Component log mappings
    components = {
        'kube-proxy': windows_logs_path / 'kube-proxy' / 'kube-proxy.log',
        'hybrid-overlay': windows_logs_path / 'hybrid-overlay' / 'hybrid-overlay.log',
        'kubelet': windows_logs_path / 'kubelet' / 'kubelet.log',
        'containerd': windows_logs_path / 'containerd' / 'containerd.log',
        'wicd-info': windows_logs_path / 'wicd' / 'windows-instance-config-daemon.exe.INFO',
        'wicd-error': windows_logs_path / 'wicd' / 'windows-instance-config-daemon.exe.ERROR',
        'wicd-warning': windows_logs_path / 'wicd' / 'windows-instance-config-daemon.exe.WARNING',
        'csi-proxy': windows_logs_path / 'csi-proxy' / 'csi-proxy.log'
    }

    # Filter to specific component if requested
    if component:
        components = {k: v for k, v in components.items() if component.lower() in k.lower()}
        if not components:
            print(f"❌ No component matching '{component}' found.")
            print(f"   Available components: {', '.join(['kube-proxy', 'hybrid-overlay', 'kubelet', 'containerd', 'wicd', 'csi-proxy'])}")
            return 1

    # Parse all logs
    results = []
    total_errors = 0
    total_warnings = 0
    total_lines = 0

    for comp_name, log_path in components.items():
        result = parse_log_file(log_path, comp_name, max_errors)
        results.append(result)
        if result['exists']:
            total_errors += result['error_count']
            total_warnings += result['warning_count']
            total_lines += result['total_lines']

    # Print summary
    existing_components = [r for r in results if r['exists']]

    if not existing_components:
        print("❌ No log files found for any Windows components.")
        return 1

    print(f"Components analyzed: {len(existing_components)}/{len(components)}")
    print(f"Total log lines:     {total_lines:,}")
    print(f"Total errors found:  {total_errors}")
    print(f"Total warnings:      {total_warnings}")
    print()

    # Print component breakdown
    print("COMPONENT STATUS:")
    print(f"{'COMPONENT':<25} {'LINES':<10} {'ERRORS':<10} {'WARNINGS':<10} STATUS")
    print("-" * 80)

    for result in results:
        if not result['exists']:
            comp = result['component']
            print(f"{comp:<25} {'N/A':<10} {'N/A':<10} {'N/A':<10} ⚠️  Not collected")
            continue

        comp = result['component']
        lines = f"{result['total_lines']:,}"
        errors = result['error_count']
        warnings = result['warning_count']

        if errors > 0:
            status = '❌ ERRORS'
        elif warnings > 0:
            status = '⚠️  WARNINGS'
        else:
            status = '✅ OK'

        print(f"{comp:<25} {lines:<10} {errors:<10} {warnings:<10} {status}")

    print()

    # Detect common issues
    if total_errors > 0:
        issues = detect_common_issues(results)

        if issues:
            print("=" * 80)
            print("DETECTED ISSUES")
            print("=" * 80)
            print()

            for idx, issue in enumerate(issues, 1):
                print(f"{idx}. [{issue['severity']}] {issue['issue']}")
                print(f"   {issue['description']}")
                print(f"   → {issue['recommendation']}")
                print()

    # Print detailed errors by category if not errors_only or if there are errors
    if total_errors > 0 and not errors_only:
        print("=" * 80)
        print("DETAILED ERRORS BY CATEGORY")
        print("=" * 80)

        errors_by_category = defaultdict(list)

        for result in results:
            for error in result['errors']:
                errors_by_category[error['category']].append({
                    'component': result['component'],
                    'line_num': error['line_num'],
                    'message': error['message']
                })

        for category, errors in sorted(errors_by_category.items()):
            print()
            print(f"{category.upper()} ERRORS ({len(errors)}):")
            print("-" * 80)
            for error in errors[:10]:  # Limit to first 10 per category
                comp = error['component'][:20]
                line = error['line_num']
                msg = error['message'][:90]
                print(f"  [{comp}:{line}] {msg}")

            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")

    # Return exit code
    if total_errors > 0:
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze Windows node logs from must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./must-gather.local.123456789
  %(prog)s ./must-gather.local.123456789 --component kubelet
  %(prog)s ./must-gather.local.123456789 --errors-only
  %(prog)s ./must-gather.local.123456789 --max-errors 100
        """
    )

    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('--component', help='Analyze specific component only (e.g., kubelet, containerd)')
    parser.add_argument('--errors-only', action='store_true', help='Show only summary, skip detailed errors')
    parser.add_argument('--max-errors', type=int, default=50,
                       help='Maximum errors to collect per log file (default: 50)')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    return analyze_windows_logs(
        args.must_gather_path,
        component=args.component,
        errors_only=args.errors_only,
        max_errors=args.max_errors
    )


if __name__ == '__main__':
    sys.exit(main())
