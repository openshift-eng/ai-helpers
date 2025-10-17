#!/usr/bin/env python3
"""Create HTML files with line numbers for inline viewing."""

import os
import sys
import hashlib
import html as html_module
from pathlib import Path


def create_html_files_for_logs(logs_dir, build_id):
    """Create .html files with line numbers for log files under 1MB."""
    MAX_INLINE_SIZE = 1 * 1024 * 1024  # 1MB
    links_dir = os.path.join(logs_dir, '_links')

    # Create _links directory if it doesn't exist
    os.makedirs(links_dir, exist_ok=True)

    html_count = 0
    file_mapping = {}  # Map from original path to HTML path

    # Walk through all log files
    for root, dirs, filenames in os.walk(logs_dir):
        # Skip the _links directory itself
        if '_links' in root:
            continue

        for filename in filenames:
            file_path = os.path.join(root, filename)

            try:
                # Get file size
                size = os.path.getsize(file_path)

                if size < MAX_INLINE_SIZE:
                    # Get relative path from logs_dir
                    rel_path = os.path.relpath(file_path, logs_dir)

                    # Generate unique HTML name by hashing the full path
                    path_hash = hashlib.md5(rel_path.encode()).hexdigest()[:8]
                    html_name = f"{filename}.{path_hash}.html"
                    html_path = os.path.join(links_dir, html_name)

                    # Read original file content
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
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
                        numbered_lines.append(f'<span class="line-number" id="linenum-{i}">{line_num}</span> {escaped_line}')

                    numbered_content = '\n'.join(numbered_lines)

                    # Wrap in HTML
                    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{html_module.escape(filename)}</title>
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
</html>'''

                    # Write HTML file
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)

                    # Store mapping
                    rel_html_path = f"logs/_links/{html_name}"
                    file_mapping[rel_path] = rel_html_path
                    html_count += 1

            except Exception as e:
                print(f"WARNING: Could not create HTML for {file_path}: {e}", file=sys.stderr)

    print(f"Created {html_count} .html files for inline viewing", file=sys.stderr)
    return file_mapping


def main():
    if len(sys.argv) < 3:
        print("Usage: create_inline_html_files.py <logs_dir> <build_id>")
        sys.exit(1)

    logs_dir = sys.argv[1]
    build_id = sys.argv[2]

    if not os.path.exists(logs_dir):
        print(f"ERROR: Logs directory not found: {logs_dir}", file=sys.stderr)
        sys.exit(1)

    file_mapping = create_html_files_for_logs(logs_dir, build_id)

    # Output mapping as JSON for use by other scripts
    import json
    print(json.dumps(file_mapping))


if __name__ == '__main__':
    main()
