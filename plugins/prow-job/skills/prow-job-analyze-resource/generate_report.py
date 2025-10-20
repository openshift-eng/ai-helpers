#!/usr/bin/env python3
"""
Generate HTML report from parsed audit and pod log entries.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


def parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse timestamp string to datetime object."""
    if not ts_str:
        return None

    # Try various formats
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',  # RFC3339 with microseconds
        '%Y-%m-%dT%H:%M:%SZ',      # RFC3339 without microseconds
        '%Y-%m-%d %H:%M:%S.%f',    # Common with microseconds
        '%Y-%m-%d %H:%M:%S',       # Common without microseconds
    ]

    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue

    return None


def calculate_timeline_position(timestamp: Optional[str], min_time: datetime, max_time: datetime) -> float:
    """
    Calculate position on timeline (0-100%).

    Args:
        timestamp: ISO timestamp string
        min_time: Earliest timestamp
        max_time: Latest timestamp

    Returns:
        Position as percentage (0-100)
    """
    if not timestamp:
        return 100.0  # Put entries without timestamps at the end

    dt = parse_timestamp(timestamp)
    if not dt:
        return 100.0

    if max_time == min_time:
        return 50.0

    time_range = (max_time - min_time).total_seconds()
    position = (dt - min_time).total_seconds()

    return (position / time_range) * 100.0


def get_level_color(level: str) -> str:
    """Get SVG color for log level."""
    colors = {
        'info': '#3498db',
        'warn': '#f39c12',
        'error': '#e74c3c',
    }
    return colors.get(level, '#95a5a6')


def format_timestamp(ts_str: Optional[str]) -> str:
    """Format timestamp for display."""
    if not ts_str:
        return 'N/A'

    dt = parse_timestamp(ts_str)
    if not dt:
        return ts_str

    return dt.strftime('%Y-%m-%d %H:%M:%S')


def generate_timeline_events(entries: List[Dict], min_time: datetime, max_time: datetime) -> str:
    """Generate SVG elements for timeline events."""
    svg_lines = []

    for i, entry in enumerate(entries):
        timestamp = entry.get('timestamp')
        level = entry.get('level', 'info')
        summary = entry.get('summary', '')

        position = calculate_timeline_position(timestamp, min_time, max_time)
        color = get_level_color(level)

        # Create vertical line
        svg_line = (
            f'<line x1="{position}%" y1="0" x2="{position}%" y2="100" '
            f'stroke="{color}" stroke-width="2" '
            f'class="timeline-event" data-entry-id="entry-{i}" '
            f'opacity="0.7">'
            f'<title>{summary[:100]}</title>'
            f'</line>'
        )
        svg_lines.append(svg_line)

    return '\n'.join(svg_lines)


def generate_entries_html(entries: List[Dict]) -> str:
    """Generate HTML for all log entries."""
    html_parts = []

    for i, entry in enumerate(entries):
        timestamp = entry.get('timestamp')
        level = entry.get('level', 'info')
        filename = entry.get('filename', 'unknown')
        line_number = entry.get('line_number', 0)
        summary = entry.get('summary', '')
        content = entry.get('content', '')

        # Escape HTML in content
        content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        entry_html = f'''
        <div class="entry" id="entry-{i}" data-level="{level}">
            <div class="entry-header">
                <span class="timestamp">{format_timestamp(timestamp)}</span>
                <span class="level {level}">{level}</span>
                <span class="source">{filename}:{line_number}</span>
            </div>
            <div class="entry-summary">{summary}</div>
            <details class="entry-details">
                <summary>Show full content</summary>
                <pre><code>{content}</code></pre>
            </details>
        </div>
        '''
        html_parts.append(entry_html)

    return '\n'.join(html_parts)


def generate_report(
    template_path: Path,
    output_path: Path,
    metadata: Dict,
    entries: List[Dict]
) -> None:
    """
    Generate HTML report from template and data.

    Args:
        template_path: Path to HTML template
        output_path: Path to write output HTML
        metadata: Metadata dict with prowjob info
        entries: List of log entry dicts (combined audit + pod logs)
    """
    # Read template
    with open(template_path, 'r') as f:
        template = f.read()

    # Sort entries by timestamp
    entries_with_time = []
    entries_without_time = []

    for entry in entries:
        ts_str = entry.get('timestamp')
        dt = parse_timestamp(ts_str)
        if dt:
            entries_with_time.append((dt, entry))
        else:
            entries_without_time.append(entry)

    entries_with_time.sort(key=lambda x: x[0])
    sorted_entries = [e for _, e in entries_with_time] + entries_without_time

    # Calculate timeline bounds
    if entries_with_time:
        min_time = entries_with_time[0][0]
        max_time = entries_with_time[-1][0]
        time_range = f"{min_time.strftime('%Y-%m-%d %H:%M:%S')} to {max_time.strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        min_time = datetime.now()
        max_time = datetime.now()
        time_range = "N/A"

    # Count entries by type and level
    audit_count = sum(1 for e in entries if 'verb' in e or 'http_code' in e)
    pod_count = len(entries) - audit_count
    error_count = sum(1 for e in entries if e.get('level') == 'error')

    # Generate timeline events
    timeline_events = generate_timeline_events(sorted_entries, min_time, max_time)

    # Generate entries HTML
    entries_html = generate_entries_html(sorted_entries)

    # Replace template variables
    replacements = {
        '{{prowjob_name}}': metadata.get('prowjob_name', 'Unknown'),
        '{{build_id}}': metadata.get('build_id', 'Unknown'),
        '{{original_url}}': metadata.get('original_url', '#'),
        '{{target}}': metadata.get('target', 'Unknown'),
        '{{resources}}': ', '.join(metadata.get('resources', [])),
        '{{time_range}}': time_range,
        '{{total_entries}}': str(len(entries)),
        '{{audit_entries}}': str(audit_count),
        '{{pod_entries}}': str(pod_count),
        '{{error_count}}': str(error_count),
        '{{min_time}}': min_time.strftime('%Y-%m-%d %H:%M:%S') if entries_with_time else 'N/A',
        '{{max_time}}': max_time.strftime('%Y-%m-%d %H:%M:%S') if entries_with_time else 'N/A',
        '{{timeline_events}}': timeline_events,
        '{{entries}}': entries_html,
    }

    html = template
    for key, value in replacements.items():
        html = html.replace(key, value)

    # Write output
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"Report generated: {output_path}")


def main():
    """
    Generate HTML report from JSON data.

    Usage: generate_report.py <template> <output> <metadata.json> <audit_entries.json> <pod_entries.json>
    """
    if len(sys.argv) != 6:
        print("Usage: generate_report.py <template> <output> <metadata.json> <audit_entries.json> <pod_entries.json>", file=sys.stderr)
        sys.exit(1)

    template_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    metadata_path = Path(sys.argv[3])
    audit_entries_path = Path(sys.argv[4])
    pod_entries_path = Path(sys.argv[5])

    # Load data
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    with open(audit_entries_path, 'r') as f:
        audit_entries = json.load(f)

    with open(pod_entries_path, 'r') as f:
        pod_entries = json.load(f)

    # Combine entries
    all_entries = audit_entries + pod_entries

    # Generate report
    generate_report(template_path, output_path, metadata, all_entries)

    return 0


if __name__ == '__main__':
    sys.exit(main())
