#!/usr/bin/env python3
"""Generate interactive HTML file browser for must-gather extraction."""

import os
import sys
import json
import hashlib
import html as html_module
from datetime import datetime
from pathlib import Path


def human_readable_size(size_bytes):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def get_file_type(filename):
    """Determine file type based on extension."""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''

    type_map = {
        'log': 'log',
        'txt': 'log',
        'yaml': 'yaml',
        'yml': 'yaml',
        'json': 'json',
        'xml': 'xml',
        'crt': 'cert',
        'pem': 'cert',
        'key': 'cert',
        'tar': 'archive',
        'gz': 'archive',
        'tgz': 'archive',
        'zip': 'archive',
        'sh': 'script',
        'py': 'script',
        'conf': 'config',
        'cfg': 'config',
        'ini': 'config',
    }

    return type_map.get(ext, 'other')


def get_file_icon(file_type):
    """Get icon character for file type."""
    icons = {
        'log': '📄',
        'yaml': '📋',
        'json': '{ }',
        'xml': '</>',
        'cert': '🔐',
        'archive': '📦',
        'script': '⚙️',
        'config': '⚙️',
        'other': '📄',
    }
    return icons.get(file_type, '📄')


def scan_directory(base_path):
    """Scan directory and collect file information."""
    files = []
    type_counts = {}
    dir_counts = {}
    total_size = 0

    for root, dirs, filenames in os.walk(base_path):
        # Skip the _links directory
        if '_links' in dirs:
            dirs.remove('_links')

        for filename in filenames:
            file_path = os.path.join(root, filename)
            try:
                # Get relative path from base_path
                rel_path = os.path.relpath(file_path, base_path)

                # Get file info
                stat_info = os.stat(file_path)
                size = stat_info.st_size
                total_size += size

                # Determine file type
                file_type = get_file_type(filename)
                type_counts[file_type] = type_counts.get(file_type, 0) + 1

                # Get directory path (everything except filename)
                dir_path = os.path.dirname(rel_path)

                # Get top-level directory (first segment after content/)
                top_level_dir = ''
                if dir_path.startswith('content/'):
                    path_parts = dir_path.split('/', 2)
                    if len(path_parts) >= 2:
                        top_level_dir = path_parts[1]
                        dir_counts[top_level_dir] = dir_counts.get(top_level_dir, 0) + 1
                elif '/' in dir_path:
                    # If not under content/, use first directory
                    top_level_dir = dir_path.split('/', 1)[0]
                    dir_counts[top_level_dir] = dir_counts.get(top_level_dir, 0) + 1

                files.append({
                    'name': filename,
                    'path': rel_path,
                    'dir': dir_path,
                    'top_level_dir': top_level_dir,
                    'size': size,
                    'size_human': human_readable_size(size),
                    'type': file_type,
                    'modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                })
            except Exception as e:
                print(f"WARNING: Could not process {file_path}: {e}", file=sys.stderr)

    # Sort files by path
    files.sort(key=lambda f: f['path'])

    return files, type_counts, dir_counts, total_size


def generate_html_report(files, type_counts, dir_counts, total_size, prowjob_name, build_id, target, gcsweb_url):
    """Generate an interactive HTML file browser."""

    total_files = len(files)
    total_size_human = human_readable_size(total_size)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Must-Gather Browser: {build_id}</title>
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

        .filters {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 24px;
            margin-bottom: 24px;
        }}

        .filter-group {{
            margin-bottom: 16px;
        }}

        .filter-group:last-child {{
            margin-bottom: 0;
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
            font-family: ui-monospace, SFMono-Regular, monospace;
        }}

        .search-box:focus {{
            outline: none;
            border-color: #58a6ff;
        }}

        .file-list {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 24px;
        }}

        .file-item {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            margin-bottom: 8px;
            transition: border-color 0.2s;
        }}

        .file-item:hover {{
            border-color: #58a6ff;
        }}

        .file-icon {{
            font-size: 24px;
            flex-shrink: 0;
        }}

        .file-info {{
            flex: 1;
            min-width: 0;
        }}

        .file-name {{
            font-size: 14px;
            margin-bottom: 4px;
        }}

        .file-name a {{
            color: #58a6ff;
            text-decoration: none;
            word-break: break-all;
        }}

        .file-name a:hover {{
            text-decoration: underline;
        }}

        .file-meta {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            font-size: 12px;
            color: #8b949e;
        }}

        .file-path {{
            font-family: ui-monospace, SFMono-Regular, monospace;
        }}

        .file-size {{
            color: #8b949e;
        }}

        .badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-log {{
            background: rgba(88, 166, 255, 0.15);
            color: #58a6ff;
            border: 1px solid rgba(88, 166, 255, 0.3);
        }}

        .badge-yaml {{
            background: rgba(147, 51, 234, 0.15);
            color: #a78bfa;
            border: 1px solid rgba(147, 51, 234, 0.3);
        }}

        .badge-json {{
            background: rgba(34, 134, 58, 0.15);
            color: #3fb950;
            border: 1px solid rgba(34, 134, 58, 0.3);
        }}

        .badge-xml {{
            background: rgba(187, 128, 9, 0.15);
            color: #d29922;
            border: 1px solid rgba(187, 128, 9, 0.3);
        }}

        .badge-cert {{
            background: rgba(248, 81, 73, 0.15);
            color: #f85149;
            border: 1px solid rgba(248, 81, 73, 0.3);
        }}

        .badge-archive {{
            background: rgba(139, 148, 158, 0.15);
            color: #8b949e;
            border: 1px solid rgba(139, 148, 158, 0.3);
        }}

        .badge-script {{
            background: rgba(56, 139, 253, 0.15);
            color: #58a6ff;
            border: 1px solid rgba(56, 139, 253, 0.3);
        }}

        .badge-config {{
            background: rgba(187, 128, 9, 0.15);
            color: #d29922;
            border: 1px solid rgba(187, 128, 9, 0.3);
        }}

        .badge-other {{
            background: rgba(139, 148, 158, 0.15);
            color: #8b949e;
            border: 1px solid rgba(139, 148, 158, 0.3);
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

        .pattern-error {{
            color: #f85149;
            font-size: 12px;
            margin-top: 4px;
            display: none;
        }}

        .pattern-error.visible {{
            display: block;
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

        .file-name:hover .external-link-icon {{
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

        .file-name a {{
            cursor: pointer;
        }}

        .file-size-badge {{
            background: rgba(139, 148, 158, 0.15);
            color: #8b949e;
            border: 1px solid rgba(139, 148, 158, 0.3);
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
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
        <h1>Must-Gather File Browser</h1>
        <div class="metadata">
            <div>
                <p><strong>Prow Job:</strong> {prowjob_name}</p>
                <p><strong>Build ID:</strong> {build_id}</p>
                <p><strong>Target:</strong> {target}</p>
            </div>
            <div>
                <p><strong>GCS URL:</strong> <a href="{gcsweb_url}" target="_blank">View in gcsweb</a></p>
                <p><strong>Local Path:</strong> .work/prow-job-extract-must-gather/{build_id}/logs/</p>
            </div>
        </div>
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{total_files:,}</div>
                <div class="stat-label">Total Files</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_size_human}</div>
                <div class="stat-label">Total Size</div>
            </div>'''

    # Add stats for each file type
    for file_type in sorted(type_counts.keys()):
        count = type_counts[file_type]
        html += f'''
            <div class="stat">
                <div class="stat-value">{count:,}</div>
                <div class="stat-label">{file_type}</div>
            </div>'''

    html += '''
        </div>
    </div>

    <div class="filters">
        <div class="filter-group">
            <label class="filter-label">File Type (multi-select)</label>
            <div class="filter-buttons">'''

    # Add filter buttons for each type
    for file_type in sorted(type_counts.keys()):
        count = type_counts[file_type]
        html += f'''
                <button class="filter-btn active" data-filter="type" data-value="{file_type}">{file_type} ({count:,})</button>'''

    html += f'''
            </div>
        </div>
        <div class="filter-group">
            <label class="filter-label">Directory (multi-select)</label>
            <div class="filter-buttons">'''

    # Add filter buttons for each top-level directory
    for directory in sorted(dir_counts.keys()):
        count = dir_counts[directory]
        # Display name with proper formatting
        display_name = directory if directory else '(root)'
        html += f'''
                <button class="filter-btn active" data-filter="dir" data-value="{directory}">{display_name} ({count:,})</button>'''

    html += f'''
            </div>
        </div>
        <div class="filter-group">
            <label class="filter-label">Filter by Regex Pattern</label>
            <input type="text" class="search-box" id="pattern" placeholder="Enter regex pattern (e.g., .*etcd.*, .*\\.log$, ^content/namespaces/.*)">
            <div class="pattern-error" id="pattern-error">Invalid regex pattern</div>
        </div>
        <div class="filter-group">
            <label class="filter-label">Search by Name</label>
            <input type="text" class="search-box" id="search" placeholder="Search file names or paths...">
        </div>
    </div>

    <div class="file-list">
        <div id="file-container">'''

    # Add file items
    for file in files:
        icon = get_file_icon(file['type'])
        # Use symlink path for iframe if available, otherwise use original
        iframe_path = file.get('symlink_path', f"logs/{file['path']}")
        original_path = f"logs/{file['path']}"

        html += f'''
        <div class="file-item" data-type="{file['type']}" data-path="{file['path']}" data-name="{file['name'].lower()}" data-dir="{file['top_level_dir']}" data-size="{file['size']}">
            <div class="file-icon">{icon}</div>
            <div class="file-info">
                <div class="file-name">
                    <a class="file-link" data-iframe-path="{iframe_path}" data-original-path="{original_path}" data-size="{file['size']}">{file['name']}</a>
                    <span class="external-link-icon" data-path="{original_path}" title="Open in new tab">
                        <svg viewBox="0 0 16 16">
                            <path d="M3.75 2A1.75 1.75 0 002 3.75v8.5c0 .966.784 1.75 1.75 1.75h8.5A1.75 1.75 0 0014 12.25v-3.5a.75.75 0 00-1.5 0v3.5a.25.25 0 01-.25.25h-8.5a.25.25 0 01-.25-.25v-8.5a.25.25 0 01.25-.25h3.5a.75.75 0 000-1.5h-3.5zM9.5 2.75a.75.75 0 01.75-.75h3.5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0V4.56L8.78 8.78a.75.75 0 01-1.06-1.06l4.22-4.22h-1.69a.75.75 0 01-.75-.75z"/>
                        </svg>
                    </span>
                </div>
                <div class="file-meta">
                    <span class="file-path">{file['dir']}</span>
                    <span class="file-size-badge">{file['size_human']}</span>
                    <span class="badge badge-{file['type']}">{file['type']}</span>
                </div>
            </div>
        </div>'''

    html += f'''
        </div>
        <div id="no-results" class="no-results hidden">
            No files match the current filters
        </div>
    </div>

    <script>
        const filters = {{
            types: new Set({json.dumps(list(type_counts.keys()))}),  // All selected by default
            dirs: new Set({json.dumps(list(dir_counts.keys()))}),  // All selected by default
            pattern: null,
            search: ''
        }};

        function applyFilters() {{
            const fileItems = document.querySelectorAll('.file-item');
            let visibleCount = 0;

            fileItems.forEach(item => {{
                let show = true;

                // Type filter
                if (filters.types.size > 0 && !filters.types.has(item.dataset.type)) {{
                    show = false;
                }}

                // Directory filter
                if (filters.dirs.size > 0 && show) {{
                    const itemDir = item.dataset.dir || '';
                    if (!filters.dirs.has(itemDir)) {{
                        show = false;
                    }}
                }}

                // Regex pattern filter
                if (filters.pattern && show) {{
                    try {{
                        if (!filters.pattern.test(item.dataset.path)) {{
                            show = false;
                        }}
                    }} catch (e) {{
                        // Invalid regex, skip pattern filter
                    }}
                }}

                // Search filter
                if (filters.search && show) {{
                    const searchLower = filters.search.toLowerCase();
                    const path = item.dataset.path.toLowerCase();
                    const name = item.dataset.name;
                    if (!path.includes(searchLower) && !name.includes(searchLower)) {{
                        show = false;
                    }}
                }}

                item.classList.toggle('hidden', !show);
                if (show) visibleCount++;
            }});

            document.getElementById('no-results').classList.toggle('hidden', visibleCount > 0);
        }}

        // Filter buttons (both type and directory)
        document.querySelectorAll('.filter-btn').forEach(btn => {{
            btn.addEventListener('click', function(e) {{
                const filterType = this.dataset.filter;
                const value = this.dataset.value;
                const isActive = this.classList.contains('active');

                if (filterType === 'type') {{
                    if (isActive) {{
                        this.classList.remove('active');
                        filters.types.delete(value);
                    }} else {{
                        this.classList.add('active');
                        filters.types.add(value);
                    }}
                }} else if (filterType === 'dir') {{
                    if (isActive) {{
                        this.classList.remove('active');
                        filters.dirs.delete(value);
                    }} else {{
                        this.classList.add('active');
                        filters.dirs.add(value);
                    }}
                }}

                applyFilters();
            }});

            btn.addEventListener('dblclick', function(e) {{
                const filterType = this.dataset.filter;
                const value = this.dataset.value;

                if (filterType === 'type') {{
                    // Deselect all type filters
                    document.querySelectorAll('.filter-btn[data-filter="type"]').forEach(b => {{
                        b.classList.remove('active');
                    }});
                    filters.types.clear();

                    // Select only this one
                    this.classList.add('active');
                    filters.types.add(value);
                }} else if (filterType === 'dir') {{
                    // Deselect all directory filters
                    document.querySelectorAll('.filter-btn[data-filter="dir"]').forEach(b => {{
                        b.classList.remove('active');
                    }});
                    filters.dirs.clear();

                    // Select only this one
                    this.classList.add('active');
                    filters.dirs.add(value);
                }}

                applyFilters();
            }});
        }});

        // Regex pattern filter
        const patternInput = document.getElementById('pattern');
        const patternError = document.getElementById('pattern-error');
        let patternTimeout;

        patternInput.addEventListener('input', function() {{
            clearTimeout(patternTimeout);
            patternTimeout = setTimeout(() => {{
                const pattern = this.value.trim();
                if (pattern) {{
                    try {{
                        filters.pattern = new RegExp(pattern);
                        patternError.classList.remove('visible');
                    }} catch (e) {{
                        filters.pattern = null;
                        patternError.classList.add('visible');
                    }}
                }} else {{
                    filters.pattern = null;
                    patternError.classList.remove('visible');
                }}
                applyFilters();
            }}, 300);
        }});

        // Search filter
        const searchInput = document.getElementById('search');
        let searchTimeout;

        searchInput.addEventListener('input', function() {{
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {{
                filters.search = this.value.trim();
                applyFilters();
            }}, 300);
        }});

        // Scroll to top button
        const scrollToTopBtn = document.getElementById('scroll-to-top');

        window.addEventListener('scroll', function() {{
            if (window.pageYOffset > 300) {{
                scrollToTopBtn.classList.add('visible');
            }} else {{
                scrollToTopBtn.classList.remove('visible');
            }}
        }});

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
                const iframePath = e.target.dataset.iframePath;
                const originalPath = e.target.dataset.originalPath;
                const size = parseInt(e.target.dataset.size);

                if (size < MAX_INLINE_SIZE) {{
                    // Load .log symlink in iframe (should display as text/plain)
                    viewerTitle.textContent = originalPath;
                    viewerIframe.src = iframePath;  // Use the .log symlink
                    viewer.classList.add('visible');
                    updateViewerHeight();
                }} else {{
                    // Open in new tab for large files
                    window.open(originalPath, '_blank');
                }}
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


def create_txt_symlinks(logs_dir, files):
    """Create .html files with escaped content for files under 1MB to prevent download dialogs."""
    MAX_INLINE_SIZE = 1 * 1024 * 1024  # 1MB
    links_dir = os.path.join(logs_dir, 'content', '_links')

    # Create _links directory if it doesn't exist
    os.makedirs(links_dir, exist_ok=True)

    html_count = 0

    for file in files:
        if file['size'] < MAX_INLINE_SIZE:
            # Create HTML file with escaped content
            original_path = os.path.join(logs_dir, file['path'])

            # Generate unique HTML name by hashing the full path
            path_hash = hashlib.md5(file['path'].encode()).hexdigest()[:8]
            html_name = f"{file['name']}.{path_hash}.html"
            html_path = os.path.join(links_dir, html_name)

            try:
                # Read original file content
                with open(original_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

                # Split into lines and add line numbers
                lines = content.split('\n')
                line_count = len(lines)
                line_number_width = len(str(line_count))

                # Build content with line numbers
                numbered_lines = []
                for i, line in enumerate(lines, 1):
                    escaped_line = html_module.escape(line)
                    line_num = str(i).rjust(line_number_width)
                    numbered_lines.append(f'<span class="line-number">{line_num}</span> {escaped_line}')

                numbered_content = '\n'.join(numbered_lines)

                # Wrap in HTML
                html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{html_module.escape(file['name'])}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background: #161b22;
            color: #c9d1d9;
            font-family: ui-monospace, SFMono-Regular, 'SF Mono', Monaco, 'Cascadia Mono', 'Segoe UI Mono', monospace;
            font-size: 12px;
            line-height: 1.5;
        }}
        .filter-bar {{
            position: sticky;
            top: 0;
            background: #0d1117;
            border-bottom: 1px solid #30363d;
            padding: 8px 16px;
            z-index: 100;
        }}
        .filter-input-wrapper {{
            position: relative;
            display: flex;
            gap: 8px;
        }}
        .filter-input {{
            flex: 1;
            padding: 6px 10px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            color: #c9d1d9;
            font-size: 12px;
            font-family: ui-monospace, SFMono-Regular, monospace;
        }}
        .filter-input:focus {{
            outline: none;
            border-color: #58a6ff;
        }}
        .clear-btn {{
            padding: 6px 12px;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 4px;
            color: #c9d1d9;
            cursor: pointer;
            font-size: 12px;
            white-space: nowrap;
        }}
        .clear-btn:hover {{
            background: #30363d;
            border-color: #58a6ff;
        }}
        .filter-error {{
            color: #f85149;
            font-size: 11px;
            margin-top: 4px;
            display: none;
        }}
        .filter-error.visible {{
            display: block;
        }}
        .content-wrapper {{
            padding: 16px;
        }}
        pre {{
            margin: 0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .line-number {{
            color: #6e7681;
            user-select: none;
            margin-right: 16px;
            display: inline-block;
        }}
        .line {{
            display: block;
            cursor: pointer;
        }}
        .line:hover {{
            background: rgba(139, 148, 158, 0.1);
        }}
        .line.hidden {{
            display: none;
        }}
        .line.match {{
            background: rgba(88, 166, 255, 0.15);
        }}
        .line.selected {{
            background: rgba(187, 128, 9, 0.25);
            border-left: 3px solid #d29922;
            padding-left: 13px;
        }}
        .line.selected.match {{
            background: rgba(187, 128, 9, 0.25);
        }}
    </style>
</head>
<body>
    <div class="filter-bar">
        <div class="filter-input-wrapper">
            <input type="text" class="filter-input" id="filter" placeholder="Filter lines by regex (e.g., error|warning, ^INFO.*)">
            <button class="clear-btn" id="clear-btn" title="Clear filter (Ctrl+C)">Clear</button>
        </div>
        <div class="filter-error" id="filter-error">Invalid regex pattern</div>
    </div>
    <div class="content-wrapper">
        <pre id="content">{numbered_content}</pre>
    </div>
    <script>
        const filterInput = document.getElementById('filter');
        const filterError = document.getElementById('filter-error');
        const clearBtn = document.getElementById('clear-btn');
        const content = document.getElementById('content');
        let filterTimeout;
        let selectedLine = null;

        // Wrap each line in a span for filtering
        const lines = content.innerHTML.split('\\n');
        const wrappedLines = lines.map(line => `<span class="line">${{line}}</span>`).join('');
        content.innerHTML = wrappedLines;

        // Line selection handler
        content.addEventListener('click', function(e) {{
            const clickedLine = e.target.closest('.line');
            if (clickedLine) {{
                // Remove previous selection
                if (selectedLine) {{
                    selectedLine.classList.remove('selected');
                }}
                // Select new line
                selectedLine = clickedLine;
                selectedLine.classList.add('selected');
            }}
        }});

        // Clear filter function
        function clearFilter() {{
            filterInput.value = '';
            filterError.classList.remove('visible');

            const lineElements = content.querySelectorAll('.line');
            lineElements.forEach(line => {{
                line.classList.remove('hidden', 'match');
            }});

            // Scroll to selected line if exists
            if (selectedLine) {{
                selectedLine.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }}

        // Clear button click handler
        clearBtn.addEventListener('click', clearFilter);

        // Ctrl+C hotkey to clear filter
        document.addEventListener('keydown', function(e) {{
            if (e.ctrlKey && e.key === 'c') {{
                // Only clear if filter input is not focused (to allow normal copy)
                if (document.activeElement !== filterInput) {{
                    e.preventDefault();
                    clearFilter();
                }}
            }}
        }});

        // Filter input handler
        filterInput.addEventListener('input', function() {{
            clearTimeout(filterTimeout);
            filterTimeout = setTimeout(() => {{
                const pattern = this.value.trim();
                const lineElements = content.querySelectorAll('.line');

                if (!pattern) {{
                    // Show all lines
                    lineElements.forEach(line => {{
                        line.classList.remove('hidden', 'match');
                    }});
                    filterError.classList.remove('visible');

                    // Scroll to selected line if exists
                    if (selectedLine) {{
                        selectedLine.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    }}
                    return;
                }}

                try {{
                    const regex = new RegExp(pattern);
                    filterError.classList.remove('visible');

                    lineElements.forEach(line => {{
                        // Get text content without line number span
                        const textContent = line.textContent;
                        const lineNumberMatch = textContent.match(/^\\s*\\d+\\s+/);
                        const actualContent = lineNumberMatch ? textContent.substring(lineNumberMatch[0].length) : textContent;

                        if (regex.test(actualContent)) {{
                            line.classList.remove('hidden');
                            line.classList.add('match');
                        }} else {{
                            line.classList.add('hidden');
                            line.classList.remove('match');
                        }}
                    }});
                }} catch (e) {{
                    filterError.classList.add('visible');
                }}
            }}, 300);
        }});
    </script>
</body>
</html>'''

                # Write HTML file
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                # Store HTML path in file metadata
                file['symlink_path'] = f"logs/content/_links/{html_name}"
                html_count += 1
            except Exception as e:
                print(f"WARNING: Could not create HTML for {file['path']}: {e}", file=sys.stderr)
                file['symlink_path'] = None
        else:
            file['symlink_path'] = None

    print(f"Created {html_count:,} .html files for inline viewing")
    return files


def main():
    if len(sys.argv) < 6:
        print("Usage: generate_html_report.py <logs-directory> <prowjob_name> <build_id> <target> <gcsweb_url>")
        sys.exit(1)

    logs_dir = sys.argv[1]
    prowjob_name = sys.argv[2]
    build_id = sys.argv[3]
    target = sys.argv[4]
    gcsweb_url = sys.argv[5]

    # Validate logs directory
    if not os.path.exists(logs_dir):
        print(f"ERROR: Logs directory not found: {logs_dir}", file=sys.stderr)
        sys.exit(1)

    print("Scanning directory tree...")
    files, type_counts, dir_counts, total_size = scan_directory(logs_dir)

    print(f"Found {len(files):,} files ({human_readable_size(total_size)})")

    print("Creating .html files for inline viewing...")
    files = create_txt_symlinks(logs_dir, files)

    print("Generating HTML report...")
    html = generate_html_report(files, type_counts, dir_counts, total_size, prowjob_name, build_id, target, gcsweb_url)

    # Determine output path
    output_dir = os.path.dirname(logs_dir)
    output_file = os.path.join(output_dir, 'must-gather-browser.html')

    # Write to file
    with open(output_file, 'w') as f:
        f.write(html)

    print(f"Report generated: {output_file}")


if __name__ == '__main__':
    main()
