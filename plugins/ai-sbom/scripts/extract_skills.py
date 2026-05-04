#!/usr/bin/env python3
"""Extract skill invocations from Claude Code session transcripts.

Parses JSONL session files to find all Skill tool_use events,
deduplicates them, and outputs a JSON summary of skills used
along with model information.

Usage:
    # Single session file
    python3 extract_skills.py ~/.claude/projects/<project>/<session>.jsonl

    # All sessions in a project directory
    python3 extract_skills.py ~/.claude/projects/<project>/
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

COMMAND_NAME_RE = re.compile(r"<command-name>/([^<]+)</command-name>")
BUILTIN_COMMANDS = {
    "add-dir", "bug", "clear", "compact", "config", "cost", "doctor",
    "exit", "fast", "help", "init", "install-github-app", "login", "logout",
    "loop", "memory", "model", "permissions", "pr-review", "resume", "review",
    "search", "status", "tasks", "terminal-setup", "vim", "worktree",
}


def get_tool_version():
    """Get the installed Claude Code version via CLI."""
    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def extract_from_session(filepath):
    """Extract skill names and model info from a single JSONL session file."""
    skills = set()
    models = set()

    with open(filepath) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue

            msg = obj.get("message", {})
            if not isinstance(msg, dict):
                continue
            msg_type = obj.get("type", "")

            if msg_type == "assistant":
                model = msg.get("model")
                if model:
                    models.add(model)

                content = msg.get("content", [])
                if not isinstance(content, list):
                    continue

                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue
                    if block.get("name") != "Skill":
                        continue

                    skill_input = block.get("input", {})
                    if not isinstance(skill_input, dict):
                        continue
                    skill_name = skill_input.get("skill", "")
                    if skill_name:
                        skills.add(skill_name)

            elif msg_type == "user":
                content = msg.get("content", [])
                if isinstance(content, str):
                    content = [{"type": "text", "text": content}]
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text", "")
                    for match in COMMAND_NAME_RE.findall(text):
                        name = match.strip()
                        if name not in BUILTIN_COMMANDS:
                            skills.add(name)

    return skills, models


def main():
    """Parse CLI arguments and extract skills from session files or directories."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <session.jsonl | project-dir/>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1])
    all_skills = set()
    all_models = set()

    if target.is_file() and target.suffix == ".jsonl":
        skills, models = extract_from_session(target)
        all_skills.update(skills)
        all_models.update(models)
    elif target.is_dir():
        for jsonl_file in sorted(target.glob("*.jsonl")):
            skills, models = extract_from_session(jsonl_file)
            all_skills.update(skills)
            all_models.update(models)
    else:
        print(f"Error: {target} is not a .jsonl file or directory", file=sys.stderr)
        sys.exit(1)

    all_models.discard("<synthetic>")

    normalized = set()
    for skill in all_skills:
        parts = skill.split(":")
        if len(parts) == 2 and parts[0] == parts[1]:
            normalized.add(parts[0])
        else:
            normalized.add(skill)
    bare = {s for s in normalized if ":" not in s}
    normalized = {s for s in normalized if ":" in s or not any(s == q.split(":")[-1] for q in normalized if ":" in q)}
    normalized.update(bare - {q.split(":")[-1] for q in normalized if ":" in q})

    tool_version = get_tool_version()
    tool_name = None
    if tool_version:
        match = re.match(r"^([\d.]+)\s*\((.+)\)$", tool_version)
        if match:
            tool_name = f"{match.group(2)} {match.group(1)}"
        else:
            tool_name = f"Claude Code {tool_version}"

    result = {
        "skills": sorted(normalized),
        "models": sorted(all_models),
        "tool": tool_name,
        "session_count": len(list(target.glob("*.jsonl"))) if target.is_dir() else 1,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
