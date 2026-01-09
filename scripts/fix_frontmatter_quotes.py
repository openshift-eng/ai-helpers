#!/usr/bin/env python3
"""
Auto-fix frontmatter quotes in markdown files.

This script automatically adds quotes to frontmatter values that start with '['
to prevent YAML parsing errors in browsers. It processes all command markdown files
in the plugins directory.
"""

import re
import sys
from pathlib import Path


def needs_quoting(value: str) -> bool:
    """
    Check if a frontmatter value needs to be quoted.

    Values starting with '[' should be quoted to prevent YAML array interpretation.
    """
    value = value.strip()
    # Check if value starts with '[' and is not already quoted
    if value.startswith('['):
        # Check if it's already quoted (either single or double quotes)
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return False
        return True
    return False


def fix_frontmatter_in_file(file_path: Path) -> bool:
    """
    Fix frontmatter quotes in a single markdown file.

    Returns True if file was modified, False otherwise.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if file has frontmatter
        if not content.startswith('---'):
            return False

        # Split frontmatter from content
        parts = content.split('---', 2)
        if len(parts) < 3:
            return False

        frontmatter_lines = parts[1].strip().split('\n')
        modified = False
        new_frontmatter_lines = []

        for line in frontmatter_lines:
            if ':' in line:
                key, value = line.split(':', 1)
                value_stripped = value.strip()

                if needs_quoting(value_stripped):
                    # Add double quotes around the value
                    # Preserve original spacing by counting leading spaces in value
                    leading_spaces = len(value) - len(value.lstrip())
                    new_line = f'{key}:{" " * leading_spaces}"{value_stripped}"'
                    new_frontmatter_lines.append(new_line)
                    modified = True
                else:
                    new_frontmatter_lines.append(line)
            else:
                new_frontmatter_lines.append(line)

        if modified:
            # Reconstruct the file
            new_content = '---\n' + '\n'.join(new_frontmatter_lines) + '\n---' + parts[2]

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point."""

    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    plugins_dir = repo_root / 'plugins'

    if not plugins_dir.exists():
        print(f"Error: Plugins directory not found: {plugins_dir}", file=sys.stderr)
        sys.exit(1)

    # Find all command markdown files
    command_files = list(plugins_dir.glob('*/commands/*.md'))

    if not command_files:
        print("No command files found")
        return

    modified_count = 0

    for file_path in sorted(command_files):
        if fix_frontmatter_in_file(file_path):
            modified_count += 1
            print(f"Fixed: {file_path.relative_to(repo_root)}")

    if modified_count > 0:
        print(f"✓ Fixed frontmatter quotes in {modified_count} file(s)\n")
    else:
        print("✓ No files needed fixing - all frontmatter quotes are correct")


if __name__ == '__main__':
    main()
