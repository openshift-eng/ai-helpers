#!/usr/bin/env python3
"""
Test Structure Report Generator
Generates HTML reports for test structure analysis
"""

import json
import os
from datetime import datetime
from typing import Dict, List

# Import shared CSS styles
try:
    from ..common.report_styles import get_common_css
except ImportError:
    try:
        from plugins.test_coverage.skills.common.report_styles import get_common_css
    except ImportError:
        from common.report_styles import get_common_css


# ============================================================================
# Test Structure Analysis Reports
# ============================================================================

def generate_test_structure_html(data: Dict, output_path: str):
    """
    Generate HTML report for test structure analysis
    Handles both test-only mode and full coverage analysis mode
    """

    # Check if this is test-only mode
    test_only_mode = data.get('test_only_mode', False)

    if test_only_mode:
        _generate_test_only_html(data, output_path)
    else:
        _generate_full_structure_html(data, output_path)


def _generate_test_only_html(data: Dict, output_path: str):
    """Generate HTML report for test-only mode (single test file analysis)"""

    language = data.get('language', 'unknown')
    test_file_details = data.get('test_file_details', {})

    file_path = test_file_details.get('path', '')
    file_name = os.path.basename(file_path)
    test_count = test_file_details.get('test_count', 0)
    tests = test_file_details.get('tests', [])
    imports = test_file_details.get('imports', [])

    # Generate test rows
    test_rows = ""
    for i, test in enumerate(tests, 1):
        test_name = test.get('name', 'Unnamed Test')
        line_start = test.get('line_start', 0)
        line_end = test.get('line_end', 0)
        targets = test.get('targets', [])

        # Clean up test name
        display_name = test_name.replace("It: ", "")

        # Format targets
        targets_html = ""
        if targets:
            targets_list = ', '.join(targets[:10])
            if len(targets) > 10:
                targets_list += f' +{len(targets) - 10} more'
            targets_html = f'<div class="test-targets">Calls: {targets_list}</div>'

        test_rows += f"""
                <tr>
                    <td>{i}</td>
                    <td>
                        <strong>{display_name}</strong>
                        <div class="line">Lines {line_start}-{line_end}</div>
                        {targets_html}
                    </td>
                </tr>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Structure Analysis - {file_name}</title>
    <style>
        {get_common_css()}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 Test Structure Analysis</h1>
            <div class="meta">
                <strong>File:</strong> {file_name} |
                <strong>Language:</strong> {language.upper()} |
                <strong>Mode:</strong> Test-Only Analysis |
                <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>

        <div class="section">
            <div class="summary-stats">
                <div class="stat-card">
                    <h3>Test Cases</h3>
                    <div class="value">{test_count}</div>
                    <div class="subvalue">Total test functions</div>
                </div>
                <div class="stat-card">
                    <h3>Imports</h3>
                    <div class="value">{len(imports)}</div>
                    <div class="subvalue">Dependencies</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>🧪 Test Cases</h2>
            <table class="matrix-table">
                <thead>
                    <tr>
                        <th style="width: 60px;">#</th>
                        <th>Test Name</th>
                    </tr>
                </thead>
                <tbody>
                    {test_rows if test_rows else '<tr><td colspan="2">No tests found</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section" style="background: #f9fafb;">
            <h2>📦 Imports</h2>
            <div style="background: white; padding: 20px; border-radius: 8px;">
                <ul style="list-style: none; padding: 0;">
"""

    for imp in imports[:20]:
        html += f"<li style='padding: 8px; border-bottom: 1px solid #e5e7eb;'><code>{imp}</code></li>\n"

    if len(imports) > 20:
        html += f"<li style='padding: 8px; color: #666;'>... and {len(imports) - 20} more imports</li>\n"

    html += """
                </ul>
            </div>
        </div>

        <div class="section" style="background: #fffbeb;">
            <h2>ℹ️ Note</h2>
            <p style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                This is a <strong>test-structure-only analysis</strong>. No source files were analyzed or mapped.
                For full coverage gap analysis, run the analyzer on a directory instead of a single file.
            </p>
        </div>

    </div>
</body>
</html>
"""

    with open(output_path, 'w') as f:
        f.write(html)


def _generate_full_structure_html(data: Dict, output_path: str):
    """Generate HTML report for full test structure analysis with gaps"""

    language = data.get('language', 'unknown')
    source_dir = data.get('source_dir', '')
    gaps = data.get('gaps', {})
    summary = data.get('summary', {})

    untested_files = gaps.get('untested_files', [])
    partially_tested = gaps.get('partially_tested_files', [])
    untested_functions = gaps.get('untested_functions', [])

    total_source = summary.get('total_source_files', 0)
    total_test = summary.get('total_test_files', 0)
    untested_count = summary.get('untested_files_count', 0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Structure Analysis</title>
    <style>
        {get_common_css()}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Test Structure Analysis</h1>
            <div class="meta">
                <strong>Directory:</strong> {source_dir} |
                <strong>Language:</strong> {language.upper()} |
                <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>

        <div class="section">
            <div class="summary-stats">
                <div class="stat-card">
                    <h3>Source Files</h3>
                    <div class="value">{total_source}</div>
                    <div class="subvalue">Total source files</div>
                </div>
                <div class="stat-card">
                    <h3>Test Files</h3>
                    <div class="value">{total_test}</div>
                    <div class="subvalue">E2E/Integration tests</div>
                </div>
                <div class="stat-card">
                    <h3>Untested Files</h3>
                    <div class="value">{untested_count}</div>
                    <div class="subvalue">{(untested_count/max(total_source,1)*100):.0f}% without tests</div>
                </div>
            </div>
        </div>

        <div class="section" style="background: #fef2f2;">
            <h2>🚨 Coverage Gaps</h2>

            <h3 style="margin: 20px 0 15px;">Files Without Tests</h3>
            {_generate_untested_files_section(untested_files)}

            <h3 style="margin: 30px 0 15px;">Partially Tested Files</h3>
            {_generate_partially_tested_files_section(partially_tested)}

            <h3 style="margin: 30px 0 15px;">Untested Functions</h3>
            {_generate_untested_functions_section(untested_functions)}
        </div>

        <div class="section" style="background: #f0fdf4;">
            <h2>📈 Recommendations</h2>
            {_generate_recommendations_section(gaps)}
        </div>

    </div>
</body>
</html>
"""

    with open(output_path, 'w') as f:
        f.write(html)


def _generate_untested_files_section(untested_files: List[Dict]) -> str:
    """Generate HTML section for untested files"""
    if not untested_files:
        return '<p style="color: #059669; background: white; padding: 15px; border-radius: 8px;">✅ All source files have test coverage!</p>'

    html = '<table class="matrix-table"><thead><tr><th>File</th><th>Functions</th><th>Exported</th><th>Priority</th></tr></thead><tbody>'

    for file in untested_files[:20]:
        file_path = file.get('file', '')
        file_name = os.path.basename(file_path)
        total_funcs = file.get('total_functions', 0)
        exported = file.get('exported_functions', 0)
        priority = file.get('priority', 'low')

        html += f"""
        <tr>
            <td><strong>{file_name}</strong><br><small style="color: #666;">{file_path}</small></td>
            <td>{total_funcs}</td>
            <td>{exported}</td>
            <td><span class="status-badge priority-{priority}">{priority.upper()}</span></td>
        </tr>
        """

    if len(untested_files) > 20:
        html += f'<tr><td colspan="4" style="text-align: center; color: #666;">... and {len(untested_files) - 20} more files</td></tr>'

    html += '</tbody></table>'
    return html


def _generate_partially_tested_files_section(partially_tested: List[Dict]) -> str:
    """Generate HTML section for partially tested files"""
    if not partially_tested:
        return '<p style="color: #666; background: white; padding: 15px; border-radius: 8px;">No partially tested files found.</p>'

    html = '<table class="matrix-table"><thead><tr><th>File</th><th>Coverage</th><th>Tested</th><th>Untested</th><th>Priority</th></tr></thead><tbody>'

    for file in partially_tested[:20]:
        file_path = file.get('file', '')
        file_name = os.path.basename(file_path)
        coverage = file.get('coverage', 0)
        tested = file.get('tested_functions', 0)
        untested = file.get('untested_functions', 0)
        priority = file.get('priority', 'low')

        html += f"""
        <tr>
            <td><strong>{file_name}</strong><br><small style="color: #666;">{file_path}</small></td>
            <td>
                <div class="progress-bar" style="height: 20px;">
                    <div class="progress-fill" style="width: {coverage}%; font-size: 0.75em;">{coverage:.0f}%</div>
                </div>
            </td>
            <td>{tested}</td>
            <td>{untested}</td>
            <td><span class="status-badge priority-{priority}">{priority.upper()}</span></td>
        </tr>
        """

    if len(partially_tested) > 20:
        html += f'<tr><td colspan="5" style="text-align: center; color: #666;">... and {len(partially_tested) - 20} more files</td></tr>'

    html += '</tbody></table>'
    return html


def _generate_untested_functions_section(untested_functions: List[Dict]) -> str:
    """Generate HTML section for untested functions"""
    if not untested_functions:
        return '<p style="color: #059669; background: white; padding: 15px; border-radius: 8px;">✅ All functions have test coverage!</p>'

    # Show only high priority functions in HTML (limit to 30)
    high_priority = [f for f in untested_functions if f.get('priority') == 'high'][:30]

    if not high_priority:
        return f'<p style="color: #666; background: white; padding: 15px; border-radius: 8px;">{len(untested_functions)} untested functions (all low priority)</p>'

    html = '<table class="matrix-table"><thead><tr><th>Function</th><th>File</th><th>Visibility</th><th>Complexity</th></tr></thead><tbody>'

    for func in high_priority:
        func_name = func.get('function', '')
        file_path = func.get('file', '')
        file_name = os.path.basename(file_path)
        visibility = func.get('visibility', 'unknown')
        complexity = func.get('complexity', 1)

        html += f"""
        <tr>
            <td><strong>{func_name}</strong></td>
            <td><small>{file_name}</small></td>
            <td><span class="tag">{visibility}</span></td>
            <td>{complexity}</td>
        </tr>
        """

    total_untested = len(untested_functions)
    if total_untested > len(high_priority):
        html += f'<tr><td colspan="4" style="text-align: center; color: #666;">... and {total_untested - len(high_priority)} more untested functions (lower priority)</td></tr>'

    html += '</tbody></table>'
    return html


def _generate_recommendations_section(gaps: Dict) -> str:
    """Generate HTML section for recommendations"""
    untested_files = len(gaps.get('untested_files', []))
    untested_functions = len(gaps.get('untested_functions', []))
    partially_tested = len(gaps.get('partially_tested_files', []))

    html = '<div style="background: white; padding: 20px; border-radius: 8px;"><ul style="line-height: 2; margin-left: 20px;">'

    if untested_files > 0:
        html += f'<li>✓ Create test files for <strong>{untested_files}</strong> untested source files</li>'

    if untested_functions > 0:
        html += f'<li>✓ Add tests for <strong>{untested_functions}</strong> untested functions</li>'

    if partially_tested > 0:
        html += f'<li>✓ Strengthen test coverage for <strong>{partially_tested}</strong> partially tested files</li>'

    high_priority = len([f for f in gaps.get('untested_files', []) if f.get('priority') == 'high'])
    if high_priority > 0:
        html += f'<li>⚠️ <strong>Focus on high-priority gaps first</strong> ({high_priority} items)</li>'

    html += '</ul></div>'
    return html


# ============================================================================
# Comprehensive Analysis Reports (from comprehensive_analyzer.py)
# ============================================================================

def generate_comprehensive_html(data: Dict, output_path: str):
    """Generate comprehensive HTML report combining structure and gap analysis"""

    metadata = data.get('metadata', {})
    structure = data.get('structure', {})
    gaps = data.get('gaps', [])
    recommendations = data.get('recommendations', [])
    strengths = data.get('strengths', [])
    summary_stats = data.get('summary', {})

    source_dir = metadata.get('source_dir', '')
    language = metadata.get('language', 'unknown')
    framework = metadata.get('test_framework', 'unknown')

    total_tests = structure.get('total_tests', 0)
    total_source = structure.get('total_source_files', 0)
    total_test_files = structure.get('total_test_files', 0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unified Test Coverage Analysis</title>
    <style>
        {get_common_css()}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Unified Test Coverage Analysis</h1>
            <div class="meta">
                <strong>Directory:</strong> {source_dir} |
                <strong>Language:</strong> {language.upper()} |
                <strong>Framework:</strong> {framework} |
                <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>

        <div class="section">
            <h2>📊 Summary Statistics</h2>
            <div class="summary-stats">
                <div class="stat-card">
                    <h3>Test Cases</h3>
                    <div class="value">{total_tests}</div>
                    <div class="subvalue">Total tests</div>
                </div>
                <div class="stat-card">
                    <h3>Test Files</h3>
                    <div class="value">{total_test_files}</div>
                    <div class="subvalue">E2E/Integration</div>
                </div>
                <div class="stat-card">
                    <h3>Source Files</h3>
                    <div class="value">{total_source}</div>
                    <div class="subvalue">Total files</div>
                </div>
                <div class="stat-card">
                    <h3>Gaps Found</h3>
                    <div class="value">{len(gaps)}</div>
                    <div class="subvalue">{summary_stats.get('high_priority_gaps', 0)} high priority</div>
                </div>
            </div>
        </div>

        <div class="section" style="background: #f0fdf4;">
            <h2>✨ Strengths</h2>
            <div style="background: white; padding: 20px; border-radius: 8px;">
                <ul style="line-height: 2; margin-left: 20px;">
"""

    for strength in strengths:
        html += f'<li>{strength}</li>\n'

    html += """
                </ul>
            </div>
        </div>

        <div class="section" style="background: #fef2f2;">
            <h2>🚨 Identified Gaps</h2>
"""

    for gap in gaps:
        severity = gap.get('severity', 'MEDIUM')
        area = gap.get('area', 'Unknown')
        finding = gap.get('finding', '')
        recommendation = gap.get('recommendation', '')

        priority_class = severity.lower()

        html += f"""
            <div class="gap-card {priority_class}">
                <h4>
                    <span class="status-badge priority-{priority_class}">{severity} PRIORITY</span>
                    {area}
                </h4>
                <div class="impact"><strong>Finding:</strong> {finding}</div>
                <div class="recommendation">💡 {recommendation}</div>
            </div>
"""

    html += """
        </div>

        <div class="section" style="background: #eff6ff;">
            <h2>📈 Recommendations</h2>
            <div style="background: white; padding: 20px; border-radius: 8px;">
"""

    # Group recommendations by priority
    high_recs = [r for r in recommendations if r[0] == 'HIGH']
    medium_recs = [r for r in recommendations if r[0] == 'MEDIUM']
    low_recs = [r for r in recommendations if r[0] == 'LOW']

    if high_recs:
        html += '<h3 style="color: #dc2626; margin-bottom: 15px;">🔴 High Priority</h3><ul style="margin-left: 20px; line-height: 2;">'
        for _, area, rec in high_recs[:5]:
            html += f'<li><strong>{area}:</strong> {rec}</li>\n'
        html += '</ul>'

    if medium_recs:
        html += '<h3 style="color: #f59e0b; margin: 20px 0 15px;">🟡 Medium Priority</h3><ul style="margin-left: 20px; line-height: 2;">'
        for _, area, rec in medium_recs[:5]:
            html += f'<li><strong>{area}:</strong> {rec}</li>\n'
        html += '</ul>'

    if low_recs:
        html += '<h3 style="color: #3b82f6; margin: 20px 0 15px;">🔵 Low Priority</h3><ul style="margin-left: 20px; line-height: 2;">'
        for _, area, rec in low_recs[:3]:
            html += f'<li><strong>{area}:</strong> {rec}</li>\n'
        html += '</ul>'

    html += """
            </div>
        </div>

    </div>
</body>
</html>
"""

    with open(output_path, 'w') as f:
        f.write(html)
