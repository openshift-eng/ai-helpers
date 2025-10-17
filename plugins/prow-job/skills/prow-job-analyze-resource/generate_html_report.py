#!/usr/bin/env python3
"""Generate interactive HTML report for resource lifecycle analysis."""

import json
import sys
import hashlib
from datetime import datetime
from pathlib import Path

def generate_html_report(entries, prowjob_name, build_id, target, resource_name, gcsweb_url, file_mapping=None):
    """Generate an interactive HTML report."""

    # Default to empty dict if no file mapping provided
    if file_mapping is None:
        file_mapping = {}

    # Calculate time range
    timestamps = [e['timestamp'] for e in entries if e['timestamp']]
    if timestamps:
        min_time = min(timestamps)
        max_time = max(timestamps)
        time_range_seconds = (max_time - min_time).total_seconds()
    else:
        min_time = max_time = None
        time_range_seconds = 1

    total_entries = len(entries)
    audit_entries = len([e for e in entries if e['source'] == 'audit'])
    pod_entries = len([e for e in entries if e['source'] == 'pod'])

    # Parse resource_name to extract searched resources
    # resource_name could be a single name or a regex pattern like "res1|res2"
    if '|' in resource_name:
        # Regex pattern with multiple resources
        resources_list = sorted(resource_name.split('|'))
    else:
        # Single resource or pattern - just use as-is
        resources_list = [resource_name]

    # Group by verb
    verb_counts = {}
    for e in entries:
        verb = e.get('verb', 'unknown')
        verb_counts[verb] = verb_counts.get(verb, 0) + 1

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resource Lifecycle: {resource_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            padding: 20px;
            line-height: 1.6;
        }}

        .header {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 24px;
            margin-bottom: 24px;
        }}

        .header h1 {{
            font-size: 24px;
            margin-bottom: 16px;
            color: #58a6ff;
        }}

        .metadata {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 12px;
        }}

        .metadata p {{
            margin: 4px 0;
            font-size: 14px;
        }}

        .metadata strong {{
            color: #8b949e;
            font-weight: 600;
        }}

        .metadata a {{
            color: #58a6ff;
            text-decoration: none;
        }}

        .metadata a:hover {{
            text-decoration: underline;
        }}

        .stats {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #30363d;
        }}

        .stat {{
            background: #0d1117;
            padding: 8px 12px;
            border-radius: 6px;
            border: 1px solid #30363d;
        }}

        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #58a6ff;
        }}

        .stat-label {{
            font-size: 12px;
            color: #8b949e;
            text-transform: uppercase;
        }}

        .timeline-container {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 24px;
            margin-bottom: 24px;
            position: relative;
        }}

        .timeline-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}

        .timeline-title {{
            font-size: 18px;
            color: #58a6ff;
        }}

        .timeline-times {{
            display: flex;
            gap: 24px;
            font-size: 12px;
            color: #8b949e;
        }}

        .timeline-time {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}

        .timeline-time-label {{
            text-transform: uppercase;
            font-size: 10px;
            margin-bottom: 2px;
        }}

        .timeline-time-value {{
            font-family: ui-monospace, SFMono-Regular, monospace;
            font-size: 13px;
            color: #c9d1d9;
        }}

        #timeline-wrapper {{
            position: relative;
        }}

        #timeline {{
            width: 100%;
            height: 100px;
            background: #0d1117;
            border-radius: 4px;
            cursor: crosshair;
        }}

        #timeline-hover {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 1px;
            background: rgba(88, 166, 255, 0.5);
            pointer-events: none;
            display: none;
        }}

        #timeline-tooltip {{
            position: absolute;
            top: -30px;
            padding: 4px 8px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 4px;
            font-size: 11px;
            font-family: ui-monospace, SFMono-Regular, monospace;
            color: #c9d1d9;
            white-space: nowrap;
            pointer-events: none;
            display: none;
        }}

        .timeline-event {{
            cursor: pointer;
            transition: stroke-width 0.2s;
        }}

        .timeline-event:hover {{
            stroke-width: 4 !important;
        }}

        .entries {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 24px;
        }}

        .filters {{
            margin-bottom: 24px;
            padding-bottom: 24px;
            border-bottom: 1px solid #30363d;
        }}

        .filter-group {{
            margin-bottom: 12px;
        }}

        .filter-label {{
            font-size: 14px;
            color: #8b949e;
            margin-bottom: 8px;
            display: block;
        }}

        .filter-buttons {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            padding: 6px 12px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            color: #c9d1d9;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }}

        .filter-btn:hover {{
            background: #21262d;
            border-color: #58a6ff;
        }}

        .filter-btn.active {{
            background: #58a6ff;
            border-color: #58a6ff;
            color: #fff;
        }}

        .search-box {{
            width: 100%;
            padding: 8px 12px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            color: #c9d1d9;
            font-size: 14px;
            font-family: inherit;
        }}

        .search-box:focus {{
            outline: none;
            border-color: #58a6ff;
        }}

        .entry {{
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 12px;
            transition: border-color 0.2s;
        }}

        .entry:target {{
            border-color: #58a6ff;
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.1);
        }}

        .entry-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 8px;
        }}

        .timestamp {{
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
            font-size: 13px;
            color: #8b949e;
        }}

        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-info {{
            background: rgba(88, 166, 255, 0.15);
            color: #58a6ff;
            border: 1px solid rgba(88, 166, 255, 0.3);
        }}

        .badge-warn {{
            background: rgba(187, 128, 9, 0.15);
            color: #d29922;
            border: 1px solid rgba(187, 128, 9, 0.3);
        }}

        .badge-error {{
            background: rgba(248, 81, 73, 0.15);
            color: #f85149;
            border: 1px solid rgba(248, 81, 73, 0.3);
        }}

        .badge-pod {{
            background: rgba(147, 51, 234, 0.15);
            color: #a78bfa;
            border: 1px solid rgba(147, 51, 234, 0.3);
        }}

        .badge-audit {{
            background: rgba(34, 134, 58, 0.15);
            color: #3fb950;
            border: 1px solid rgba(34, 134, 58, 0.3);
        }}

        .source {{
            font-size: 12px;
            color: #8b949e;
            font-family: ui-monospace, SFMono-Regular, monospace;
        }}

        .source a {{
            color: #58a6ff;
            text-decoration: none;
        }}

        .source a:hover {{
            text-decoration: underline;
        }}

        .entry-summary {{
            font-size: 14px;
            margin-bottom: 8px;
            color: #c9d1d9;
        }}

        .entry-details {{
            margin-top: 12px;
        }}

        .entry-details summary {{
            cursor: pointer;
            color: #58a6ff;
            font-size: 13px;
            padding: 4px 0;
        }}

        .entry-details summary:hover {{
            text-decoration: underline;
        }}

        .entry-details pre {{
            margin-top: 8px;
            padding: 12px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 12px;
            line-height: 1.5;
        }}

        .entry-details code {{
            font-family: ui-monospace, SFMono-Regular, monospace;
            color: #c9d1d9;
        }}

        .hidden {{
            display: none !important;
        }}

        .no-results {{
            text-align: center;
            padding: 48px;
            color: #8b949e;
        }}

        #scroll-to-top {{
            position: fixed;
            bottom: 32px;
            right: 32px;
            width: 48px;
            height: 48px;
            background: #58a6ff;
            border: none;
            border-radius: 50%;
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
            transition: all 0.3s;
            z-index: 1000;
        }}

        #scroll-to-top:hover {{
            background: #79c0ff;
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.5);
        }}

        #scroll-to-top svg {{
            fill: #fff;
        }}

        #scroll-to-top.visible {{
            display: flex;
        }}

        .viewer-container {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #161b22;
            border-top: 2px solid #58a6ff;
            display: none;
            flex-direction: column;
            z-index: 999;
            box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.5);
        }}

        .viewer-container.visible {{
            display: flex;
        }}

        .viewer-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 16px;
            background: #0d1117;
            border-bottom: 1px solid #30363d;
        }}

        .viewer-title {{
            font-size: 14px;
            color: #c9d1d9;
            font-family: ui-monospace, SFMono-Regular, monospace;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .viewer-controls {{
            display: flex;
            gap: 8px;
            align-items: center;
        }}

        .viewer-size-label {{
            font-size: 12px;
            color: #8b949e;
            margin-right: 4px;
        }}

        .viewer-size-slider {{
            width: 120px;
            height: 4px;
            background: #30363d;
            border-radius: 2px;
            outline: none;
            cursor: pointer;
        }}

        .viewer-size-slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 14px;
            height: 14px;
            background: #58a6ff;
            border-radius: 50%;
            cursor: pointer;
        }}

        .viewer-size-slider::-moz-range-thumb {{
            width: 14px;
            height: 14px;
            background: #58a6ff;
            border-radius: 50%;
            cursor: pointer;
            border: none;
        }}

        .viewer-btn {{
            padding: 4px 8px;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 4px;
            color: #c9d1d9;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }}

        .viewer-btn:hover {{
            background: #30363d;
            border-color: #58a6ff;
        }}

        .viewer-iframe {{
            flex: 1;
            border: none;
            background: #fff;
        }}

        .external-link-icon {{
            display: inline-block;
            margin-left: 6px;
            opacity: 0;
            transition: opacity 0.2s;
            cursor: pointer;
            font-size: 12px;
        }}

        .source:hover .external-link-icon {{
            opacity: 1;
        }}

        .external-link-icon svg {{
            width: 14px;
            height: 14px;
            fill: #58a6ff;
            vertical-align: middle;
        }}

        .external-link-icon:hover svg {{
            fill: #79c0ff;
        }}

        .source a {{
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <button id="scroll-to-top" title="Scroll to top">
        <svg width="24" height="24" viewBox="0 0 24 24">
            <path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/>
        </svg>
    </button>

    <div class="viewer-container" id="viewer">
        <div class="viewer-header">
            <div class="viewer-title" id="viewer-title">File Viewer</div>
            <div class="viewer-controls">
                <span class="viewer-size-label">Height:</span>
                <input type="range" class="viewer-size-slider" id="viewer-size" min="20" max="80" value="50">
                <button class="viewer-btn" id="viewer-close">Close</button>
            </div>
        </div>
        <iframe class="viewer-iframe" id="viewer-iframe"></iframe>
    </div>

    <div class="header">
        <h1>Prow Job Resource Lifecycle Analysis</h1>
        <div class="metadata">
            <div>
                <p><strong>Prow Job:</strong> {prowjob_name}</p>
                <p><strong>Build ID:</strong> {build_id}</p>
                <p><strong>Target:</strong> {target}</p>
            </div>
            <div>
                <p><strong>Resources:</strong> {', '.join(resources_list) if resources_list else resource_name}</p>
                <p><strong>GCS URL:</strong> <a href="{gcsweb_url}" target="_blank">View in gcsweb</a></p>
            </div>
        </div>
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{total_entries}</div>
                <div class="stat-label">Total Events</div>
            </div>
            <div class="stat">
                <div class="stat-value">{audit_entries}</div>
                <div class="stat-label">Audit Log Events</div>
            </div>
            <div class="stat">
                <div class="stat-value">{pod_entries}</div>
                <div class="stat-label">Pod Log Events</div>
            </div>'''

    for verb, count in sorted(verb_counts.items(), key=lambda x: -x[1])[:5]:
        html += f'''
            <div class="stat">
                <div class="stat-value">{count}</div>
                <div class="stat-label">{verb}</div>
            </div>'''

    html += '''
        </div>
    </div>

    <div class="timeline-container">
        <div class="timeline-header">
            <div class="timeline-title">Timeline</div>'''

    if min_time and max_time:
        # Store min/max time as ISO strings for JavaScript
        min_time_iso = min_time.isoformat()
        max_time_iso = max_time.isoformat()
        html += f'''
            <div class="timeline-times">
                <div class="timeline-time">
                    <div class="timeline-time-label">Start Time</div>
                    <div class="timeline-time-value">{min_time.strftime('%H:%M:%S')}</div>
                </div>
                <div class="timeline-time">
                    <div class="timeline-time-label">End Time</div>
                    <div class="timeline-time-value">{max_time.strftime('%H:%M:%S')}</div>
                </div>
            </div>'''
    else:
        min_time_iso = ""
        max_time_iso = ""

    html += '''
        </div>
        <div id="timeline-wrapper">
            <div id="timeline-hover"></div>
            <div id="timeline-tooltip"></div>
            <svg id="timeline" preserveAspectRatio="none">'''

    # Add timeline events
    for idx, entry in enumerate(entries):
        if entry['timestamp'] and min_time and time_range_seconds > 0:
            position = ((entry['timestamp'] - min_time).total_seconds() / time_range_seconds) * 100
            color = {'info': '#58a6ff', 'warn': '#d29922', 'error': '#f85149'}.get(entry['level'], '#8b949e')
            html += f'''
            <line x1="{position}%" y1="0" x2="{position}%" y2="100"
                  stroke="{color}" stroke-width="2"
                  class="timeline-event" data-entry-id="entry-{idx}"
                  onclick="scrollToEntry('entry-{idx}')">
                <title>{entry['summary']}</title>
            </line>'''

    html += f'''
        </svg>
        </div>
    </div>

    <div class="entries">
        <div class="filters">
            <div class="filter-group">
                <label class="filter-label">Filter by Level</label>
                <div class="filter-buttons">
                    <button class="filter-btn" data-filter="level" data-value="info">Info</button>
                    <button class="filter-btn" data-filter="level" data-value="warn">Warn</button>
                    <button class="filter-btn" data-filter="level" data-value="error">Error</button>
                </div>
            </div>
            <div class="filter-group">
                <label class="filter-label">Filter by Source</label>
                <div class="filter-buttons">
                    <button class="filter-btn" data-filter="source" data-value="audit">Audit</button>
                    <button class="filter-btn" data-filter="source" data-value="pod">Pod</button>
                </div>
            </div>
            <div class="filter-group">
                <label class="filter-label">Filter by Verb</label>
                <div class="filter-buttons">'''

    for verb in sorted(set(e.get('verb', '') for e in entries if e.get('verb'))):
        html += f'''
                    <button class="filter-btn" data-filter="verb" data-value="{verb}">{verb}</button>'''

    html += f'''
                </div>
            </div>
            <div class="filter-group">
                <label class="filter-label">Search</label>
                <input type="text" class="search-box" id="search" placeholder="Search in summaries and content...">
            </div>
        </div>

        <div id="entries-container">'''

    # Add entries
    for idx, entry in enumerate(entries):
        timestamp_display = entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if entry['timestamp'] else 'No timestamp'
        level = entry.get('level', 'info')
        source = entry.get('source', 'audit')
        summary = entry.get('summary', '')
        full_filename = entry.get('filename', '')
        filename_short = full_filename.split('/')[-1]
        line_num = entry.get('line_number', '')
        verb = entry.get('verb', '')
        content = entry.get('content', '')

        # Calculate relative path from HTML to log file
        # HTML is at: .work/prow-job-analyze-resource/{build_id}/{resource_name}.html
        # Logs are at: .work/prow-job-analyze-resource/{build_id}/logs/...
        # So we need to extract everything after {build_id}/
        if full_filename and f'.work/prow-job-analyze-resource/{build_id}/' in full_filename:
            relative_path = full_filename.split(f'.work/prow-job-analyze-resource/{build_id}/')[-1]
        else:
            relative_path = ''

        # Get file size for display
        file_size_str = ''
        if full_filename:
            try:
                import os
                file_size_bytes = os.path.getsize(full_filename)
                # Format file size in human-readable format
                if file_size_bytes < 1024:
                    file_size_str = f'{file_size_bytes}B'
                elif file_size_bytes < 1024 * 1024:
                    file_size_str = f'{file_size_bytes / 1024:.1f}K'
                elif file_size_bytes < 1024 * 1024 * 1024:
                    file_size_str = f'{file_size_bytes / (1024 * 1024):.1f}M'
                else:
                    file_size_str = f'{file_size_bytes / (1024 * 1024 * 1024):.1f}G'
            except:
                file_size_str = ''

        # Format JSON content for better display
        try:
            content_obj = json.loads(content)
            content_formatted = json.dumps(content_obj, indent=2)
        except:
            content_formatted = content

        # Create source link if we have a relative path
        if relative_path:
            # The file_mapping keys are relative to logs/ directory
            # So strip 'logs/' prefix from relative_path to match the mapping keys
            mapping_key = relative_path[5:] if relative_path.startswith('logs/') else relative_path

            # Check if HTML version exists in file_mapping
            html_path = file_mapping.get(mapping_key)

            if html_path:
                # Use HTML version with line anchor
                target_path = f'{html_path}#line-{line_num}'
            else:
                # Use original file with line anchor (browser may not support this for non-HTML)
                target_path = f'{relative_path}#line-{line_num}'

            # Include file size in the source HTML display
            size_display = f' ({file_size_str})' if file_size_str else ''
            source_html = f'<a class="file-link" data-path="{target_path}" data-line="{line_num}">{filename_short}</a>:{line_num}{size_display}<span class="external-link-icon" data-path="{relative_path}" title="Open in new tab"><svg viewBox="0 0 16 16"><path d="M3.75 2A1.75 1.75 0 002 3.75v8.5c0 .966.784 1.75 1.75 1.75h8.5A1.75 1.75 0 0014 12.25v-3.5a.75.75 0 00-1.5 0v3.5a.25.25 0 01-.25.25h-8.5a.25.25 0 01-.25-.25v-8.5a.25.25 0 01.25-.25h3.5a.75.75 0 000-1.5h-3.5zM9.5 2.75a.75.75 0 01.75-.75h3.5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0V4.56L8.78 8.78a.75.75 0 01-1.06-1.06l4.22-4.22h-1.69a.75.75 0 01-.75-.75z"/></svg></span>'
        else:
            source_html = f'{filename_short}:{line_num}'

        html += f'''
        <div class="entry" id="entry-{idx}" data-level="{level}" data-verb="{verb}" data-source="{source}">
            <div class="entry-header">
                <span class="timestamp">{timestamp_display}</span>
                <span class="badge badge-{level}">{level}</span>
                <span class="badge badge-{source}">{source}</span>
                <span class="source">{source_html}</span>
            </div>
            <div class="entry-summary">{summary}</div>
            <details class="entry-details">
                <summary>Show matching line</summary>
                <pre><code>{content_formatted[:2000]}</code></pre>
            </details>
        </div>'''

    html += f'''
        </div>
        <div id="no-results" class="no-results hidden">
            No entries match the current filters
        </div>
    </div>

    <script>
        const filters = {{
            levels: new Set(['info', 'warn', 'error']),  // All selected by default
            sources: new Set(['audit', 'pod']),  // All selected by default
            verbs: new Set(),  // None selected by default (show all)
            search: ''
        }};

        const minTime = new Date('{min_time_iso}');
        const maxTime = new Date('{max_time_iso}');
        const timeRangeMs = maxTime - minTime;

        function scrollToEntry(entryId) {{
            const entry = document.getElementById(entryId);
            if (entry) {{
                entry.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                entry.style.borderColor = '#58a6ff';
                setTimeout(() => {{
                    entry.style.borderColor = '';
                }}, 2000);
            }}
        }}

        function applyFilters() {{
            const entries = document.querySelectorAll('.entry');
            let visibleCount = 0;

            entries.forEach(entry => {{
                let show = true;

                // Level filter (multi-select)
                if (filters.levels.size > 0 && !filters.levels.has(entry.dataset.level)) {{
                    show = false;
                }}

                // Source filter (multi-select)
                if (filters.sources.size > 0 && !filters.sources.has(entry.dataset.source)) {{
                    show = false;
                }}

                // Verb filter (multi-select)
                if (filters.verbs.size > 0 && !filters.verbs.has(entry.dataset.verb)) {{
                    show = false;
                }}

                // Search filter
                if (filters.search) {{
                    const text = entry.textContent.toLowerCase();
                    if (!text.includes(filters.search.toLowerCase())) {{
                        show = false;
                    }}
                }}

                entry.classList.toggle('hidden', !show);
                if (show) visibleCount++;
            }});

            document.getElementById('no-results').classList.toggle('hidden', visibleCount > 0);
        }}

        // Filter button handlers
        document.querySelectorAll('.filter-btn').forEach(btn => {{
            const filterType = btn.dataset.filter;
            const value = btn.dataset.value;

            // Set initial active state for level and source filters
            if (filterType === 'level' || filterType === 'source') {{
                btn.classList.add('active');
            }}

            // Single click - toggle this button
            btn.addEventListener('click', function() {{
                const isActive = this.classList.contains('active');

                if (filterType === 'level') {{
                    if (isActive) {{
                        this.classList.remove('active');
                        filters.levels.delete(value);
                    }} else {{
                        this.classList.add('active');
                        filters.levels.add(value);
                    }}
                }} else if (filterType === 'source') {{
                    if (isActive) {{
                        this.classList.remove('active');
                        filters.sources.delete(value);
                    }} else {{
                        this.classList.add('active');
                        filters.sources.add(value);
                    }}
                }} else if (filterType === 'verb') {{
                    if (isActive) {{
                        this.classList.remove('active');
                        filters.verbs.delete(value);
                    }} else {{
                        this.classList.add('active');
                        filters.verbs.add(value);
                    }}
                }}

                applyFilters();
            }});

            // Double click - select only this button, deselect others in group
            btn.addEventListener('dblclick', function() {{
                // Get all buttons in the same filter group
                const allButtons = document.querySelectorAll(`.filter-btn[data-filter="${{filterType}}"]`);

                // Deselect all buttons in this group
                allButtons.forEach(b => {{
                    b.classList.remove('active');
                }});

                // Select only this button
                this.classList.add('active');

                // Update filter state
                if (filterType === 'level') {{
                    filters.levels.clear();
                    filters.levels.add(value);
                }} else if (filterType === 'source') {{
                    filters.sources.clear();
                    filters.sources.add(value);
                }} else if (filterType === 'verb') {{
                    filters.verbs.clear();
                    filters.verbs.add(value);
                }}

                applyFilters();
            }});
        }});

        // Timeline hover functionality
        const timeline = document.getElementById('timeline');
        const timelineWrapper = document.getElementById('timeline-wrapper');
        const hoverLine = document.getElementById('timeline-hover');
        const tooltip = document.getElementById('timeline-tooltip');

        if (timeline && minTime && maxTime) {{
            timeline.addEventListener('mousemove', function(e) {{
                const rect = timeline.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const percentage = (x / rect.width) * 100;

                // Calculate time at this position
                const timeAtPosition = new Date(minTime.getTime() + (percentage / 100) * timeRangeMs);
                const timeStr = timeAtPosition.toISOString().substr(11, 12); // HH:MM:SS.mmm

                // Update hover line and tooltip
                hoverLine.style.left = percentage + '%';
                hoverLine.style.display = 'block';

                tooltip.textContent = timeStr;
                tooltip.style.left = percentage + '%';
                tooltip.style.display = 'block';

                // Adjust tooltip position if near edges
                const tooltipRect = tooltip.getBoundingClientRect();
                const wrapperRect = timelineWrapper.getBoundingClientRect();
                if (tooltipRect.right > wrapperRect.right) {{
                    tooltip.style.transform = 'translateX(-100%)';
                }} else if (tooltipRect.left < wrapperRect.left) {{
                    tooltip.style.transform = 'translateX(0)';
                }} else {{
                    tooltip.style.transform = 'translateX(-50%)';
                }}
            }});

            timeline.addEventListener('mouseleave', function() {{
                hoverLine.style.display = 'none';
                tooltip.style.display = 'none';
            }});
        }}

        // Search handler
        const searchBox = document.getElementById('search');
        let searchTimeout;
        searchBox.addEventListener('input', function() {{
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {{
                filters.search = this.value;
                applyFilters();
            }}, 300);
        }});

        // Scroll to top button
        const scrollToTopBtn = document.getElementById('scroll-to-top');

        // Show/hide button based on scroll position
        window.addEventListener('scroll', function() {{
            if (window.pageYOffset > 300) {{
                scrollToTopBtn.classList.add('visible');
            }} else {{
                scrollToTopBtn.classList.remove('visible');
            }}
        }});

        // Scroll to top when clicked
        scrollToTopBtn.addEventListener('click', function() {{
            window.scrollTo({{
                top: 0,
                behavior: 'smooth'
            }});
        }});

        // File viewer functionality
        const viewer = document.getElementById('viewer');
        const viewerTitle = document.getElementById('viewer-title');
        const viewerIframe = document.getElementById('viewer-iframe');
        const viewerClose = document.getElementById('viewer-close');
        const viewerSize = document.getElementById('viewer-size');
        const MAX_INLINE_SIZE = 1 * 1024 * 1024; // 1MB

        // Handle file link clicks
        document.addEventListener('click', function(e) {{
            if (e.target.classList.contains('file-link')) {{
                e.preventDefault();
                const targetPath = e.target.dataset.path;
                const lineNum = e.target.dataset.line;

                // Extract display name from path (remove hash anchor if present)
                const displayPath = targetPath.split('#')[0];

                viewerTitle.textContent = `${{displayPath}}:${{lineNum}}`;
                viewerIframe.src = targetPath;
                viewer.classList.add('visible');
                updateViewerHeight();
            }}
        }});

        // Handle external link icon clicks
        document.addEventListener('click', function(e) {{
            const externalIcon = e.target.closest('.external-link-icon');
            if (externalIcon) {{
                e.preventDefault();
                e.stopPropagation();
                const path = externalIcon.dataset.path;
                window.open(path, '_blank');
            }}
        }});

        // Close viewer
        viewerClose.addEventListener('click', function() {{
            viewer.classList.remove('visible');
            viewerIframe.src = '';
        }});

        // Adjust viewer height
        function updateViewerHeight() {{
            const height = viewerSize.value;
            viewer.style.height = height + 'vh';
        }}

        viewerSize.addEventListener('input', updateViewerHeight);

        // ESC key to close viewer
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape' && viewer.classList.contains('visible')) {{
                viewer.classList.remove('visible');
                viewerIframe.src = '';
            }}
        }});
    </script>
</body>
</html>'''

    return html

def main():
    if len(sys.argv) < 7:
        print("Usage: generate_html_report.py <entries.json> <prowjob_name> <build_id> <target> <resource_pattern> <gcsweb_url>")
        sys.exit(1)

    entries_file = sys.argv[1]
    prowjob_name = sys.argv[2]
    build_id = sys.argv[3]
    target = sys.argv[4]
    resource_pattern = sys.argv[5]
    gcsweb_url = sys.argv[6]

    # Load entries
    with open(entries_file) as f:
        entries = json.load(f)

    # Convert timestamp strings to datetime objects
    for entry in entries:
        if entry['timestamp_str']:
            try:
                entry['timestamp'] = datetime.fromisoformat(entry['timestamp_str'].replace('Z', '+00:00'))
            except:
                entry['timestamp'] = None
        else:
            entry['timestamp'] = None

    # Create context-based HTML files for log files (full HTML for <1MB, context view for >1MB)
    import subprocess
    logs_dir = f".work/prow-job-analyze-resource/{build_id}/logs"
    file_mapping = {}

    # Check if create_context_html_files.py exists
    create_inline_script = Path(__file__).parent / "create_context_html_files.py"
    if create_inline_script.exists():
        print("Creating context-based HTML files for log files...", file=sys.stderr)
        try:
            result = subprocess.run(
                ["python3", str(create_inline_script), logs_dir, build_id, entries_file],
                capture_output=True,
                text=True,
                check=True
            )
            # Parse JSON output (the script outputs JSON to stdout)
            file_mapping = json.loads(result.stdout)
            print(f"Created {len(file_mapping)} HTML files", file=sys.stderr)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to create HTML files: {e.stderr}", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse file mapping JSON: {e}", file=sys.stderr)
    else:
        print(f"Warning: create_context_html_files.py not found at {create_inline_script}", file=sys.stderr)

    # Generate HTML
    html = generate_html_report(entries, prowjob_name, build_id, target, resource_pattern, gcsweb_url, file_mapping)

    # Determine filename - use first resource from pattern for safe filesystem naming
    if '|' in resource_pattern:
        first_resource = resource_pattern.split('|')[0]
    else:
        first_resource = resource_pattern

    # Sanitize filename (remove regex special chars that might cause issues)
    filename_safe = first_resource.replace('.*', '').replace('[', '').replace(']', '').replace('(', '').replace(')', '')

    # Write to file
    output_file = f".work/prow-job-analyze-resource/{build_id}/{filename_safe}.html"
    with open(output_file, 'w') as f:
        f.write(html)

    # Calculate statistics for JSON output
    level_counts = {}
    audit_count = 0
    pod_count = 0
    for entry in entries:
        level = entry.get('level', 'unknown')
        level_counts[level] = level_counts.get(level, 0) + 1
        if entry.get('source') == 'audit':
            audit_count += 1
        elif entry.get('source') == 'pod':
            pod_count += 1

    # Parse resource_pattern to get list of resources
    if '|' in resource_pattern:
        resources_list = sorted(resource_pattern.split('|'))
    else:
        resources_list = [resource_pattern]

    # Get timestamp range
    timestamps = [e['timestamp'] for e in entries if e['timestamp']]
    if timestamps:
        first_timestamp = min(timestamps).isoformat()
        last_timestamp = max(timestamps).isoformat()
    else:
        first_timestamp = None
        last_timestamp = None

    # Output structured JSON to stdout for parsing
    result = {
        "success": True,
        "output_file": output_file,
        "prowjob_name": prowjob_name,
        "build_id": build_id,
        "target": target,
        "resources": resources_list,
        "total_entries": len(entries),
        "audit_entries": audit_count,
        "pod_entries": pod_count,
        "level_counts": level_counts,
        "inline_html_files": len(file_mapping),
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp
    }

    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
