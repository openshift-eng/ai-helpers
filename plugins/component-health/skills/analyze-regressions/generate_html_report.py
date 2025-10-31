#!/usr/bin/env python3
"""
Generate HTML component health report from JSON data.

This script reads regression data and generates an interactive HTML report
using the template. It handles all the data processing and HTML generation.

Usage:
    python3 generate_html_report.py --release 4.20 --data data.json --output report.html

    Or pipe JSON data directly:
    cat data.json | python3 generate_html_report.py --release 4.20 --output report.html
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def format_hours_to_days(hours):
    """Convert hours to days with one decimal place."""
    if hours is None:
        return "N/A"
    return f"{hours / 24:.1f}"


def get_grade_class(value, thresholds, reverse=False):
    """
    Get CSS class based on value and thresholds.

    Args:
        value: The value to grade
        thresholds: Dict with 'excellent', 'good', 'warning' keys
        reverse: If True, lower is better (for time metrics)
    """
    if value is None:
        return "poor"

    if reverse:
        if value < thresholds['excellent']:
            return "good"
        elif value < thresholds['good']:
            return "good"
        elif value < thresholds['warning']:
            return "warning"
        else:
            return "poor"
    else:
        if value >= thresholds['excellent']:
            return "good"
        elif value >= thresholds['good']:
            return "good"
        elif value >= thresholds['warning']:
            return "warning"
        else:
            return "poor"


def get_grade_text(value, thresholds, reverse=False):
    """Get grade text (emoji + text) based on value."""
    grade_class = get_grade_class(value, thresholds, reverse)

    grade_map = {
        'good': '✅ EXCELLENT',
        'warning': '⚠️ NEEDS IMPROVEMENT',
        'poor': '❌ POOR'
    }

    # Special handling for coverage and timeliness
    if not reverse:  # Coverage
        if value is None:
            return '❌ POOR'
        elif value >= 90:
            return '✅ EXCELLENT'
        elif value >= 70:
            return '✅ GOOD'
        elif value >= 50:
            return '⚠️ NEEDS IMPROVEMENT'
        else:
            return '❌ POOR'
    else:  # Timeliness
        if value is None:
            return 'N/A'
        elif value < 24:
            return '✅ EXCELLENT'
        elif value < 72:
            return '⚠️ GOOD'
        elif value < 168:
            return '⚠️ NEEDS IMPROVEMENT'
        else:
            return '❌ POOR'


def get_component_grade(component_data):
    """Calculate overall grade for a component."""
    triage_pct = component_data['summary']['triage_percentage']

    if triage_pct >= 70:
        return 'good', '✅ GOOD'
    elif triage_pct >= 50:
        return 'good', '⚠️ GOOD'
    elif triage_pct >= 25:
        return 'warning', '⚠️ NEEDS IMPROVEMENT'
    else:
        return 'poor', '❌ POOR'


def format_time_value(value):
    """Format time value, handling None."""
    if value is None:
        return '-'
    return f"{int(value)} hrs"


def format_percentage_value(value):
    """Format percentage value with grade class."""
    if value is None or value == 0:
        return '<span class="grade-poor">0.0%</span>'
    elif value >= 90:
        return f'<span class="grade-excellent">{value:.1f}%</span>'
    elif value >= 70:
        return f'<span class="grade-good">{value:.1f}%</span>'
    elif value >= 50:
        return f'<span class="grade-warning">{value:.1f}%</span>'
    else:
        return f'<span class="grade-poor">{value:.1f}%</span>'


def generate_component_row(name, data):
    """Generate a table row for a component."""
    summary = data['summary']
    grade_class, grade_text = get_component_grade(data)

    return f'''<tr data-grade="{grade_class}">
                            <td class="component-name">{name}</td>
                            <td>{summary['total']}</td>
                            <td>{format_percentage_value(summary['triage_percentage'])}</td>
                            <td>{format_time_value(summary['time_to_triage_hrs_avg'])}</td>
                            <td>{format_time_value(summary['time_to_close_hrs_avg'])}</td>
                            <td>{summary['open']['total']}</td>
                            <td class="grade-{grade_class}">{grade_text}</td>
                        </tr>'''


def generate_html_report(release, data, release_dates, output_path):
    """Generate HTML report from data."""
    template_path = Path(__file__).parent / "report_template.html"

    with open(template_path, 'r') as f:
        template = f.read()

    # Extract summary data
    summary = data['summary']

    # Calculate derived values
    triage_coverage = summary['triage_percentage']
    triage_time_avg = summary['time_to_triage_hrs_avg'] or 0
    resolution_time_avg = summary['time_to_close_hrs_avg'] or 0

    # Determine release period
    dev_start = release_dates.get('development_start', 'Unknown')
    ga_date = release_dates.get('ga')

    if dev_start != 'Unknown':
        dev_start = dev_start.split('T')[0]

    if ga_date:
        ga_date = ga_date.split('T')[0]
        release_period = f"Development Period: {dev_start} - {ga_date} (GA)"
        date_range = f"{dev_start} (Development Start) to {ga_date} (GA)"
    else:
        release_period = f"Development Period: {dev_start} - Present (In Development)"
        date_range = f"{dev_start} (Development Start) - Present"

    # Calculate grades
    triage_coverage_class = get_grade_class(triage_coverage,
                                            {'excellent': 90, 'good': 70, 'warning': 50})
    triage_time_class = get_grade_class(triage_time_avg,
                                        {'excellent': 24, 'good': 72, 'warning': 168},
                                        reverse=True)
    resolution_time_class = get_grade_class(resolution_time_avg,
                                            {'excellent': 168, 'good': 336, 'warning': 720},
                                            reverse=True)

    # Build component rows (sorted by health)
    components = data.get('components', {})
    component_rows = []

    for name, comp_data in sorted(components.items(),
                                  key=lambda x: x[1]['summary']['triage_percentage'],
                                  reverse=True):
        component_rows.append(generate_component_row(name, comp_data))

    # Generate attention sections
    attention_sections = []

    # Zero triage components
    zero_triage = [name for name, comp in components.items()
                   if comp['summary']['triage_percentage'] == 0]
    if zero_triage:
        items = '\n'.join([f'<li><strong>{name}</strong> - {components[name]["summary"]["total"]} regressions</li>'
                          for name in zero_triage])
        attention_sections.append(f'''<div class="alert-box">
                    <h3>🚨 Zero Triage Coverage (0% triaged)</h3>
                    <ul>
                        {items}
                    </ul>
                </div>''')

    # Low triage components
    low_triage = [(name, comp) for name, comp in components.items()
                  if 0 < comp['summary']['triage_percentage'] < 25]
    if low_triage:
        items = '\n'.join([f'<li><strong>{name}</strong> - {comp["summary"]["total"]} regressions, only {comp["summary"]["triage_percentage"]:.1f}% triaged</li>'
                          for name, comp in low_triage])
        attention_sections.append(f'''<div class="alert-box">
                    <h3>⚠️ Low Triage Coverage (&lt;25%)</h3>
                    <ul>
                        {items}
                    </ul>
                </div>''')

    # High volume components
    high_volume = [(name, comp) for name, comp in components.items()
                   if comp['summary']['total'] >= 20]
    if high_volume:
        high_volume.sort(key=lambda x: x[1]['summary']['total'], reverse=True)
        items = '\n'.join([f'<li><strong>{name}</strong> - {comp["summary"]["total"]} regressions ({comp["summary"]["triage_percentage"]:.1f}% triaged)</li>'
                          for name, comp in high_volume[:5]])
        attention_sections.append(f'''<div class="alert-box">
                    <h3>📊 High Regression Volume (Top 5)</h3>
                    <ul>
                        {items}
                    </ul>
                </div>''')

    # Substitutions
    substitutions = {
        'RELEASE': release,
        'RELEASE_PERIOD': release_period,
        'DATE_RANGE': date_range,
        'TRIAGE_COVERAGE': f"{triage_coverage:.1f}",
        'TRIAGE_COVERAGE_CLASS': triage_coverage_class,
        'TRIAGE_COVERAGE_GRADE': get_grade_text(triage_coverage, {}, False),
        'TRIAGE_COVERAGE_GRADE_CLASS': f"grade-{triage_coverage_class}",
        'TOTAL_REGRESSIONS': str(summary['total']),
        'TRIAGED_REGRESSIONS': str(summary['triaged']),
        'UNTRIAGED_REGRESSIONS': str(summary['total'] - summary['triaged']),
        'TRIAGE_TIME_AVG': str(int(triage_time_avg)) if triage_time_avg else 'N/A',
        'TRIAGE_TIME_AVG_DAYS': format_hours_to_days(triage_time_avg),
        'TRIAGE_TIME_MAX': str(int(summary['time_to_triage_hrs_max'])) if summary['time_to_triage_hrs_max'] else 'N/A',
        'TRIAGE_TIME_MAX_DAYS': format_hours_to_days(summary['time_to_triage_hrs_max']),
        'TRIAGE_TIME_CLASS': triage_time_class,
        'TRIAGE_TIME_GRADE': get_grade_text(triage_time_avg, {}, True),
        'TRIAGE_TIME_GRADE_CLASS': f"grade-{triage_time_class}",
        'RESOLUTION_TIME_AVG': str(int(resolution_time_avg)) if resolution_time_avg else 'N/A',
        'RESOLUTION_TIME_AVG_DAYS': format_hours_to_days(resolution_time_avg),
        'RESOLUTION_TIME_MAX': str(int(summary['time_to_close_hrs_max'])) if summary['time_to_close_hrs_max'] else 'N/A',
        'RESOLUTION_TIME_MAX_DAYS': format_hours_to_days(summary['time_to_close_hrs_max']),
        'RESOLUTION_TIME_CLASS': resolution_time_class,
        'RESOLUTION_TIME_GRADE': get_grade_text(resolution_time_avg, {}, True),
        'RESOLUTION_TIME_GRADE_CLASS': f"grade-{resolution_time_class}",
        'OPEN_REGRESSIONS': str(summary['open']['total']),
        'OPEN_TRIAGE_PERCENTAGE': f"{summary['open']['triage_percentage']:.1f}",
        'CLOSED_REGRESSIONS': str(summary['closed']['total']),
        'CLOSED_TRIAGE_PERCENTAGE': f"{summary['closed']['triage_percentage']:.1f}",
        'OPEN_AGE_AVG': str(int(summary['open']['open_hrs_avg'])) if summary['open']['open_hrs_avg'] else 'N/A',
        'OPEN_AGE_AVG_DAYS': format_hours_to_days(summary['open']['open_hrs_avg']),
        'COMPONENT_ROWS': '\n'.join(component_rows),
        'ATTENTION_SECTIONS': '\n'.join(attention_sections),
        'INSIGHTS': '<li>Report generated automatically from regression data</li>',
        'RECOMMENDATIONS': '<li>Review components with zero triage coverage</li><li>Address high-volume components</li>',
        'GENERATED_DATE': datetime.now().strftime("%B %d, %Y"),
    }

    # Apply substitutions
    for key, value in substitutions.items():
        template = template.replace(f'{{{{{key}}}}}', value)

    # Write output
    with open(output_path, 'w') as f:
        f.write(template)

    print(f"HTML report generated: {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='Generate HTML component health report')
    parser.add_argument('--release', required=True, help='Release version (e.g., 4.20)')
    parser.add_argument('--data', help='Path to JSON data file (or read from stdin)')
    parser.add_argument('--dates', help='Path to release dates JSON file')
    parser.add_argument('--output', required=True, help='Output HTML file path')

    args = parser.parse_args()

    # Read regression data
    if args.data:
        with open(args.data, 'r') as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    # Read release dates
    release_dates = {}
    if args.dates:
        with open(args.dates, 'r') as f:
            release_dates = json.load(f)

    generate_html_report(args.release, data, release_dates, args.output)


if __name__ == '__main__':
    main()
