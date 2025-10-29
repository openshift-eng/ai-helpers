#!/usr/bin/env python3
"""
Generate plugin documentation by scanning all plugins in the repository.

This script scans the plugins directory, reads plugin metadata and command files,
and generates a markdown documentation section listing all available plugins and commands.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class PluginInfo:
    """Information about a plugin."""
    
    def __init__(self, name: str, description: str, version: str):
        self.name = name
        self.description = description
        self.version = version
        self.commands = []
    
    def add_command(self, command_name: str, description: str, argument_hint: str = ""):
        """Add a command to this plugin."""
        self.commands.append({
            'name': command_name,
            'description': description,
            'argument_hint': argument_hint
        })


def parse_frontmatter(content: str) -> Dict[str, str]:
    """Parse YAML frontmatter from a markdown file."""
    frontmatter = {}
    
    # Match frontmatter between --- markers
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        frontmatter_text = match.group(1)
        
        # Parse simple YAML key-value pairs
        for line in frontmatter_text.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip()
    
    return frontmatter


def get_plugin_info(plugin_dir: Path) -> PluginInfo:
    """Extract plugin information from plugin.json and command files."""
    
    # Read plugin metadata
    plugin_json_path = plugin_dir / '.claude-plugin' / 'plugin.json'
    if not plugin_json_path.exists():
        return None
    
    with open(plugin_json_path, 'r') as f:
        plugin_data = json.load(f)
    
    plugin_info = PluginInfo(
        name=plugin_data.get('name', plugin_dir.name),
        description=plugin_data.get('description', ''),
        version=plugin_data.get('version', '0.0.0')
    )
    
    # Scan commands
    commands_dir = plugin_dir / 'commands'
    if commands_dir.exists():
        command_files = sorted(commands_dir.glob('*.md'))
        
        for command_file in command_files:
            with open(command_file, 'r') as f:
                content = f.read()
            
            frontmatter = parse_frontmatter(content)
            command_name = command_file.stem
            
            plugin_info.add_command(
                command_name=command_name,
                description=frontmatter.get('description', ''),
                argument_hint=frontmatter.get('argument-hint', '')
            )
    
    return plugin_info


def generate_plugin_docs(plugins_dir: Path) -> str:
    """Generate markdown documentation for all plugins."""
    
    # Collect all plugins
    plugins = []
    
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue
        
        plugin_info = get_plugin_info(plugin_dir)
        if plugin_info and plugin_info.commands:
            plugins.append(plugin_info)
    
    # Generate markdown
    lines = []
    lines.append("# Available Plugins")
    lines.append("")
    lines.append("This document lists all available Claude Code plugins and their commands in the ai-helpers repository.")
    lines.append("")

    # Generate table of contents
    for plugin in plugins:
        plugin_title = plugin.name.replace('-', ' ').title()
        # Create anchor link (GitHub converts headers to lowercase with hyphens)
        anchor = plugin_title.lower().replace(' ', '-') + '-plugin'
        lines.append(f"- [{plugin_title}](#{anchor})")
    lines.append("")

    for plugin in plugins:
        # Plugin header
        lines.append(f"### {plugin.name.replace('-', ' ').title()} Plugin")
        lines.append("")
        
        if plugin.description:
            lines.append(plugin.description)
            lines.append("")
        
        # Commands list
        if plugin.commands:
            lines.append("**Commands:**")
            for cmd in plugin.commands:
                cmd_signature = f"`/{plugin.name}:{cmd['name']}`"
                if cmd['argument_hint']:
                    cmd_signature += f" `{cmd['argument_hint']}`"
                lines.append(f"- **{cmd_signature}** - {cmd['description']}")
            lines.append("")
        
        # Link to plugin README if it exists
        readme_path = plugins_dir / plugin.name / 'README.md'
        if readme_path.exists():
            lines.append(f"See [plugins/{plugin.name}/README.md](plugins/{plugin.name}/README.md) for detailed documentation.")
            lines.append("")
    
    return '\n'.join(lines)


def write_plugins_file(plugins_path: Path, plugins_content: str) -> None:
    """Write the PLUGINS.md file with plugin documentation."""
    
    with open(plugins_path, 'w') as f:
        f.write(plugins_content)


def main():
    """Main entry point."""
    
    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    plugins_dir = repo_root / 'plugins'
    plugins_path = repo_root / 'PLUGINS.md'
    
    if not plugins_dir.exists():
        print(f"Error: Plugins directory not found: {plugins_dir}", file=sys.stderr)
        sys.exit(1)
    
    print("Scanning plugins...")
    plugins_docs = generate_plugin_docs(plugins_dir)
    
    print("Writing PLUGINS.md...")
    write_plugins_file(plugins_path, plugins_docs)
    
    print("✓ Plugin documentation updated successfully in PLUGINS.md!")


if __name__ == '__main__':
    main()

