#!/usr/bin/env python3
"""
Test Coverage Report Generator
Consolidated module for generating HTML, JSON, and text reports for both:
- Test structure analysis
- E2E test gap analysis
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

# Import component type constants
try:
    from ..gaps.gap_analyzer import NETWORK_COMPONENTS, STORAGE_COMPONENTS
except ImportError:
    try:
        from gaps.gap_analyzer import NETWORK_COMPONENTS, STORAGE_COMPONENTS
    except ImportError:
        # Fallback if imports fail
        NETWORK_COMPONENTS = {'networking', 'router', 'dns', 'network-observability'}
        STORAGE_COMPONENTS = {'storage', 'csi'}

# Import shared CSS styles
try:
    from ...utils.common.report_styles import get_common_css
except ImportError:
    try:
        from plugins.test_coverage.utils.common.report_styles import get_common_css
    except ImportError:
        from utils.common.report_styles import get_common_css

# Import test structure HTML generation functions
try:
    from .test_structure_reports import (
        generate_test_structure_html,
        generate_comprehensive_html
    )
except ImportError:
    try:
        from test_structure_reports import (
            generate_test_structure_html,
            generate_comprehensive_html
        )
    except ImportError:
        from plugins.test_coverage.skills.analyze.test_structure_reports import (
            generate_test_structure_html,
            generate_comprehensive_html
        )


# ============================================================================
# E2E Test Gap Analysis Reports
# ============================================================================

def generate_gap_html_report(analysis: Dict, scores: Dict, output_path: str):
    """Generate HTML report for E2E test gap analysis"""

    file_name = os.path.basename(analysis['file'])
    test_count = analysis['test_count']
    coverage = analysis['coverage']
    gaps = analysis['gaps']
    component_type = analysis.get('component_type', 'unknown')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Coverage Gap Analysis - {file_name}</title>
    <style>
        {get_common_css()}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Test Coverage Gap Analysis</h1>
            <div class="meta">
                <strong>File:</strong> {file_name} |
                <strong>Test Cases:</strong> {test_count} |
                <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>

        <div class="score-section">
            <div class="overall-score">
                <div class="score-circle" style="--score: {scores['overall']}">
                    <div class="score-value">{scores['overall']:.0f}</div>
                </div>
                <h2>Overall Coverage Score</h2>
                <p style="color: #666; margin-top: 10px;">Component-aware scoring based on relevant metrics</p>
            </div>

            <div class="score-grid">
                <div class="score-card">
                    <h3>Platform Coverage</h3>
                    <div class="value">{scores['platform_coverage']:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {scores['platform_coverage']}%"></div>
                    </div>
                </div>"""

    # Add component-specific metrics
    if component_type in NETWORK_COMPONENTS:
        html += f"""
                <div class="score-card">
                    <h3>Protocol Coverage</h3>
                    <div class="value">{scores['protocol_coverage']:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {scores['protocol_coverage']}%"></div>
                    </div>
                </div>
                <div class="score-card">
                    <h3>Service Type Coverage</h3>
                    <div class="value">{scores['service_type_coverage']:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {scores['service_type_coverage']}%"></div>
                    </div>
                </div>
                <div class="score-card">
                    <h3>IP Stack Coverage</h3>
                    <div class="value">{scores['ip_stack_coverage']:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {scores['ip_stack_coverage']}%"></div>
                    </div>
                </div>
                <div class="score-card">
                    <h3>Topology Coverage</h3>
                    <div class="value">{scores['topology_coverage']:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {scores['topology_coverage']}%"></div>
                    </div>
                </div>"""
    elif component_type in STORAGE_COMPONENTS:
        html += f"""
                <div class="score-card">
                    <h3>Storage Class Coverage</h3>
                    <div class="value">{scores['storage_class_coverage']:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {scores['storage_class_coverage']}%"></div>
                    </div>
                </div>
                <div class="score-card">
                    <h3>Volume Mode Coverage</h3>
                    <div class="value">{scores['volume_mode_coverage']:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {scores['volume_mode_coverage']}%"></div>
                    </div>
                </div>"""

    html += f"""
                <div class="score-card">
                    <h3>Scenario Coverage</h3>
                    <div class="value">{scores['scenario_coverage']:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {scores['scenario_coverage']}%"></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>📊 Coverage Matrices</h2>
"""

    # Platform matrix (all components)
    html += """
            <h3 style="margin: 30px 0 15px;">Platform Coverage</h3>
            <table class="matrix-table">
                <thead>
                    <tr>
                        <th>Platform</th>
                        <th>Status</th>
                        <th>Gap Impact</th>
                    </tr>
                </thead>
                <tbody>
"""

    # Platform matrix
    all_platforms = ['vSphere', 'ROSA', 'AWS', 'Azure', 'GCP', 'Bare Metal']
    tested_platforms = coverage['platforms']['tested']
    platform_impacts = {
        'vSphere': 'On-premise deployments',
        'ROSA': 'Managed OpenShift on AWS',
        'AWS': 'Standard AWS deployments',
        'Azure': 'Major cloud provider - High impact',
        'GCP': 'Major cloud provider - High impact',
        'Bare Metal': 'Edge/on-premise scenarios'
    }

    for platform in all_platforms:
        is_tested = platform in tested_platforms
        status_class = 'status-tested' if is_tested else 'status-not-tested'
        status_text = '✓ Tested' if is_tested else '✗ Not Tested'
        impact = platform_impacts.get(platform, '')

        html += f"""
                    <tr>
                        <td><strong>{platform}</strong></td>
                        <td><span class="status-badge {status_class}">{status_text}</span></td>
                        <td>{impact}</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
"""

    # Add component-specific matrices
    if component_type in NETWORK_COMPONENTS:
        # Protocol matrix
        html += """
            <h3 style="margin: 30px 0 15px;">Protocol Coverage</h3>
            <table class="matrix-table">
                <thead>
                    <tr>
                        <th>Protocol</th>
                        <th>Status</th>
                        <th>Priority</th>
                    </tr>
                </thead>
                <tbody>
"""
        tested_protocols = coverage.get('protocols', {}).get('tested', [])
        not_tested_protocols = coverage.get('protocols', {}).get('not_tested', [])
        all_protocols = tested_protocols + not_tested_protocols

        for protocol in all_protocols:
            is_tested = protocol in tested_protocols
            status_class = 'status-tested' if is_tested else 'status-not-tested'
            status_text = '✓ Tested' if is_tested else '✗ Not Tested'
            priority = 'high' if protocol in ['TCP', 'SCTP', 'UDP'] else 'medium'

            html += f"""
                    <tr>
                        <td><strong>{protocol}</strong></td>
                        <td><span class="status-badge {status_class}">{status_text}</span></td>
                        <td><span class="status-badge priority-{priority}">{priority.upper()}</span></td>
                    </tr>
"""

        html += """
                </tbody>
            </table>

            <h3 style="margin: 30px 0 15px;">Service Type Coverage</h3>
            <table class="matrix-table">
                <thead>
                    <tr>
                        <th>Service Type</th>
                        <th>Status</th>
                        <th>Use Case</th>
                    </tr>
                </thead>
                <tbody>
"""
        service_types = {
            'NodePort': 'External access via node ports',
            'LoadBalancer': 'Cloud load balancer integration',
            'ClusterIP': 'Internal cluster traffic'
        }
        tested_services = coverage.get('service_types', {}).get('tested', [])

        for service, use_case in service_types.items():
            is_tested = service in tested_services
            status_class = 'status-tested' if is_tested else 'status-not-tested'
            status_text = '✓ Tested' if is_tested else '✗ Not Tested'

            html += f"""
                    <tr>
                        <td><strong>{service}</strong></td>
                        <td><span class="status-badge {status_class}">{status_text}</span></td>
                        <td>{use_case}</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>
"""

    elif component_type in STORAGE_COMPONENTS:
        # Storage class matrix
        html += """
            <h3 style="margin: 30px 0 15px;">Storage Class Coverage</h3>
            <table class="matrix-table">
                <thead>
                    <tr>
                        <th>Storage Class</th>
                        <th>Status</th>
                        <th>Use Case</th>
                    </tr>
                </thead>
                <tbody>
"""
        tested_storage_classes = coverage.get('storage_classes', {}).get('tested', [])
        not_tested_storage_classes = coverage.get('storage_classes', {}).get('not_tested', [])
        all_storage_classes = tested_storage_classes + not_tested_storage_classes

        storage_class_use_cases = {
            'gp2': 'General purpose SSD',
            'gp3': 'Latest generation general purpose SSD',
            'io1': 'Provisioned IOPS SSD',
            'sc1': 'Cold HDD',
            'st1': 'Throughput optimized HDD',
            'standard': 'Previous generation magnetic'
        }

        for sc in all_storage_classes:
            is_tested = sc in tested_storage_classes
            status_class = 'status-tested' if is_tested else 'status-not-tested'
            status_text = '✓ Tested' if is_tested else '✗ Not Tested'
            use_case = storage_class_use_cases.get(sc, '')

            html += f"""
                    <tr>
                        <td><strong>{sc}</strong></td>
                        <td><span class="status-badge {status_class}">{status_text}</span></td>
                        <td>{use_case}</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>

            <h3 style="margin: 30px 0 15px;">Volume Mode Coverage</h3>
            <table class="matrix-table">
                <thead>
                    <tr>
                        <th>Volume Mode</th>
                        <th>Status</th>
                        <th>Use Case</th>
                    </tr>
                </thead>
                <tbody>
"""
        tested_volume_modes = coverage.get('volume_modes', {}).get('tested', [])
        not_tested_volume_modes = coverage.get('volume_modes', {}).get('not_tested', [])
        all_volume_modes = tested_volume_modes + not_tested_volume_modes

        volume_mode_use_cases = {
            'Filesystem': 'Standard filesystem mount',
            'Block': 'Raw block device'
        }

        for vm in all_volume_modes:
            is_tested = vm in tested_volume_modes
            status_class = 'status-tested' if is_tested else 'status-not-tested'
            status_text = '✓ Tested' if is_tested else '✗ Not Tested'
            use_case = volume_mode_use_cases.get(vm, '')

            html += f"""
                    <tr>
                        <td><strong>{vm}</strong></td>
                        <td><span class="status-badge {status_class}">{status_text}</span></td>
                        <td>{use_case}</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>
"""

    html += """
        </div>

        <div class="section" style="background: #fef2f2;">
            <h2>🚨 Identified Gaps</h2>
"""

    # Platform gaps (all components)
    if gaps.get('platforms'):
        html += "<h3 style='margin: 20px 0 15px;'>Platform Gaps</h3>"
        for gap in gaps['platforms']:
            priority_class = gap['priority']
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{gap['priority'].upper()} PRIORITY</span>
                    {gap['platform']}
                </h4>
                <div class="impact"><strong>Impact:</strong> {gap['impact']}</div>
                <div class="recommendation">💡 {gap['recommendation']}</div>
            </div>
"""

    # Protocol gaps (networking only)
    if component_type in NETWORK_COMPONENTS and gaps.get('protocols'):
        html += "<h3 style='margin: 20px 0 15px;'>Protocol Gaps</h3>"
        for gap in gaps['protocols']:
            priority_class = gap['priority']
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{gap['priority'].upper()} PRIORITY</span>
                    {gap['protocol']}
                </h4>
                <div class="impact"><strong>Impact:</strong> {gap['impact']}</div>
                <div class="recommendation">💡 {gap['recommendation']}</div>
            </div>
"""

    # Service type gaps (networking only)
    if component_type in NETWORK_COMPONENTS and gaps.get('service_types'):
        html += "<h3 style='margin: 20px 0 15px;'>Service Type Gaps</h3>"
        for gap in gaps['service_types']:
            priority_class = gap['priority']
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{gap['priority'].upper()} PRIORITY</span>
                    {gap['service_type']}
                </h4>
                <div class="impact"><strong>Impact:</strong> {gap['impact']}</div>
                <div class="recommendation">💡 {gap['recommendation']}</div>
            </div>
"""

    # IP stack gaps (networking only)
    if component_type in NETWORK_COMPONENTS and gaps.get('ip_stacks'):
        html += "<h3 style='margin: 20px 0 15px;'>IP Stack Gaps</h3>"
        for gap in gaps['ip_stacks']:
            priority_class = gap['priority']
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{gap['priority'].upper()} PRIORITY</span>
                    {gap['ip_stack']}
                </h4>
                <div class="impact"><strong>Impact:</strong> {gap['impact']}</div>
                <div class="recommendation">💡 {gap['recommendation']}</div>
            </div>
"""

    # Topology gaps (networking only)
    if component_type in NETWORK_COMPONENTS and gaps.get('topologies'):
        html += "<h3 style='margin: 20px 0 15px;'>Topology Gaps</h3>"
        for gap in gaps['topologies']:
            priority_class = gap['priority']
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{gap['priority'].upper()} PRIORITY</span>
                    {gap['topology']}
                </h4>
                <div class="impact"><strong>Impact:</strong> {gap['impact']}</div>
                <div class="recommendation">💡 {gap['recommendation']}</div>
            </div>
"""

    # Storage class gaps (storage only)
    if component_type in STORAGE_COMPONENTS and gaps.get('storage_classes'):
        html += "<h3 style='margin: 20px 0 15px;'>Storage Class Gaps</h3>"
        for gap in gaps['storage_classes']:
            priority_class = gap['priority']
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{gap['priority'].upper()} PRIORITY</span>
                    {gap['storage_class']}
                </h4>
                <div class="impact"><strong>Impact:</strong> {gap['impact']}</div>
                <div class="recommendation">💡 {gap['recommendation']}</div>
            </div>
"""

    # Volume mode gaps (storage only)
    if component_type in STORAGE_COMPONENTS and gaps.get('volume_modes'):
        html += "<h3 style='margin: 20px 0 15px;'>Volume Mode Gaps</h3>"
        for gap in gaps['volume_modes']:
            priority_class = gap['priority']
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{gap['priority'].upper()} PRIORITY</span>
                    {gap['volume_mode']}
                </h4>
                <div class="impact"><strong>Impact:</strong> {gap['impact']}</div>
                <div class="recommendation">💡 {gap['recommendation']}</div>
            </div>
"""

    # Scenario gaps (all components)
    if gaps.get('scenarios'):
        html += "<h3 style='margin: 20px 0 15px;'>Scenario Gaps</h3>"
        for gap in gaps['scenarios']:
            priority_class = gap['priority']
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{gap['priority'].upper()} PRIORITY</span>
                    {gap['scenario']}
                </h4>
                <div class="impact"><strong>Impact:</strong> {gap['impact']}</div>
                <div class="recommendation">💡 {gap['recommendation']}</div>
            </div>
"""

    html += """
        </div>

        <div class="section">
            <h2>✅ Test Cases Found</h2>
            <div class="test-cases">
"""

    for i, test in enumerate(analysis['test_cases'], 1):
        tags_html = ''.join([f'<span class="tag">{tag}</span>' for tag in test['tags']])
        html += f"""
                <div class="test-case">
                    <strong>{i}. {test['name'][:80]}{"..." if len(test['name']) > 80 else ""}</strong>
                    <div class="line">Line {test['line']} | ID: {test['id']}</div>
                    <div class="tags">{tags_html if tags_html else '<span class="tag">No tags</span>'}</div>
                </div>
"""

    html += """
            </div>
        </div>

        <div class="section" style="background: #f0fdf4;">
            <h2>📈 Recommendations</h2>
            <div style="background: white; padding: 20px; border-radius: 8px; margin-top: 20px;">
                <h3 style="color: #059669; margin-bottom: 15px;">🔴 High Priority (Production Blockers)</h3>
                <ul style="margin-left: 20px; line-height: 2;">
"""

    # High priority recommendations (component-aware)
    high_priority_gaps = []

    # Determine relevant gap categories based on component type
    if component_type in NETWORK_COMPONENTS:
        relevant_categories = ['platforms', 'protocols', 'service_types', 'ip_stacks', 'topologies', 'scenarios']
    elif component_type in STORAGE_COMPONENTS:
        relevant_categories = ['platforms', 'storage_classes', 'volume_modes', 'scenarios']
    else:
        # For other components (kube-api, etcd, auth, etc.), only platforms and scenarios
        relevant_categories = ['platforms', 'scenarios']

    # Collect high priority gaps from relevant categories only
    for category in relevant_categories:
        for gap in gaps.get(category, []):
            if gap.get('priority') == 'high':
                high_priority_gaps.append(gap['recommendation'])

    for rec in high_priority_gaps[:5]:
        html += f"<li>{rec}</li>\n"

    html += """
                </ul>

                <h3 style="color: #d97706; margin: 20px 0 15px;">🟡 Medium Priority</h3>
                <ul style="margin-left: 20px; line-height: 2;">
"""

    # Medium priority recommendations (component-aware, same categories as high priority)
    medium_priority_gaps = []
    for category in relevant_categories:
        for gap in gaps.get(category, []):
            if gap.get('priority') == 'medium':
                medium_priority_gaps.append(gap['recommendation'])

    for rec in medium_priority_gaps[:5]:
        html += f"<li>{rec}</li>\n"

    target_score = min(95, scores['overall'] + 20)

    html += f"""
                </ul>

                <div style="margin-top: 30px; padding: 20px; background: #f0fdf4; border-radius: 8px; border-left: 4px solid #059669;">
                    <strong>Target:</strong> Address high-priority gaps to improve coverage from
                    <strong style="color: #667eea;">{scores['overall']:.0f}%</strong> to
                    <strong style="color: #059669;">{target_score:.0f}%</strong>
                </div>
            </div>
        </div>

    </div>
</body>
</html>
"""

    with open(output_path, 'w') as f:
        f.write(html)


def generate_gap_json_report(analysis: Dict, scores: Dict, output_path: str):
    """Generate JSON report for E2E test gap analysis"""
    report = {
        'analysis': analysis,
        'scores': scores,
        'generated_at': datetime.now().isoformat()
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)


def generate_gap_text_report(analysis: Dict, scores: Dict, output_path: str):
    """Generate text summary report for E2E test gap analysis"""

    file_name = os.path.basename(analysis['file'])
    coverage = analysis['coverage']
    gaps = analysis['gaps']

    lines = [
        "=" * 60,
        "Test Coverage Gap Analysis",
        "=" * 60,
        "",
        f"File: {file_name}",
        f"Test Cases: {analysis['test_count']}",
        f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "=" * 60,
        "Coverage Scores",
        "=" * 60,
        "",
        f"Overall Coverage:          {scores.get('overall', 0):.1f}%",
        f"Platform Coverage:         {scores.get('platform_coverage', 0):.1f}%",
    ]

    # Component-aware scores
    component_type = analysis.get('component_type', 'unknown')

    if component_type in NETWORK_COMPONENTS:
        lines.extend([
            f"Protocol Coverage:         {scores.get('protocol_coverage', 0):.1f}%",
            f"Service Type Coverage:     {scores.get('service_type_coverage', 0):.1f}%",
            f"IP Stack Coverage:         {scores.get('ip_stack_coverage', 0):.1f}%",
            f"Topology Coverage:         {scores.get('topology_coverage', 0):.1f}%",
        ])
    elif component_type in STORAGE_COMPONENTS:
        lines.extend([
            f"Storage Class Coverage:    {scores.get('storage_class_coverage', 0):.1f}%",
            f"Volume Mode Coverage:      {scores.get('volume_mode_coverage', 0):.1f}%",
        ])

    lines.extend([
        f"Scenario Coverage:         {scores.get('scenario_coverage', 0):.1f}%",
        "",
        "=" * 60,
        "What's Tested",
        "=" * 60,
        "",
    ])

    # Platforms (all components)
    if coverage.get('platforms', {}).get('tested'):
        lines.append("Platforms:")
        lines.extend([f"  ✓ {p}" for p in coverage['platforms']['tested']])
        lines.append("")

    # Protocols (networking only)
    if component_type in NETWORK_COMPONENTS and coverage.get('protocols', {}).get('tested'):
        lines.append("Protocols:")
        lines.extend([f"  ✓ {p}" for p in coverage['protocols']['tested']])
        lines.append("")

    # Service Types (networking only)
    if component_type in NETWORK_COMPONENTS and coverage.get('service_types', {}).get('tested'):
        lines.append("Service Types:")
        lines.extend([f"  ✓ {s}" for s in coverage['service_types']['tested']])
        lines.append("")

    # IP Stacks (networking only)
    if component_type in NETWORK_COMPONENTS and coverage.get('ip_stacks', {}).get('tested'):
        lines.append("IP Stacks:")
        lines.extend([f"  ✓ {stack}" for stack in coverage['ip_stacks']['tested']])
        lines.append("")

    # Topologies (networking only)
    if component_type in NETWORK_COMPONENTS and coverage.get('topologies', {}).get('tested'):
        lines.append("Topologies:")
        lines.extend([f"  ✓ {topo}" for topo in coverage['topologies']['tested']])
        lines.append("")

    # Storage Classes (storage only)
    if component_type in STORAGE_COMPONENTS and coverage.get('storage_classes', {}).get('tested'):
        lines.append("Storage Classes:")
        lines.extend([f"  ✓ {sc}" for sc in coverage['storage_classes']['tested']])
        lines.append("")

    # Volume Modes (storage only)
    if component_type in STORAGE_COMPONENTS and coverage.get('volume_modes', {}).get('tested'):
        lines.append("Volume Modes:")
        lines.extend([f"  ✓ {vm}" for vm in coverage['volume_modes']['tested']])
        lines.append("")

    lines.extend([
        "=" * 60,
        "Identified Gaps",
        "=" * 60,
        "",
    ])

    # Add gaps (component-aware, component_type already set above)
    # Platform gaps (all components)
    if gaps.get('platforms'):
        lines.append("PLATFORM GAPS:")
        for gap in gaps['platforms']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['platform']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    # Protocol gaps (networking components)
    if component_type in NETWORK_COMPONENTS and gaps.get('protocols'):
        lines.append("PROTOCOL GAPS:")
        for gap in gaps['protocols']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['protocol']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    # Service type gaps (networking components)
    if component_type in NETWORK_COMPONENTS and gaps.get('service_types'):
        lines.append("SERVICE TYPE GAPS:")
        for gap in gaps['service_types']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['service_type']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    # IP stack gaps (networking components)
    if component_type in NETWORK_COMPONENTS and gaps.get('ip_stacks'):
        lines.append("IP STACK GAPS:")
        for gap in gaps['ip_stacks']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['ip_stack']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    # Topology gaps (networking components)
    if component_type in NETWORK_COMPONENTS and gaps.get('topologies'):
        lines.append("TOPOLOGY GAPS:")
        for gap in gaps['topologies']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['topology']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    # Storage class gaps (storage components)
    if component_type in STORAGE_COMPONENTS and gaps.get('storage_classes'):
        lines.append("STORAGE CLASS GAPS:")
        for gap in gaps['storage_classes']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['storage_class']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    # Volume mode gaps (storage components)
    if component_type in STORAGE_COMPONENTS and gaps.get('volume_modes'):
        lines.append("VOLUME MODE GAPS:")
        for gap in gaps['volume_modes']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['volume_mode']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    # Scenario gaps (all components)
    if gaps.get('scenarios'):
        lines.append("SCENARIO GAPS:")
        for gap in gaps['scenarios']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['scenario']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    lines.extend([
        "=" * 60,
        "Recommendations",
        "=" * 60,
        "",
        f"Current Coverage: {scores['overall']:.0f}%",
        f"Target Coverage: {min(95, scores['overall'] + 20):.0f}%",
        "",
        "Focus on addressing HIGH priority gaps first to maximize",
        "test coverage and ensure production readiness.",
    ])

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))


