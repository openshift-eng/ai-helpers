#!/usr/bin/env python3
"""
Create HTML files for log viewing with line numbers, regex filtering, and line selection.
For files >1MB, creates context files with ±1000 lines around each referenced line.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from collections import defaultdict

# HTML template for viewing log files
HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
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
        .context-notice {{
            background: #1c2128;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 8px 12px;
            margin: 8px 16px;
            color: #8b949e;
            font-size: 11px;
        }}
        .context-notice strong {{
            color: #58a6ff;
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
    {context_notice}
    <div class="content-wrapper">
        <pre id="content">{content}</pre>
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

        // Select line from hash on load
        if (window.location.hash) {{
            const lineNum = window.location.hash.substring(1).replace('line-', '');
            const lineNumElement = document.getElementById('linenum-' + lineNum);
            if (lineNumElement) {{
                const lineElement = lineNumElement.closest('.line');
                if (lineElement) {{
                    selectedLine = lineElement;
                    selectedLine.classList.add('selected');
                    setTimeout(() => {{
                        selectedLine.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    }}, 100);
                }}
            }}
        }}
    </script>
</body>
</html>
'''

def create_html_for_file(file_path, logs_dir, build_id, line_numbers=None, context_lines=1000):
    """
    Create an HTML file for viewing a log file.

    Args:
        file_path: Absolute path to the log file
        logs_dir: Base logs directory
        build_id: Build ID
        line_numbers: List of line numbers to include (for large files). If None, includes all lines.
        context_lines: Number of lines before/after each line_number to include (default 1000)

    Returns:
        Tuple of (relative_path_key, html_file_path) or None if file should be skipped
    """
    file_size = os.path.getsize(file_path)
    relative_path = os.path.relpath(file_path, logs_dir)

    # For small files (<1MB), create full HTML
    if file_size < 1024 * 1024:
        line_numbers = None  # Include all lines

    # Read the file and extract lines
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return None

    # Determine which lines to include
    if line_numbers is None:
        # Include all lines (small file)
        lines_to_include = set(range(1, len(all_lines) + 1))
        context_notice = ''
    else:
        # Include context around each line number (large file)
        lines_to_include = set()
        for line_num in line_numbers:
            start = max(1, line_num - context_lines)
            end = min(len(all_lines), line_num + context_lines)
            lines_to_include.update(range(start, end + 1))

        # Create context notice
        line_ranges = []
        sorted_lines = sorted(lines_to_include)
        if sorted_lines:
            range_start = sorted_lines[0]
            range_end = sorted_lines[0]
            for line in sorted_lines[1:]:
                if line == range_end + 1:
                    range_end = line
                else:
                    line_ranges.append(f"{range_start}-{range_end}" if range_start != range_end else str(range_start))
                    range_start = line
                    range_end = line
            line_ranges.append(f"{range_start}-{range_end}" if range_start != range_end else str(range_start))

        context_notice = f'''<div class="context-notice">
        <strong>Context View:</strong> Showing {len(lines_to_include):,} of {len(all_lines):,} lines
        (±{context_lines} lines around {len(line_numbers)} reference points).
        Full file is {file_size / (1024 * 1024):.1f}MB.
    </div>'''

    # Build HTML content with line numbers
    html_lines = []
    for i, line in enumerate(all_lines, 1):
        if i in lines_to_include:
            # Escape HTML characters
            line_content = line.rstrip('\n').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html_lines.append(f'<span class="line-number" id="linenum-{i}">{i:>5}</span> {line_content}')

    content = '\n'.join(html_lines)

    # Generate unique filename based on content and line selection
    if line_numbers is None:
        # For full files, use simple hash of path
        hash_str = hashlib.md5(relative_path.encode()).hexdigest()[:8]
        suffix = ''
    else:
        # For context files, include line numbers in hash
        hash_input = f"{relative_path}:{','.join(map(str, sorted(line_numbers)))}"
        hash_str = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        suffix = f"-ctx{len(line_numbers)}"

    filename = os.path.basename(file_path)
    html_filename = f"{filename}{suffix}.{hash_str}.html"

    # Create _links directory
    links_dir = os.path.join(logs_dir, "_links")
    os.makedirs(links_dir, exist_ok=True)

    html_path = os.path.join(links_dir, html_filename)
    relative_html_path = f"logs/_links/{html_filename}"

    # Generate HTML
    title = filename
    html = HTML_TEMPLATE.format(
        title=title,
        context_notice=context_notice,
        content=content
    )

    # Write HTML file
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return (relative_path, relative_html_path)

def main():
    if len(sys.argv) < 3:
        print("Usage: create_context_html_files.py <logs_dir> <build_id> [entries_json]", file=sys.stderr)
        sys.exit(1)

    logs_dir = sys.argv[1]
    build_id = sys.argv[2]
    entries_json = sys.argv[3] if len(sys.argv) > 3 else None

    # Load entries to get line numbers per file
    file_line_numbers = defaultdict(set)
    if entries_json:
        with open(entries_json, 'r') as f:
            entries = json.load(f)

        for entry in entries:
            filename = entry.get('filename', '')
            line_num = entry.get('line_number', 0)
            if filename and line_num:
                file_line_numbers[filename].add(line_num)

    # Collect all log files
    log_files = []
    for root, dirs, files in os.walk(logs_dir):
        # Skip _links directory
        if '_links' in root:
            continue
        for file in files:
            if file.endswith('.log') or file.endswith('.jsonl'):
                log_files.append(os.path.join(root, file))

    # Create HTML files
    file_mapping = {}
    for log_file in log_files:
        # Get line numbers for this file (if any)
        line_nums = file_line_numbers.get(log_file)
        if line_nums:
            line_nums = sorted(list(line_nums))
        else:
            line_nums = None

        result = create_html_for_file(log_file, logs_dir, build_id, line_nums)
        if result:
            relative_path, html_path = result
            file_mapping[relative_path] = html_path

    # Output JSON mapping to stdout
    print(json.dumps(file_mapping, indent=2))

if __name__ == '__main__':
    main()
