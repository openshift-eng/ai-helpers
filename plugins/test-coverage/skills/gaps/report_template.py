#!/usr/bin/env python3
"""
Custom report template that matches the exact format of the example report
"""

from datetime import datetime
from typing import Dict, List
import re


def generate_custom_gap_report(analysis: Dict, scores: Dict, output_path: str):
    """Generate gap report matching the exact format of the example"""

    file_name = analysis['file'].split('/')[-1]
    file_path = analysis['file']
    test_count = analysis['test_count']
    component = analysis.get('component_type', 'unknown').title()
    coverage = analysis['coverage']
    gaps = analysis['gaps']
    test_cases = analysis.get('test_cases', [])

    # Flatten all gaps and assign GAP IDs
    all_gaps = []
    gap_id_counter = 1

    # Collect all gaps from different categories
    for category, gap_list in gaps.items():
        for gap in gap_list:
            gap_copy = gap.copy()
            gap_copy['gap_id'] = f"GAP-{gap_id_counter:03d}"
            gap_copy['category'] = category.replace('_', ' ').title()
            gap_id_counter += 1
            all_gaps.append(gap_copy)

    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    all_gaps.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 3))

    # Count gaps by priority
    high_count = sum(1 for g in all_gaps if g.get('priority') == 'high')
    medium_count = sum(1 for g in all_gaps if g.get('priority') == 'medium')
    low_count = sum(1 for g in all_gaps if g.get('priority') == 'low')

    # Determine score card classes
    def get_score_class(score):
        if score >= 80: return 'excellent'
        elif score >= 60: return 'good'
        elif score >= 40: return 'fair'
        else: return 'poor'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Coverage Gap Analysis - {file_name}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; margin-bottom: 10px; font-size: 2em; }}
        h2 {{ color: #34495e; margin-top: 30px; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #e74c3c; font-size: 1.5em; }}
        h3 {{ color: #34495e; margin-top: 20px; margin-bottom: 10px; font-size: 1.2em; }}
        .metadata {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin-bottom: 25px; }}
        .metadata p {{ margin: 5px 0; }}
        .score-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin: 20px 0; }}
        .score-card {{ padding: 20px; border-radius: 8px; text-align: center; color: white; }}
        .score-card.excellent {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
        .score-card.good {{ background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); }}
        .score-card.fair {{ background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); }}
        .score-card.poor {{ background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); }}
        .score-card .number {{ font-size: 2.5em; font-weight: bold; margin: 10px 0; }}
        .score-card .label {{ font-size: 0.9em; opacity: 0.9; }}
        .gap-card {{ background: #fff; border-left: 4px solid #e74c3c; padding: 20px; margin: 15px 0; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .gap-card.high {{ border-left-color: #e74c3c; }}
        .gap-card.medium {{ border-left-color: #f39c12; }}
        .gap-card.low {{ border-left-color: #3498db; }}
        .gap-card h4 {{ color: #2c3e50; margin-bottom: 10px; font-size: 1.1em; }}
        .gap-card .gap-id {{ font-family: "Courier New", monospace; font-size: 0.85em; color: #7f8c8d; margin-bottom: 5px; }}
        .gap-card .priority {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.75em; font-weight: bold; margin-right: 8px; }}
        .priority.high {{ background: #e74c3c; color: white; }}
        .priority.medium {{ background: #f39c12; color: white; }}
        .priority.low {{ background: #3498db; color: white; }}
        .gap-card .category {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.75em; background: #95a5a6; color: white; margin-right: 8px; }}
        .gap-card p {{ margin: 10px 0; }}
        .gap-card .impact {{ background: #fff3cd; border-left: 3px solid #ffc107; padding: 10px; margin: 10px 0; border-radius: 3px; }}
        .gap-card .recommendation {{ background: #d4edda; border-left: 3px solid #28a745; padding: 10px; margin: 10px 0; border-radius: 3px; }}
        .gap-card .effort {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }}
        .effort.low {{ background: #d4edda; color: #155724; }}
        .effort.medium {{ background: #fff3cd; color: #856404; }}
        .effort.high {{ background: #f8d7da; color: #721c24; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #34495e; color: white; font-weight: 600; }}
        tr:hover {{ background: #f5f5f5; }}
        .tested {{ background: #d4edda; color: #155724; font-weight: bold; text-align: center; }}
        .not-tested {{ background: #f8d7da; color: #721c24; font-weight: bold; text-align: center; }}
        .partial {{ background: #fff3cd; color: #856404; font-weight: bold; text-align: center; }}
        .summary-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .warning-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .success-box {{ background: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: "Courier New", monospace; font-size: 0.9em; }}
        ul {{ margin: 10px 0 10px 20px; }}
        li {{ margin: 5px 0; }}
        .filter-buttons {{ margin: 20px 0; }}
        .filter-btn {{ padding: 10px 20px; margin-right: 10px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }}
        .filter-btn.active {{ box-shadow: 0 0 0 3px rgba(0,0,0,0.2); }}
        .filter-btn.all {{ background: #95a5a6; color: white; }}
        .filter-btn.high {{ background: #e74c3c; color: white; }}
        .filter-btn.medium {{ background: #f39c12; color: white; }}
        .filter-btn.low {{ background: #3498db; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Test Coverage Gap Analysis</h1>

        <div class="metadata">
            <p><strong>File:</strong> <code>{file_name}</code></p>
            <p><strong>Path:</strong> <code>{file_path}</code></p>
            <p><strong>Component:</strong> {component}</p>
            <p><strong>Analysis Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>
            <p><strong>Total Test Cases:</strong> {test_count}</p>
        </div>

        <h2>Coverage Scores</h2>
        <div class="score-grid">
"""

    # Define display order and labels for score cards
    # This allows any component to define custom scores while maintaining consistent ordering
    SCORE_DISPLAY = {
        'overall': {'order': 1, 'label': 'Overall Coverage'},
        'platform_coverage': {'order': 2, 'label': 'Platform Coverage'},
        'ip_stack_coverage': {'order': 3, 'label': 'IP Stack Coverage'},
        'topology_coverage': {'order': 4, 'label': 'Topology Coverage'},
        'protocol_coverage': {'order': 5, 'label': 'Protocol Coverage'},
        'service_type_coverage': {'order': 6, 'label': 'Service Type Coverage'},
        'scenario_coverage': {'order': 7, 'label': 'Scenario Coverage'},
        'storage_class_coverage': {'order': 8, 'label': 'Storage Class Coverage'},
        'volume_mode_coverage': {'order': 9, 'label': 'Volume Mode Coverage'},
        'volume_coverage': {'order': 10, 'label': 'Volume Type Coverage'},
        'csi_driver_coverage': {'order': 11, 'label': 'CSI Driver Coverage'},
        'snapshot_coverage': {'order': 12, 'label': 'Snapshot Coverage'},
        'operator_coverage': {'order': 13, 'label': 'Operator Coverage'},
        'api_coverage': {'order': 14, 'label': 'API Coverage'},
        'rbac_coverage': {'order': 15, 'label': 'RBAC Coverage'},
    }

    # Sort scores by defined order, then render dynamically
    sorted_scores = sorted(
        scores.items(),
        key=lambda x: SCORE_DISPLAY.get(x[0], {}).get('order', 999)
    )

    for score_key, score_value in sorted_scores:
        # Skip if score is 0 or None (not calculated for this component)
        if score_value is None or (score_value == 0 and score_key not in ['overall', 'platform_coverage']):
            continue

        # Get label or generate from key
        display_info = SCORE_DISPLAY.get(score_key, {})
        label = display_info.get('label', score_key.replace('_', ' ').title())

        html += f"""            <div class="score-card {get_score_class(score_value)}">
                <div class="label">{label}</div>
                <div class="number">{score_value:.1f}%</div>
            </div>
"""

    html += """        </div>
"""

    # Add warning box if coverage is low
    if scores['overall'] < 60:
        html += f"""
        <div class="warning-box">
            <h3>⚠️ Key Finding</h3>
            <p><strong>Overall coverage is {scores['overall']:.1f}% with critical gaps.</strong></p>
            <p>Focus on addressing high-priority gaps to improve test coverage and production readiness.</p>
        </div>
"""

    # Add "What's Tested" section for all components
    html += _generate_whats_tested_section(coverage, scores, test_cases, component.lower())

    # Add gaps section
    html += f"""
        <h2>Coverage Gaps by Priority</h2>

        <div class="summary-box">
            <h3>Gap Summary</h3>
            <ul>
                <li><strong>High Priority Gaps:</strong> {high_count} (require immediate attention)</li>
                <li><strong>Medium Priority Gaps:</strong> {medium_count} (important for comprehensive coverage)</li>
                <li><strong>Low Priority Gaps:</strong> {low_count} (nice to have)</li>
                <li><strong>Total Gaps Identified:</strong> {len(all_gaps)}</li>
            </ul>
        </div>

        <div class="filter-buttons">
            <button class="filter-btn all active" onclick="filterGaps('all')">All Gaps ({len(all_gaps)})</button>
            <button class="filter-btn high" onclick="filterGaps('high')">High Priority ({high_count})</button>
            <button class="filter-btn medium" onclick="filterGaps('medium')">Medium Priority ({medium_count})</button>
            <button class="filter-btn low" onclick="filterGaps('low')">Low Priority ({low_count})</button>
        </div>

        <div id="gaps-container">
"""

    # Add gap cards
    for gap in all_gaps:
        html += _generate_gap_card(gap)

    html += """
        </div>

        <h2>Recommendations</h2>
        <div class="success-box">
            <h3>Immediate Actions (High Priority)</h3>
            <ul>
"""

    for gap in [g for g in all_gaps if g.get('priority') == 'high'][:5]:
        html += f"                <li>{gap.get('recommendation', 'No recommendation')}</li>\n"

    html += """
            </ul>
        </div>

        <script>
        function filterGaps(priority) {
            const cards = document.querySelectorAll('.gap-card');
            const buttons = document.querySelectorAll('.filter-btn');

            buttons.forEach(btn => btn.classList.remove('active'));
            document.querySelector(`.filter-btn.${priority}`).classList.add('active');

            cards.forEach(card => {
                if (priority === 'all' || card.dataset.priority === priority) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
        </script>
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def _analyze_feature_coverage(test_cases: List[Dict], component_type: str = 'unknown') -> Dict:
    """Analyze which features are tested across IP stacks (component-aware)"""

    # Detect component-specific features from test content
    test_content = ' '.join([t.get('name', '') for t in test_cases]).lower()

    # Build feature list based on what's actually being tested
    features = {}

    # Generic networking features (apply to most networking components)
    features['Node Restart'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}
    features['Node Reboot'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}
    features['Node Deletion'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}

    # Add component-specific features only if detected in test content
    if 'udn' in test_content or 'user defined network' in test_content:
        features['Non-overlapping UDNs'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}
        features['Overlapping UDNs'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}
        features['UDN Recreation'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}

    if 'egressip' in test_content or 'egress ip' in test_content:
        features['EgressIP Failover'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}

    if 'ovnk' in test_content or 'ovn-kubernetes' in test_content:
        features['OVNK Restart'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}

    if 'load balanc' in test_content:
        features['Load Balancing'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}

    if 'firewall' in test_content or 'infw' in test_content:
        features['Firewall Rules'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}
        features['Allow/Deny Rules'] = {'ipv4': False, 'ipv6': False, 'dualstack': False}

    for test in test_cases:
        name = test.get('name', '').lower()

        # Detect IP stack explicitly mentioned in test name
        has_ipv4 = 'ipv4' in name or 'IPv4' in test.get('name', '')
        has_ipv6 = 'ipv6' in name or 'IPv6' in test.get('name', '') or 'ipv6single' in name
        has_dualstack = 'dualstack' in name or 'dual' in name

        # If no IP stack mentioned in name, assume test covers all stacks
        # (many tests check ipStackType in code and handle all cases)
        no_stack_specified = not (has_ipv4 or has_ipv6 or has_dualstack)

        # Helper to set IP stack for a feature
        def set_ip_stack(feature_name):
            if feature_name in features:
                if no_stack_specified:
                    # Test doesn't specify stack in name - mark all as tested
                    features[feature_name]['ipv4'] = True
                    features[feature_name]['ipv6'] = True
                    features[feature_name]['dualstack'] = True
                elif has_dualstack:
                    features[feature_name]['dualstack'] = True
                elif has_ipv6:
                    features[feature_name]['ipv6'] = True
                elif has_ipv4:
                    features[feature_name]['ipv4'] = True

        # Detect component-specific features based on test name
        if 'non-overlapping' in name:
            set_ip_stack('Non-overlapping UDNs')

        if 'overlapping' in name and 'non-overlapping' not in name:
            set_ip_stack('Overlapping UDNs')

        if 'failover' in name:
            set_ip_stack('EgressIP Failover')

        if 'deleted then recreated' in name or 'recreation' in name:
            set_ip_stack('UDN Recreation')

        if 'ovnk restarted' in name or 'ovnk restart' in name:
            set_ip_stack('OVNK Restart')

        if 'restart' in name and 'ovnk' not in name:
            set_ip_stack('Node Restart')

        if 'reboot' in name:
            set_ip_stack('Node Reboot')

        if 'node after previous' in name or 'node was deleted' in name or 'deletion' in name:
            set_ip_stack('Node Deletion')

        if 'load balanced' in name:
            set_ip_stack('Load Balancing')

        if 'firewall' in name or 'allow' in name or 'deny' in name or 'block' in name:
            set_ip_stack('Firewall Rules')
            if 'allow' in name or 'deny' in name:
                set_ip_stack('Allow/Deny Rules')

    return features


def _analyze_scenario_coverage(test_cases: List[Dict], component_type: str = 'unknown') -> Dict:
    """Analyze which scenarios are covered (component-aware)"""
    scenarios = {}

    # Detect component-specific scenarios from test content
    test_content = ' '.join([t.get('name', '') for t in test_cases]).lower()

    # Analyze test names to determine coverage
    has_non_overlapping = any('non-overlapping' in t.get('name', '').lower() for t in test_cases)
    has_overlapping = any('overlapping' in t.get('name', '').lower() for t in test_cases)
    has_failover = any('failover' in t.get('name', '').lower() for t in test_cases)
    has_recreation = any('deleted then recreated' in t.get('name', '').lower() or 'recreation' in t.get('name', '').lower() for t in test_cases)
    has_ovnk_restart = any('ovnk restarted' in t.get('name', '').lower() for t in test_cases)
    has_reboot = any('reboot' in t.get('name', '').lower() for t in test_cases)
    has_deletion = any('node was deleted' in t.get('name', '').lower() or 'node after previous' in t.get('name', '').lower() or 'deletion' in t.get('name', '').lower() for t in test_cases)
    has_load_balancing = any('load balanced' in t.get('name', '').lower() for t in test_cases)
    has_restart = any('restart' in t.get('name', '').lower() for t in test_cases)

    # Check for IPv4/IPv6/dualstack in these tests
    ipv4_only = lambda tests: all('ipv4' in t.get('name', '').lower() and 'ipv6' not in t.get('name', '').lower() for t in tests if tests)

    # Only add component-specific scenarios if they're relevant
    if 'udn' in test_content or 'user defined network' in test_content:
        if has_non_overlapping or has_overlapping:
            scenarios['Non-overlapping/Overlapping UDNs'] = {'status': 'tested', 'gap': '-'}

        if has_recreation:
            scenarios['UDN Deletion/Recreation'] = {'status': 'tested', 'gap': '-'}

    if 'egressip' in test_content or 'egress ip' in test_content:
        if has_failover:
            scenarios['EgressIP Failover'] = {'status': 'tested', 'gap': '-'}

    if 'ovnk' in test_content or 'ovn-kubernetes' in test_content:
        if has_ovnk_restart:
            scenarios['OVNK Pod Restart'] = {'status': 'tested', 'gap': '-'}

    # Generic scenarios (apply to all components)
    if has_restart:
        scenarios['Component Restart'] = {'status': 'tested', 'gap': '-'}

    if has_reboot:
        reboot_tests = [t for t in test_cases if 'reboot' in t.get('name', '').lower()]
        if ipv4_only(reboot_tests):
            scenarios['Node Reboot'] = {'status': 'partial', 'gap': 'IPv4 only'}
        else:
            scenarios['Node Reboot'] = {'status': 'tested', 'gap': '-'}
    else:
        scenarios['Node Reboot'] = {'status': 'not-tested', 'gap': 'Node reboot scenario not covered'}

    if has_deletion:
        deletion_tests = [t for t in test_cases if 'deleted' in t.get('name', '').lower() or 'deletion' in t.get('name', '').lower()]
        if ipv4_only(deletion_tests):
            scenarios['Node Deletion'] = {'status': 'partial', 'gap': 'IPv4 only'}
        else:
            scenarios['Node Deletion'] = {'status': 'tested', 'gap': '-'}
    else:
        scenarios['Node Deletion'] = {'status': 'not-tested', 'gap': 'Node deletion not covered'}

    if has_load_balancing:
        lb_tests = [t for t in test_cases if 'load balanced' in t.get('name', '').lower()]
        if ipv4_only(lb_tests):
            scenarios['Load Balancing'] = {'status': 'partial', 'gap': 'IPv4 only'}
        else:
            scenarios['Load Balancing'] = {'status': 'tested', 'gap': '-'}

    # Standard scenarios that apply to all components
    has_error_handling = any('invalid' in t.get('name', '').lower() or 'negative' in t.get('name', '').lower() or 'error' in t.get('name', '').lower() for t in test_cases)
    has_exhaustion = any('exhaustion' in t.get('name', '').lower() for t in test_cases)
    has_rbac = any('rbac' in t.get('name', '').lower() or 'permission' in t.get('name', '').lower() for t in test_cases)
    has_performance = any('performance' in t.get('name', '').lower() or 'scale' in t.get('name', '').lower() for t in test_cases)
    has_upgrade = any('upgrade' in t.get('name', '').lower() for t in test_cases)

    if not has_error_handling:
        scenarios['Error Handling (Invalid Config)'] = {'status': 'not-tested', 'gap': 'Critical gap - no negative tests'}

    # Only add EgressIP Exhaustion scenario if component is actually testing EgressIP
    if ('egressip' in test_content or 'egress ip' in test_content) and not has_exhaustion:
        scenarios['EgressIP Exhaustion'] = {'status': 'not-tested', 'gap': 'Resource limits not validated'}

    if not has_rbac:
        scenarios['RBAC/Security'] = {'status': 'not-tested', 'gap': 'Permission model not validated'}

    if not has_performance:
        scenarios['Performance/Scale'] = {'status': 'not-tested', 'gap': 'No throughput/latency/scale tests'}

    if not has_upgrade:
        scenarios['Operator Upgrades'] = {'status': 'not-tested', 'gap': 'Critical for production - upgrade path not tested'}

    return scenarios


def _generate_whats_tested_section(coverage: Dict, scores: Dict, test_cases: List[Dict], component_type: str = 'unknown') -> str:
    """Generate 'What's Tested vs Not Tested' tables (component-aware)"""
    html = """
        <h2>What's Tested vs. Not Tested</h2>
"""

    # Protocol Coverage - Only for networking components AND if protocols are detected in tests
    protocols_data = coverage.get('protocols', {})
    has_protocol_data = len(protocols_data.get('tested', [])) + len(protocols_data.get('not_tested', [])) > 0

    if component_type in ('networking', 'router', 'dns', 'network-observability') and has_protocol_data:
        html += """
        <h3>Protocol Coverage</h3>
        <table>
            <thead>
                <tr>
                    <th>Protocol</th>
                    <th>Status</th>
                    <th>Coverage</th>
                </tr>
            </thead>
            <tbody>
"""

        # Protocol rows
        all_protocols = [
            ('HTTP (over TCP)', 'Used for validation via curl'),
            ('TCP (native)', 'No TCP-specific tests (port allocation, connection tracking)'),
            ('UDP', 'Critical for DNS, streaming, VoIP, IoT workloads'),
            ('SCTP', 'Important for telco/5G workloads'),
            ('ICMP', 'Needed for ping/traceroute troubleshooting'),
        ]
        tested = protocols_data.get('tested', [])

        # Check if HTTP is used (via curl in tests)
        test_cases_str = str(test_cases).lower()
        has_http = 'curl' in test_cases_str or 'http' in test_cases_str

        for proto, desc in all_protocols:
            proto_name = proto.split()[0]  # Get base protocol name
            if proto == 'HTTP (over TCP)' and has_http:
                html += f"""                <tr>
                    <td>{proto}</td>
                    <td class="tested">✓ TESTED</td>
                    <td>{desc}</td>
                </tr>
"""
            elif proto_name in tested:
                html += f"""                <tr>
                    <td>{proto}</td>
                    <td class="tested">✓ TESTED</td>
                    <td>{proto_name} protocol validated</td>
                </tr>
"""
            else:
                html += f"""                <tr>
                    <td>{proto}</td>
                    <td class="not-tested">✗ NOT TESTED</td>
                    <td>{desc}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>
"""

    # Platform Coverage - All components
    html += """
        <h3>Platform Coverage</h3>
        <table>
            <thead>
                <tr>
                    <th>Platform</th>
                    <th>Status</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
"""

    # Platform rows
    platforms_data = coverage.get('platforms', {})
    tested_platforms = platforms_data.get('tested', [])

    all_platforms = [
        'AWS', 'GCP', 'Azure', 'OpenStack', 'vSphere',
        'Bare Metal', 'Nutanix', 'PowerVS', 'IBM Cloud', 'Alibaba Cloud'
    ]

    for platform in all_platforms:
        if platform in tested_platforms:
            html += f"""                <tr>
                    <td>{platform}</td>
                    <td class="tested">✓ TESTED</td>
                    <td>Covered in test suite</td>
                </tr>
"""
        elif platform == 'IBM Cloud' and 'PowerVS' in tested_platforms:
            html += f"""                <tr>
                    <td>{platform}</td>
                    <td class="partial">⚠ PARTIAL</td>
                    <td>PowerVS covered, not standard IBM Cloud</td>
                </tr>
"""
        else:
            html += f"""                <tr>
                    <td>{platform}</td>
                    <td class="not-tested">✗ NOT TESTED</td>
                    <td>Platform not covered</td>
                </tr>
"""

    html += """
            </tbody>
        </table>
"""

    # IP Stack Coverage - Only for networking components AND if IP stacks are detected
    ip_stacks_data = coverage.get('ip_stacks', {})
    has_ip_stack_data = len(ip_stacks_data.get('tested', [])) + len(ip_stacks_data.get('not_tested', [])) > 0

    if component_type in ('networking', 'router', 'dns', 'network-observability') and has_ip_stack_data:
        html += """
        <h3>IP Stack Coverage</h3>
        <table>
            <thead>
                <tr>
                    <th>Feature</th>
                    <th>IPv4</th>
                    <th>IPv6</th>
                    <th>Dualstack</th>
                </tr>
            </thead>
            <tbody>
"""

        # Analyze feature coverage
        features = _analyze_feature_coverage(test_cases, component_type)

        for feature_name, stacks in features.items():
            html += f"""                <tr>
                    <td>{feature_name}</td>
                    <td class="{'tested' if stacks['ipv4'] else 'not-tested'}">{'✓' if stacks['ipv4'] else '✗'}</td>
                    <td class="{'tested' if stacks['ipv6'] else 'not-tested'}">{'✓' if stacks['ipv6'] else '✗'}</td>
                    <td class="{'tested' if stacks['dualstack'] else 'not-tested'}">{'✓' if stacks['dualstack'] else '✗'}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>
"""

    # Topology Coverage - Only if topology patterns are detected in tests
    topologies_data = coverage.get('topologies', {})
    has_topology_data = len(topologies_data.get('tested', [])) + len(topologies_data.get('not_tested', [])) > 0

    if component_type in ('networking', 'router', 'dns', 'network-observability', 'node', 'kata', 'windows-containers', 'apiserver', 'etcd', 'installer', 'hypershift', 'mco') and has_topology_data:
        html += """
        <h3>Topology Coverage</h3>
        <table>
            <thead>
                <tr>
                    <th>Topology</th>
                    <th>Status</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
"""
        tested_topologies = topologies_data.get('tested', [])

        all_topologies = [
            ('Multi-Node', 'Standard HA cluster with 3+ control plane nodes'),
            ('Single Node', 'SNO - Single Node OpenShift for edge deployments'),
            ('Hosted Control Plane', 'HyperShift - Decoupled control plane')
        ]

        for topo, desc in all_topologies:
            if topo in tested_topologies:
                html += f"""                <tr>
                    <td>{topo}</td>
                    <td class="tested">✓ TESTED</td>
                    <td>{desc}</td>
                </tr>
"""
            else:
                html += f"""                <tr>
                    <td>{topo}</td>
                    <td class="not-tested">✗ NOT TESTED</td>
                    <td>{desc}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>
"""

    # Scenario Coverage - All components
    html += """
        <h3>Scenario Coverage</h3>
        <table>
            <thead>
                <tr>
                    <th>Scenario</th>
                    <th>Status</th>
                    <th>Gap</th>
                </tr>
            </thead>
            <tbody>
"""

    # Analyze scenario coverage
    scenarios = _analyze_scenario_coverage(test_cases, component_type)

    for scenario_name, info in scenarios.items():
        status = info['status']
        gap = info['gap']

        html += f"""                <tr>
                    <td>{scenario_name}</td>
                    <td class="{status}">{'✓ TESTED' if status == 'tested' else '⚠ PARTIAL' if status == 'partial' else '✗ NOT TESTED'}</td>
                    <td>{gap}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>
"""

    return html


def _generate_gap_card(gap: Dict) -> str:
    """Generate a single gap card HTML"""
    gap_id = gap.get('gap_id', 'GAP-000')
    priority = gap.get('priority', 'low')
    category = gap.get('category', 'General')
    impact = gap.get('impact', 'No impact specified')
    recommendation = gap.get('recommendation', 'No recommendation')
    effort = gap.get('effort', 'medium')
    coverage_improvement = gap.get('coverage_improvement', 0)

    # Get the gap name/title from the gap data
    title = gap.get('protocol') or gap.get('scenario') or gap.get('platform') or gap.get('service_type') or gap.get('ip_stack') or gap.get('topology') or 'Coverage Gap'

    return f"""
            <div class="gap-card {priority}" data-priority="{priority}">
                <div class="gap-id">{gap_id}</div>
                <h4><span class="priority {priority}">{priority.upper()}</span><span class="category">{category}</span> {title}</h4>
                <div class="impact">
                    <strong>Impact:</strong> {impact}
                </div>
                <div class="recommendation">
                    <strong>Recommendation:</strong> {recommendation}
                </div>
                <p><strong>Effort:</strong> <span class="effort {effort}">{effort.title()}</span> | <strong>Coverage Improvement:</strong> +{coverage_improvement:.1f}%</p>
            </div>
"""
