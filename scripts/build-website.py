#!/usr/bin/env python3
"""
Build website data for ai-helpers GitHub Pages
Extracts plugin and command information from the repository
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List

def parse_frontmatter(content: str) -> Dict[str, str]:
    """Extract frontmatter from markdown file"""
    frontmatter = {}
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 2:
            fm_lines = parts[1].strip().split('\n')
            for line in fm_lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    frontmatter[key.strip()] = value.strip()
    return frontmatter

def extract_synopsis(content: str) -> str:
    """Extract synopsis from command markdown"""
    match = re.search(r'## Synopsis\s*```\s*([^\n]+)', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""

def get_plugin_commands(plugin_path: Path) -> List[Dict[str, str]]:
    """Get all commands for a plugin"""
    commands = []
    commands_dir = plugin_path / "commands"

    if not commands_dir.exists():
        return commands

    for cmd_file in sorted(commands_dir.glob("*.md")):
        try:
            content = cmd_file.read_text()
            frontmatter = parse_frontmatter(content)
            synopsis = extract_synopsis(content)

            command_name = cmd_file.stem
            commands.append({
                "name": command_name,
                "description": frontmatter.get("description", ""),
                "synopsis": synopsis,
                "argument_hint": frontmatter.get("argument-hint", "")
            })
        except Exception as e:
            print(f"Error processing {cmd_file}: {e}")

    return commands

def get_plugin_skills(plugin_path: Path) -> List[Dict[str, str]]:
    """Get all skills for a plugin"""
    skills = []
    skills_dir = plugin_path / "skills"

    if not skills_dir.exists():
        return skills

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        try:
            content = skill_file.read_text()
            frontmatter = parse_frontmatter(content)

            skill_name = skill_dir.name
            skills.append({
                "name": frontmatter.get("name", skill_name),
                "id": skill_name,
                "description": frontmatter.get("description", "")
            })
        except Exception as e:
            print(f"Error processing {skill_file}: {e}")

    return skills

def build_website_data():
    """Build complete website data structure"""
    # Get repository root (parent of scripts directory)
    base_path = Path(__file__).parent.parent
    marketplace_file = base_path / ".claude-plugin" / "marketplace.json"

    with open(marketplace_file) as f:
        marketplace = json.load(f)

    website_data = {
        "name": marketplace["name"],
        "owner": marketplace["owner"]["name"],
        "plugins": []
    }

    for plugin_info in marketplace["plugins"]:
        plugin_path = base_path / plugin_info["source"]

        # Read plugin.json
        plugin_json_path = plugin_path / ".claude-plugin" / "plugin.json"
        plugin_metadata = {}
        if plugin_json_path.exists():
            with open(plugin_json_path) as f:
                plugin_metadata = json.load(f)

        # Get commands and skills
        commands = get_plugin_commands(plugin_path)
        skills = get_plugin_skills(plugin_path)

        # Read README if exists
        readme_path = plugin_path / "README.md"
        readme = ""
        if readme_path.exists():
            readme = readme_path.read_text()

        plugin_data = {
            "name": plugin_info["name"],
            "description": plugin_info["description"],
            "version": plugin_metadata.get("version", "unknown"),
            "commands": commands,
            "skills": skills,
            "has_readme": readme_path.exists()
        }

        website_data["plugins"].append(plugin_data)

    return website_data

if __name__ == "__main__":
    data = build_website_data()

    # Output as JSON (in docs directory at repo root)
    output_file = Path(__file__).parent.parent / "docs" / "data.json"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Website data written to {output_file}")
    print(f"Total plugins: {len(data['plugins'])}")
    total_commands = sum(len(p['commands']) for p in data['plugins'])
    print(f"Total commands: {total_commands}")
    total_skills = sum(len(p['skills']) for p in data['plugins'])
    print(f"Total skills: {total_skills}")
