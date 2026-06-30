#!/usr/bin/env python3
"""
CLI entry point for NetworkPolicy analysis command.

Usage:
    python3 netpol_analyzer_cli.py --namespace=production --mode=security
    python3 netpol_analyzer_cli.py --cluster-wide --mode=performance

Author: Shreyas Be <shbehera@redhat.com>
Date: 2026-06-29
"""

import argparse
import sys
import logging
from typing import List, Dict, Any

from netpol_parser import NetworkPolicyParser
from policy_analyzer import SecurityAnalyzer, Severity


# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_finding(finding: Dict[str, Any]) -> str:
    """Format a single finding for display"""
    severity_emoji = {
        Severity.CRITICAL: '🔴',
        Severity.WARNING: '⚠️ ',
        Severity.INFO: 'ℹ️ '
    }

    emoji = severity_emoji.get(finding['severity'], '  ')
    title = finding.get('title', 'Unknown issue')
    description = finding.get('description', '')
    recommendation = finding.get('recommendation', '')

    output = f"{emoji} {title}\n"

    if finding.get('policy'):
        output += f"   Policy: {finding['policy']}\n"
    if finding.get('namespace'):
        output += f"   Namespace: {finding['namespace']}\n"

    output += f"   {description}\n"

    if recommendation:
        output += f"   → Recommendation: {recommendation}\n"

    return output


def print_report(findings: List[Dict[str, Any]], stats: Dict[str, Any], mode: str):
    """Print formatted analysis report"""

    # Header
    if stats['namespaces'] == 1:
        ns_list = list(stats['policies_by_namespace'].keys())
        print(f"\nNetworkPolicy {mode.capitalize()} Analysis - namespace: {ns_list[0]}")
    else:
        print(f"\nNetworkPolicy {mode.capitalize()} Analysis - Cluster-Wide")
        print(f"Scanned: {stats['namespaces']} namespaces, {stats['total_policies']} policies")

    print("=" * 70)

    if not findings:
        print("\n✅ No issues found! All policies follow best practices.\n")
        return

    # Group findings by severity
    critical = [f for f in findings if f['severity'] == Severity.CRITICAL]
    warnings = [f for f in findings if f['severity'] == Severity.WARNING]
    info = [f for f in findings if f['severity'] == Severity.INFO]

    # Critical issues
    if critical:
        print(f"\n🔴 CRITICAL ISSUES ({len(critical)})")
        print("-" * 70)
        for finding in critical:
            print(format_finding(finding))

    # Warnings
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)})")
        print("-" * 70)
        for finding in warnings:
            print(format_finding(finding))

    # Info
    if info:
        print(f"\nℹ️  INFORMATIONAL ({len(info)})")
        print("-" * 70)
        for finding in info:
            print(format_finding(finding))

    # Statistics
    print("\n📊 STATISTICS")
    print("-" * 70)
    print(f"  Total policies: {stats['total_policies']}")
    print(f"  Namespaces analyzed: {stats['namespaces']}")
    print(f"  Critical findings: {stats['critical_findings']}")
    print(f"  Warnings: {stats['warning_findings']}")
    print(f"  Info findings: {stats['info_findings']}")

    # Security score (for security mode)
    if mode == 'security':
        total_checks = len(findings)
        passed_checks = max(0, 10 - stats['critical_findings'] - stats['warning_findings'] // 2)
        total_possible = 10
        score = int((passed_checks / total_possible) * 100)
        print(f"  Security score: {score}/100")

    print("\n" + "=" * 70)

    # Recommended actions
    if critical:
        print("\n🔧 RECOMMENDED ACTIONS (Priority Order)")
        print("-" * 70)
        for idx, finding in enumerate(critical[:5], 1):  # Top 5 critical
            print(f"  {idx}. [{finding['title']}]")
            if finding.get('recommendation'):
                print(f"     {finding['recommendation']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Analyze NetworkPolicies for security, performance, and compliance issues'
    )
    parser.add_argument(
        '--namespace',
        type=str,
        help='Target namespace to analyze'
    )
    parser.add_argument(
        '--cluster-wide',
        type=str,
        choices=['true', 'false'],
        default='false',
        help='Analyze all namespaces in cluster'
    )
    parser.add_argument(
        '--mode',
        type=str,
        choices=['security', 'performance', 'compliance'],
        default='security',
        help='Analysis mode'
    )
    parser.add_argument(
        '--kubeconfig',
        type=str,
        help='Path to kubeconfig file'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Enable verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    # Determine cluster-wide flag
    cluster_wide = args.cluster_wide == 'true'

    # Validate arguments
    if not cluster_wide and not args.namespace:
        print("Error: Either --namespace or --cluster-wide must be specified", file=sys.stderr)
        sys.exit(1)

    try:
        # Initialize parser
        logger.info("Initializing NetworkPolicy parser...")
        parser_obj = NetworkPolicyParser(
            namespace=args.namespace if not cluster_wide else None,
            cluster_wide=cluster_wide,
            kubeconfig=args.kubeconfig
        )

        # Fetch policies
        logger.info("Fetching NetworkPolicies from cluster...")
        policies_raw = parser_obj.get_policies()

        if not policies_raw:
            print(f"\n⚠️  No NetworkPolicies found", file=sys.stderr)
            if not cluster_wide:
                print(f"    Namespace: {args.namespace}", file=sys.stderr)
                print("\nThis is a CRITICAL security finding:", file=sys.stderr)
                print("Without NetworkPolicies, all traffic is allowed by default.", file=sys.stderr)
            sys.exit(1)

        # Parse policies
        logger.info(f"Parsing {len(policies_raw)} NetworkPolicies...")
        policies = [parser_obj.parse_policy(p) for p in policies_raw]

        # Analyze policies
        logger.info(f"Running {args.mode} analysis...")
        analyzer = SecurityAnalyzer(policies)
        findings = analyzer.analyze(mode=args.mode)
        stats = analyzer.get_statistics()

        # Print report
        print_report(findings, stats, args.mode)

        # Exit code based on findings
        if stats['critical_findings'] > 0:
            sys.exit(1)  # Critical issues found
        else:
            sys.exit(0)  # Success

    except Exception as e:
        print(f"\n❌ Error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    main()
