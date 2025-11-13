#!/usr/bin/env python3
"""
E2E Test Gap Analysis Report Generator
Generates HTML, JSON, and text reports for e2e test scenario gap analysis
"""

import html
import json
import os
from datetime import datetime
from typing import Dict, List

# Import shared CSS styles
try:
    from ...utils.common.report_styles import get_common_css
except ImportError:
    import sys
    import os
    # Add parent directory to path for absolute imports
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from utils.common.report_styles import get_common_css


# Component type constants
NETWORK_COMPONENTS = {'networking', 'router', 'dns', 'network-observability'}
STORAGE_COMPONENTS = {'storage', 'csi'}


# HTML escape helper function
esc = lambda value: html.escape(str(value), quote=True)


# Priority sanitization helper
def sanitize_priority(priority):
    """Sanitize priority value to prevent XSS injection"""
    safe_priority = (priority or 'low').lower() if isinstance(priority, str) else 'low'
    return safe_priority if safe_priority in ('high', 'medium', 'low') else 'low'


# ============================================================================
# E2E Test Gap Analysis Reports
# ============================================================================

def generate_gap_html_report(analysis: Dict, scores: Dict, output_path: str):
    """Generate HTML report for E2E test gap analysis"""

    file_name = esc(os.path.basename(analysis['file']))
    test_count = analysis['test_count']
    coverage = analysis['coverage']
    gaps = analysis['gaps']

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
    component_type = analysis.get('component_type', 'unknown')
    if component_type in NETWORK_COMPONENTS:
        metric_cards = [
            ("Protocol Coverage", scores.get('protocol_coverage')),
            ("Service Type Coverage", scores.get('service_type_coverage')),
            ("IP Stack Coverage", scores.get('ip_stack_coverage')),
            ("Topology Coverage", scores.get('topology_coverage')),
        ]
        for label, value in metric_cards:
            if value is None:
                continue
            html += f"""
                <div class="score-card">
                    <h3>{esc(label)}</h3>
                    <div class="value">{value:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {value}%"></div>
                    </div>
                </div>"""
    elif component_type in STORAGE_COMPONENTS:
        metric_cards = [
            ("Storage Class Coverage", scores.get('storage_class_coverage')),
            ("Volume Mode Coverage", scores.get('volume_mode_coverage')),
        ]
        for label, value in metric_cards:
            if value is None:
                continue
            html += f"""
                <div class="score-card">
                    <h3>{esc(label)}</h3>
                    <div class="value">{value:.0f}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {value}%"></div>
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
                        <td><strong>{esc(platform)}</strong></td>
                        <td><span class="status-badge {status_class}">{esc(status_text)}</span></td>
                        <td>{esc(impact)}</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
        </div>

        <div class="section" style="background: #fef2f2;">
            <h2>🚨 Identified Gaps</h2>
"""

    # Platform gaps
    if gaps.get('platforms'):
        html += "<h3 style='margin: 20px 0 15px;'>Platform Gaps</h3>"
        for gap in gaps['platforms']:
            priority_class = sanitize_priority(gap.get('priority'))
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{esc(priority_class.upper())} PRIORITY</span>
                    {esc(gap['platform'])}
                </h4>
                <div class="impact"><strong>Impact:</strong> {esc(gap['impact'])}</div>
                <div class="recommendation">💡 {esc(gap['recommendation'])}</div>
            </div>
"""

    # Protocol gaps
    if gaps.get('protocols'):
        html += "<h3 style='margin: 20px 0 15px;'>Protocol Gaps</h3>"
        for gap in gaps['protocols']:
            priority_class = sanitize_priority(gap.get('priority'))
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{esc(priority_class.upper())} PRIORITY</span>
                    {esc(gap['protocol'])}
                </h4>
                <div class="impact"><strong>Impact:</strong> {esc(gap['impact'])}</div>
                <div class="recommendation">💡 {esc(gap['recommendation'])}</div>
            </div>
"""

    # Service type gaps
    if gaps.get('service_types'):
        html += "<h3 style='margin: 20px 0 15px;'>Service Type Gaps</h3>"
        for gap in gaps['service_types']:
            priority_class = sanitize_priority(gap.get('priority'))
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{esc(priority_class.upper())} PRIORITY</span>
                    {esc(gap['service_type'])}
                </h4>
                <div class="impact"><strong>Impact:</strong> {esc(gap['impact'])}</div>
                <div class="recommendation">💡 {esc(gap['recommendation'])}</div>
            </div>
"""

    # IP stack gaps
    if gaps.get('ip_stacks'):
        html += "<h3 style='margin: 20px 0 15px;'>IP Stack Gaps</h3>"
        for gap in gaps['ip_stacks']:
            priority_class = sanitize_priority(gap.get('priority'))
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{esc(priority_class.upper())} PRIORITY</span>
                    {esc(gap['ip_stack'])}
                </h4>
                <div class="impact"><strong>Impact:</strong> {esc(gap['impact'])}</div>
                <div class="recommendation">💡 {esc(gap['recommendation'])}</div>
            </div>
"""

    # Topology gaps
    if gaps.get('topologies'):
        html += "<h3 style='margin: 20px 0 15px;'>Topology Gaps</h3>"
        for gap in gaps['topologies']:
            priority_class = sanitize_priority(gap.get('priority'))
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{esc(priority_class.upper())} PRIORITY</span>
                    {esc(gap['topology'])}
                </h4>
                <div class="impact"><strong>Impact:</strong> {esc(gap['impact'])}</div>
                <div class="recommendation">💡 {esc(gap['recommendation'])}</div>
            </div>
"""

    # Storage class gaps
    if gaps.get('storage_classes'):
        html += "<h3 style='margin: 20px 0 15px;'>Storage Class Gaps</h3>"
        for gap in gaps['storage_classes']:
            priority_class = sanitize_priority(gap.get('priority'))
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{esc(priority_class.upper())} PRIORITY</span>
                    {esc(gap['storage_class'])}
                </h4>
                <div class="impact"><strong>Impact:</strong> {esc(gap['impact'])}</div>
                <div class="recommendation">💡 {esc(gap['recommendation'])}</div>
            </div>
"""

    # Volume mode gaps
    if gaps.get('volume_modes'):
        html += "<h3 style='margin: 20px 0 15px;'>Volume Mode Gaps</h3>"
        for gap in gaps['volume_modes']:
            priority_class = sanitize_priority(gap.get('priority'))
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{esc(priority_class.upper())} PRIORITY</span>
                    {esc(gap['volume_mode'])}
                </h4>
                <div class="impact"><strong>Impact:</strong> {esc(gap['impact'])}</div>
                <div class="recommendation">💡 {esc(gap['recommendation'])}</div>
            </div>
"""

    # Scenario gaps
    if gaps.get('scenarios'):
        html += "<h3 style='margin: 20px 0 15px;'>Scenario Gaps</h3>"
        for gap in gaps['scenarios']:
            priority_class = sanitize_priority(gap.get('priority'))
            html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{esc(priority_class.upper())} PRIORITY</span>
                    {esc(gap['scenario'])}
                </h4>
                <div class="impact"><strong>Impact:</strong> {esc(gap['impact'])}</div>
                <div class="recommendation">💡 {esc(gap['recommendation'])}</div>
            </div>
"""

    html += """
        </div>

        <div class="section">
            <h2>✅ Test Cases Found</h2>
            <div class="test-cases">
"""

    for i, test in enumerate(analysis['test_cases'], 1):
        tags_html = ''.join([f'<span class="tag">{esc(tag)}</span>' for tag in test['tags']])
        test_name = esc(test['name'][:80])
        test_name_suffix = "..." if len(test['name']) > 80 else ""
        html += f"""
                <div class="test-case">
                    <strong>{i}. {test_name}{test_name_suffix}</strong>
                    <div class="line">Line {test['line']} | ID: {esc(test['id'])}</div>
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
        html += f"<li>{esc(rec)}</li>\n"

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
        html += f"<li>{esc(rec)}</li>\n"

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

    component_type = analysis.get('component_type', 'generic')

    lines = [
        "=" * 60,
        "Test Coverage Gap Analysis",
        "=" * 60,
        "",
        f"File: {file_name}",
        f"Component: {component_type}",
        f"Test Cases: {analysis['test_count']}",
        f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "=" * 60,
        "Coverage Scores",
        "=" * 60,
        "",
        f"Overall Coverage:          {scores['overall']:.1f}%",
    ]

    # Component-specific scores
    lines.append(f"Platform Coverage:         {scores.get('platform_coverage', 0):.1f}%")

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

    lines.append(f"Scenario Coverage:         {scores.get('scenario_coverage', 0):.1f}%")

    lines.extend([
        "",
        "=" * 60,
        "What's Tested",
        "=" * 60,
        "",
    ])

    # Component-agnostic tested items
    lines.extend([
        "Platforms:",
        *[f"  ✓ {p}" for p in coverage.get('platforms', {}).get('tested', [])],
    ])

    # Add tested scenarios if any
    tested_scenarios = coverage.get('scenarios', {}).get('tested', [])
    if tested_scenarios:
        lines.extend([
            "",
            "Scenarios:",
            *[f"  ✓ {s}" for s in tested_scenarios],
        ])

    lines.extend([
        "",
        "=" * 60,
        "Identified Gaps",
        "=" * 60,
        "",
    ])

    # Component-agnostic gaps
    if gaps.get('platforms'):
        lines.append("PLATFORM GAPS:")
        for gap in gaps['platforms']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['platform']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    if gaps.get('protocols'):
        lines.append("PROTOCOL GAPS:")
        for gap in gaps['protocols']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['protocol']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    if gaps.get('service_types'):
        lines.append("SERVICE TYPE GAPS:")
        for gap in gaps['service_types']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['service_type']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    if gaps.get('ip_stacks'):
        lines.append("IP STACK GAPS:")
        for gap in gaps['ip_stacks']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['ip_stack']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    if gaps.get('topologies'):
        lines.append("TOPOLOGY GAPS:")
        for gap in gaps['topologies']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['topology']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    if gaps.get('storage_classes'):
        lines.append("STORAGE CLASS GAPS:")
        for gap in gaps['storage_classes']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['storage_class']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

    if gaps.get('volume_modes'):
        lines.append("VOLUME MODE GAPS:")
        for gap in gaps['volume_modes']:
            lines.extend([
                f"  [{gap['priority'].upper()}] {gap['volume_mode']}",
                f"    Impact: {gap['impact']}",
                f"    Recommendation: {gap['recommendation']}",
                ""
            ])

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
